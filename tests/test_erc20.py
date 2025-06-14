import json
from pathlib import Path

import pytest
from eth_contract.create2 import create2_address, create2_deploy
from eth_contract.create3 import create3_address, create3_deploy
from eth_contract.erc20 import ERC20
from eth_contract.utils import get_initcode

MockERC20_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("contracts/MockERC20.json").read_text()
)


@pytest.mark.asyncio
async def test_erc20_live(fork_w3):
    # Test with live forked mainnet
    addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC
    balance = await ERC20.fns.balanceOf(
        "0x0000000000000000000000000000000000000000"
    ).call(fork_w3, {"to": addr})
    assert isinstance(balance, int)


@pytest.mark.asyncio
async def test_create2_deploy(w3):
    owner = (await w3.eth.accounts)[0]
    salt = 100
    initcode = get_initcode(MockERC20_ARTIFACT, "TEST", "TEST", 18)
    token = await create2_deploy(w3, initcode, salt=salt, extra={"from": owner})
    assert (
        token
        == create2_address(initcode, salt)
        == "0x854d811d90C6E81B84b29C1d7ed957843cF87bba"
    )

    tx = {"to": token, "from": owner}
    assert await ERC20.fns.balanceOf(owner).call(w3, tx=tx) == 0
    await ERC20.fns.mint(owner, 1000).transact(w3, tx=tx)
    assert await ERC20.fns.balanceOf(owner).call(w3, tx=tx) == 1000


@pytest.mark.asyncio
async def test_create3_deploy(w3):
    owner = (await w3.eth.accounts)[0]
    salt = 200
    initcode = get_initcode(MockERC20_ARTIFACT, "TEST", "TEST", 18)
    token = await create3_deploy(w3, initcode, salt=salt, extra={"from": owner})
    assert (
        token == create3_address(salt) == "0x60f7B32B5799838a480572Aee2A8F0355f607b38"
    )

    tx = {"to": token, "from": owner}
    assert await ERC20.fns.balanceOf(owner).call(w3, tx=tx) == 0
    await ERC20.fns.mint(owner, 1000).transact(w3, tx=tx)
    assert await ERC20.fns.balanceOf(owner).call(w3, tx=tx) == 1000
