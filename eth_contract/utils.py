import json
import os
import platform
from getpass import getpass
from pathlib import Path
from typing import cast

from eth_account import Account
from eth_account.signers.base import BaseAccount
from eth_account.types import TransactionDictType
from eth_typing import ChecksumAddress
from eth_utils import to_bytes, to_checksum_address
from eth_utils.toolz import assoc
from typing_extensions import Unpack
from web3 import AsyncWeb3
from web3._utils.async_transactions import (async_fill_nonce,
                                            async_fill_transaction_defaults)
from web3.types import Nonce, TxParams, TxReceipt, Wei

ZERO_ADDRESS = to_checksum_address("0x0000000000000000000000000000000000000000")


async def fill_transaction_defaults(w3: AsyncWeb3, **tx: Unpack[TxParams]) -> TxParams:
    """
    Fill in default fields for a transaction
    """
    tx = await async_fill_nonce(w3, tx)
    tx = await async_fill_transaction_defaults(w3, tx)
    return tx


async def sign_transaction(w3: AsyncWeb3, acct: BaseAccount, **tx: Unpack[TxParams]):
    "fill default fields and sign"
    tx = assoc(tx, "from", acct.address)
    tx = await fill_transaction_defaults(w3, **tx)
    return acct.sign_transaction(cast(TransactionDictType, tx))


async def send_transactions(
    w3: AsyncWeb3,
    txs: list[TxParams],
    account: BaseAccount | ChecksumAddress | None = None,
    /,
    check: bool = True,
    **extra: Unpack[TxParams],
) -> list[TxReceipt]:
    """
    Send a batch of transactions, filling in increasing nonces for the same sender
    if not provided.
    """
    nonces: dict[ChecksumAddress, int] = {}

    async def get_nonce(addr: ChecksumAddress) -> Nonce:
        "simulate nonce increase locally"
        if addr not in nonces:
            nonces[addr] = await w3.eth.get_transaction_count(addr)
        else:
            nonces[addr] += 1
        return Nonce(nonces[addr])

    if account is not None:
        extra.setdefault(
            "from", account.address if isinstance(account, BaseAccount) else account
        )

    txhashes = []
    for tx in txs:
        tx = {**tx, **extra}
        if "nonce" not in tx:
            tx["nonce"] = await get_nonce(to_checksum_address(tx["from"]))
        if isinstance(account, BaseAccount):
            signed = await sign_transaction(w3, account, **tx)
            txhash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        else:
            txhash = await w3.eth.send_transaction(tx)
        txhashes.append(txhash)

    receipts = []
    for txhash in txhashes:
        receipt = await w3.eth.wait_for_transaction_receipt(txhash)
        if check:
            assert receipt["status"] == 1, receipt
        receipts.append(receipt)

    return receipts


async def send_transaction(
    w3: AsyncWeb3,
    account: BaseAccount | ChecksumAddress,
    check: bool = True,
    **tx: Unpack[TxParams],
) -> TxReceipt:
    """
    account: if provided, sign transaction locally and call `eth_sendRawTransaction`,
             otherwise, call `eth_sendTransaction` with the `from` field in the tx.
    """
    return (await send_transactions(w3, [tx], account, check=check))[0]


def get_default_keystore() -> Path:
    """
    Get the default keystore path based on the platform.
    Returns the path to the keystore directory.
    If the `ETH_KEYSTORE` environment variable is set, it will use that path instead.
    """
    keystore = os.getenv("ETH_KEYSTORE")
    if keystore:
        return Path(keystore)

    system = platform.system()
    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Ethereum" / "keystore"
    elif system == "Windows":
        return Path.home() / "AppData" / "Roaming" / "Ethereum" / "keystore"
    else:
        return Path.home() / ".ethereum" / "keystore"  # default to linux


def load_account(
    address: str, password: str | None = None, keystore: Path | None = None
) -> BaseAccount | None:
    """
    Load an account from the keystore by address and password.
    If keystore is not provided, it will use the default keystore path on the platform.
    Returns the account if found, otherwise None.
    """
    if keystore is None:
        keystore = get_default_keystore()
    keyfile_json = None
    for f in keystore.iterdir():
        keyfile_json = json.loads(f.read_text())
        if to_checksum_address(address) == to_checksum_address(keyfile_json["address"]):
            if password is None:
                password = getpass("Enter your keystore password: ")
            return Account.from_key(Account.decrypt(keyfile_json, password))
    return None


def get_bytescode(artifact: dict) -> bytes:
    """
    Extracts the bytecode from a contract artifact,
    try to be compatible with multiple formats.
    Args:
        artifact (dict): The contract artifact containing bytecode information.
    """
    bytecode = artifact.get("bytecode") or artifact.get("byte")
    assert bytecode is not None, "Bytecode not found in artifact"
    if isinstance(bytecode, dict):
        bytecode = bytecode["object"]
    return to_bytes(hexstr=bytecode)


def get_initcode(artifact: dict, *args, **kwargs) -> bytes:
    """
    Build the deploy initcode from a contract artifact and contructor arguments,
    try to be compatible with multiple formats.
    Args:
        artifact (dict): The contract artifact containing initcode information.
    """
    from .contract import Contract

    bytecode = get_bytescode(artifact)
    contract = Contract(artifact["abi"])
    if contract.constructor is None:
        if args or kwargs:
            raise ValueError(
                "Constructor arguments provided but no constructor "
                "found in the artifact"
            )
        ctor = b""
    else:
        ctor = contract.constructor(*args, **kwargs).data
    return bytecode + ctor


def parse_cli_arg(arg: str) -> str | bytes | int:
    """
    Parse a command line argument, converting it to the specified type.
    If the argument is not provided, return the default value.
    """
    if arg.startswith("0x"):
        return to_bytes(hexstr=arg)
    try:
        return int(arg)
    except ValueError:
        return arg


async def transfer(
    w3: AsyncWeb3,
    token: ChecksumAddress,
    from_: BaseAccount | ChecksumAddress,
    to: ChecksumAddress,
    amount: Wei,
):
    from .erc20 import ERC20

    if token == ZERO_ADDRESS:
        # transfer native currency
        tx = TxParams(
            {
                "to": to,
                "value": amount,
            }
        )
    else:
        # transfer ERC20 token
        tx = TxParams(
            {
                "to": token,
                "data": ERC20.fns.transfer(to, amount).data,
            }
        )
    await send_transaction(w3, from_, **tx)


async def balance_of(
    w3: AsyncWeb3, token: ChecksumAddress, address: ChecksumAddress
) -> int:
    "get balance of address for token"
    from .erc20 import ERC20

    if token == ZERO_ADDRESS:
        return await w3.eth.get_balance(address)

    return await ERC20.fns.balanceOf(address).call(w3, to=token)


async def deploy_presigned_tx(
    w3: AsyncWeb3,
    tx: bytes,
    contract: ChecksumAddress,
    funder: BaseAccount | None = None,
    fee: Wei = Wei(10**17),  # default to 0.1eth
):
    """
    deploy well known contracts with a presigned transaction.

    funder: default to the first account in the node,
    fee: default to 0.1 ETH.
    """
    if await w3.eth.get_code(contract):
        # already deployed
        return

    deployer = Account.recover_transaction(tx)
    if await w3.eth.get_balance(deployer) < fee:
        # fund the deployer if needed
        await transfer(
            w3, ZERO_ADDRESS, funder or (await w3.eth.accounts)[0], deployer, fee
        )

    receipt = await w3.eth.wait_for_transaction_receipt(
        await w3.eth.send_raw_transaction(tx)
    )

    assert receipt["status"] == 1, "deployment failed"
    assert receipt["contractAddress"] == contract
