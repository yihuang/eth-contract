from eth_account.signers.base import BaseAccount
from eth_typing import ChecksumAddress
from eth_utils import keccak, to_bytes, to_checksum_address
from web3 import AsyncWeb3
from web3.types import TxParams

from .utils import send_transaction

CREATE2_FACTORY = to_checksum_address("0x4e59b44847b379578588920ca78fbf26c0b4956c")


def create2_address(
    initcode: bytes, salt: bytes, factory=CREATE2_FACTORY
) -> ChecksumAddress:
    data = b"\xff" + to_bytes(hexstr=factory) + salt + keccak(initcode)
    return to_checksum_address(keccak(data)[12:])


def create2_tx(initcode: bytes, salt: bytes, factory=CREATE2_FACTORY) -> TxParams:
    """
    deploy a contract using create2 factory
    """
    assert len(salt) == 32, "Salt must be 32 bytes"
    return {"to": factory, "data": salt + initcode}


async def create2_deploy(
    w3: AsyncWeb3,
    initcode: bytes,
    acct: BaseAccount | None = None,
    salt: bytes | int = 0,
    factory=CREATE2_FACTORY,
    extra: TxParams | None = None,  # extra tx parameters
) -> ChecksumAddress:
    """
    Deploy a contract using create2 factory.
    """
    if isinstance(salt, int):
        salt = salt.to_bytes(32, "big")
    tx = create2_tx(initcode, salt, factory)
    tx.update(extra or {})
    await send_transaction(w3, acct, tx)
    return create2_address(initcode, salt, factory)


if __name__ == "__main__":
    # simple cli to deploy a contract artifact using create2 factory
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
        description="Deploy a contract using create2 factory"
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
        help="Salt (integer) for the create2 deployment (default: 0)",
    )
    argparser.add_argument(
        "--factory",
        default=CREATE2_FACTORY,
        help=f"Factory address for create2 deployment (default: {CREATE2_FACTORY})",
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
            tx["from"] = to_checksum_address(account)

        w3 = AsyncWeb3(AsyncHTTPProvider(args.rpc_url))
        artifact = json.loads(Path(args.artifact).read_text())
        initcode = get_initcode(artifact, *map(parse_cli_arg, args.ctor_args))
        factory = to_checksum_address(args.factory)
        addr = create2_address(initcode, args.salt.to_bytes(32, "big"), factory)
        if await w3.eth.get_code(addr):
            print(f"Contract address already exists {addr}")
            return addr
        else:
            print(f"Deploying contract to {addr}")
            return await create2_deploy(
                w3, initcode, acct, args.salt, factory, extra=tx
            )

    asyncio.run(main())
