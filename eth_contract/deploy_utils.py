from pathlib import Path

import rlp  # type: ignore
from eth_account._utils.legacy_transactions import Transaction
from eth_account.signers.base import BaseAccount
from eth_typing import ChecksumAddress
from hexbytes import HexBytes
from web3 import AsyncWeb3
from web3.types import Wei

from .create2 import CREATE2_FACTORY, create2_address, create2_deploy
from .create3 import CREATEX_FACTORY
from .history_storage import HISTORY_STORAGE_ADDRESS
from .multicall3 import MULTICALL3_ADDRESS
from .utils import deploy_presigned_tx


async def ensure_create2_deployed(
    w3: AsyncWeb3, funder: BaseAccount | ChecksumAddress | None = None
):
    "https://github.com/Arachnid/deterministic-deployment-proxy"
    tx = bytes.fromhex(
        Path(__file__).parent.joinpath("txs/create2.tx").read_text().strip()[2:]
    )
    await deploy_presigned_tx(w3, tx, CREATE2_FACTORY, funder, fee=Wei(10**16))


async def ensure_multicall3_deployed(
    w3: AsyncWeb3, funder: BaseAccount | ChecksumAddress | None = None
):
    "https://github.com/mds1/multicall3#new-deployments"
    tx = bytes.fromhex(
        Path(__file__).parent.joinpath("txs/multicall3.tx").read_text().strip()[2:]
    )
    await deploy_presigned_tx(w3, tx, MULTICALL3_ADDRESS, funder)


async def ensure_createx_deployed(
    w3: AsyncWeb3, funder: BaseAccount | ChecksumAddress | None = None
):
    "https://github.com/pcaversaccio/createx#new-deployments"
    tx = bytes.fromhex(
        Path(__file__).parent.joinpath("txs/createx.tx").read_text().strip()[2:]
    )
    await deploy_presigned_tx(w3, tx, CREATEX_FACTORY, funder, fee=Wei(3 * 10**17))


async def ensure_history_storage_deployed(
    w3: AsyncWeb3, funder: BaseAccount | ChecksumAddress | None = None
):
    "https://eips.ethereum.org/EIPS/eip-2935"
    tx = Transaction(
        gas=0x3D090,
        gasPrice=0xE8D4A51000,
        data=HexBytes(
            "0x60538060095f395ff33373fffffffffffffffffffffffffffffffffffffffe14"
            "604657602036036042575f35600143038111604257611fff8143031160425761"
            "1fff9006545f5260205ff35b5f5ffd5b5f35611fff60014303065500"
        ),
        v=0x1B,
        r=0x539,
        s=0xAA12693182426612186309F02CFE8A80A0000,
        nonce=0,
        value=0,
        to=b"",
    )
    await deploy_presigned_tx(
        w3, rlp.encode(tx), HISTORY_STORAGE_ADDRESS, funder, fee=tx.gasPrice * tx.gas
    )


async def ensure_deployed_by_create2(
    w3: AsyncWeb3,
    account: BaseAccount | ChecksumAddress,
    initcode: bytes,
    salt: bytes | int = 0,
) -> ChecksumAddress:
    if isinstance(salt, int):
        salt = salt.to_bytes(32, "big")
    addr = create2_address(initcode, salt)
    if await w3.eth.get_code(addr):
        print(f"Contract already deployed at {addr}")
        return addr

    print(f"Deploying contract at {addr} using create2")
    return await create2_deploy(w3, account, initcode, salt=salt, value=Wei(0))
