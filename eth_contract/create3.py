import json
from pathlib import Path

from eth_account.signers.base import BaseAccount
from eth_typing import ChecksumAddress
from eth_utils import keccak, to_bytes, to_checksum_address
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
CREATEX = Contract(CREATEX_ABI)


def create3_address(
    salt: bytes, factory: ChecksumAddress = CREATEX_FACTORY
) -> ChecksumAddress:
    """
    Calculate the deterministic CREATE3 address.

    Args:
        factory: The CreateX contract address (0xba5...)
        salt: Bytes32 salt value
    """
    # Create3 address calculation formula:
    # proxy_code = 67363d3d37363d34f03d5260086018f3
    # proxy_code_hash = 21c35dbe1b344a2488cf3321d6ce542f8e9f305544ff09e4993a62319a497c1f
    # keccak256(0xff ++ sender ++ keccak(salt) ++ proxy_code_hash)[12:]
    data = b"\xff" + to_bytes(hexstr=factory) + keccak(salt) + CREATE3_PROXY_HASH
    return to_checksum_address(keccak(b"\xd6\x94" + keccak(data)[12:] + b"\x01")[12:])


async def create3_deploy(
    w3: AsyncWeb3,
    initcode: bytes,
    acct: BaseAccount | None = None,
    salt: bytes | int = 0,
    factory: ChecksumAddress = CREATEX_FACTORY,
    extra: TxParams | None = None,  # extra tx parameters
) -> ChecksumAddress:
    if isinstance(salt, int):
        salt = salt.to_bytes(32, "big")

    if extra is None:
        extra = {}

    await CREATEX.fns.deployCreate3(salt, initcode).transact(
        w3, acct, tx={"to": factory, **extra}
    )

    return create3_address(salt, factory=factory)


if __name__ == "__main__":
    # simple cli to deploy a contract artifact using createx factory
    import argparse
    import asyncio
    import json
    import os
    from pathlib import Path

    from web3 import AsyncHTTPProvider, AsyncWeb3
    from web3.types import TxParams

    from .utils import (get_default_keystore, get_initcode, load_account,
                        parse_cli_arg)

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
        help="Account address to use for deployment, should be available from keystore, "
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

        tx: TxParams = {"value": args.value}
        account = args.account or os.environ["ETH_FROM"]
        acct = load_account(account, keystore=keystore_path)
        if acct is None:
            tx["from"] = to_checksum_address(args.account)

        w3 = AsyncWeb3(AsyncHTTPProvider(args.rpc_url))
        artifact = json.loads(Path(args.artifact).read_text())
        initcode = get_initcode(artifact, *map(parse_cli_arg, args.ctor_args))
        factory = to_checksum_address(args.factory)
        addr = create3_address(args.salt.to_bytes(32, "big"), factory)
        if await w3.eth.get_code(addr):
            print(f"Contract address already exists {addr}")
            return addr
        else:
            print(f"Deploying contract to {addr}")
            return await create3_deploy(
                w3, initcode, acct, args.salt, factory, extra=tx
            )

    asyncio.run(main())
