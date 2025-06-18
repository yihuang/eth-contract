import json
from pathlib import Path

from eth_contract.create2 import create2_address, create2_deploy
from eth_contract.utils import get_initcode
from web3 import AsyncWeb3

MockERC20_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("contracts/MockERC20.json").read_text()
)
WETH9_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("contracts/WETH9.json").read_text()
)
MULTICALL3ROUTER_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("contracts/Multicall3Router.json").read_text()
)

WETH_SALT = 999
WETH_ADDRESS = create2_address(get_initcode(WETH9_ARTIFACT), WETH_SALT)


async def deploy_weth(w3: AsyncWeb3) -> None:
    sender = (await w3.eth.accounts)[0]
    address = await create2_deploy(
        w3, sender, get_initcode(WETH9_ARTIFACT), salt=WETH_SALT
    )
    assert address == WETH_ADDRESS, f"Expected {WETH_ADDRESS}, got {address}"
