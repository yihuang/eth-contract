"""
Test for slots module using pyrevm with memory tracing.
"""

import os

import pyrevm
import pytest
from eth_utils import to_hex
from hexbytes import HexBytes
from web3 import AsyncHTTPProvider, AsyncWeb3

from eth_contract.erc20 import ERC20
from eth_contract.slots import (
    parse_allowance_slot,
    parse_balance_slot,
    parse_supply_slot,
)

from .conftest import ETH_MAINNET_FORK
from .trace import trace_call


@pytest.mark.asyncio
async def test_pyrevm_balance_slot_tracing():
    """Test balance slot detection with pyrevm tracing"""
    # USDC contract
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    user = b"\x01".rjust(20, b"\x00")
    fn = ERC20.fns.balanceOf(user)

    # Capture and parse traces
    vm = pyrevm.EVM(fork_url=ETH_MAINNET_FORK, tracing=True, with_memory=True)
    traces = trace_call(vm, to=token, data=fn.data)

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
async def test_pyrevm_supply_slot_tracing():
    """Test supply slot detection with pyrevm tracing"""
    tokens = [
        ("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
        ("UNI", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"),
        ("AAVE", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"),
        ("MKR", "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2"),
    ]
    fn = ERC20.fns.totalSupply()
    # Capture and parse traces
    vm = pyrevm.EVM(fork_url=ETH_MAINNET_FORK, tracing=True, with_memory=True)
    w3 = AsyncWeb3(AsyncHTTPProvider(ETH_MAINNET_FORK))
    for name, token in tokens:
        print("Testing", name, token)
        traces = trace_call(vm, to=token, data=fn.data)

        # Parse totalSupply slot from traces
        slot = parse_supply_slot(HexBytes(token), traces)
        bz = os.urandom(16).rjust(32, b"\x00")
        new_total = int.from_bytes(bz, "big")
        if not slot:
            # WETH case: totalSupply = address(this).balance
            assert await fn.call(w3, to=token) == await w3.eth.get_balance(token)
            # verify the slot with state overrides
            assert new_total == await fn.call(
                w3, to=token, state_override={token: {"balance": hex(new_total)}}
            )
        else:
            # Storage-based tokens: override storage slot
            # verify the slot with state overrides
            state = {to_hex(slot.slot): to_hex(bz)}
            assert new_total == await fn.call(
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
        pyrevm.EVM(fork_url=ETH_MAINNET_FORK, tracing=True, with_memory=True),
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
