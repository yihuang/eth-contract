import json
from pathlib import Path

from eth_account.signers.base import BaseAccount
from eth_typing import ChecksumAddress
from eth_utils import keccak, to_bytes, to_checksum_address
from eth_utils.toolz import assoc
from typing_extensions import Unpack
from web3 import AsyncWeb3
from web3.types import TxParams

from .contract import Contract

CREATEX_FACTORY = to_checksum_address("0xba5Ed099633D3B313e4D5F7bdc1305d3c28ba5Ed")
CREATE3_PROXY_HASH = to_bytes(
    hexstr="0x21c35dbe1b344a2488cf3321d6ce542f8e9f305544ff09e4993a62319a497c1f"
)

CREATEX_ABI = json.loads(
    Path(__file__).parent.joinpath("abis/createx.json").read_text()
)
CREATEX = Contract(CREATEX_ABI, tx={"to": CREATEX_FACTORY})


def guard_salt(
    salt: bytes,
    deployer: ChecksumAddress | None = None,
    chainid: int | None = None,
) -> bytes:
    """
    Reproduce CreateX's ``_guard(salt)`` so the predicted CREATE3 address
    matches the deployed one.

    ``deployer`` is required for permissioned salts, ``chainid`` for
    cross-chain-protected ones (flag ``0x01``).
    """
    assert len(salt) == 32, "Salt must be 32 bytes"
    sender, flag = salt[:20], salt[20]

    deployer_bytes = to_bytes(hexstr=deployer) if deployer is not None else None
    permissioned = sender == deployer_bytes  # False when deployer is None
    if not (permissioned or sender == bytes(20)):
        return keccak(salt)  # a random sender field is never guarded
    if flag not in (0x00, 0x01):
        raise ValueError(f"guarded salt requires flag 0x00/0x01, got {flag:#04x}")

    # guarded salt is keccak(prefix ++ salt); the prefix folds in the deployer
    # (permissioned deploy) and/or the chainid (cross-chain redeploy protection)
    prefix = sender.rjust(32, b"\x00") if permissioned else b""
    if flag == 0x01:
        if chainid is None:
            raise ValueError("chainid required for cross-chain protected salt")
        prefix += chainid.to_bytes(32, "big")
    return keccak(prefix + salt)


def create3_address(
    salt: bytes | int = 0,
    factory: ChecksumAddress = CREATEX_FACTORY,
    deployer: ChecksumAddress | None = None,
    chainid: int | None = None,
) -> ChecksumAddress:
    """
    Calculate the deterministic CREATE3 address.

    Args:
        salt: Bytes32 salt value (or int, big-endian encoded to 32 bytes).
        factory: The CreateX contract address (0xba5...)
        deployer: Deploy tx sender; pass it for guarded (permissioned or
            cross-chain) salts so the prediction matches ``_guard(salt)``.
        chainid: Needed only for cross-chain-protected salts (flag ``0x01``).
    """
    if isinstance(salt, int):
        salt = salt.to_bytes(32, "big")
    # Create3 address calculation formula:
    # proxy_code = 67363d3d37363d34f03d5260086018f3
    # proxy_code_hash = 21c35dbe1b344a2488cf3321d6ce542f8e9f305544ff09e4993a62319a497c1f
    # keccak256(0xff ++ sender ++ keccak(guarded_salt) ++ proxy_code_hash)[12:]
    guarded = guard_salt(salt, deployer, chainid)
    data = b"\xff" + to_bytes(hexstr=factory) + guarded + CREATE3_PROXY_HASH
    return to_checksum_address(keccak(b"\xd6\x94" + keccak(data)[12:] + b"\x01")[12:])


async def create3_deploy(
    w3: AsyncWeb3,
    acct: BaseAccount | ChecksumAddress,
    initcode: bytes,
    salt: bytes | int = 0,
    factory: ChecksumAddress = CREATEX_FACTORY,
    **tx: Unpack[TxParams],
) -> ChecksumAddress:
    if isinstance(salt, int):
        salt = salt.to_bytes(32, "big")

    deployer = acct.address if isinstance(acct, BaseAccount) else acct
    # chainid is only consulted for cross-chain-protected salts (flag 0x01)
    chainid = await w3.eth.chain_id if salt[20] == 0x01 else None

    tx = assoc(tx, "to", factory)
    await CREATEX.fns.deployCreate3(salt, initcode).transact(w3, acct, **tx)
    return create3_address(salt, factory=factory, deployer=deployer, chainid=chainid)


if __name__ == "__main__":
    # simple cli to deploy a contract artifact using createx factory
    import argparse
    import asyncio
    import json
    import os
    from pathlib import Path

    from web3 import AsyncHTTPProvider, AsyncWeb3
    from web3.types import TxParams

    from .utils import get_default_keystore, get_initcode, load_account, parse_cli_arg

    argparser = argparse.ArgumentParser(
        description="Deploy a contract using create3 factory"
    )

    argparser.add_argument(
        "artifact",
        type=str,
        help="Path to the contract artifact file (JSON format)",
    )
    argparser.add_argument("ctor_args", nargs="*", help="Constructor arguments")
    argparser.add_argument(
        "--salt",
        type=int,
        default=0,
        help="Salt (integer) for the create3 deployment (default: 0)",
    )
    argparser.add_argument(
        "--factory",
        default=CREATEX_FACTORY,
        help=f"Factory address for create3 deployment (default: {CREATEX_FACTORY})",
    )
    argparser.add_argument(
        "--value",
        default=0,
        help="Value to send with the transaction (default: 0)",
    )
    argparser.add_argument(
        "--rpc-url",
        type=str,
        default=os.getenv("ETH_RPC_URL", "http://localhost:8545"),
        help="RPC URL to connect to the Ethereum node "
        "(default: $ETH_RPC_URL or http://localhost:8545)",
    )
    argparser.add_argument(
        "--account",
        type=str,
        required=False,
        help="Account address to use for deployment, "
        "should be available from keystore, "
        "default is $ETH_FROM",
    )
    argparser.add_argument(
        "--keystore",
        type=str,
        default=None,
        help="Path to the keystore file (default: $ETH_KEYSTORE or "
        f'{get_default_keystore()}")',
    )

    async def main() -> ChecksumAddress:
        args = argparser.parse_args()

        if args.keystore is None:
            keystore_path = get_default_keystore()
        else:
            keystore_path = Path(args.keystore)

        account = args.account or os.environ["ETH_FROM"]
        acct = load_account(account, keystore=keystore_path) or to_checksum_address(
            args.account
        )

        w3 = AsyncWeb3(AsyncHTTPProvider(args.rpc_url))
        artifact = json.loads(Path(args.artifact).read_text())
        initcode = get_initcode(artifact, *map(parse_cli_arg, args.ctor_args))
        factory = to_checksum_address(args.factory)
        salt = args.salt.to_bytes(32, "big")
        deployer = acct.address if isinstance(acct, BaseAccount) else acct
        chainid = await w3.eth.chain_id if salt[20] == 0x01 else None
        addr = create3_address(salt, factory, deployer=deployer, chainid=chainid)
        if await w3.eth.get_code(addr):
            print(f"Contract address already exists {addr}")
            return addr
        else:
            print(f"Deploying contract to {addr}")
            return await create3_deploy(
                w3, acct, initcode, args.salt, factory, value=args.value
            )

    asyncio.run(main())
