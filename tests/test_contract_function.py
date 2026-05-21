import pytest
from eth_abi import encode
from eth_abi.codec import ABICodec
from eth_abi.decoding import AddressDecoder
from eth_abi.registry import registry as default_registry
from eth_typing import ABIFunction

from eth_contract import ABIStruct
from eth_contract.contract import Contract, ContractFunction


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

    def test_monkey_patch_codec(self) -> None:
        fn = ContractFunction.from_abi("function sender() returns (address)")
        addr = fn.decode(b"\x00" * 32)
        assert addr == "0x0000000000000000000000000000000000000000"

        class AddressBytesDecoder(AddressDecoder):
            @staticmethod
            def decoder_fn(data):
                return data

        reg = default_registry.copy()
        reg.unregister_decoder("address")
        reg.register_decoder("address", AddressBytesDecoder, label="address_bytes")

        import eth_contract.contract

        old_codec = eth_contract.contract._abi_codec
        eth_contract.contract._abi_codec = ABICodec(reg)

        try:
            addr = fn.decode(b"\x00" * 32)
            assert addr == b"\x00" * 20
        finally:
            # restore
            eth_contract.contract._abi_codec = old_codec


@pytest.mark.parametrize(
    "signature,args,expected",
    [
        (
            "function transfer(address,uint256)",
            (b"\xaa" * 20, 1000),
            ("0x" + "aa" * 20, 1000),
        ),
        (
            "function supply(address,uint256,address,uint16)",
            (b"\xee" * 20, 12345, b"\xff" * 20, 99),
            ("0x" + "ee" * 20, 12345, "0x" + "ff" * 20, 99),
        ),
        (
            "function flashLoanSimple(address,address,uint256,bytes,uint16)",
            (b"\xcc" * 20, b"\xdd" * 20, 1_000_000, b"\xde\xad\xbe\xef", 0),
            ("0x" + "cc" * 20, "0x" + "dd" * 20, 1_000_000, b"\xde\xad\xbe\xef", 0),
        ),
    ],
    ids=["static", "multi-arg", "dynamic-bytes"],
)
def test_decode_input_round_trip(signature: str, args: tuple, expected: tuple) -> None:
    """Encode then decode_input recovers every argument."""
    fn = ContractFunction.from_abi(signature)
    assert tuple(fn.decode_input(fn(*args).data)) == expected


def test_decode_input_single_arg_unwrapped() -> None:
    """Single-input functions return the value directly."""
    fn = ContractFunction.from_abi("function setUserEMode(uint8)")
    assert fn.decode_input(fn(7).data) == 7


def test_decode_input_rejects_selector_mismatch() -> None:
    """Body-only payloads (no selector prefix) must be rejected."""
    fn = ContractFunction.from_abi("function transfer(address,uint256)")
    body = bytes(fn(b"\xbb" * 20, 42).data)[4:]
    with pytest.raises(ValueError, match="selector mismatch"):
        fn.decode_input(body)


def test_decode_input_does_not_strip_bytes4_arg_equal_to_selector() -> None:
    """A first arg whose value equals the selector must still decode cleanly."""
    fn = ContractFunction.from_abi("function setMagic(bytes4,uint256)")
    magic, nonce = fn.decode_input(fn(bytes(fn.selector), 7).data)
    assert magic == bytes(fn.selector)
    assert nonce == 7


def test_decode_keeps_bytes4_return_equal_to_selector() -> None:
    """A bytes4 return value equal to the selector must not be re-read as calldata."""
    fn = ContractFunction.from_abi("function mySelector() view returns (bytes4)")
    return_data = bytes(fn.selector) + b"\x00" * 28
    assert fn.decode(return_data) == bytes(fn.selector)


class TestDecodeNamedStructs:
    """``ContractFunction.decode`` maps ``tuple`` outputs to ``ABIStruct``
    instances. These cover the decode path itself; the deeper ``ABIStruct``
    synthesis invariants are in ``test_struct.py``'s ``TestDynamicStruct``."""

    def test_decode_returns_abistruct(self) -> None:
        """A struct output decodes to a named, tuple-compatible ``ABIStruct``."""
        fn = Contract.from_abi(
            [
                "struct Point { uint256 x; uint256 y; }",
                "function getPoint() view returns (Point)",
            ]
        ).fns.getPoint
        result = fn.decode(encode(fn.output_types, [(1, 2)]))

        assert issubclass(type(result), ABIStruct)
        assert (result.x, result.y) == (1, 2)  # by name
        assert result == (1, 2)  # equal to a plain tuple

    def test_decode_wraps_struct_arrays(self) -> None:
        """``decode`` wraps struct elements inside (possibly nested) arrays."""
        points = Contract.from_abi(
            [
                "struct Point { uint256 x; uint256 y; }",
                "function getPoints() view returns (Point[])",
            ]
        ).fns.getPoints
        flat = points.decode(encode(points.output_types, [[(1, 2), (3, 4)]]))
        assert [(p.x, p.y) for p in flat] == [(1, 2), (3, 4)]

        grid = Contract.from_abi(
            [
                "struct Point { uint256 x; uint256 y; }",
                "function getGrid() view returns (Point[][])",
            ]
        ).fns.getGrid
        rows = grid.decode(encode(grid.output_types, [[[(1, 2)], [(3, 4)]]]))
        assert [[(p.x, p.y) for p in row] for row in rows] == [[(1, 2)], [(3, 4)]]

    def test_decode_multi_return_stays_plain_tuple(self) -> None:
        """Multiple top-level return values are left as a plain tuple."""
        fn = ContractFunction.from_abi(
            "function pair() view returns (uint256 a, uint256 b)"
        )
        result = fn.decode(encode(fn.output_types, [7, 8]))

        assert result == (7, 8)
        assert type(result) is tuple


def test_decode_input_resolves_overloaded_function() -> None:
    """decode_input picks the matching overload by selector, not just abis[0]."""
    fn = Contract.from_abi(
        [
            "function transfer(address,uint256)",
            "function transfer(address,uint256,bytes)",
        ]
    ).fns.transfer
    assert len(fn.abis) == 2

    assert tuple(fn.decode_input(fn(b"\xaa" * 20, 1000).data)) == (
        "0x" + "aa" * 20,
        1000,
    )
    assert tuple(fn.decode_input(fn(b"\xbb" * 20, 2000, b"\xde\xad").data)) == (
        "0x" + "bb" * 20,
        2000,
        b"\xde\xad",
    )
