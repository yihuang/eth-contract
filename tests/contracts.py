import json
from pathlib import Path

from eth_contract import entrypoint
from eth_contract.create2 import create2_address
from eth_contract.utils import get_initcode

MockERC20_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("contracts/MockERC20.json").read_text()
)

WETH_SALT = 999
WETH_ADDRESS = create2_address(get_initcode(entrypoint.WETH9_ARTIFACT), WETH_SALT)
