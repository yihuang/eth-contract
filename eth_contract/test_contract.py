from .erc20 import ERC20


def test_erc20():
    fn = ERC20.fns.transfer
    assert fn.name == "transfer"
    assert fn.input_types == ["address", "uint256"]
    assert fn.output_types == ["bool"]
    assert fn.signature == "transfer(address,uint256)"
    assert fn.selector == bytes.fromhex("a9059cbb")

    evt = ERC20.events.Transfer
    assert evt.name == "Transfer"
    assert evt.input_types == ["address", "address", "uint256"]
    assert evt.signature == "Transfer(address,address,uint256)"
    assert evt.topic == bytes.fromhex(
        "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    )
