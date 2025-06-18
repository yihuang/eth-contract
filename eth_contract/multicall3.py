from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NamedTuple

from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address
from web3 import AsyncWeb3
from web3.types import Wei

from .contract import Contract, ContractFunction


class Call3(NamedTuple):
    target: ChecksumAddress
    allow_failure: bool = False
    data: bytes = b""


class Call3Value(NamedTuple):
    target: ChecksumAddress
    allow_failure: bool = False
    value: int = Wei(0)
    data: bytes = b""


MULTICALL3_ADDRESS = to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
MULTICALL3_ABI = json.loads(
    Path(__file__).parent.joinpath("abis/multicall3.json").read_text()
)
MULTICALL3 = Contract(MULTICALL3_ABI, {"to": MULTICALL3_ADDRESS})


async def multicall(
    w3: AsyncWeb3,
    calls: list[tuple[ChecksumAddress, ContractFunction]],
    allow_failure=False,
) -> list[Any]:
    call3 = [Call3(target, allow_failure, fn.data) for target, fn in calls]
    results = await MULTICALL3.fns.aggregate3(call3).call(w3)
    values = []
    for (_, fn), (success, data) in zip(calls, results):
        if success and data:
            values.append(fn.decode(data))
        else:
            values.append(None)
    return values


if __name__ == "__main__":
    import asyncio
    import os
    import sys

    from web3 import AsyncHTTPProvider

    from .erc20 import ERC20

    async def main(w3, token: ChecksumAddress, users: list[ChecksumAddress]):
        balances = await multicall(
            w3, [(token, ERC20.fns.balanceOf(user)) for user in users]
        )
        for user, balance in zip(users, balances):
            print(f"{user}: {balance}")

    w3 = AsyncWeb3(AsyncHTTPProvider(os.environ["ETH_RPC_URL"]))
    asyncio.run(
        main(
            w3,
            to_checksum_address(sys.argv[1]),
            [to_checksum_address(addr) for addr in sys.argv[2:]],
        )
    )
