import pytest
from eth_contract.contract import Contract
from eth_contract.create2 import create2_address, create2_deploy
from eth_contract.create3 import create3_address, create3_deploy
from eth_contract.erc20 import ERC20
from eth_contract.multicall3 import (MULTICALL3, MULTICALL3_ADDRESS,
                                     Call3Value, multicall)
from eth_contract.utils import ZERO_ADDRESS, balance_of, get_initcode
from eth_contract.weth import WETH

from .contracts import (MULTICALL3ROUTER_ARTIFACT, WETH_ADDRESS,
                        MockERC20_ARTIFACT)


@pytest.mark.asyncio
async def test_erc20_live(fork_w3):
    # Test with live forked mainnet
    addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC
    balance = await ERC20.fns.balanceOf(
        "0x0000000000000000000000000000000000000000"
    ).call(fork_w3, {"to": addr})
    assert isinstance(balance, int)


@pytest.mark.asyncio
async def test_create2_deploy(w3):
    owner = (await w3.eth.accounts)[0]
    salt = 100
    initcode = get_initcode(MockERC20_ARTIFACT, "TEST", "TEST", 18)
    token = await create2_deploy(w3, initcode, salt=salt, extra={"from": owner})
    assert (
        token
        == create2_address(initcode, salt)
        == "0x854d811d90C6E81B84b29C1d7ed957843cF87bba"
    )

    tx = {"to": token, "from": owner}
    assert await ERC20.fns.balanceOf(owner).call(w3, tx=tx) == 0
    await ERC20.fns.mint(owner, 1000).transact(w3, tx=tx)
    assert await ERC20.fns.balanceOf(owner).call(w3, tx=tx) == 1000


@pytest.mark.asyncio
async def test_create3_deploy(w3):
    owner = (await w3.eth.accounts)[0]
    salt = 200
    initcode = get_initcode(MockERC20_ARTIFACT, "TEST", "TEST", 18)
    token = await create3_deploy(w3, initcode, salt=salt, extra={"from": owner})
    assert (
        token == create3_address(salt) == "0x60f7B32B5799838a480572Aee2A8F0355f607b38"
    )

    tx = {"to": token, "from": owner}
    assert await ERC20.fns.balanceOf(owner).call(w3, tx=tx) == 0
    await ERC20.fns.mint(owner, 1000).transact(w3, tx=tx)
    assert await ERC20.fns.balanceOf(owner).call(w3, tx=tx) == 1000


@pytest.mark.asyncio
async def test_weth(w3):
    acct = (await w3.eth.accounts)[0]
    before = await balance_of(w3, ZERO_ADDRESS, acct)
    receipt = await WETH.fns.deposit().transact(
        w3, tx={"from": acct, "to": WETH_ADDRESS, "value": 1000}
    )
    fee = receipt["effectiveGasPrice"] * receipt["gasUsed"]
    await balance_of(w3, WETH_ADDRESS, acct) == 1000
    receipt = await WETH.fns.withdraw(1000).transact(
        w3, tx={"from": acct, "to": WETH_ADDRESS}
    )
    fee += receipt["effectiveGasPrice"] * receipt["gasUsed"]
    await balance_of(w3, WETH_ADDRESS, acct) == 0
    assert await balance_of(w3, ZERO_ADDRESS, acct) == before - fee


@pytest.mark.asyncio
async def test_batch_call(w3):
    users = (await w3.eth.accounts)[:10]
    amount = 1000
    amount_all = amount * len(users)

    balances = [(WETH_ADDRESS, ERC20.fns.balanceOf(user)) for user in users]
    assert all(x == 0 for x in await multicall(w3, balances))

    await MULTICALL3.fns.aggregate3Value(
        [Call3Value(WETH_ADDRESS, False, amount_all, WETH.fns.deposit().data)]
        + [
            Call3Value(WETH_ADDRESS, False, 0, ERC20.fns.transfer(user, amount).data)
            for user in users
        ]
    ).transact(w3, tx={"from": users[0], "to": MULTICALL3_ADDRESS, "value": amount_all})

    assert all(x == amount for x in await multicall(w3, balances))

    for user in users:
        await ERC20.fns.approve(MULTICALL3_ADDRESS, amount).transact(
            w3, tx={"from": user, "to": WETH_ADDRESS}
        )

    await MULTICALL3.fns.aggregate3Value(
        [
            Call3Value(
                WETH_ADDRESS,
                False,
                0,
                ERC20.fns.transferFrom(user, MULTICALL3_ADDRESS, amount).data,
            )
            for user in users
        ]
        + [
            Call3Value(
                WETH_ADDRESS,
                False,
                0,
                WETH.fns.transferFrom(MULTICALL3_ADDRESS, users[0], amount_all).data,
            ),
        ]
    ).transact(w3, tx={"from": users[0], "to": MULTICALL3_ADDRESS})
    await WETH.fns.withdraw(amount_all).transact(
        w3, tx={"from": users[0], "to": WETH_ADDRESS}
    )

    assert all(x == 0 for x in await multicall(w3, balances))
    assert await balance_of(w3, WETH_ADDRESS, MULTICALL3_ADDRESS) == 0


@pytest.mark.asyncio
async def test_multicall3_router(w3):
    """
    multicall3 extends standard multicall3 with some more abilities
    """
    users = (await w3.eth.accounts)[:10]
    amount = 1000
    amount_all = amount * len(users)
    router = Contract(MULTICALL3ROUTER_ARTIFACT["abi"])
    multicall3 = await create2_deploy(
        w3,
        get_initcode(MULTICALL3ROUTER_ARTIFACT, MULTICALL3_ADDRESS),
        extra={"from": users[0]},
    )

    balances = [(WETH_ADDRESS, ERC20.fns.balanceOf(user)) for user in users]
    assert all(x == 0 for x in await multicall(w3, balances))

    before = await balance_of(w3, ZERO_ADDRESS, users[0])

    # convert amount_all into WETH and distribute to users
    receipt = await MULTICALL3.fns.aggregate3Value(
        [Call3Value(WETH_ADDRESS, False, amount_all, WETH.fns.deposit().data)]
        + [
            Call3Value(WETH_ADDRESS, False, 0, ERC20.fns.transfer(user, amount).data)
            for user in users
        ]
    ).transact(w3, tx={"from": users[0], "to": multicall3, "value": amount_all})
    before -= receipt["effectiveGasPrice"] * receipt["gasUsed"]

    # check users's weth balances
    assert all(x == amount for x in await multicall(w3, balances))

    # approve multicall3 to transfer WETH on behalf of users
    for i, user in enumerate(users):
        receipt = await ERC20.fns.approve(multicall3, amount).transact(
            w3, tx={"from": user, "to": WETH_ADDRESS}
        )
        if i == 0:
            before -= receipt["effectiveGasPrice"] * receipt["gasUsed"]

    # transfer WETH from all users to multicall3, withdraw it,
    # and send back to users[0]
    receipt = await MULTICALL3.fns.aggregate3Value(
        [
            Call3Value(
                WETH_ADDRESS,
                False,
                0,
                ERC20.fns.transferFrom(user, multicall3, amount).data,
            )
            for user in users
        ]
        + [
            Call3Value(WETH_ADDRESS, False, 0, WETH.fns.withdraw(amount_all).data),
            Call3Value(
                multicall3,
                False,
                0,
                router.fns.sellToPool(ZERO_ADDRESS, 10000, users[0], 0, b"").data,
            ),
        ]
    ).transact(w3, tx={"from": users[0], "to": multicall3})
    before -= receipt["effectiveGasPrice"] * receipt["gasUsed"]

    assert all(x == 0 for x in await multicall(w3, balances))
    assert await balance_of(w3, WETH_ADDRESS, multicall3) == 0
    assert await balance_of(w3, ZERO_ADDRESS, multicall3) == 0

    # user get all funds back other than gas fees
    assert await balance_of(w3, ZERO_ADDRESS, users[0]) == before
