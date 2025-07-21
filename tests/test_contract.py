import pytest
from eth_contract.history_storage import HISTORY_STORAGE_ADDRESS


@pytest.mark.asyncio
async def test_history_storage(w3):
    assert await w3.eth.get_code(HISTORY_STORAGE_ADDRESS)
