"""
ERC-4337 EntryPoint

https://github.com/eth-infinitism/account-abstraction/
"""

import json
from pathlib import Path

from eth_utils import to_checksum_address
from hexbytes import HexBytes

from .contract import Contract

ENTRYPOINT08_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("deployments/EntryPoint08.json").read_text()
)
ENTRYPOINT08_ABI = ENTRYPOINT08_ARTIFACT["abi"]
ENTRYPOINT08 = Contract(ENTRYPOINT08_ABI)
ENTRYPOINT08_SALT = HexBytes(
    "0x0a59dbff790c23c976a548690c27297883cc66b4c67024f9117b0238995e35e9"
)
ENTRYPOINT08_ADDRESS = to_checksum_address(ENTRYPOINT08_ARTIFACT["address"])

ENTRYPOINT07_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("deployments/EntryPoint07.json").read_text()
)
ENTRYPOINT07_ABI = ENTRYPOINT07_ARTIFACT["abi"]
ENTRYPOINT07 = Contract(ENTRYPOINT07_ABI)
ENTRYPOINT07_SALT = HexBytes(
    "0x90d8084deab30c2a37c45e8d47f49f2f7965183cb6990a98943ef94940681de3"
)
ENTRYPOINT07_ADDRESS = to_checksum_address(ENTRYPOINT07_ARTIFACT["address"])
WETH9_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("deployments/WETH9.json").read_text()
)
MULTICALL3ROUTER_ARTIFACT = json.loads(
    Path(__file__).parent.joinpath("deployments/Multicall3Router.json").read_text()
)
