import asyncio

import pyrevm
import pytest
from eth_utils import keccak, to_checksum_address, to_hex

from eth_contract.contract import Contract
from eth_contract.deploy_utils import (
    ensure_deployed_by_create2,
    ensure_deployed_by_create3,
)
from eth_contract.entrypoint import MULTICALL3ROUTER_ARTIFACT
from eth_contract.erc20 import ERC20
from eth_contract.multicall3 import (
    MULTICALL3,
    MULTICALL3_ADDRESS,
    Call3Value,
    multicall,
)
from eth_contract.utils import (
    ZERO_ADDRESS,
    balance_of,
    get_initcode,
    send_transaction,
)
from eth_contract.weth import WETH

from .conftest import ETH_MAINNET_FORK, MULTICALL3ROUTER
from .contracts import WETH_ADDRESS, MockERC20_ARTIFACT
from .trace import trace_call


@pytest.mark.asyncio
async def test_erc20_live(fork_w3):
    # Test with live forked mainnet
    addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC
    balance = await ERC20.fns.balanceOf(
        "0x0000000000000000000000000000000000000000"
    ).call(fork_w3, to=addr)
    assert isinstance(balance, int)


def solidity_mapping_loc(index: int, address: bytes) -> bytes:
    return keccak(address.rjust(32, b"\x00") + index.to_bytes(32, "big"))


def vyper_mapping_loc(index: int, address: bytes) -> bytes:
    return keccak(address.rjust(32, b"\x00") + index.to_bytes(32, "big"))


@pytest.mark.asyncio
async def test_erc20_balance_overrides(fork_w3) -> None:
    """
    play with erc20 storage slots
    """
    w3 = fork_w3
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC
    addr = (1000000).to_bytes(20, "big")
    balance = 99999
    # tx: TxParams = {
    #     "to": token,
    #     "data": ERC20.fns.balanceOf(addr).data,
    # }
    # rsp = await w3.provider.make_request("debug_traceCall", [tx, "latest"])
    # print(json.dumps(rsp, indent=2))
    locs = [solidity_mapping_loc(i, addr) for i in range(0, 10)] + [
        vyper_mapping_loc(i, addr) for i in range(0, 10)
    ]
    await asyncio.gather(
        *[
            w3.provider.make_request(
                "anvil_setStorageAt",
                [token, to_hex(loc), balance.to_bytes(32, "big")],
            )
            for loc in locs
        ]
    )

    assert (await ERC20.fns.balanceOf(addr).call(w3, to=token)) == balance


@pytest.mark.asyncio
async def test_create2_deploy(w3):
    owner = (await w3.eth.accounts)[0]
    salt = 100
    initcode = get_initcode(MockERC20_ARTIFACT, "TEST", "TEST", 18)
    token = await ensure_deployed_by_create2(w3, owner, initcode, salt=salt)
    assert token == "0x854d811d90C6E81B84b29C1d7ed957843cF87bba"
    balance = await ERC20.fns.balanceOf(owner).call(w3, to=token)
    amt = 1000
    await ERC20.fns.mint(owner, amt).transact(w3, owner, to=token)
    assert await ERC20.fns.balanceOf(owner).call(w3, to=token) == balance + amt


@pytest.mark.asyncio
async def test_create3_deploy(w3):
    owner = (await w3.eth.accounts)[0]
    salt = 200
    initcode = get_initcode(MockERC20_ARTIFACT, "TEST", "TEST", 18)
    token = await ensure_deployed_by_create3(w3, owner, initcode, salt=salt)
    assert token == "0x60f7B32B5799838a480572Aee2A8F0355f607b38"
    balance = await ERC20.fns.balanceOf(owner).call(w3, to=token)
    amt = 1000
    await ERC20.fns.mint(owner, amt).transact(w3, owner, to=token)
    assert await ERC20.fns.balanceOf(owner).call(w3, to=token) == balance + amt


@pytest.mark.asyncio
async def test_weth(w3):
    weth = WETH(to=WETH_ADDRESS)
    acct = (await w3.eth.accounts)[0]
    before = await balance_of(w3, ZERO_ADDRESS, acct)
    receipt = await weth.fns.deposit().transact(w3, acct, value=1000)
    fee = receipt["effectiveGasPrice"] * receipt["gasUsed"]
    await balance_of(w3, WETH_ADDRESS, acct) == 1000
    receipt = await weth.fns.withdraw(1000).transact(w3, acct)
    fee += receipt["effectiveGasPrice"] * receipt["gasUsed"]
    await balance_of(w3, WETH_ADDRESS, acct) == 0
    assert await balance_of(w3, ZERO_ADDRESS, acct) == before - fee


@pytest.mark.asyncio
async def test_batch_call(w3):
    weth = WETH(to=WETH_ADDRESS)
    users = (await w3.eth.accounts)[:10]
    amount = 1000
    amount_all = amount * len(users)

    balances = [(WETH_ADDRESS, ERC20.fns.balanceOf(user)) for user in users]
    assert all(x == 0 for x in await multicall(w3, balances))

    await MULTICALL3.fns.aggregate3Value(
        [Call3Value(WETH_ADDRESS, False, amount_all, weth.fns.deposit().data)]
        + [
            Call3Value(WETH_ADDRESS, False, 0, ERC20.fns.transfer(user, amount).data)
            for user in users
        ]
    ).transact(w3, users[0], value=amount_all)

    assert all(x == amount for x in await multicall(w3, balances))

    for user in users:
        await ERC20.fns.approve(MULTICALL3_ADDRESS, amount).transact(
            w3, user, to=WETH_ADDRESS
        )

    await MULTICALL3.fns.aggregate3Value(
        [
            Call3Value(
                WETH_ADDRESS,
                data=ERC20.fns.transferFrom(user, MULTICALL3_ADDRESS, amount).data,
            )
            for user in users
        ]
        + [
            Call3Value(
                WETH_ADDRESS,
                data=weth.fns.transferFrom(
                    MULTICALL3_ADDRESS, users[0], amount_all
                ).data,
            ),
        ]
    ).transact(w3, users[0])
    await weth.fns.withdraw(amount_all).transact(w3, users[0], to=WETH_ADDRESS)

    assert all(x == 0 for x in await multicall(w3, balances))
    assert await balance_of(w3, WETH_ADDRESS, MULTICALL3_ADDRESS) == 0


@pytest.mark.asyncio
async def test_multicall3_router(w3):
    """
    multicall3router extends standard multicall3 with some more abilities
    """
    users = (await w3.eth.accounts)[:10]
    amount = 1000
    amount_all = amount * len(users)
    router = Contract(MULTICALL3ROUTER_ARTIFACT["abi"])
    multicall3 = MULTICALL3ROUTER

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
    ).transact(w3, users[0], to=multicall3, value=amount_all)
    before -= receipt["effectiveGasPrice"] * receipt["gasUsed"]

    # check users's weth balances
    assert all(x == amount for x in await multicall(w3, balances))

    # approve multicall3 to transfer WETH on behalf of users
    for i, user in enumerate(users):
        receipt = await ERC20.fns.approve(multicall3, amount).transact(
            w3, user, to=WETH_ADDRESS
        )
        if i == 0:
            before -= receipt["effectiveGasPrice"] * receipt["gasUsed"]

    # transfer WETH from all users to multicall3, withdraw it,
    # and send back to users[0]
    receipt = await MULTICALL3.fns.aggregate3Value(
        [
            Call3Value(
                WETH_ADDRESS, data=ERC20.fns.transferFrom(user, multicall3, amount).data
            )
            for user in users
        ]
        + [
            Call3Value(WETH_ADDRESS, data=WETH.fns.withdraw(amount_all).data),
            Call3Value(
                multicall3,
                data=router.fns.sellToPool(ZERO_ADDRESS, 10000, users[0], 0, b"").data,
            ),
        ]
    ).transact(w3, users[0], to=multicall3)
    before -= receipt["effectiveGasPrice"] * receipt["gasUsed"]

    assert all(x == 0 for x in await multicall(w3, balances))
    assert await balance_of(w3, WETH_ADDRESS, multicall3) == 0
    assert await balance_of(w3, ZERO_ADDRESS, multicall3) == 0

    # user get all funds back other than gas fees
    assert await balance_of(w3, ZERO_ADDRESS, users[0]) == before


@pytest.mark.asyncio
async def test_7702(w3, test_accounts):
    acct = test_accounts[0]
    multicall3 = MULTICALL3ROUTER

    nonce = await w3.eth.get_transaction_count(acct.address)
    chain_id = await w3.eth.chain_id
    auth = acct.sign_authorization(
        {
            "chainId": chain_id,
            "address": multicall3,
            "nonce": nonce + 1,
        }
    )
    amount = 1000
    calls = [
        Call3Value(WETH_ADDRESS, False, amount, WETH.fns.deposit().data),
        Call3Value(WETH_ADDRESS, False, 0, WETH.fns.withdraw(amount).data),
    ]
    before = await balance_of(w3, ZERO_ADDRESS, acct.address)
    receipt = await send_transaction(
        w3,
        acct,
        chainId=chain_id,
        to=acct.address,
        value=amount,
        nonce=nonce,
        authorizationList=[auth],
        data=MULTICALL3.fns.aggregate3Value(calls).data,
    )
    fee = receipt["effectiveGasPrice"] * receipt["gasUsed"]
    after = await balance_of(w3, ZERO_ADDRESS, acct.address)
    assert after == before - fee


def test_pyrevm_trace():
    vm = pyrevm.EVM(fork_url=ETH_MAINNET_FORK, tracing=True, with_memory=True)
    addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC
    whale = "0x37305B1cD40574E4C5Ce33f8e8306Be057fD7341"

    for trace in trace_call(vm, data=ERC20.fns.balanceOf(whale).data, to=addr):
        if trace.get("opName") == "SLOAD":
            print(trace)


def test_pyrevm_trace_log():
    WETH_ADDRESS = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    whale = "0x44663D61BD6Ad13848D1E90b1F5940eB6836D2F5"
    deposit_amount = 2589000000000000
    deposit_fn = "Deposit(address,uint256)"
    deposit_hash = f"0x{keccak(deposit_fn.encode()).hex()}"

    vm = pyrevm.EVM(fork_url=ETH_MAINNET_FORK, tracing=True, with_memory=True)
    for trace in trace_call(
        vm,
        **{
            "from": whale,
            "to": WETH_ADDRESS,
            "data": WETH.fns.deposit().data,
            "value": deposit_amount,
        },
    ):
        op = trace.get("opName", "")
        if op.startswith("LOG"):
            # LOG2 -> 2, LOG0 -> 0 etc
            num_topics = int(op[3])
            stack = trace["stack"]
            topics = stack[-(2 + num_topics) : -2][::-1]
            assert topics[0] == deposit_hash, "deposit event hash mismatch"
            assert to_checksum_address(topics[1]) == whale, "whale address mismatch"
