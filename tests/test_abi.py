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
