import pytest

from eth_contract import entrypoint
from eth_contract.create2 import create2_address
from eth_contract.history_storage import HISTORY_STORAGE_ADDRESS
from eth_contract.utils import get_initcode


def test_contract_addresses():
    assert entrypoint.ENTRYPOINT08_ADDRESS == create2_address(
        get_initcode(entrypoint.ENTRYPOINT08_ARTIFACT), entrypoint.ENTRYPOINT08_SALT
    )
    assert entrypoint.ENTRYPOINT07_ADDRESS == create2_address(
        get_initcode(entrypoint.ENTRYPOINT07_ARTIFACT), entrypoint.ENTRYPOINT07_SALT
    )


@pytest.mark.asyncio
async def test_history_storage(w3):
    assert await w3.eth.get_code(HISTORY_STORAGE_ADDRESS)
    latest = await w3.eth.block_number
    height = latest - 1
    result = await w3.eth.call(
        {
            "to": HISTORY_STORAGE_ADDRESS,
            "data": height.to_bytes(32, "big"),
        }
    )
    print(result)
