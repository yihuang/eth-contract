import json
from pathlib import Path

from .contract import Contract

# https://github.com/gnosis/canonical-weth
# there's no universal address for WETH.
WETH_ABI = json.loads(Path(__file__).parent.joinpath("abis/weth.json").read_text())
WETH = Contract(WETH_ABI)
WETH9_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("deployments/WETH9.json").read_text()
)
