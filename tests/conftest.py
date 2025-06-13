import asyncio
from pathlib import Path
from typing import AsyncGenerator

import pytest_asyncio
from eth_contract.create3 import CREATEX_FACTORY
from eth_contract.multicall3 import MULTICALL3_ADDRESS
from eth_contract.utils import send_transaction
from eth_utils import to_checksum_address
from hexbytes import HexBytes
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
    "https://github.com/mds1/multicall3#new-deployments"
    deployer_address = to_checksum_address("0x05f32b3cc3888453ff71b01135b34ff8e41263f2")
    if await w3.eth.get_code(MULTICALL3_ADDRESS):
        # already deployed
        print("multicall3 already deployed at", MULTICALL3_ADDRESS)
        return
    amount = Wei(10**17)
    if await w3.eth.get_balance(deployer_address) < amount:
        funder = (await w3.eth.accounts)[0]
        await send_transaction(
            w3,
            tx={
                "from": funder,
                "to": deployer_address,
                "value": amount,
            },
        )
    tx = HexBytes(
        Path(__file__).parent.joinpath("txs/multicall3.tx").read_text().strip()
    )
    txhash = await w3.eth.send_raw_transaction(tx)
    receipt = await w3.eth.wait_for_transaction_receipt(txhash)
    assert receipt["status"] == 1, "Multicall3 deployment failed"
    assert receipt["contractAddress"] == MULTICALL3_ADDRESS
    print("multicall3 deployed at", MULTICALL3_ADDRESS)


async def ensure_createx_deployed(w3: AsyncWeb3):
    "https://github.com/pcaversaccio/createx#new-deployments"
    deployer_address = to_checksum_address("0xeD456e05CaAb11d66C4c797dD6c1D6f9A7F352b5")
    if await w3.eth.get_code(deployer_address):
        # already deployed
        print("createx already deployed at", deployer_address)
        return
    amount = Wei(3 * 10**17)
    if await w3.eth.get_balance(deployer_address) < amount:
        funder = (await w3.eth.accounts)[0]
        await send_transaction(
            w3,
            tx={
                "from": funder,
                "to": deployer_address,
                "value": amount,
            },
        )
    tx = HexBytes(Path(__file__).parent.joinpath("txs/createx.tx").read_text().strip())
    txhash = await w3.eth.send_raw_transaction(tx)
    receipt = await w3.eth.wait_for_transaction_receipt(txhash)
    assert receipt["status"] == 1, "CreateX deployment failed"
    assert receipt["contractAddress"] == CREATEX_FACTORY
    print("createx deployed at", CREATEX_FACTORY)


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
        await ensure_createx_deployed(w3)
        yield w3
    finally:
        proc.terminate()
        await proc.wait()
