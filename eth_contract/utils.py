from typing import cast

from eth_account.signers.base import BaseAccount
from eth_account.types import TransactionDictType
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address, to_normalized_address
from eth_utils.toolz import assoc
from typing_extensions import Unpack
from web3 import AsyncWeb3
from web3._utils.async_transactions import (async_fill_nonce,
                                            async_fill_transaction_defaults)
from web3.types import Nonce, TxParams, TxReceipt


async def sign_transaction(w3: AsyncWeb3, acct: BaseAccount, **tx: Unpack[TxParams]):
    "fill default fields and sign"
    tx = assoc(tx, "from", acct.address)
    tx = await async_fill_nonce(w3, tx)
    tx = await async_fill_transaction_defaults(w3, tx)
    return acct.sign_transaction(cast(TransactionDictType, tx))


async def send_transactions(
    w3: AsyncWeb3,
    account: BaseAccount | None,
    txs: list[TxParams],
    /,
    check: bool = True,
    **kwargs: Unpack[TxParams],
) -> list[TxReceipt]:
    nonces: dict[str, int] = {}

    async def get_nonce(addr: ChecksumAddress) -> Nonce:
        "simulate nonce increase locally"
        naddr = to_normalized_address(addr)
        if naddr not in nonces:
            nonces[naddr] = await w3.eth.get_transaction_count(addr)
        else:
            nonces[naddr] += 1
        return Nonce(nonces[naddr])

    txhashes = []
    for tx in txs:
        tx = {**tx, **kwargs}
        if "from" not in tx and account is not None:
            tx["from"] = account.address
        if "nonce" not in tx:
            tx["nonce"] = await get_nonce(to_checksum_address(tx["from"]))
        if account is not None:
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
    account: BaseAccount | None = None,
    tx: TxParams | None = None,
    check: bool = True,
) -> TxReceipt:
    return (await send_transactions(w3, account, [tx or {}], check=check))[0]
