"""
Test for slots module using pyrevm with memory tracing.
"""

import os

import pytest
from eth_utils import to_hex
from hexbytes import HexBytes
from web3 import AsyncHTTPProvider, AsyncWeb3

from eth_contract.erc20 import ERC20
from eth_contract.slots import parse_allowance_slot, parse_balance_slot

from .conftest import ETH_MAINNET_FORK
from eth_contract.utils import trace_call


@pytest.mark.asyncio
async def test_pyrevm_balance_slot_tracing():
    """Test balance slot detection with pyrevm tracing"""
    # USDC contract
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    user = b"\x01".rjust(20, b"\x00")
    fn = ERC20.fns.balanceOf(user)

    # Capture and parse traces
    traces = trace_call(ETH_MAINNET_FORK, to=token, data=fn.data)

    # Parse balance slot from traces
    slot = parse_balance_slot(HexBytes(token), user, traces)
    assert slot is not None

    # verify the slot with state overrides
    bz = os.urandom(16).rjust(32, b"\x00")
    w3 = AsyncWeb3(AsyncHTTPProvider(ETH_MAINNET_FORK))
    state = {to_hex(slot.value(user).slot): to_hex(bz)}
    assert int.from_bytes(bz, "big") == await fn.call(
        w3, to=token, state_override={token: {"stateDiff": state}}
    )


@pytest.mark.asyncio
async def test_pyrevm_allowance_slot_tracing():
    """Test allowance slot detection with pyrevm tracing and memory support."""
    # USDC contract
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    owner = b"\x01".rjust(20, b"\x00")
    spender = b"\x02".rjust(20, b"\x00")
    fn = ERC20.fns.allowance(owner, spender)

    # Capture and parse traces
    traces = trace_call(
        ETH_MAINNET_FORK,
        to=token,
        data=fn.data,
    )

    # Parse allowance slot from traces
    slot = parse_allowance_slot(HexBytes(token), owner, HexBytes(spender), traces)
    assert slot is not None

    # verify the slot with state overrides
    bz = os.urandom(16).rjust(32, b"\x00")
    w3 = AsyncWeb3(AsyncHTTPProvider(ETH_MAINNET_FORK))
    state = {
        to_hex(slot.value(owner).value(spender).slot): to_hex(bz),
    }
    assert int.from_bytes(bz, "big") == await fn.call(
        w3, to=token, state_override={token: {"stateDiff": state}}
    )
