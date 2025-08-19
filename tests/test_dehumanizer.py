import pytest

from eth_contract.contract import ContractFunction
from eth_contract.dehumanizer import dehumanize, parse_parentheses


def test_parse_parentheses():
    assert parse_parentheses("uint256") == ["uint256"]
    assert parse_parentheses("transfer(address,uint256)") == [
        "transfer",
        ["address", "uint256"],
    ]
    assert parse_parentheses("balanceOf(address)(uint256)") == [
        "balanceOf",
        ["address"],
        ["uint256"],
    ]

    # strip spaces
    assert parse_parentheses("balanceOf ( address ) ( uint256 )") == [
        "balanceOf",
        ["address"],
        ["uint256"],
    ]

    # remove empty strings
    assert parse_parentheses("balanceOf ( address, , , ) ( uint256 )") == [
        "balanceOf",
        ["address"],
        ["uint256"],
    ]


def test_dehumanize():
    assert dehumanize("Transfer(address,uint256)", type="event") == {
        "inputs": [
            {"indexed": False, "type": "address"},
            {"indexed": False, "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }
    assert dehumanize("Transfer(address indexed, uint256)", type="event") == {
        "inputs": [
            {"indexed": True, "type": "address"},
            {"indexed": False, "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }
    assert dehumanize("function transfer(address,uint256)") == {
        "inputs": [{"type": "address"}, {"type": "uint256"}],
        "name": "transfer",
        "outputs": [],
        "type": "function",
    }
    for name in ["increaseAllowance", "decreaseAllowance"]:
        assert dehumanize(f"{name}(address,uint256)(bool)", type="function") == {
            "inputs": [{"type": "address"}, {"type": "uint256"}],
            "name": name,
            "outputs": [{"type": "bool"}],
            "type": "function",
        }


@pytest.mark.asyncio
async def test_human_readable_function(fork_w3):
    balance_of = ContractFunction.from_abi("balanceOf(address)(uint256)")
    addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC
    balance = await balance_of("0x0000000000000000000000000000000000000000").call(
        fork_w3, to=addr
    )
    assert isinstance(balance, int)
    for name in ["increaseAllowance", "decreaseAllowance"]:
        fn = ContractFunction.from_abi(f"{name}(address,uint256)(bool)")
        assert fn.abis[0]["name"] == name
        assert fn.abis[0]["inputs"] == [
            {"type": "address"},
            {"type": "uint256"},
        ]
