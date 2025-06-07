import pytest
from eth_contract.erc20 import ERC20


@pytest.mark.asyncio
async def test_erc20_live(w3):
    # Test with live forked mainnet
    addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC
    balance = await ERC20.fns.balanceOf(
        "0x0000000000000000000000000000000000000000"
    ).call(w3, {"to": addr})
    assert isinstance(balance, int)
