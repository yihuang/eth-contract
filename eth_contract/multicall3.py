from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

from eth_abi import decode, encode
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address
from web3 import AsyncWeb3

from .contract import Contract


class Call3(NamedTuple):
    target: ChecksumAddress
    allow_failure: bool
    data: bytes

    def encode(self) -> bytes:
        return encode(["(address,bool,bytes)"], [self])

    @classmethod
    def decode(cls, data: bytes) -> Call3:
        target, allow_failure, data = decode(["(address,bool,bytes)"], data)[0]
        return cls(
            target=to_checksum_address(target), allow_failure=allow_failure, data=data
        )


class Result(NamedTuple):
    success: bool
    return_data: bytes

    def encode(self) -> bytes:
        return encode(["(bool,bytes)"], [self])

    @classmethod
    def decode(cls, data: bytes) -> Result:
        success, return_data = decode(["(bool,bytes)"], data)
        return cls(success=success, return_data=return_data)


MULTICALL3_ADDRESS = to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
MULTICALL3_ABI = json.loads(
    Path(__file__).parent.joinpath("abis/multicall3.json").read_text()
)
MULTICALL3 = Contract(MULTICALL3_ABI)


async def aggregate3(w3: AsyncWeb3, calls: list[Call3]) -> list[Result]:
    """
    Batch calls using the multicall3 contract
    """
    result = await MULTICALL3.fns.aggregate3(calls).call(w3, {"to": MULTICALL3_ADDRESS})
    return [Result(success, data) for success, data in result]


if __name__ == "__main__":
    import asyncio
    import os
    import sys

    from web3 import AsyncHTTPProvider

    from .erc20 import ERC20

    async def main(w3, token: str, users: list[str]):
        result = await aggregate3(
            w3,
            [
                Call3(
                    target=to_checksum_address(token),
                    allow_failure=False,
                    data=ERC20.fns.balanceOf(user).data,
                )
                for user in users
            ],
        )
        for success, data in result:
            if success:
                balance = ERC20.fns.balanceOf.decode(data)
                print(f"Balance: {balance}")
            else:
                print("Call failed")

    w3 = AsyncWeb3(AsyncHTTPProvider(os.environ["ETH_RPC_URL"]))
    asyncio.run(main(w3, sys.argv[1], sys.argv[2:]))
