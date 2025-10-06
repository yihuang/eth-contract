import pytest

from eth_contract.human import (
    CONSTRUCTOR_SIGNATURE_REGEX,
    ERROR_SIGNATURE_REGEX,
    EVENT_MODIFIERS,
    EVENT_SIGNATURE_REGEX,
    FALLBACK_SIGNATURE_REGEX,
    FUNCTION_MODIFIERS,
    FUNCTION_SIGNATURE_REGEX,
    RECEIVE_SIGNATURE_REGEX,
    STRUCT_SIGNATURE_REGEX,
    is_solidity_type,
    is_struct_signature,
    parse_abi,
    parse_abi_parameter,
    parse_constructor_signature,
    parse_error_signature,
    parse_event_signature,
    parse_fallback_signature,
    parse_function_signature,
    parse_receive_signature,
    parse_signature,
    parse_structs,
    split_parameters,
)


class TestSplitParameters:
    """Test parameter splitting functionality."""

    def test_basic_parameters(self):
        """Test splitting basic comma-separated parameters."""
        assert split_parameters("address,uint256") == ["address", "uint256"]
        assert split_parameters("address, uint256, bool") == [
            "address",
            "uint256",
            "bool",
        ]

    def test_parameters_with_spaces(self):
        """Test parameters with various spacing."""
        assert split_parameters("address , uint256 , bool") == [
            "address",
            "uint256",
            "bool",
        ]
        assert split_parameters("address,uint256,bool") == [
            "address",
            "uint256",
            "bool",
        ]

    def test_nested_parentheses(self):
        """Test parameters with nested parentheses."""
        assert split_parameters("(uint256,address),bool") == [
            "(uint256,address)",
            "bool",
        ]
        assert split_parameters("((uint256),address),bool") == [
            "((uint256),address)",
            "bool",
        ]

    def test_empty_parameters(self):
        """Test empty parameter strings."""
        assert split_parameters("") == []
        assert split_parameters(" ") == []

    def test_invalid_parentheses(self):
        """Test invalid parentheses raise errors."""
        with pytest.raises(ValueError, match="Invalid parenthesis"):
            split_parameters("(uint256,address")
        with pytest.raises(ValueError, match="Invalid parenthesis"):
            split_parameters("uint256,address)")


class TestParseABIParameter:
    """Test ABI parameter parsing."""

    def test_basic_types(self):
        """Test parsing basic parameter types."""
        assert parse_abi_parameter("address") == {"type": "address"}
        assert parse_abi_parameter("uint256") == {"type": "uint256"}
        assert parse_abi_parameter("bool") == {"type": "bool"}

    def test_parameter_with_name(self):
        """Test parameters with names."""
        assert parse_abi_parameter("address to") == {"type": "address", "name": "to"}
        assert parse_abi_parameter("uint256 amount") == {
            "type": "uint256",
            "name": "amount",
        }

    def test_parameter_with_modifiers(self):
        """Test parameters with modifiers."""
        assert parse_abi_parameter("address indexed from") == {
            "type": "address",
            "name": "from",
            "indexed": True,
        }
        assert parse_abi_parameter("uint256 calldata value") == {
            "type": "uint256",
            "name": "value",
        }

    def test_array_types(self):
        """Test array parameter types."""
        assert parse_abi_parameter("uint256[]") == {"type": "uint256[]"}
        assert parse_abi_parameter("address[10]") == {"type": "address[10]"}
        assert parse_abi_parameter("bool[][]") == {"type": "bool[][]"}

    def test_tuple_types(self):
        """Test tuple parameter types."""
        result = parse_abi_parameter("(uint256,address)")
        assert result == {
            "type": "tuple",
            "components": [{"type": "uint256"}, {"type": "address"}],
        }

    def test_dynamic_integers(self):
        """Test dynamic integer types."""
        assert parse_abi_parameter("uint") == {"type": "uint256"}
        assert parse_abi_parameter("int") == {"type": "int256"}

    def test_address_payable(self):
        """Test address payable type."""
        assert parse_abi_parameter("address payable") == {"type": "address"}

    def test_invalid_parameter(self):
        """Test invalid parameter structure raises error."""
        # The current implementation doesn't validate types, so it accepts any string
        # Test with malformed parameter structure instead
        with pytest.raises(ValueError, match="Invalid parameter"):
            parse_abi_parameter("invalid parameter structure with spaces")

    def test_all_solidity_types(self):
        """Test parsing all Solidity ABI types with named parameters."""
        # Basic types
        assert parse_abi_parameter("bool isActive") == {
            "type": "bool",
            "name": "isActive",
        }
        assert parse_abi_parameter("address owner") == {
            "type": "address",
            "name": "owner",
        }
        assert parse_abi_parameter("string name") == {"type": "string", "name": "name"}
        assert parse_abi_parameter("bytes data") == {"type": "bytes", "name": "data"}

        # Integer types
        assert parse_abi_parameter("uint8 decimals") == {
            "type": "uint8",
            "name": "decimals",
        }
        assert parse_abi_parameter("int256 balance") == {
            "type": "int256",
            "name": "balance",
        }
        assert parse_abi_parameter("uint total") == {"type": "uint256", "name": "total"}
        assert parse_abi_parameter("int count") == {"type": "int256", "name": "count"}

        # Fixed point types
        assert parse_abi_parameter("ufixed128x18 price") == {
            "type": "ufixed128x18",
            "name": "price",
        }
        assert parse_abi_parameter("fixed256x80 rate") == {
            "type": "fixed256x80",
            "name": "rate",
        }

        # Bytes types
        assert parse_abi_parameter("bytes1 flag") == {"type": "bytes1", "name": "flag"}
        assert parse_abi_parameter("bytes32 hash") == {
            "type": "bytes32",
            "name": "hash",
        }

    def test_complex_array_types(self):
        """Test complex array types with named parameters."""
        # Single dimension arrays
        assert parse_abi_parameter("uint256[] amounts") == {
            "type": "uint256[]",
            "name": "amounts",
        }
        assert parse_abi_parameter("address[10] recipients") == {
            "type": "address[10]",
            "name": "recipients",
        }

        # Multi-dimensional arrays
        assert parse_abi_parameter("uint256[][] matrix") == {
            "type": "uint256[][]",
            "name": "matrix",
        }
        assert parse_abi_parameter("address[][5] lists") == {
            "type": "address[][5]",
            "name": "lists",
        }

        # Arrays with complex types
        assert parse_abi_parameter("string[] names") == {
            "type": "string[]",
            "name": "names",
        }
        assert parse_abi_parameter("bytes32[] hashes") == {
            "type": "bytes32[]",
            "name": "hashes",
        }

    def test_nested_tuples(self):
        """Test nested tuple types with named parameters."""
        # Simple tuple
        result = parse_abi_parameter("(uint256,address) pair")
        assert result == {
            "type": "tuple",
            "name": "pair",
            "components": [{"type": "uint256"}, {"type": "address"}],
        }

        # Nested tuple
        result = parse_abi_parameter("((uint256,address),bool) complex")
        assert result == {
            "type": "tuple",
            "name": "complex",
            "components": [
                {
                    "type": "tuple",
                    "components": [{"type": "uint256"}, {"type": "address"}],
                },
                {"type": "bool"},
            ],
        }

    def test_array_of_tuples(self):
        """Test array of tuple types."""
        # Array of simple tuples
        result = parse_abi_parameter("(uint256,address)[] pairs")
        assert result == {
            "type": "tuple[]",
            "name": "pairs",
            "components": [{"type": "uint256"}, {"type": "address"}],
        }

        # Fixed-size array of tuples
        result = parse_abi_parameter("(uint256,address)[10] fixedPairs")
        assert result == {
            "type": "tuple[10]",
            "name": "fixedPairs",
            "components": [{"type": "uint256"}, {"type": "address"}],
        }

        # Multi-dimensional array of tuples
        result = parse_abi_parameter("(uint256,address)[][] nestedPairs")
        assert result == {
            "type": "tuple[][]",
            "name": "nestedPairs",
            "components": [{"type": "uint256"}, {"type": "address"}],
        }

        # Array of nested tuples
        result = parse_abi_parameter("((uint256,address),bool)[] complexPairs")
        assert result == {
            "type": "tuple[]",
            "name": "complexPairs",
            "components": [
                {
                    "type": "tuple",
                    "components": [{"type": "uint256"}, {"type": "address"}],
                },
                {"type": "bool"},
            ],
        }

    def test_parameter_with_modifiers(self):
        """Test parameters with various modifiers."""
        # Function modifiers
        assert parse_abi_parameter("uint256 calldata value", FUNCTION_MODIFIERS) == {
            "type": "uint256",
            "name": "value",
        }
        assert parse_abi_parameter("string memory data", FUNCTION_MODIFIERS) == {
            "type": "string",
            "name": "data",
        }

        # Event modifiers
        assert parse_abi_parameter("address indexed from", EVENT_MODIFIERS) == {
            "type": "address",
            "name": "from",
            "indexed": True,
        }

    def test_invalid_modifiers(self):
        """Test invalid modifier usage raises errors."""
        # Invalid modifier for function
        with pytest.raises(
            ValueError, match="Invalid modifier 'indexed' for type function"
        ):
            parse_abi_parameter(
                "uint256 indexed value", FUNCTION_MODIFIERS, abi_type="function"
            )

        # Invalid modifier for event
        with pytest.raises(
            ValueError, match="Invalid modifier 'memory' for type event"
        ):
            parse_abi_parameter("string memory data", EVENT_MODIFIERS, abi_type="event")


class TestParseFunctionSignature:
    """Test function signature parsing."""

    def test_basic_function(self):
        """Test basic function parsing."""
        result = parse_function_signature("function transfer(address,uint256)")
        assert result == {
            "type": "function",
            "name": "transfer",
            "stateMutability": "nonpayable",
            "inputs": [{"type": "address"}, {"type": "uint256"}],
            "outputs": [],
        }

    def test_function_with_state_mutability(self):
        """Test function with state mutability."""
        result = parse_function_signature(
            "function balanceOf(address) view returns (uint256)"
        )
        assert result == {
            "type": "function",
            "name": "balanceOf",
            "stateMutability": "view",
            "inputs": [{"type": "address"}],
            "outputs": [{"type": "uint256"}],
        }

    def test_function_with_returns(self):
        """Test function with return values."""
        result = parse_function_signature("function getValues() returns (uint256,bool)")
        assert result == {
            "type": "function",
            "name": "getValues",
            "stateMutability": "nonpayable",
            "inputs": [],
            "outputs": [{"type": "uint256"}, {"type": "bool"}],
        }

    def test_function_with_scope(self):
        """Test function with scope modifiers."""
        result = parse_function_signature("function transfer(address,uint256) external")
        assert result["name"] == "transfer"
        assert result["stateMutability"] == "nonpayable"

    def test_function_with_payable(self):
        """Test payable function."""
        result = parse_function_signature("function deposit() payable")
        assert result == {
            "type": "function",
            "name": "deposit",
            "stateMutability": "payable",
            "inputs": [],
            "outputs": [],
        }

    def test_invalid_function_signature(self):
        """Test invalid function signature raises error."""
        with pytest.raises(ValueError, match="Invalid function signature"):
            parse_function_signature("invalid signature")


class TestParseEventSignature:
    """Test event signature parsing."""

    def test_basic_event(self):
        """Test basic event parsing."""
        result = parse_event_signature("event Transfer(address,uint256)")
        assert result == {
            "type": "event",
            "name": "Transfer",
            "inputs": [{"type": "address"}, {"type": "uint256"}],
        }

    def test_event_with_indexed_parameters(self):
        """Test event with indexed parameters."""
        result = parse_event_signature(
            "event Transfer(address indexed from, address indexed to, uint256 value)"
        )
        assert result == {
            "type": "event",
            "name": "Transfer",
            "inputs": [
                {"type": "address", "name": "from", "indexed": True},
                {"type": "address", "name": "to", "indexed": True},
                {"type": "uint256", "name": "value"},
            ],
        }

    def test_event_with_named_parameters(self):
        """Test event with named parameters."""
        result = parse_event_signature(
            "event Approval(address owner, address spender, uint256 value)"
        )
        assert result == {
            "type": "event",
            "name": "Approval",
            "inputs": [
                {"type": "address", "name": "owner"},
                {"type": "address", "name": "spender"},
                {"type": "uint256", "name": "value"},
            ],
        }

    def test_invalid_event_signature(self):
        """Test invalid event signature raises error."""
        with pytest.raises(ValueError, match="Invalid event signature"):
            parse_event_signature("invalid event signature")


class TestParseErrorSignature:
    """Test error signature parsing."""

    def test_basic_error(self):
        """Test basic error parsing."""
        result = parse_error_signature("error InsufficientBalance(uint256, uint256)")
        assert result == {
            "type": "error",
            "name": "InsufficientBalance",
            "inputs": [{"type": "uint256"}, {"type": "uint256"}],
        }

    def test_error_with_named_parameters(self):
        """Test error with named parameters."""
        result = parse_error_signature(
            "error InsufficientBalance(uint256 available, uint256 required)"
        )
        assert result == {
            "type": "error",
            "name": "InsufficientBalance",
            "inputs": [
                {"type": "uint256", "name": "available"},
                {"type": "uint256", "name": "required"},
            ],
        }

    def test_error_with_complex_types(self):
        """Test error with complex parameter types."""
        result = parse_error_signature(
            "error TransferFailed(address from, address to, uint256 amount)"
        )
        assert result == {
            "type": "error",
            "name": "TransferFailed",
            "inputs": [
                {"type": "address", "name": "from"},
                {"type": "address", "name": "to"},
                {"type": "uint256", "name": "amount"},
            ],
        }

    def test_invalid_error_signature(self):
        """Test invalid error signature raises error."""
        with pytest.raises(ValueError, match="Invalid error signature"):
            parse_error_signature("invalid error signature")


class TestParseConstructorSignature:
    """Test constructor signature parsing."""

    def test_basic_constructor(self):
        """Test basic constructor parsing."""
        result = parse_constructor_signature("constructor(address, uint256)")
        assert result == {
            "type": "constructor",
            "stateMutability": "nonpayable",
            "inputs": [{"type": "address"}, {"type": "uint256"}],
        }

    def test_constructor_with_named_parameters(self):
        """Test constructor with named parameters."""
        result = parse_constructor_signature(
            "constructor(address owner, uint256 initialSupply)"
        )
        assert result == {
            "type": "constructor",
            "stateMutability": "nonpayable",
            "inputs": [
                {"type": "address", "name": "owner"},
                {"type": "uint256", "name": "initialSupply"},
            ],
        }

    def test_payable_constructor(self):
        """Test payable constructor."""
        result = parse_constructor_signature("constructor(address) payable")
        assert result == {
            "type": "constructor",
            "stateMutability": "payable",
            "inputs": [{"type": "address"}],
        }

    def test_constructor_with_complex_types(self):
        """Test constructor with complex parameter types."""
        result = parse_constructor_signature(
            "constructor(string memory name, string memory symbol, uint8 decimals)"
        )
        assert result == {
            "type": "constructor",
            "stateMutability": "nonpayable",
            "inputs": [
                {"type": "string", "name": "name"},
                {"type": "string", "name": "symbol"},
                {"type": "uint8", "name": "decimals"},
            ],
        }

    def test_invalid_constructor_signature(self):
        """Test invalid constructor signature raises error."""
        with pytest.raises(ValueError, match="Invalid constructor signature"):
            parse_constructor_signature("invalid constructor signature")


class TestParseFallbackSignature:
    """Test fallback signature parsing."""

    def test_basic_fallback(self):
        """Test basic fallback parsing."""
        result = parse_fallback_signature("fallback() external")
        assert result == {
            "type": "fallback",
            "stateMutability": "nonpayable",
        }

    def test_payable_fallback(self):
        """Test payable fallback."""
        result = parse_fallback_signature("fallback() external payable")
        assert result == {
            "type": "fallback",
            "stateMutability": "payable",
        }

    def test_invalid_fallback_signature(self):
        """Test invalid fallback signature raises error."""
        with pytest.raises(ValueError, match="Invalid fallback signature"):
            parse_fallback_signature("invalid fallback signature")


class TestParseReceiveSignature:
    """Test receive signature parsing."""

    def test_receive(self):
        """Test receive parsing."""
        result = parse_receive_signature("receive() external payable")
        assert result == {
            "type": "receive",
            "stateMutability": "payable",
        }

    def test_invalid_receive_signature(self):
        """Test invalid receive signature raises error."""
        with pytest.raises(ValueError, match="Invalid receive signature"):
            parse_receive_signature("invalid receive signature")


class TestRegexPatterns:
    """Test regex patterns for signature matching."""

    def test_function_signature_regex(self):
        """Test function signature regex patterns."""
        # Basic function
        match = FUNCTION_SIGNATURE_REGEX.match("function transfer(address,uint256)")
        assert match is not None
        assert match.group("name") == "transfer"
        assert match.group("parameters") == "address,uint256"

        # Function with returns
        match = FUNCTION_SIGNATURE_REGEX.match(
            "function balanceOf(address) returns (uint256)"
        )
        assert match is not None
        assert match.group("returns") == "uint256"

        # Function with state mutability
        match = FUNCTION_SIGNATURE_REGEX.match(
            "function getBalance() view returns (uint256)"
        )
        assert match is not None
        assert match.group("stateMutability") == "view"

    def test_event_signature_regex(self):
        """Test event signature regex patterns."""
        match = EVENT_SIGNATURE_REGEX.match("event Transfer(address,uint256)")
        assert match is not None
        assert match.group("name") == "Transfer"
        assert match.group("parameters") == "address,uint256"

    def test_error_signature_regex(self):
        """Test error signature regex patterns."""
        match = ERROR_SIGNATURE_REGEX.match(
            "error InsufficientBalance(uint256 available, uint256 required)"
        )
        assert match is not None
        assert match.group("name") == "InsufficientBalance"
        assert match.group("parameters") == "uint256 available, uint256 required"

    def test_constructor_signature_regex(self):
        """Test constructor signature regex patterns."""
        match = CONSTRUCTOR_SIGNATURE_REGEX.match("constructor(address,uint256)")
        assert match is not None
        assert match.group("parameters") == "address,uint256"

        match = CONSTRUCTOR_SIGNATURE_REGEX.match("constructor(address) payable")
        assert match is not None
        assert match.group("stateMutability") == "payable"

    def test_fallback_signature_regex(self):
        """Test fallback signature regex patterns."""
        match = FALLBACK_SIGNATURE_REGEX.match("fallback() external")
        assert match is not None

        match = FALLBACK_SIGNATURE_REGEX.match("fallback() external payable")
        assert match is not None
        assert match.group("stateMutability") == "payable"

    def test_receive_signature_regex(self):
        """Test receive signature regex patterns."""
        match = RECEIVE_SIGNATURE_REGEX.match("receive() external payable")
        assert match is not None


class TestParseSignature:
    """Test generic signature parsing."""

    def test_parse_function_signature(self):
        """Test parsing function signature via generic parser."""
        result = parse_signature("function transfer(address to, uint256 amount)")
        assert result == {
            "type": "function",
            "name": "transfer",
            "stateMutability": "nonpayable",
            "inputs": [
                {"type": "address", "name": "to"},
                {"type": "uint256", "name": "amount"},
            ],
            "outputs": [],
        }

    def test_parse_event_signature(self):
        """Test parsing event signature via generic parser."""
        result = parse_signature(
            "event Transfer(address indexed from, address indexed to, uint256 value)"
        )
        assert result == {
            "type": "event",
            "name": "Transfer",
            "inputs": [
                {"type": "address", "name": "from", "indexed": True},
                {"type": "address", "name": "to", "indexed": True},
                {"type": "uint256", "name": "value"},
            ],
        }

    def test_parse_error_signature(self):
        """Test parsing error signature via generic parser."""
        result = parse_signature(
            "error InsufficientBalance(uint256 available, uint256 required)"
        )
        assert result == {
            "type": "error",
            "name": "InsufficientBalance",
            "inputs": [
                {"type": "uint256", "name": "available"},
                {"type": "uint256", "name": "required"},
            ],
        }

    def test_parse_constructor_signature(self):
        """Test parsing constructor signature via generic parser."""
        result = parse_signature("constructor(address owner, uint256 initialSupply)")
        assert result == {
            "type": "constructor",
            "stateMutability": "nonpayable",
            "inputs": [
                {"type": "address", "name": "owner"},
                {"type": "uint256", "name": "initialSupply"},
            ],
        }

    def test_parse_fallback_signature(self):
        """Test parsing fallback signature via generic parser."""
        result = parse_signature("fallback() external payable")
        assert result == {
            "type": "fallback",
            "stateMutability": "payable",
        }

    def test_parse_receive_signature(self):
        """Test parsing receive signature via generic parser."""
        result = parse_signature("receive() external payable")
        assert result == {
            "type": "receive",
            "stateMutability": "payable",
        }

    def test_parse_signature_with_structs(self):
        """Test parsing signatures with struct definitions."""
        structs = {
            "Point": [
                {"type": "uint256", "name": "x"},
                {"type": "uint256", "name": "y"},
            ]
        }
        result = parse_signature("function setPoint(Point p)", structs)
        assert result == {
            "type": "function",
            "name": "setPoint",
            "stateMutability": "nonpayable",
            "inputs": [
                {
                    "type": "tuple",
                    "name": "p",
                    "components": [
                        {"type": "uint256", "name": "x"},
                        {"type": "uint256", "name": "y"},
                    ],
                }
            ],
            "outputs": [],
        }

    def test_unknown_signature_type(self):
        """Test unknown signature type raises error."""
        with pytest.raises(ValueError, match="Unknown signature type"):
            parse_signature("unknown signature type")


class TestComplexFunctionSignatures:
    """Test complex function signatures with all ABI types."""

    def test_function_with_all_parameter_types(self):
        """Test function with all ABI parameter types."""
        signature = (
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
            ") returns (bool success, uint256 result)"
        )
        result = parse_function_signature(signature)
        assert result["name"] == "complexFunction"
        assert len(result["inputs"]) == 11
        assert len(result["outputs"]) == 2

    def test_function_with_memory_modifiers(self):
        """Test function with memory and calldata modifiers."""
        signature = (
            "function processData("
            "string memory name, "
            "bytes calldata data, "
            "uint256[] memory numbers"
            ") returns (string memory result)"
        )
        result = parse_function_signature(signature)
        assert result["name"] == "processData"
        assert len(result["inputs"]) == 3
        assert len(result["outputs"]) == 1

    def test_function_with_complex_returns(self):
        """Test function with complex return types."""
        signature = (
            "function getMultipleValues() returns ("
            "uint256 total, "
            "bool success, "
            "string message, "
            "address recipient"
            ")"
        )
        result = parse_function_signature(signature)
        assert result["name"] == "getMultipleValues"
        assert len(result["outputs"]) == 4
        assert result["outputs"][0] == {"type": "uint256", "name": "total"}
        assert result["outputs"][1] == {"type": "bool", "name": "success"}
        assert result["outputs"][2] == {"type": "string", "name": "message"}
        assert result["outputs"][3] == {"type": "address", "name": "recipient"}

    def test_function_with_array_of_tuples(self):
        """Test function with array of tuple parameters and returns."""
        # Function with array of tuples as parameter
        signature = "function processPairs((uint256,address)[] pairs)"
        result = parse_function_signature(signature)
        assert result["name"] == "processPairs"
        assert result["inputs"] == [
            {
                "type": "tuple[]",
                "name": "pairs",
                "components": [{"type": "uint256"}, {"type": "address"}],
            }
        ]

        # Function with array of tuples as return value
        signature = "function getPairs() returns ((uint256,address)[])"
        result = parse_function_signature(signature)
        assert result["name"] == "getPairs"
        assert result["outputs"] == [
            {
                "type": "tuple[]",
                "components": [{"type": "uint256"}, {"type": "address"}],
            }
        ]

        # Function with multi-dimensional array of tuples
        signature = "function processMatrix((uint256,address)[][] matrix)"
        result = parse_function_signature(signature)
        assert result["name"] == "processMatrix"
        assert result["inputs"] == [
            {
                "type": "tuple[][]",
                "name": "matrix",
                "components": [{"type": "uint256"}, {"type": "address"}],
            }
        ]

        # Function with fixed-size array of tuples
        signature = "function processFixedPairs((uint256,address)[10] pairs)"
        result = parse_function_signature(signature)
        assert result["name"] == "processFixedPairs"
        assert result["inputs"] == [
            {
                "type": "tuple[10]",
                "name": "pairs",
                "components": [{"type": "uint256"}, {"type": "address"}],
            }
        ]


class TestIsSolidityType:
    """Test Solidity type validation."""

    def test_basic_types(self):
        """Test basic Solidity types."""
        assert is_solidity_type("address") is True
        assert is_solidity_type("bool") is True
        assert is_solidity_type("string") is True
        assert is_solidity_type("bytes") is True
        assert is_solidity_type("function") is True

    def test_integer_types(self):
        """Test integer types."""
        assert is_solidity_type("uint8") is True
        assert is_solidity_type("uint256") is True
        assert is_solidity_type("int8") is True
        assert is_solidity_type("int256") is True
        assert is_solidity_type("uint") is False  # Should be uint256
        assert is_solidity_type("int") is False  # Should be int256

    def test_bytes_types(self):
        """Test fixed-size bytes types."""
        assert is_solidity_type("bytes1") is True
        assert is_solidity_type("bytes32") is True
        assert is_solidity_type("bytes33") is False  # Invalid
        assert is_solidity_type("bytes0") is False  # Invalid

    def test_invalid_types(self):
        """Test invalid types."""
        assert is_solidity_type("invalid") is False
        assert is_solidity_type("tuple") is False
        assert is_solidity_type("struct") is False


class TestIsStructSignature:
    """Test struct signature detection."""

    def test_valid_struct_signatures(self):
        """Test valid struct signatures."""
        assert is_struct_signature("struct Point { uint256 x; uint256 y; }") is True
        assert is_struct_signature("struct User { string name; address addr; }") is True
        assert is_struct_signature("struct Empty { }") is True

    def test_invalid_struct_signatures(self):
        """Test invalid struct signatures."""
        assert is_struct_signature("function test()") is False
        assert is_struct_signature("event Transfer(address)") is False
        assert is_struct_signature("struct") is False
        assert is_struct_signature("struct Point") is False


class TestParseStructs:
    """Test struct parsing functionality."""

    def test_basic_struct(self):
        """Test parsing a basic struct."""
        signatures = ["struct Point { uint256 x; uint256 y; }"]
        structs = parse_structs(signatures)

        assert "Point" in structs
        assert structs["Point"] == [
            {"type": "uint256", "name": "x"},
            {"type": "uint256", "name": "y"},
        ]

    def test_struct_with_various_types(self):
        """Test struct with various field types."""
        signatures = [
            "struct User { string name; address addr; uint256 balance; bool active; }"
        ]
        structs = parse_structs(signatures)

        assert "User" in structs
        assert structs["User"] == [
            {"type": "string", "name": "name"},
            {"type": "address", "name": "addr"},
            {"type": "uint256", "name": "balance"},
            {"type": "bool", "name": "active"},
        ]

    def test_multiple_structs(self):
        """Test parsing multiple structs."""
        signatures = [
            "struct Point { uint256 x; uint256 y; }",
            "struct User { string name; address addr; }",
            "function test()",  # Should be ignored
        ]
        structs = parse_structs(signatures)

        assert "Point" in structs
        assert "User" in structs
        assert len(structs) == 2

    def test_nested_structs(self):
        """Test nested struct references."""
        signatures = [
            "struct Point { uint256 x; uint256 y; }",
            "struct Line { Point start; Point end; }",
        ]
        structs = parse_structs(signatures)

        assert "Point" in structs
        assert "Line" in structs

        # Line should have resolved Point references to tuples
        assert structs["Line"] == [
            {
                "type": "tuple",
                "name": "start",
                "components": [
                    {"type": "uint256", "name": "x"},
                    {"type": "uint256", "name": "y"},
                ],
            },
            {
                "type": "tuple",
                "name": "end",
                "components": [
                    {"type": "uint256", "name": "x"},
                    {"type": "uint256", "name": "y"},
                ],
            },
        ]

    def test_struct_with_arrays(self):
        """Test struct with array fields."""
        signatures = ["struct Data { uint256[] values; address[10] addresses; }"]
        structs = parse_structs(signatures)

        assert "Data" in structs
        assert structs["Data"] == [
            {"type": "uint256[]", "name": "values"},
            {"type": "address[10]", "name": "addresses"},
        ]

    def test_circular_reference_detection(self):
        """Test circular reference detection."""
        signatures = [
            "struct A { B b; }",
            "struct B { A a; }",
        ]

        with pytest.raises(ValueError, match="Circular reference detected"):
            parse_structs(signatures)

    def test_invalid_struct_signature(self):
        """Test invalid struct signature raises error."""
        signatures = ["struct Invalid { }"]

        with pytest.raises(ValueError, match="Invalid struct signature"):
            parse_structs(signatures)

    def test_struct_with_unknown_type(self):
        """Test struct with unknown type raises error."""
        signatures = ["struct Invalid { unknown_type field; }"]

        with pytest.raises(ValueError, match="Unknown type"):
            parse_structs(signatures)


class TestParseABI:
    """Test top-level ABI parsing functionality."""

    def test_basic_abi(self):
        """Test parsing basic ABI without structs."""
        signatures = [
            "function transfer(address to, uint256 amount)",
            "event Transfer(address indexed from, address indexed to, uint256 value)",
            "error InsufficientBalance(uint256 available, uint256 required)",
        ]

        abi = parse_abi(signatures)

        assert len(abi) == 3
        assert abi[0]["type"] == "function"
        assert abi[1]["type"] == "event"
        assert abi[2]["type"] == "error"

    def test_abi_with_structs(self):
        """Test parsing ABI with struct definitions."""
        signatures = [
            "struct Point { uint256 x; uint256 y; }",
            "function setPoint(Point p)",
            "function getPoint() returns (Point)",
            "event PointSet(Point point)",
        ]

        abi = parse_abi(signatures)

        # Struct should not be in final ABI
        assert len(abi) == 3

        # Check function with struct parameter
        set_point = next(item for item in abi if item["name"] == "setPoint")
        assert set_point["inputs"] == [
            {
                "type": "tuple",
                "name": "p",
                "components": [
                    {"type": "uint256", "name": "x"},
                    {"type": "uint256", "name": "y"},
                ],
            }
        ]

        # Check function with struct return
        get_point = next(item for item in abi if item["name"] == "getPoint")
        assert get_point["outputs"] == [
            {
                "type": "tuple",
                "components": [
                    {"type": "uint256", "name": "x"},
                    {"type": "uint256", "name": "y"},
                ],
            }
        ]

    def test_abi_with_nested_structs(self):
        """Test parsing ABI with nested structs."""
        signatures = [
            "struct Point { uint256 x; uint256 y; }",
            "struct Line { Point start; Point end; }",
            "function drawLine(Line line)",
        ]

        abi = parse_abi(signatures)

        assert len(abi) == 1
        draw_line = abi[0]
        assert draw_line["inputs"] == [
            {
                "type": "tuple",
                "name": "line",
                "components": [
                    {
                        "type": "tuple",
                        "name": "start",
                        "components": [
                            {"type": "uint256", "name": "x"},
                            {"type": "uint256", "name": "y"},
                        ],
                    },
                    {
                        "type": "tuple",
                        "name": "end",
                        "components": [
                            {"type": "uint256", "name": "x"},
                            {"type": "uint256", "name": "y"},
                        ],
                    },
                ],
            }
        ]

    def test_abi_with_struct_arrays(self):
        """Test parsing ABI with struct arrays."""
        signatures = [
            "struct Point { uint256 x; uint256 y; }",
            "function setPoints(Point[] points)",
        ]

        abi = parse_abi(signatures)

        assert len(abi) == 1
        set_points = abi[0]
        assert set_points["inputs"] == [
            {
                "type": "tuple[]",
                "name": "points",
                "components": [
                    {"type": "uint256", "name": "x"},
                    {"type": "uint256", "name": "y"},
                ],
            }
        ]

    def test_empty_signatures(self):
        """Test empty signatures list raises error."""
        with pytest.raises(ValueError, match="At least one signature required"):
            parse_abi([])

    def test_mixed_abi_elements(self):
        """Test parsing mixed ABI elements."""
        signatures = [
            "struct User { string name; address addr; }",
            "function transfer(address to, uint256 amount)",
            "event Transfer(address indexed from, address indexed to, uint256 value)",
            "error InsufficientBalance(uint256 available, uint256 required)",
            "constructor(string name, string symbol)",
            "fallback() external",
            "receive() external payable",
        ]

        abi = parse_abi(signatures)

        # Should have 6 elements (struct is excluded)
        assert len(abi) == 6

        # Verify all types are present
        types = {item["type"] for item in abi}
        assert types == {
            "function",
            "event",
            "error",
            "constructor",
            "fallback",
            "receive",
        }

    def test_struct_regex_pattern(self):
        """Test struct regex pattern matching."""
        # Valid struct signatures
        match = STRUCT_SIGNATURE_REGEX.match("struct Point { uint256 x; uint256 y; }")
        assert match is not None
        assert match.group("name") == "Point"
        assert match.group("properties").strip() == "uint256 x; uint256 y;"

        match = STRUCT_SIGNATURE_REGEX.match(
            "struct User { string name; address addr; }"
        )
        assert match is not None
        assert match.group("name") == "User"

        # Invalid struct signatures
        assert STRUCT_SIGNATURE_REGEX.match("function test()") is None
        assert STRUCT_SIGNATURE_REGEX.match("struct Point") is None
