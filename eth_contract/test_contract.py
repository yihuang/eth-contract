from .erc20 import ERC20


def test_erc20():
    # by default, it resolve to the first function in the overloaded ones
    fn = ERC20.fns.transfer
    assert fn.name == "transfer"
    assert fn.input_types == ["address", "uint256"]
    assert fn.output_types == ["bool"]
    assert fn.signature == "transfer(address,uint256)"
    assert fn.selector == bytes.fromhex("a9059cbb")

    # passing arguments to resolve to a specific overloaded function
    fn = ERC20.fns.transfer((1).to_bytes(20, "big"), 1000)
    assert fn.data.to_0x_hex() == (
        "0xa9059cbb"
        "0000000000000000000000000000000000000000000000000000000000000001"
        "00000000000000000000000000000000000000000000000000000000000003e8"
    )

    evt = ERC20.events.Transfer
    assert evt.name == "Transfer"
    assert evt.signature == "Transfer(address,address,uint256)"
    assert evt.topic == bytes.fromhex(
        "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    )
