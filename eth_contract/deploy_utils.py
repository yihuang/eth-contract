from pathlib import Path

from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address
from web3 import AsyncWeb3
from web3.types import Wei

from eth_contract.create2 import CREATE2_FACTORY, create2_address, create2_deploy
from eth_contract.create3 import CREATEX_FACTORY
from eth_contract.multicall3 import MULTICALL3_ADDRESS
from eth_contract.utils import deploy_presigned_tx


async def ensure_create2_deployed(w3: AsyncWeb3):
    "https://github.com/Arachnid/deterministic-deployment-proxy"
    deployer_address = to_checksum_address("0x3fab184622dc19b6109349b94811493bf2a45362")
    tx = bytes.fromhex(
        Path(__file__).parent.joinpath("txs/create2.tx").read_text().strip()[2:]
    )
    await deploy_presigned_tx(
        w3, tx, deployer_address, CREATE2_FACTORY, fee=Wei(10**16)
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


async def ensure_deployed_by_create2(
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
