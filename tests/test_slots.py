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
from eth_contract.slots import parse_allowance_slot, parse_balance_slot

from .conftest import ETH_MAINNET_FORK
from .trace import trace_call


@pytest.mark.asyncio
async def test_pyrevm_balance_slot_tracing():
    """Test balance slot detection with pyrevm tracing"""
    # USDC contract
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    user = b"\x01".rjust(20)
    fn = ERC20.fns.balanceOf(user)

    # Capture and parse traces
    vm = pyrevm.EVM(fork_url=ETH_MAINNET_FORK, tracing=True, with_memory=True)
    traces = trace_call(vm, to=token, data=fn.data)

    # Parse balance slot from traces
    slot = parse_balance_slot(HexBytes(token), user, traces)
    assert slot is not None

    # verify the slot with state overrides
    bz = os.urandom(32)
    w3 = AsyncWeb3(AsyncHTTPProvider(ETH_MAINNET_FORK))
    assert int.from_bytes(bz, "big") == await fn.call(
        w3,
        to=token,
        state_override={
            token: {
                "stateDiff": {to_hex(slot.value(user.rjust(32, b"\x00")).slot): to_hex(bz)},
            }
        },
    )


@pytest.mark.asyncio
async def test_pyrevm_allowance_slot_tracing():
    """Test allowance slot detection with pyrevm tracing and memory support."""
    # USDC contract
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    owner = b"\x01".rjust(20)
    spender = b"\x02".rjust(20)
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
    bz = os.urandom(32)
    w3 = AsyncWeb3(AsyncHTTPProvider(ETH_MAINNET_FORK))
    assert int.from_bytes(bz, "big") == await fn.call(
        w3,
        to=token,
        state_override={
            token: {
                "stateDiff": {
                    to_hex(slot.value(owner).value(spender).slot): to_hex(bz),
                },
            }
        },
    )
