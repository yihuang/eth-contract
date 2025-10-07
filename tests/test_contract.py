import pytest

from eth_contract import Contract, entrypoint
from eth_contract.create2 import create2_address
from eth_contract.history_storage import HISTORY_STORAGE_ADDRESS
from eth_contract.utils import get_initcode


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
