import asyncio
import socket
import time
from typing import AsyncGenerator

import pytest_asyncio
from eth_contract.multicall3 import (DEPLOY_SIGNED_TX, DEPLOYER_ADDRESS,
                                     MULTICALL3_ADDRESS)
from eth_contract.utils import send_transaction
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.types import Wei

PORT = 9545


async def await_port(port: int, retries: int = 100, host="127.0.0.1") -> None:
    """Check if a port is open and available for connection."""
    for i in range(retries):
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, asyncio.TimeoutError):
            await asyncio.sleep(0.1)
    raise asyncio.TimeoutError(
        f"Port {port} did not become available after {retries} retries."
    )


async def ensure_multicall3_deployed(w3: AsyncWeb3):
    if await w3.eth.get_code(MULTICALL3_ADDRESS):
        # already deployed
        print("multicall3 already deployed at", MULTICALL3_ADDRESS)
        return
    amount = Wei(10**17)
    if await w3.eth.get_balance(DEPLOYER_ADDRESS) < amount:
        funder = (await w3.eth.accounts)[0]
        await send_transaction(
            w3,
            tx={
                "from": funder,
                "to": DEPLOYER_ADDRESS,
                "value": amount,
            },
        )
    txhash = await w3.eth.send_raw_transaction(DEPLOY_SIGNED_TX)
    receipt = await w3.eth.wait_for_transaction_receipt(txhash)
    assert receipt["status"] == 1, "Multicall3 deployment failed"
    assert receipt["contractAddress"] == MULTICALL3_ADDRESS
    print("multicall3 deployed at", MULTICALL3_ADDRESS)


@pytest_asyncio.fixture(scope="session")
async def w3() -> AsyncGenerator[AsyncWeb3, None]:
    proc = await asyncio.create_subprocess_exec(
        "anvil",
        "-q",
        "--fork-url",
        "https://eth-mainnet.public.blastapi.io",
        "--fork-block-number",
        "18000000",
        "--port",
        str(PORT),
    )

    try:
        await await_port(PORT)
        w3 = AsyncWeb3(AsyncHTTPProvider(f"http://localhost:{PORT}"))
        await ensure_multicall3_deployed(w3)
        yield w3
    finally:
        proc.terminate()
        await proc.wait()
