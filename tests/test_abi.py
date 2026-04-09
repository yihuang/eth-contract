import pytest
from eth_typing import ABI, ChecksumAddress
from hexbytes import HexBytes

from eth_contract.contract import Contract, ContractEvent


def test_receive_fallback() -> None:
    abi: ABI = [
        {"stateMutability": "payable", "type": "receive"},
        {"stateMutability": "payable", "type": "fallback"},
    ]

    c = Contract(abi)
    assert c.receive is not None
    assert c.fallback is not None
    assert c.receive().data == bytes.fromhex("a3e76c0f")
    assert c.fallback().data == bytes.fromhex("552079dc")


def test_event_abi() -> None:
    evt = ContractEvent.from_abi(
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    )
    assert evt.name == "Transfer"
    assert evt.signature == "Transfer(address,address,uint256)"
    assert evt.topic == HexBytes(
        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    )


def test_build_filter_no_args() -> None:
    evt = ContractEvent.from_abi(
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    )
    params = evt.build_filter()
    # topics[0] must always be the event signature hash
    t0 = params["topics"][0]
    assert isinstance(t0, str)
    assert HexBytes(t0) == evt.topic
    assert "address" not in params
    assert "fromBlock" not in params
    assert "toBlock" not in params


def test_build_filter_with_address() -> None:
    evt = ContractEvent.from_abi(
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    )
    addr = ChecksumAddress("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
    params = evt.build_filter(address=addr)
    assert params["address"] == addr
    t0 = params["topics"][0]
    assert isinstance(t0, str)
    assert HexBytes(t0) == evt.topic


def test_build_filter_with_block_range() -> None:
    evt = ContractEvent.from_abi(
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    )
    params = evt.build_filter(from_block=100, to_block="latest")
    assert params["fromBlock"] == 100
    assert params["toBlock"] == "latest"
    t0 = params["topics"][0]
    assert isinstance(t0, str)
    assert HexBytes(t0) == evt.topic


def test_build_filter_with_indexed_argument() -> None:
    evt = ContractEvent.from_abi(
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    )
    sender = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    params = evt.build_filter(argument_filters={"from": sender})
    topics = params["topics"]
    # topic[0] = event sig, topic[1] = encoded `from` arg, topic[2] = None (any `to`)
    t0 = topics[0]
    assert isinstance(t0, str)
    assert HexBytes(t0) == evt.topic
    # The encoded address should be left-padded to 32 bytes
    t1 = topics[1]
    assert t1 is not None
    assert isinstance(t1, str)
    assert sender[2:].lower() in t1.lower()  # strip 0x before substring check
    # trailing None topics for unfiltered indexed args are stripped by web3
    assert len(topics) == 2


def test_build_filter_with_non_indexed_argument_raises() -> None:
    evt = ContractEvent.from_abi(
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    )
    with pytest.raises(ValueError, match="not an indexed parameter"):
        evt.build_filter(argument_filters={"value": 100})
