from eth_typing import ABI

from eth_contract import Contract


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
