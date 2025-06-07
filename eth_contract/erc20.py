import json
from pathlib import Path

from .contract import Contract

ERC20_ABI = json.loads(Path(__file__).parent.joinpath("abis/erc20.json").read_text())
ERC20 = Contract(ERC20_ABI)
