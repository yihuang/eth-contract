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
    assert dehumanize("Transfer(uint256)", type="event") == {
        "inputs": [{"indexed": False, "type": "uint256"}],
        "name": "Transfer",
        "type": "event",
    }
    assert dehumanize("function transfer(address,uint256)") == {
        "inputs": [{"type": "address"}, {"type": "uint256"}],
        "name": "function transfer",
        "outputs": [],
        "type": "function",
    }
