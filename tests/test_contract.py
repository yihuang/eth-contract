from typing import cast

import pytest
from eth_abi.abi import encode
from hexbytes import HexBytes
from web3.types import TxReceipt

from eth_contract import Contract, entrypoint
from eth_contract.create2 import create2_address
from eth_contract.deploy_utils import ensure_deployed_by_create2
from eth_contract.erc20 import ERC20
from eth_contract.history_storage import HISTORY_STORAGE_ADDRESS
from eth_contract.utils import ZERO_ADDRESS, get_initcode

from .contracts import MockERC20_ARTIFACT


def test_contract_addresses():
    assert entrypoint.ENTRYPOINT08_ADDRESS == create2_address(
        get_initcode(entrypoint.ENTRYPOINT08_ARTIFACT), entrypoint.ENTRYPOINT08_SALT
    )
    assert entrypoint.ENTRYPOINT07_ADDRESS == create2_address(
        get_initcode(entrypoint.ENTRYPOINT07_ARTIFACT), entrypoint.ENTRYPOINT07_SALT
    )


@pytest.mark.asyncio
async def test_history_storage(w3):
    assert await w3.eth.get_code(HISTORY_STORAGE_ADDRESS)
    latest = await w3.eth.block_number
    height = latest - 1
    result = await w3.eth.call(
        {
            "to": HISTORY_STORAGE_ADDRESS,
            "data": height.to_bytes(32, "big"),
        }
    )
    print(result)


class TestContractFromABI:
    """Test Contract.from_abi method."""

    def test_from_abi_with_human_readable_signatures(self):
        """Test creating contract from human-readable ABI signatures."""
        signatures = [
            "function transfer(address to, uint256 amount) external",
            "function balanceOf(address owner) external view returns (uint256)",
            "event Transfer(address indexed from, address indexed to, uint256 amount)",
            "error InsufficientBalance(uint256 available, uint256 required)",
        ]

        contract = Contract.from_abi(signatures)

        # Verify functions
        assert len(contract.fns._abis) == 2
        assert "transfer" in contract.fns._abis
        assert "balanceOf" in contract.fns._abis

        # Verify events
        assert len(contract.events.abis) == 1
        assert contract.events.abis[0]["name"] == "Transfer"

        # Verify constructor is None (no constructor in signatures)
        assert contract.constructor is None

    def test_from_abi_with_parsed_abi(self):
        """Test creating contract from parsed ABI."""
        parsed_abi = [
            {
                "type": "function",
                "name": "transfer",
                "inputs": [
                    {"name": "to", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "stateMutability": "nonpayable"
            },
            {
                "type": "event",
                "name": "Transfer",
                "inputs": [
                    {"name": "from", "type": "address", "indexed": True},
                    {"name": "to", "type": "address", "indexed": True},
                    {"name": "amount", "type": "uint256"}
                ]
            }
        ]

        contract = Contract.from_abi(parsed_abi)

        # Verify functions
        assert len(contract.fns._abis) == 1
        assert "transfer" in contract.fns._abis

        # Verify events
        assert len(contract.events.abis) == 1
        assert contract.events.abis[0]["name"] == "Transfer"

    def test_from_abi_with_structs(self):
        """Test creating contract with struct definitions."""
        signatures = [
            "struct Point { uint256 x; uint256 y; }",
            "function setPoint(Point p) external",
            "function getPoint() external returns (Point)",
            "event PointSet(Point point)",
        ]

        contract = Contract.from_abi(signatures)

        # Verify functions
        assert len(contract.fns._abis) == 2
        assert "setPoint" in contract.fns._abis
        assert "getPoint" in contract.fns._abis

        # Verify events
        assert len(contract.events.abis) == 1
        assert contract.events.abis[0]["name"] == "PointSet"

        # Verify function signatures include tuple types (shown as (type1,type2))
        set_point_fn = contract.fns.setPoint
        assert "(uint256,uint256)" in set_point_fn.signature

    def test_from_abi_with_constructor(self):
        """Test creating contract with constructor."""
        signatures = [
            "constructor(address owner, uint256 initialSupply)",
            "function transfer(address to, uint256 amount) external",
        ]

        contract = Contract.from_abi(signatures)

        # Verify constructor is present
        assert contract.constructor is not None
        assert contract.constructor.abi["type"] == "constructor"

        # Verify functions
        assert len(contract.fns._abis) == 1
        assert "transfer" in contract.fns._abis

    def test_from_abi_with_tx_parameters(self):
        """Test creating contract with transaction parameters."""
        signatures = [
            "function transfer(address to, uint256 amount) external",
        ]

        # Create contract with transaction parameters
        contract = Contract.from_abi(signatures)

        # Apply transaction parameters using the call method
        contract_with_tx = contract(gas=100000, value=1000)

        # Verify functions
        assert len(contract_with_tx.fns._abis) == 1
        assert "transfer" in contract_with_tx.fns._abis

        # Verify transaction parameters
        assert contract_with_tx.tx["gas"] == 100000
        assert contract_with_tx.tx["value"] == 1000

    def test_from_abi_with_complex_functions(self):
        """Test creating contract with complex function signatures."""
        signatures = [
            "function complexFunction("
            "bool active, "
            "uint256 count, "
            "int256 balance, "
            "address owner, "
            "string name, "
            "bytes data, "
            "uint8 decimals, "
            "bytes32 hash, "
            "uint256[] amounts, "
            "address[10] recipients, "
            "(uint256,address) pair"
            ") returns (bool success, uint256 result)",
        ]

        contract = Contract.from_abi(signatures)

        # Verify function
        assert len(contract.fns._abis) == 1
        assert "complexFunction" in contract.fns._abis

        # Verify function can be accessed
        fn = contract.fns.complexFunction
        assert fn.name == "complexFunction"

    def test_from_abi_with_fallback_and_receive(self):
        """Test creating contract with fallback and receive functions."""
        signatures = [
            "function transfer(address to, uint256 amount) external",
            "fallback() external",
            "receive() external payable",
        ]

        contract = Contract.from_abi(signatures)

        # Verify functions
        assert len(contract.fns._abis) == 1
        assert "transfer" in contract.fns._abis

        # Verify fallback and receive are present
        assert contract.fallback is not None
        assert contract.receive is not None

    def test_from_abi_function_access(self):
        """Test that functions can be accessed and called."""
        signatures = [
            "function transfer(address to, uint256 amount) external",
            "function balanceOf(address owner) external view returns (uint256)",
        ]

        contract = Contract.from_abi(signatures)

        # Access functions
        transfer_fn = contract.fns.transfer
        balance_of_fn = contract.fns.balanceOf

        # Verify function properties
        assert transfer_fn.name == "transfer"
        assert balance_of_fn.name == "balanceOf"

        # Verify function signatures
        assert "transfer(address,uint256)" in transfer_fn.signature
        assert "balanceOf(address)" in balance_of_fn.signature

    def test_encode_abi(self):
        """Test that encode_abi returns HexBytes with selector + encoded args."""
        contract = Contract.from_abi([
            "function transfer(address to, uint256 amount) external",
        ])
        to = "0x" + "ab" * 20
        amount = 1000

        result = contract.encode_abi("transfer", [to, amount])

        assert isinstance(result, HexBytes)
        # Matches manually calling the function
        assert result == contract.fns.transfer(to, amount).data
        # selector is first 4 bytes
        assert result[:4] == contract.fns.transfer.selector

    def test_from_abi_event_access(self):
        """Test that events can be accessed."""
        signatures = [
            "event Transfer(address indexed from, address indexed to, uint256 amount)",
            "event Approval(address owner, address spender, uint256 amount)",
        ]

        contract = Contract.from_abi(signatures)

        # Access events
        transfer_event = contract.events.Transfer
        approval_event = contract.events.Approval

        # Verify event properties
        assert transfer_event.name == "Transfer"
        assert approval_event.name == "Approval"

        # Verify event signatures
        assert "Transfer(address,address,uint256)" in transfer_event.signature
        assert "Approval(address,address,uint256)" in approval_event.signature


class TestProcessReceipt:
    """Test ContractEvent.process_receipt."""

    @pytest.mark.asyncio
    async def test_decodes_and_filters(self, w3):
        owner = (await w3.eth.accounts)[0]
        token = await ensure_deployed_by_create2(
            w3, owner, get_initcode(MockERC20_ARTIFACT, "T", "T", 18), salt=401
        )
        amount = 1000

        receipt = await ERC20.fns.mint(owner, amount).transact(w3, owner, to=token)

        events = ERC20.events.Transfer.process_receipt(receipt)
        assert len(events) == 1
        assert events[0]["args"] == {"from": ZERO_ADDRESS, "to": owner, "amount": amount}
        assert ERC20.events.Approval.process_receipt(receipt) == []

    def test_multiple_matching_events(self):
        transfer_event = ERC20.events.Transfer
        addr_a = "0x" + "aa" * 20
        addr_b = "0x" + "bb" * 20

        def make_log(from_addr, to_addr, amount):
            return {
                "address": to_addr,
                "topics": [
                    transfer_event.topic,
                    HexBytes(bytes(12) + bytes.fromhex(from_addr[2:])),
                    HexBytes(bytes(12) + bytes.fromhex(to_addr[2:])),
                ],
                "data": HexBytes(encode(["uint256"], [amount])),
                "blockHash": HexBytes(b"\x00" * 32),
                "blockNumber": 1,
                "transactionHash": HexBytes(b"\x00" * 32),
                "transactionIndex": 0,
                "logIndex": 0,
                "removed": False,
            }

        receipt = cast(TxReceipt, {"logs": [make_log(addr_a, addr_b, 500), make_log(addr_b, addr_a, 250)]})
        events = transfer_event.process_receipt(receipt)
        assert len(events) == 2
        assert events[0]["args"]["amount"] == 500
        assert events[1]["args"]["amount"] == 250

    def test_empty_logs_returns_empty(self):
        assert ERC20.events.Transfer.process_receipt(cast(TxReceipt, {"logs": []})) == []
