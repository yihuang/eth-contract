import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from eth_account import Account
from eth_account.signers.base import BaseAccount
from web3 import AsyncHTTPProvider, AsyncWeb3

from eth_contract.create2 import create2_address
from eth_contract.deploy_utils import (
    ensure_create2_deployed,
    ensure_createx_deployed,
    ensure_deployed_by_create2,
    ensure_multicall3_deployed,
)
from eth_contract.multicall3 import MULTICALL3_ADDRESS
from eth_contract.utils import get_initcode

from .contracts import MULTICALL3ROUTER_ARTIFACT, deploy_weth

Account.enable_unaudited_hdwallet_features()
TEST_MNEMONIC = (
    "body bag bird mix language evidence what liar reunion wire lesson evolve"
)
MULTICALL3ROUTER = create2_address(
    get_initcode(MULTICALL3ROUTER_ARTIFACT, MULTICALL3_ADDRESS)
)


async def await_port(port: int, retries: int = 100, host="127.0.0.1") -> None:
    """Check if a port is open and available for connection."""
    for i in range(retries):
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return
        except (ConnectionRefusedError, asyncio.TimeoutError):
            await asyncio.sleep(0.1)
    raise asyncio.TimeoutError(
        f"Port {port} did not become available after {retries} retries."
    )


@asynccontextmanager
async def anvil_w3(port: int, *args) -> AsyncGenerator[AsyncWeb3, None]:
    proc = await asyncio.create_subprocess_exec(
        "anvil", *(args + ("--port", str(port)))
    )

    try:
        await await_port(port)
        w3 = AsyncWeb3(
            AsyncHTTPProvider(f"http://localhost:{port}", cache_allowed_requests=True)
        )
        await ensure_create2_deployed(w3)
        await ensure_multicall3_deployed(w3)
        await ensure_createx_deployed(w3)
        await deploy_weth(w3)
        assert MULTICALL3ROUTER == await ensure_deployed_by_create2(
            w3, get_initcode(MULTICALL3ROUTER_ARTIFACT, MULTICALL3_ADDRESS)
        )
        yield w3
    finally:
        proc.terminate()
        await proc.wait()


@pytest_asyncio.fixture(scope="session")
async def w3() -> AsyncGenerator[AsyncWeb3, None]:
    async with anvil_w3(
        9545,
        "-q",
        "--hardfork",
        "prague",
        "--mnemonic",
        TEST_MNEMONIC,
        "--chain-id",
        "1337",
    ) as w3:
        yield w3


@pytest_asyncio.fixture(scope="session")
async def fork_w3() -> AsyncGenerator[AsyncWeb3, None]:
    async with anvil_w3(
        10545,
        "-q",
        "--hardfork",
        "prague",
        "--mnemonic",
        TEST_MNEMONIC,
        "--fork-url",
        "https://eth-mainnet.public.blastapi.io",
        "--fork-block-number",
        "18000000",
    ) as w3:
        yield w3


@pytest.fixture(scope="session")
def test_accounts() -> list[BaseAccount]:
    """Test accounts from anvil's deterministic mnemonic"""
    accounts = [
        Account.from_mnemonic(TEST_MNEMONIC, account_path=f"m/44'/60'/0'/0/{i}")
        for i in range(5)
    ]
    return accounts
