from eth_typing import ABI
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
    assert HexBytes(params["topics"][0]) == evt.topic
    assert "address" not in params
    assert "fromBlock" not in params
    assert "toBlock" not in params


def test_build_filter_with_address() -> None:
    evt = ContractEvent.from_abi(
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    )
    addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    params = evt.build_filter(address=addr)
    assert params["address"] == addr
    assert HexBytes(params["topics"][0]) == evt.topic


def test_build_filter_with_block_range() -> None:
    evt = ContractEvent.from_abi(
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    )
    params = evt.build_filter(from_block=100, to_block="latest")
    assert params["fromBlock"] == 100
    assert params["toBlock"] == "latest"
    assert HexBytes(params["topics"][0]) == evt.topic


def test_build_filter_with_indexed_argument() -> None:
    evt = ContractEvent.from_abi(
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    )
    sender = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    params = evt.build_filter(argument_filters={"from": sender})
    topics = params["topics"]
    # topic[0] = event signature, topic[1] = encoded `from` arg, topic[2] = None (any `to`)
    assert HexBytes(topics[0]) == evt.topic
    # The encoded address should be left-padded to 32 bytes
    assert topics[1] is not None
    assert sender[2:].lower() in topics[1].lower()  # strip 0x before substring check
    # trailing None topics for unfiltered indexed args are stripped by web3
    assert len(topics) == 2
