import pytest
from eth_typing import ABIFunction

from eth_contract.contract import ContractFunction


class TestContractFunctionFromABI:
    """Test ContractFunction.from_abi method integration."""

    def test_from_abi_with_string_signature_creates_function(self):
        """Test that string signature creates proper ContractFunction."""
        fn = ContractFunction.from_abi("function transfer(address,uint256)")

        assert isinstance(fn, ContractFunction)
        assert len(fn.abis) == 1
        assert fn.abi["type"] == "function"
        assert fn.abi["name"] == "transfer"

    def test_from_abi_with_abi_dict_creates_function(self):
        """Test that ABIFunction dict creates proper ContractFunction."""
        abi_dict: ABIFunction = {
            "type": "function",
            "name": "transfer",
            "stateMutability": "nonpayable",
            "inputs": [
                {"type": "address", "name": "to"},
                {"type": "uint256", "name": "amount"},
            ],
            "outputs": [],
        }

        fn = ContractFunction.from_abi(abi_dict)

        assert isinstance(fn, ContractFunction)
        assert fn.abi == abi_dict

    def test_from_abi_function_properties_are_set(self):
        """Test that ContractFunction properties are properly initialized."""
        fn = ContractFunction.from_abi("function transfer(address,uint256)")

        # Test all expected properties are set
        assert hasattr(fn, "name")
        assert hasattr(fn, "selector")
        assert hasattr(fn, "signature")
        assert hasattr(fn, "input_types")
        assert hasattr(fn, "output_types")

        # Test specific values
        assert fn.name == "transfer"
        assert fn.signature == "transfer(address,uint256)"
        assert fn.input_types == ["address", "uint256"]
        assert fn.output_types == []

    def test_from_abi_function_selector_is_correct(self):
        """Test that function selector is calculated correctly."""
        fn = ContractFunction.from_abi("function transfer(address,uint256)")

        # Known selector for transfer(address,uint256)
        expected_selector = bytes.fromhex("a9059cbb")
        assert fn.selector == expected_selector

    def test_from_abi_with_view_function(self):
        """Test that view functions work correctly."""
        fn = ContractFunction.from_abi(
            "function balanceOf(address) view returns (uint256)"
        )

        assert fn.name == "balanceOf"
        assert fn.signature == "balanceOf(address)"
        assert fn.input_types == ["address"]
        assert fn.output_types == ["uint256"]

    def test_from_abi_with_payable_function(self):
        """Test that payable functions work correctly."""
        fn = ContractFunction.from_abi("function deposit() payable")

        assert fn.name == "deposit"
        assert fn.signature == "deposit()"
        assert fn.input_types == []
        assert fn.output_types == []

    def test_from_abi_error_on_invalid_function_signature(self):
        """Test that invalid function signature raises appropriate error."""
        with pytest.raises(ValueError, match="Invalid function signature"):
            ContractFunction.from_abi("invalid signature")

    def test_from_abi_error_on_non_function_signature(self):
        """Test that non-function signatures raise appropriate error."""
        with pytest.raises(ValueError, match="Invalid function signature"):
            ContractFunction.from_abi("event Transfer(address,uint256)")

    def test_from_abi_equivalence_string_vs_dict(self) -> None:
        """Test that string and dict inputs produce equivalent ContractFunctions."""
        # Create from string
        fn_string = ContractFunction.from_abi("function transfer(address,uint256)")

        # Create from equivalent dict
        abi_dict: ABIFunction = {
            "type": "function",
            "name": "transfer",
            "stateMutability": "nonpayable",
            "inputs": [{"type": "address"}, {"type": "uint256"}],
            "outputs": [],
        }
        fn_dict = ContractFunction.from_abi(abi_dict)

        # Both should have the same essential properties
        assert fn_string.name == fn_dict.name
        assert fn_string.signature == fn_dict.signature
        assert fn_string.selector == fn_dict.selector
        assert fn_string.input_types == fn_dict.input_types
        assert fn_string.output_types == fn_dict.output_types
