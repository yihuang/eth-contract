import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from eth_account import Account
from eth_account.signers.base import BaseAccount
from eth_contract.create2 import create2_address, create2_deploy
from eth_contract.create3 import CREATEX_FACTORY
from eth_contract.multicall3 import MULTICALL3_ADDRESS
from eth_contract.utils import deploy_presigned_tx, get_initcode
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.types import Wei

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


async def ensure_multicall3_deployed(w3: AsyncWeb3):
    "https://github.com/mds1/multicall3#new-deployments"
    deployer_address = to_checksum_address("0x05f32b3cc3888453ff71b01135b34ff8e41263f2")
    tx = bytes.fromhex(
        Path(__file__).parent.joinpath("txs/multicall3.tx").read_text().strip()[2:]
    )
    await deploy_presigned_tx(w3, tx, deployer_address, MULTICALL3_ADDRESS)


async def ensure_createx_deployed(w3: AsyncWeb3):
    "https://github.com/pcaversaccio/createx#new-deployments"
    deployer_address = to_checksum_address("0xeD456e05CaAb11d66C4c797dD6c1D6f9A7F352b5")
    tx = bytes.fromhex(
        Path(__file__).parent.joinpath("txs/createx.tx").read_text().strip()[2:]
    )
    await deploy_presigned_tx(
        w3, tx, deployer_address, CREATEX_FACTORY, fee=Wei(3 * 10**17)
    )


async def ensure_create2_deployed(
    w3: AsyncWeb3, initcode: bytes, salt: bytes | int = 0
) -> ChecksumAddress:
    user = (await w3.eth.accounts)[0]
    if isinstance(salt, int):
        salt = salt.to_bytes(32, "big")
    addr = create2_address(initcode, salt)
    if await w3.eth.get_code(addr):
        print(f"Contract already deployed at {addr}")
        return addr

    print(f"Deploying contract at {addr} using create2")
    return await create2_deploy(w3, user, initcode, salt=salt, value=Wei(0))


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
        await ensure_multicall3_deployed(w3)
        await ensure_createx_deployed(w3)
        await deploy_weth(w3)
        assert MULTICALL3ROUTER == await ensure_create2_deployed(
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
