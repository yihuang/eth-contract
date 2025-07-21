import pytest
from eth_contract.history_storage import HISTORY_STORAGE_ADDRESS


@pytest.mark.asyncio
async def test_history_storage(w3):
    assert await w3.eth.get_code(HISTORY_STORAGE_ADDRESS)
    latest = await w3.eth.block_number
    height = latest - 1
    result = await w3.eth.call(
        {"to": HISTORY_STORAGE_ADDRESS, "data": height.to_bytes(32, "big")}
    )
    print(result)
