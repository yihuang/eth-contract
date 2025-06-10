import pytest
from eth_contract.erc20 import ERC20, ERC20_ABI
from eth_contract.create2 import create2_deploy, CREATE2_FACTORY
from eth_contract.utils import get_initcode

@pytest.mark.asyncio
async def test_erc20_live(w3):
    # Test with live forked mainnet
    addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC
    balance = await ERC20.fns.balanceOf(
        "0x0000000000000000000000000000000000000000"
    ).call(w3, {"to": addr})
    assert isinstance(balance, int)


@pytest.mark.asyncio
async def test_create2_deploy(w3):
    accts = await w3.eth.accounts
    acct = w3.eth.account.create()
    fund = 10**18
    tx_hash = await w3.eth.send_transaction(
        {"from": accts[0], "to": acct.address, "value": fund}
    )
    res = await w3.eth.wait_for_transaction_receipt(tx_hash)
    assert res["status"] == 1
    balance = await w3.eth.get_balance(acct.address)
    assert balance == fund
    price = await w3.eth.gas_price
    tx = {
        "from": acct.address,
        "gas": "0x2625a0",
        "gasPrice": hex(price),
    }
    initcode = get_initcode(ERC20_ABI)
    res = await create2_deploy(w3, initcode, acct, 0, CREATE2_FACTORY, extra=tx)
    assert res == "0x06aF35e31BC77ADcE5a4865B1Ec04F8E7c97E3eD"