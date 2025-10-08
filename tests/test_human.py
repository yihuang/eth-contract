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
    """test parameter splitting functionality."""

    @pytest.mark.parametrize(
        "input_str, expected",
        [
            # basic parameters
            ("address,uint256", ["address", "uint256"]),
            ("address, uint256, bool", ["address", "uint256", "bool"]),
            # parameters with various spacing
            ("address , uint256 , bool", ["address", "uint256", "bool"]),
            ("address,uint256,bool", ["address", "uint256", "bool"]),
            # nested parentheses
            ("(uint256,address),bool", ["(uint256,address)", "bool"]),
            ("((uint256),address),bool", ["((uint256),address)", "bool"]),
            # empty parameters
            ("", []),
            (" ", []),
            # deeply nested parentheses
            ("(((uint256)),address)", ["(((uint256)),address)"]),
            # mixed parentheses and commas
            (
                "(uint256,address),bool,(string,bytes)",
                ["(uint256,address)", "bool", "(string,bytes)"],
            ),
            # complex nested structures
            (
                "((uint256,(address,bool)),string)",
                ["((uint256,(address,bool)),string)"],
            ),
        ],
    )
    def test_valid_parameter_splitting(self, input_str, expected):
        """test valid parameter splitting cases."""
        assert split_parameters(input_str) == expected

    @pytest.mark.parametrize(
        "input_str, expected_error",
        [
            # invalid parentheses - extra open
            ("(uint256,address", "Invalid parenthesis"),
            # invalid parentheses - extra close
            ("uint256,address)", "Invalid parenthesis"),
            # unbalanced parentheses - extra open
            ("((uint256,address)", "Invalid parenthesis"),
            # unbalanced parentheses - extra close
            ("(uint256,address))", "Invalid parenthesis"),
        ],
    )
    def test_invalid_parameter_splitting(self, input_str, expected_error):
        """test invalid parameter splitting cases that raise errors."""
        with pytest.raises(ValueError, match=expected_error):
            split_parameters(input_str)


class TestParseABIParameter:
    """Test ABI parameter parsing."""

    @pytest.mark.parametrize(
        "input_str, expected",
        [
            # Basic types
            ("address", {"type": "address"}),
            ("uint256", {"type": "uint256"}),
            ("bool", {"type": "bool"}),
            # Parameters with names
            ("address to", {"type": "address", "name": "to"}),
            ("uint256 amount", {"type": "uint256", "name": "amount"}),
            # Array types
            ("uint256[]", {"type": "uint256[]"}),
            ("address[10]", {"type": "address[10]"}),
            ("bool[][]", {"type": "bool[][]"}),
            # Dynamic integers
            ("uint", {"type": "uint256"}),
            ("int", {"type": "int256"}),
            # Address payable
            ("address payable", {"type": "address"}),
            # Tuple types
            (
                "(uint256,address)",
                {
                    "type": "tuple",
                    "components": [{"type": "uint256"}, {"type": "address"}],
                },
            ),
            # All Solidity types with named parameters
            ("bool isActive", {"type": "bool", "name": "isActive"}),
            ("address owner", {"type": "address", "name": "owner"}),
            ("string name", {"type": "string", "name": "name"}),
            ("bytes data", {"type": "bytes", "name": "data"}),
            ("uint8 decimals", {"type": "uint8", "name": "decimals"}),
            ("int256 balance", {"type": "int256", "name": "balance"}),
            ("uint total", {"type": "uint256", "name": "total"}),
            ("int count", {"type": "int256", "name": "count"}),
            ("ufixed128x18 price", {"type": "ufixed128x18", "name": "price"}),
            ("fixed256x80 rate", {"type": "fixed256x80", "name": "rate"}),
            ("bytes1 flag", {"type": "bytes1", "name": "flag"}),
            ("bytes32 hash", {"type": "bytes32", "name": "hash"}),
            # Complex array types
            ("uint256[] amounts", {"type": "uint256[]", "name": "amounts"}),
            ("address[10] recipients", {"type": "address[10]", "name": "recipients"}),
            ("uint256[][] matrix", {"type": "uint256[][]", "name": "matrix"}),
            ("address[][5] lists", {"type": "address[][5]", "name": "lists"}),
            ("string[] names", {"type": "string[]", "name": "names"}),
            ("bytes32[] hashes", {"type": "bytes32[]", "name": "hashes"}),
            # Nested tuples
            (
                "(uint256,address) pair",
                {
                    "type": "tuple",
                    "name": "pair",
                    "components": [{"type": "uint256"}, {"type": "address"}],
                },
            ),
            (
                "((uint256,address),bool) complex",
                {
                    "type": "tuple",
                    "name": "complex",
                    "components": [
                        {
                            "type": "tuple",
                            "components": [{"type": "uint256"}, {"type": "address"}],
                        },
                        {"type": "bool"},
                    ],
                },
            ),
            # Array of tuples
            (
                "(uint256,address)[] pairs",
                {
                    "type": "tuple[]",
                    "name": "pairs",
                    "components": [{"type": "uint256"}, {"type": "address"}],
                },
            ),
            (
                "(uint256,address)[10] fixedPairs",
                {
                    "type": "tuple[10]",
                    "name": "fixedPairs",
                    "components": [{"type": "uint256"}, {"type": "address"}],
                },
            ),
            (
                "(uint256,address)[][] nestedPairs",
                {
                    "type": "tuple[][]",
                    "name": "nestedPairs",
                    "components": [{"type": "uint256"}, {"type": "address"}],
                },
            ),
            (
                "((uint256,address),bool)[] complexPairs",
                {
                    "type": "tuple[]",
                    "name": "complexPairs",
                    "components": [
                        {
                            "type": "tuple",
                            "components": [{"type": "uint256"}, {"type": "address"}],
                        },
                        {"type": "bool"},
                    ],
                },
            ),
        ],
    )
    def test_basic_parameter_parsing(self, input_str, expected):
        """Test basic parameter parsing cases."""
        assert parse_abi_parameter(input_str) == expected

    @pytest.mark.parametrize(
        "input_str, modifiers, expected",
        [
            # Function modifiers
            (
                "uint256 calldata value",
                FUNCTION_MODIFIERS,
                {"type": "uint256", "name": "value"},
            ),
            (
                "string memory data",
                FUNCTION_MODIFIERS,
                {"type": "string", "name": "data"},
            ),
            # Event modifiers
            (
                "address indexed from",
                EVENT_MODIFIERS,
                {"type": "address", "name": "from", "indexed": True},
            ),
        ],
    )
    def test_parameter_with_modifiers(self, input_str, modifiers, expected):
        """Test parameters with various modifiers."""
        assert parse_abi_parameter(input_str, modifiers) == expected

    @pytest.mark.parametrize(
        "input_str, modifiers, abi_type, expected_error",
        [
            # Invalid modifier for function
            (
                "uint256 indexed value",
                FUNCTION_MODIFIERS,
                "function",
                "Invalid modifier 'indexed' for type function",
            ),
            # Invalid modifier for event
            (
                "string memory data",
                EVENT_MODIFIERS,
                "event",
                "Invalid modifier 'memory' for type event",
            ),
        ],
    )
    def test_invalid_modifiers(self, input_str, modifiers, abi_type, expected_error):
        """Test invalid modifier usage raises errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_abi_parameter(input_str, modifiers, abi_type=abi_type)

    @pytest.mark.parametrize(
        "input_str, expected_error",
        [
            # Invalid parameter structure
            ("invalid parameter structure with spaces", "Invalid parameter"),
            # Invalid tuple parameter structure
            ("(uint256,address", "Invalid parameter"),
            # Empty tuple parameter
            ("()", "Invalid parameter"),
            # Malformed array syntax
            ("uint256[", "Invalid parameter"),
            # Invalid modifier placement
            ("indexed address from", "Invalid parameter"),
            # Parameter with unbalanced parentheses
            ("((uint256,address)", "Invalid parenthesis"),
        ],
    )
    def test_invalid_parameter_parsing(self, input_str, expected_error):
        """Test invalid parameter parsing cases that raise errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_abi_parameter(input_str)


class TestParseFunctionSignature:
    """Test function signature parsing."""

    @pytest.mark.parametrize(
        "signature, expected",
        [
            # Basic function
            (
                "function transfer(address,uint256)",
                {
                    "type": "function",
                    "name": "transfer",
                    "stateMutability": "nonpayable",
                    "inputs": [{"type": "address"}, {"type": "uint256"}],
                    "outputs": [],
                },
            ),
            # Function with state mutability
            (
                "function balanceOf(address) view returns (uint256)",
                {
                    "type": "function",
                    "name": "balanceOf",
                    "stateMutability": "view",
                    "inputs": [{"type": "address"}],
                    "outputs": [{"type": "uint256"}],
                },
            ),
            # Function with return values
            (
                "function getValues() returns (uint256,bool)",
                {
                    "type": "function",
                    "name": "getValues",
                    "stateMutability": "nonpayable",
                    "inputs": [],
                    "outputs": [{"type": "uint256"}, {"type": "bool"}],
                },
            ),
            # Function with scope modifiers
            (
                "function transfer(address,uint256) external",
                {
                    "type": "function",
                    "name": "transfer",
                    "stateMutability": "nonpayable",
                    "inputs": [{"type": "address"}, {"type": "uint256"}],
                    "outputs": [],
                },
            ),
            # Payable function
            (
                "function deposit() payable",
                {
                    "type": "function",
                    "name": "deposit",
                    "stateMutability": "payable",
                    "inputs": [],
                    "outputs": [],
                },
            ),
        ],
    )
    def test_valid_function_signatures(self, signature, expected):
        """Test valid function signature parsing."""
        result = parse_function_signature(signature)
        assert result == expected

    @pytest.mark.parametrize(
        "signature, expected_error",
        [
            # Invalid function signature
            ("invalid signature", "Invalid function signature"),
            # Function with invalid state mutability
            ("function test() invalid returns (uint256)", "Invalid parenthesis"),
        ],
    )
    def test_invalid_function_signatures(self, signature, expected_error):
        """Test invalid function signature parsing that raises errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_function_signature(signature)

    @pytest.mark.parametrize(
        "signature, expected_name, expected_input_type, expected_output_type",
        [
            # Function with malformed parameters
            ("function test(uint256)", "test", "uint256", None),
            # Function with malformed returns
            ("function test() returns (uint256)", "test", None, "uint256"),
        ],
    )
    def test_malformed_function_signatures(
        self, signature, expected_name, expected_input_type, expected_output_type
    ):
        """Test function signatures with malformed parameters or returns."""
        result = parse_function_signature(signature)
        assert result["name"] == expected_name

        if expected_input_type:
            assert result["inputs"][0]["type"] == expected_input_type

        if expected_output_type:
            assert result["outputs"][0]["type"] == expected_output_type


class TestParseEventSignature:
    """Test event signature parsing."""

    @pytest.mark.parametrize(
        "signature, expected",
        [
            # Basic event
            (
                "event Transfer(address,uint256)",
                {
                    "type": "event",
                    "name": "Transfer",
                    "inputs": [{"type": "address"}, {"type": "uint256"}],
                },
            ),
            # Event with indexed parameters
            (
                "event Transfer(address indexed from, address indexed to, "
                "uint256 value)",
                {
                    "type": "event",
                    "name": "Transfer",
                    "inputs": [
                        {"type": "address", "name": "from", "indexed": True},
                        {"type": "address", "name": "to", "indexed": True},
                        {"type": "uint256", "name": "value"},
                    ],
                },
            ),
            # Event with named parameters
            (
                "event Approval(address owner, address spender, uint256 value)",
                {
                    "type": "event",
                    "name": "Approval",
                    "inputs": [
                        {"type": "address", "name": "owner"},
                        {"type": "address", "name": "spender"},
                        {"type": "uint256", "name": "value"},
                    ],
                },
            ),
        ],
    )
    def test_valid_event_signatures(self, signature, expected):
        """Test valid event signature parsing."""
        result = parse_event_signature(signature)
        assert result == expected

    @pytest.mark.parametrize(
        "signature, expected_error",
        [
            # Invalid event signature
            ("invalid event signature", "Invalid event signature"),
            # Event with invalid modifiers
            ("event Transfer(address memory from)", "Invalid modifier"),
        ],
    )
    def test_invalid_event_signatures(self, signature, expected_error):
        """Test invalid event signature parsing that raises errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_event_signature(signature)

    @pytest.mark.parametrize(
        "signature, expected_name, expected_input_type",
        [
            # Event with malformed parameters
            ("event Transfer(address)", "Transfer", "address"),
        ],
    )
    def test_malformed_event_signatures(
        self, signature, expected_name, expected_input_type
    ):
        """Test event signatures with malformed parameters."""
        result = parse_event_signature(signature)
        assert result["name"] == expected_name
        assert result["inputs"][0]["type"] == expected_input_type


class TestParseErrorSignature:
    """Test error signature parsing."""

    @pytest.mark.parametrize(
        "signature, expected",
        [
            # Basic error
            (
                "error InsufficientBalance(uint256, uint256)",
                {
                    "type": "error",
                    "name": "InsufficientBalance",
                    "inputs": [{"type": "uint256"}, {"type": "uint256"}],
                },
            ),
            # Error with named parameters
            (
                "error InsufficientBalance(uint256 available, uint256 required)",
                {
                    "type": "error",
                    "name": "InsufficientBalance",
                    "inputs": [
                        {"type": "uint256", "name": "available"},
                        {"type": "uint256", "name": "required"},
                    ],
                },
            ),
            # Error with complex types
            (
                "error TransferFailed(address from, address to, uint256 amount)",
                {
                    "type": "error",
                    "name": "TransferFailed",
                    "inputs": [
                        {"type": "address", "name": "from"},
                        {"type": "address", "name": "to"},
                        {"type": "uint256", "name": "amount"},
                    ],
                },
            ),
        ],
    )
    def test_valid_error_signatures(self, signature, expected):
        """Test valid error signature parsing."""
        result = parse_error_signature(signature)
        assert result == expected

    @pytest.mark.parametrize(
        "signature, expected_error",
        [
            # Invalid error signature
            ("invalid error signature", "Invalid error signature"),
        ],
    )
    def test_invalid_error_signatures(self, signature, expected_error):
        """Test invalid error signature parsing that raises errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_error_signature(signature)

    @pytest.mark.parametrize(
        "signature, expected_name, expected_input_type",
        [
            # Error with malformed parameters
            ("error TestError(uint256)", "TestError", "uint256"),
        ],
    )
    def test_malformed_error_signatures(
        self, signature, expected_name, expected_input_type
    ):
        """Test error signatures with malformed parameters."""
        result = parse_error_signature(signature)
        assert result["name"] == expected_name
        assert result["inputs"][0]["type"] == expected_input_type


class TestParseConstructorSignature:
    """Test constructor signature parsing."""

    @pytest.mark.parametrize(
        "signature, expected",
        [
            # Basic constructor
            (
                "constructor(address, uint256)",
                {
                    "type": "constructor",
                    "stateMutability": "nonpayable",
                    "inputs": [{"type": "address"}, {"type": "uint256"}],
                },
            ),
            # Constructor with named parameters
            (
                "constructor(address owner, uint256 initialSupply)",
                {
                    "type": "constructor",
                    "stateMutability": "nonpayable",
                    "inputs": [
                        {"type": "address", "name": "owner"},
                        {"type": "uint256", "name": "initialSupply"},
                    ],
                },
            ),
            # Payable constructor
            (
                "constructor(address) payable",
                {
                    "type": "constructor",
                    "stateMutability": "payable",
                    "inputs": [{"type": "address"}],
                },
            ),
            # Constructor with complex types
            (
                "constructor(string memory name, string memory symbol, uint8 decimals)",
                {
                    "type": "constructor",
                    "stateMutability": "nonpayable",
                    "inputs": [
                        {"type": "string", "name": "name"},
                        {"type": "string", "name": "symbol"},
                        {"type": "uint8", "name": "decimals"},
                    ],
                },
            ),
        ],
    )
    def test_valid_constructor_signatures(self, signature, expected):
        """Test valid constructor signature parsing."""
        result = parse_constructor_signature(signature)
        assert result == expected

    @pytest.mark.parametrize(
        "signature, expected_error",
        [
            # Invalid constructor signature
            ("invalid constructor signature", "Invalid constructor signature"),
        ],
    )
    def test_invalid_constructor_signatures(self, signature, expected_error):
        """Test invalid constructor signature parsing that raises errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_constructor_signature(signature)

    @pytest.mark.parametrize(
        "signature, expected_type, expected_input_type",
        [
            # Constructor with malformed parameters
            ("constructor(uint256)", "constructor", "uint256"),
        ],
    )
    def test_malformed_constructor_signatures(
        self, signature, expected_type, expected_input_type
    ):
        """Test constructor signatures with malformed parameters."""
        result = parse_constructor_signature(signature)
        assert result["type"] == expected_type
        assert result["inputs"][0]["type"] == expected_input_type


class TestParseFallbackSignature:
    """Test fallback signature parsing."""

    @pytest.mark.parametrize(
        "signature, expected",
        [
            # Basic fallback
            (
                "fallback() external",
                {
                    "type": "fallback",
                    "stateMutability": "nonpayable",
                },
            ),
            # Payable fallback
            (
                "fallback() external payable",
                {
                    "type": "fallback",
                    "stateMutability": "payable",
                },
            ),
        ],
    )
    def test_valid_fallback_signatures(self, signature, expected):
        """Test valid fallback signature parsing."""
        result = parse_fallback_signature(signature)
        assert result == expected

    @pytest.mark.parametrize(
        "signature, expected_error",
        [
            # Invalid fallback signature
            ("invalid fallback signature", "Invalid fallback signature"),
            # Fallback with parameters
            ("fallback(address) external", "Invalid fallback signature"),
        ],
    )
    def test_invalid_fallback_signatures(self, signature, expected_error):
        """Test invalid fallback signature parsing that raises errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_fallback_signature(signature)


class TestParseReceiveSignature:
    """Test receive signature parsing."""

    @pytest.mark.parametrize(
        "signature, expected",
        [
            # Receive
            (
                "receive() external payable",
                {
                    "type": "receive",
                    "stateMutability": "payable",
                },
            ),
        ],
    )
    def test_valid_receive_signatures(self, signature, expected):
        """Test valid receive signature parsing."""
        result = parse_receive_signature(signature)
        assert result == expected

    @pytest.mark.parametrize(
        "signature, expected_error",
        [
            # Invalid receive signature
            ("invalid receive signature", "Invalid receive signature"),
            # Receive with parameters
            ("receive(address) external payable", "Invalid receive signature"),
            # Receive without payable
            ("receive() external", "Invalid receive signature"),
        ],
    )
    def test_invalid_receive_signatures(self, signature, expected_error):
        """Test invalid receive signature parsing that raises errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_receive_signature(signature)


class TestRegexPatterns:
    """Test regex patterns for signature matching."""

    @pytest.mark.parametrize(
        "pattern, signature, expected_groups",
        [
            # Function signature regex
            (
                FUNCTION_SIGNATURE_REGEX,
                "function transfer(address,uint256)",
                {"name": "transfer", "parameters": "address,uint256"},
            ),
            (
                FUNCTION_SIGNATURE_REGEX,
                "function balanceOf(address) returns (uint256)",
                {"name": "balanceOf", "parameters": "address", "returns": "uint256"},
            ),
            (
                FUNCTION_SIGNATURE_REGEX,
                "function getBalance() view returns (uint256)",
                {
                    "name": "getBalance",
                    "parameters": "",
                    "stateMutability": "view",
                    "returns": "uint256",
                },
            ),
            # Event signature regex
            (
                EVENT_SIGNATURE_REGEX,
                "event Transfer(address,uint256)",
                {"name": "Transfer", "parameters": "address,uint256"},
            ),
            # Error signature regex
            (
                ERROR_SIGNATURE_REGEX,
                "error InsufficientBalance(uint256 available, uint256 required)",
                {
                    "name": "InsufficientBalance",
                    "parameters": "uint256 available, uint256 required",
                },
            ),
            # Constructor signature regex
            (
                CONSTRUCTOR_SIGNATURE_REGEX,
                "constructor(address,uint256)",
                {"parameters": "address,uint256"},
            ),
            (
                CONSTRUCTOR_SIGNATURE_REGEX,
                "constructor(address) payable",
                {"parameters": "address", "stateMutability": "payable"},
            ),
            # Fallback signature regex
            (
                FALLBACK_SIGNATURE_REGEX,
                "fallback() external",
                {},
            ),
            (
                FALLBACK_SIGNATURE_REGEX,
                "fallback() external payable",
                {"stateMutability": "payable"},
            ),
            # Receive signature regex
            (
                RECEIVE_SIGNATURE_REGEX,
                "receive() external payable",
                {},
            ),
        ],
    )
    def test_regex_patterns(self, pattern, signature, expected_groups):
        """Test regex patterns for signature matching."""
        match = pattern.match(signature)
        assert match is not None

        for group_name, expected_value in expected_groups.items():
            assert match.group(group_name) == expected_value


class TestParseSignature:
    """Test generic signature parsing."""

    @pytest.mark.parametrize(
        "signature, expected",
        [
            # Function signature
            (
                "function transfer(address to, uint256 amount)",
                {
                    "type": "function",
                    "name": "transfer",
                    "stateMutability": "nonpayable",
                    "inputs": [
                        {"type": "address", "name": "to"},
                        {"type": "uint256", "name": "amount"},
                    ],
                    "outputs": [],
                },
            ),
            # Event signature
            (
                "event Transfer(address indexed from, address indexed to, "
                "uint256 value)",
                {
                    "type": "event",
                    "name": "Transfer",
                    "inputs": [
                        {"type": "address", "name": "from", "indexed": True},
                        {"type": "address", "name": "to", "indexed": True},
                        {"type": "uint256", "name": "value"},
                    ],
                },
            ),
            # Error signature
            (
                "error InsufficientBalance(uint256 available, uint256 required)",
                {
                    "type": "error",
                    "name": "InsufficientBalance",
                    "inputs": [
                        {"type": "uint256", "name": "available"},
                        {"type": "uint256", "name": "required"},
                    ],
                },
            ),
            # Constructor signature
            (
                "constructor(address owner, uint256 initialSupply)",
                {
                    "type": "constructor",
                    "stateMutability": "nonpayable",
                    "inputs": [
                        {"type": "address", "name": "owner"},
                        {"type": "uint256", "name": "initialSupply"},
                    ],
                },
            ),
            # Fallback signature
            (
                "fallback() external payable",
                {
                    "type": "fallback",
                    "stateMutability": "payable",
                },
            ),
            # Receive signature
            (
                "receive() external payable",
                {
                    "type": "receive",
                    "stateMutability": "payable",
                },
            ),
        ],
    )
    def test_valid_signature_parsing(self, signature, expected):
        """Test valid signature parsing via generic parser."""
        result = parse_signature(signature)
        assert result == expected

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

    @pytest.mark.parametrize(
        "signature, expected_error",
        [
            # Unknown signature type
            ("unknown signature type", "Unknown signature type"),
        ],
    )
    def test_invalid_signature_parsing(self, signature, expected_error):
        """Test invalid signature parsing that raises errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_signature(signature)

    @pytest.mark.parametrize(
        "signature, expected_type, expected_input_type",
        [
            # Signature with malformed parameters
            ("function test(uint256)", "function", "uint256"),
        ],
    )
    def test_malformed_signature_parsing(
        self, signature, expected_type, expected_input_type
    ):
        """Test signature parsing with malformed parameters."""
        result = parse_signature(signature)
        assert result["type"] == expected_type
        assert result["inputs"][0]["type"] == expected_input_type

    def test_parse_signature_with_invalid_struct_reference(self):
        """Test parsing signature with invalid struct reference."""
        structs = {
            "Point": [
                {"type": "uint256", "name": "x"},
                {"type": "uint256", "name": "y"},
            ]
        }
        # This should work fine with valid struct reference
        result = parse_signature("function test(Point p)", structs)
        assert result["type"] == "function"

        # Invalid struct reference would be treated as an unknown type
        # The parser doesn't validate types at this level
        result = parse_signature("function test(InvalidStruct)", structs)
        assert result["type"] == "function"
        assert result["inputs"][0]["type"] == "InvalidStruct"


class TestComplexFunctionSignatures:
    """Test complex function signatures with all ABI types."""

    @pytest.mark.parametrize(
        "signature, expected_name, expected_input_count, expected_output_count",
        [
            # Function with all parameter types
            (
                (
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
                ),
                "complexFunction",
                11,
                2,
            ),
            # Function with memory modifiers
            (
                (
                    "function processData("
                    "string memory name, "
                    "bytes calldata data, "
                    "uint256[] memory numbers"
                    ") returns (string memory result)"
                ),
                "processData",
                3,
                1,
            ),
            # Function with complex returns
            (
                (
                    "function getMultipleValues() returns ("
                    "uint256 total, "
                    "bool success, "
                    "string message, "
                    "address recipient"
                    ")"
                ),
                "getMultipleValues",
                0,
                4,
            ),
        ],
    )
    def test_complex_function_signatures(
        self, signature, expected_name, expected_input_count, expected_output_count
    ):
        """Test complex function signatures with various parameter types."""
        result = parse_function_signature(signature)
        assert result["name"] == expected_name
        assert len(result["inputs"]) == expected_input_count
        assert len(result["outputs"]) == expected_output_count

    @pytest.mark.parametrize(
        "signature, expected_name, expected_inputs, expected_outputs",
        [
            # Function with array of tuples as parameter
            (
                "function processPairs((uint256,address)[] pairs)",
                "processPairs",
                [
                    {
                        "type": "tuple[]",
                        "name": "pairs",
                        "components": [{"type": "uint256"}, {"type": "address"}],
                    }
                ],
                [],
            ),
            # Function with array of tuples as return value
            (
                "function getPairs() returns ((uint256,address)[])",
                "getPairs",
                [],
                [
                    {
                        "type": "tuple[]",
                        "components": [{"type": "uint256"}, {"type": "address"}],
                    }
                ],
            ),
            # Function with multi-dimensional array of tuples
            (
                "function processMatrix((uint256,address)[][] matrix)",
                "processMatrix",
                [
                    {
                        "type": "tuple[][]",
                        "name": "matrix",
                        "components": [{"type": "uint256"}, {"type": "address"}],
                    }
                ],
                [],
            ),
            # Function with fixed-size array of tuples
            (
                "function processFixedPairs((uint256,address)[10] pairs)",
                "processFixedPairs",
                [
                    {
                        "type": "tuple[10]",
                        "name": "pairs",
                        "components": [{"type": "uint256"}, {"type": "address"}],
                    }
                ],
                [],
            ),
        ],
    )
    def test_function_with_array_of_tuples(
        self, signature, expected_name, expected_inputs, expected_outputs
    ):
        """Test function with array of tuple parameters and returns."""
        result = parse_function_signature(signature)
        assert result["name"] == expected_name
        assert result["inputs"] == expected_inputs
        assert result["outputs"] == expected_outputs


class TestIsSolidityType:
    """Test Solidity type validation."""

    @pytest.mark.parametrize(
        "type_str, expected",
        [
            # Basic types
            ("address", True),
            ("bool", True),
            ("string", True),
            ("bytes", True),
            ("function", True),
            # Integer types
            ("uint8", True),
            ("uint256", True),
            ("int8", True),
            ("int256", True),
            ("uint", False),  # Should be uint256
            ("int", False),  # Should be int256
            # Bytes types
            ("bytes1", True),
            ("bytes32", True),
            ("bytes33", False),  # Invalid
            ("bytes0", False),  # Invalid
            # Invalid types
            ("invalid", False),
            ("tuple", False),
            ("struct", False),
        ],
    )
    def test_solidity_type_validation(self, type_str, expected):
        """Test Solidity type validation."""
        assert is_solidity_type(type_str) is expected


class TestIsStructSignature:
    """Test struct signature detection."""

    @pytest.mark.parametrize(
        "signature, expected",
        [
            # Valid struct signatures
            ("struct Point { uint256 x; uint256 y; }", True),
            ("struct User { string name; address addr; }", True),
            ("struct Empty { }", True),
            # Invalid struct signatures
            ("function test()", False),
            ("event Transfer(address)", False),
            ("struct", False),
            ("struct Point", False),
        ],
    )
    def test_struct_signature_detection(self, signature, expected):
        """Test struct signature detection."""
        assert is_struct_signature(signature) is expected


class TestParseStructs:
    """Test struct parsing functionality."""

    @pytest.mark.parametrize(
        "signatures, expected_structs",
        [
            # Basic struct
            (
                ["struct Point { uint256 x; uint256 y; }"],
                {
                    "Point": [
                        {"type": "uint256", "name": "x"},
                        {"type": "uint256", "name": "y"},
                    ]
                },
            ),
            # Struct with various types
            (
                [
                    "struct User { string name; address addr; uint256 balance; "
                    "bool active; }"
                ],
                {
                    "User": [
                        {"type": "string", "name": "name"},
                        {"type": "address", "name": "addr"},
                        {"type": "uint256", "name": "balance"},
                        {"type": "bool", "name": "active"},
                    ]
                },
            ),
            # Multiple structs
            (
                [
                    "struct Point { uint256 x; uint256 y; }",
                    "struct User { string name; address addr; }",
                    "function test()",  # Should be ignored
                ],
                {
                    "Point": [
                        {"type": "uint256", "name": "x"},
                        {"type": "uint256", "name": "y"},
                    ],
                    "User": [
                        {"type": "string", "name": "name"},
                        {"type": "address", "name": "addr"},
                    ],
                },
            ),
            # Struct with arrays
            (
                ["struct Data { uint256[] values; address[10] addresses; }"],
                {
                    "Data": [
                        {"type": "uint256[]", "name": "values"},
                        {"type": "address[10]", "name": "addresses"},
                    ]
                },
            ),
            # Struct with missing field name (parses successfully)
            (
                ["struct Invalid { uint256; }"],
                {"Invalid": [{"type": "uint256"}]},
            ),
        ],
    )
    def test_valid_struct_parsing(self, signatures, expected_structs):
        """Test valid struct parsing cases."""
        structs = parse_structs(signatures)
        assert structs == expected_structs

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

    @pytest.mark.parametrize(
        "signatures, expected_error",
        [
            # Circular reference
            (
                ["struct A { B b; }", "struct B { A a; }"],
                "Circular reference detected",
            ),
            # Invalid struct signature - empty
            (
                ["struct Invalid { }"],
                "Invalid struct signature",
            ),
            # Invalid struct signature - only semicolons
            (
                ["struct Invalid { ; ; }"],
                "Invalid struct signature",
            ),
            # Unknown type
            (
                ["struct Invalid { unknown_type field; }"],
                "Unknown type",
            ),
            # Malformed properties - missing semicolon
            (
                ["struct Invalid { uint256 x uint256 y; }"],
                "Invalid parameter",
            ),
        ],
    )
    def test_invalid_struct_parsing(self, signatures, expected_error):
        """Test invalid struct parsing cases that raise errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_structs(signatures)


class TestParseABI:
    """Test top-level ABI parsing functionality."""

    @pytest.mark.parametrize(
        "signatures, expected_abi_length, expected_types",
        [
            # Basic ABI without structs
            (
                [
                    "function transfer(address to, uint256 amount)",
                    "event Transfer(address indexed from, address indexed to, "
                    "uint256 value)",
                    "error InsufficientBalance(uint256 available, uint256 required)",
                ],
                3,
                {"function", "event", "error"},
            ),
            # Mixed ABI elements
            (
                [
                    "struct User { string name; address addr; }",
                    "function transfer(address to, uint256 amount)",
                    "event Transfer(address indexed from, address indexed to, "
                    "uint256 value)",
                    "error InsufficientBalance(uint256 available, uint256 required)",
                    "constructor(string name, string symbol)",
                    "fallback() external",
                    "receive() external payable",
                ],
                6,  # struct is excluded
                {"function", "event", "error", "constructor", "fallback", "receive"},
            ),
        ],
    )
    def test_valid_abi_parsing(self, signatures, expected_abi_length, expected_types):
        """Test valid ABI parsing cases."""
        abi = parse_abi(signatures)
        assert len(abi) == expected_abi_length
        types = {item["type"] for item in abi}
        assert types == expected_types

    @pytest.mark.parametrize(
        "signatures, expected_error",
        [
            # Empty signatures
            ([], "At least one signature required"),
        ],
    )
    def test_invalid_abi_parsing(self, signatures, expected_error):
        """Test invalid ABI parsing cases that raise errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_abi(signatures)

    @pytest.mark.parametrize(
        "signatures, expected_name, expected_inputs, expected_outputs",
        [
            # ABI with structs
            (
                [
                    "struct Point { uint256 x; uint256 y; }",
                    "function setPoint(Point p)",
                    "function getPoint() returns (Point)",
                    "event PointSet(Point point)",
                ],
                "setPoint",
                [
                    {
                        "type": "tuple",
                        "name": "p",
                        "components": [
                            {"type": "uint256", "name": "x"},
                            {"type": "uint256", "name": "y"},
                        ],
                    }
                ],
                None,
            ),
            # ABI with struct arrays
            (
                [
                    "struct Point { uint256 x; uint256 y; }",
                    "function setPoints(Point[] points)",
                ],
                "setPoints",
                [
                    {
                        "type": "tuple[]",
                        "name": "points",
                        "components": [
                            {"type": "uint256", "name": "x"},
                            {"type": "uint256", "name": "y"},
                        ],
                    }
                ],
                None,
            ),
        ],
    )
    def test_abi_with_structs(
        self, signatures, expected_name, expected_inputs, expected_outputs
    ):
        """Test ABI parsing with struct definitions."""
        abi = parse_abi(signatures)

        # Find the function by name
        func = next(item for item in abi if item.get("name") == expected_name)

        # Check inputs
        if expected_inputs is not None:
            assert func["inputs"] == expected_inputs

        # Check outputs
        if expected_outputs is not None:
            assert func["outputs"] == expected_outputs

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

    @pytest.mark.parametrize(
        "signature, expected_name, expected_properties",
        [
            # Valid struct signatures
            (
                "struct Point { uint256 x; uint256 y; }",
                "Point",
                "uint256 x; uint256 y;",
            ),
            (
                "struct User { string name; address addr; }",
                "User",
                "string name; address addr;",
            ),
        ],
    )
    def test_struct_regex_pattern(self, signature, expected_name, expected_properties):
        """Test struct regex pattern matching."""
        match = STRUCT_SIGNATURE_REGEX.match(signature)
        assert match is not None
        assert match.group("name") == expected_name
        assert match.group("properties").strip() == expected_properties

    @pytest.mark.parametrize(
        "signature",
        [
            # Invalid struct signatures
            "function test()",
            "struct Point",
        ],
    )
    def test_struct_regex_pattern_invalid(self, signature):
        """Test struct regex pattern with invalid signatures."""
        assert STRUCT_SIGNATURE_REGEX.match(signature) is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.parametrize(
        "parameter_str, expected_type, expected_name",
        [
            # Very long name
            ("uint256 " + "a" * 100, "uint256", "a" * 100),
            # Very long type
            ("a" * 100 + " name", "a" * 100, "name"),
            # Special characters in name (valid)
            ("uint256 _name$123", "uint256", "_name$123"),
            # Large array dimensions
            ("uint256[999999999999999999]", "uint256[999999999999999999]", None),
            # Deeply nested arrays
            ("uint256[][][][][][]", "uint256[][][][][][]", None),
            # Newlines in parameter
            ("uint256\namount", "uint256", "amount"),
            # Only modifier
            ("indexed", "indexed", None),
            # Only name
            ("amount", "amount", None),
            # Only type
            ("uint256", "uint256", None),
            # Deep nesting
            ("((((uint256))))", "tuple", None),
            # Mixed nesting
            ("((uint256,address),(bool,string))", "tuple", None),
        ],
    )
    def test_edge_case_parameter_parsing(
        self, parameter_str, expected_type, expected_name
    ):
        """Test edge case parameter parsing."""
        result = parse_abi_parameter(parameter_str)
        assert result["type"] == expected_type
        if expected_name is not None:
            assert result["name"] == expected_name

    @pytest.mark.parametrize(
        "parameter_str, expected_error",
        [
            # Invalid identifier characters
            ("uint256 name-with-dash", "Invalid parameter"),
            # Leading/trailing spaces
            ("  uint256   amount  ", "Invalid parameter"),
            # Tabs
            ("\tuint256\tamount\t", "Invalid parameter"),
            # Empty string
            ("", "Invalid parameter"),
            # Only spaces
            ("   ", "Invalid parameter"),
        ],
    )
    def test_invalid_edge_case_parameter_parsing(self, parameter_str, expected_error):
        """Test invalid edge case parameter parsing that raises errors."""
        with pytest.raises(ValueError, match=expected_error):
            parse_abi_parameter(parameter_str)

    @pytest.mark.parametrize(
        "signatures, expected_structs",
        [
            # Empty struct name
            (["struct  { uint256 x; }"], {}),
            # Invalid struct name
            (["struct 123Invalid { uint256 x; }"], {}),
        ],
    )
    def test_edge_case_struct_parsing(self, signatures, expected_structs):
        """Test edge case struct parsing."""
        result = parse_structs(signatures)
        assert result == expected_structs

    def test_parameter_cache_behavior(self):
        """Test parameter cache behavior with identical parameters."""
        # Clear cache
        from eth_contract.human import parameter_cache

        parameter_cache.clear()

        # Parse same parameter twice with explicit structs to ensure same cache key
        structs = {}
        param1 = parse_abi_parameter("uint256 amount", structs=structs)
        param2 = parse_abi_parameter("uint256 amount", structs=structs)

        # Should be the same object (cached)
        assert param1 is param2

    def test_parameter_cache_with_different_structs(self):
        """Test parameter cache behavior with different struct contexts."""
        from eth_contract.human import parameter_cache

        parameter_cache.clear()

        structs1 = {"Point": [{"type": "uint256", "name": "x"}]}
        structs2 = {"Point": [{"type": "uint256", "name": "y"}]}

        # Same parameter with different structs should be cached separately
        param1 = parse_abi_parameter("Point p", structs=structs1)
        param2 = parse_abi_parameter("Point p", structs=structs2)

        # Should be different objects due to different struct contexts
        assert param1 is not param2
