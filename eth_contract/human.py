import re
from typing import cast

from eth_typing import (
    ABI,
    ABIComponentIndexed,
    ABIConstructor,
    ABIElement,
    ABIError,
    ABIEvent,
    ABIFallback,
    ABIFunction,
    ABIReceive,
)

IDENTIFIER = r"[a-zA-Z$_][a-zA-Z0-9$_]*"
ARRAY = r"( \[ \d* \] )+"
SIGNATURE_PREFIX = re.compile(r"^(function|event|error|constructor|fallback|receive)")

# Signature regexes adapted from:
# https://github.com/wevm/abitype/tree/main/packages/abitype/src/human-readable
ERROR_SIGNATURE_REGEX = re.compile(
    rf"""^error\s+      # 'error' keyword
(?P<name>{IDENTIFIER})  # name
\(
  (?P<parameters>.*?)   # inputs
\)
$""",
    re.VERBOSE,
)

EVENT_SIGNATURE_REGEX = re.compile(
    rf"""^event\s+      # 'event' keyword
(?P<name>{IDENTIFIER})  # name
\(
    (?P<parameters>.*?) # inputs
\)
$""",
    re.VERBOSE,
)

FUNCTION_SIGNATURE_REGEX = re.compile(
    rf"""^function\s+   # 'function' keyword
(?P<name>{IDENTIFIER})  # name
\(
  (?P<parameters>.*?)   # inputs
\)
(\s* (?P<scope>external|public) )?
(\s+ (?P<stateMutability>pure|view|nonpayable|payable) )?
(\s+ returns \s* \(
    (?P<returns>.*?)    # outputs
\) )?
$""",
    re.VERBOSE,
)

CONSTRUCTOR_SIGNATURE_REGEX = re.compile(
    r"""^constructor    # 'constructor' keyword
\(
    (?P<parameters>.*?) # inputs
\)
(\s*
    (?P<stateMutability>payable)
)?
$""",
    re.VERBOSE,
)

FALLBACK_SIGNATURE_REGEX = re.compile(
    r"""^fallback \(\) \s+ external
(\s+
    (?P<stateMutability>payable)
)?
$""",
    re.VERBOSE,
)

RECEIVE_SIGNATURE_REGEX = re.compile(r"^receive\(\)\s+external\s+payable$")

# Parameter regexes
ABI_PARAMETER_WITHOUT_TUPLE_REGEX = re.compile(
    rf"""^
(?P<type>{IDENTIFIER} (\s+payable)?)
(?P<array>{ARRAY})?
(\s+ (?P<modifier>calldata|indexed|memory|storage) )?
(\s+ (?P<name>{IDENTIFIER}) )?
$""",
    re.VERBOSE,
)
ABI_PARAMETER_WITH_TUPLE_REGEX = re.compile(
    rf"""^
\( (?P<type>.+?) \)
(?P<array>{ARRAY})?
(\s+ (?P<modifier>calldata|indexed|memory|storage) )?
(\s+ (?P<name>{IDENTIFIER}) )?
$""",
    re.VERBOSE,
)

DYNAMIC_INTEGER_REGEX = re.compile(r"^u?int$")
IS_TUPLE_REGEX = re.compile(r"^\(.+?\).*?$")

TYPE_WITHOUT_TUPLE_REGEX = re.compile(
    rf"""^
(?P<type>{IDENTIFIER})
(?P<array>{ARRAY})?
$""",
    re.VERBOSE,
)

INTEGER_REGEX = re.compile(
    r"^u?int(8|16|24|32|40|48|56|64|72|80|88|96|104|112|120|128|136|144|152|160|168"
    r"|176|184|192|200|208|216|224|232|240|248|256)$"
)
BYTES_REGEX = re.compile(r"^bytes([1-9]|[12][0-9]|3[0-2])$")

# Modifier sets
EVENT_MODIFIERS = {"indexed"}
FUNCTION_MODIFIERS = {"calldata", "memory", "storage"}
ALL_MODIFIERS = {"indexed", "calldata", "memory", "storage"}

# Parameter cache
parameter_cache: dict[str, ABIComponentIndexed] = {}

# struct signature regex
STRUCT_SIGNATURE_REGEX = re.compile(
    r"^struct (?P<name>[a-zA-Z$_][a-zA-Z0-9$_]*)\s*\{\s*(?P<properties>.*)\s*\}$"
)


def is_struct_signature(signature: str) -> bool:
    """Check if signature is a struct definition."""
    return STRUCT_SIGNATURE_REGEX.match(signature) is not None


def parse_structs(signatures: list[str]) -> dict[str, list[ABIComponentIndexed]]:
    """
    Parse struct definitions from a list of signatures.
    Returns a StructLookup mapping struct names to their components.
    """
    # First pass: create shallow structs (without resolving nested struct references)
    shallow_structs: dict[str, list[ABIComponentIndexed]] = {}

    for signature in signatures:
        match = STRUCT_SIGNATURE_REGEX.match(signature)
        if not match:
            continue

        groups = match.groupdict()
        name = groups["name"]
        properties = groups["properties"].split(";")

        components = []
        for prop in properties:
            trimmed = prop.strip()
            if not trimmed:
                continue

            # Parse each property as a parameter with type='struct' to skip validation
            abi_param = parse_abi_parameter(trimmed, abi_type="struct")
            components.append(abi_param)

        if not components:
            raise ValueError(f"Invalid struct signature (no properties): {signature}")

        shallow_structs[name] = components

    # Second pass: resolve nested struct references
    resolved_structs: dict[str, list[ABIComponentIndexed]] = {}
    for name, parameters in shallow_structs.items():
        resolved_structs[name] = _resolve_struct_components(
            parameters, shallow_structs, set()
        )

    return resolved_structs


def _resolve_struct_components(
    parameters: list[ABIComponentIndexed],
    structs: dict[str, list[ABIComponentIndexed]],
    ancestors: set[str],
) -> list[ABIComponentIndexed]:
    """
    Recursively resolve struct references in parameter components.
    Detects circular references.
    """
    components = []
    for param in parameters:
        param_type = param["type"]

        # If already a tuple, keep it as-is
        if param_type.startswith("tuple"):
            components.append(param)
            continue

        # Try to match type and array suffix
        match = TYPE_WITHOUT_TUPLE_REGEX.match(param_type)
        if not match:
            raise ValueError(f"Invalid ABI type parameter: {param}")

        groups = match.groupdict()
        base_type = groups["type"]
        array_suffix = groups.get("array") or ""

        # Check if this is a struct reference
        if base_type in structs:
            # Detect circular references
            if base_type in ancestors:
                raise ValueError(f"Circular reference detected: {base_type}")

            # Recursively resolve nested structs
            resolved_components = _resolve_struct_components(
                structs[base_type], structs, ancestors | {base_type}
            )

            components.append(
                {
                    **param,
                    "type": f"tuple{array_suffix}",
                    "components": resolved_components,
                }
            )
        else:
            # Not a struct, validate it's a valid Solidity type
            if not is_solidity_type(base_type):
                raise ValueError(f"Unknown type: {base_type}")
            components.append(param)

    return components


def is_solidity_type(type_name: str) -> bool:
    """Check if a type is a valid Solidity primitive type."""
    # Basic types
    if type_name in ["address", "bool", "string", "bytes", "function"]:
        return True

    # Fixed-size bytes (bytes1 to bytes32)
    if BYTES_REGEX.match(type_name):
        return True

    # Integers (int8 to int256, uint8 to uint256, in steps of 8)
    if INTEGER_REGEX.match(type_name):
        return True

    return False


def split_parameters(
    params: str, result: list[str] | None = None, current: str = "", depth: int = 0
) -> list[str]:
    """Recursively split comma-separated parameters respecting parentheses."""
    if result is None:
        result = []

    # Trim only at the start, not on every recursion
    length = len(params.strip())

    # Base case: end of string
    for i in range(length):
        char = params[i]
        tail = params[i + 1 :]

        if char == ",":
            if depth == 0:
                return split_parameters(tail, [*result, current.strip()], "", depth)
            else:
                return split_parameters(tail, result, f"{current}{char}", depth)
        elif char == "(":
            return split_parameters(tail, result, f"{current}{char}", depth + 1)
        elif char == ")":
            return split_parameters(tail, result, f"{current}{char}", depth - 1)
        else:
            return split_parameters(tail, result, f"{current}{char}", depth)

    # End of iteration
    if current == "":
        return result
    if depth != 0:
        raise ValueError(f"Invalid parenthesis: depth={depth}, current={current}")

    result.append(current.strip())
    return result


def is_tuple(s):
    return s and s[0] == "(" and ")" in s


def parse_abi_parameter(
    param: str,
    modifiers: set[str] | None = None,
    structs: dict[str, list[ABIComponentIndexed]] | None = None,
    abi_type: str | None = None,
) -> ABIComponentIndexed:
    """Parse a single ABI parameter string into a structured object."""
    if structs is None:
        structs = {}

    # Check cache
    cache_key = f"{param}:{abi_type}:{id(structs)}"
    if cache_key in parameter_cache:
        return parameter_cache[cache_key]

    tuple_param = is_tuple(param)
    regex = (
        ABI_PARAMETER_WITH_TUPLE_REGEX
        if tuple_param
        else ABI_PARAMETER_WITHOUT_TUPLE_REGEX
    )
    match = regex.match(param)

    if not match:
        raise ValueError(f"Invalid parameter: {param}")

    groups = match.groupdict()
    name = groups.get("name")
    modifier = groups.get("modifier")
    array = groups.get("array") or ""

    # Build result
    result = {}

    if name:
        result["name"] = name

    if modifier == "indexed":
        result["indexed"] = True

    # Determine type
    if tuple_param:
        result["type"] = "tuple"
        params = split_parameters(groups["type"])
        result["components"] = [parse_abi_parameter(p, structs=structs) for p in params]
    elif groups["type"] in structs:
        result["type"] = "tuple"
        result["components"] = structs[groups["type"]]
    elif DYNAMIC_INTEGER_REGEX.match(groups["type"]):
        result["type"] = f"{groups['type']}256"
    elif groups["type"] == "address payable":
        result["type"] = "address"
    else:
        result["type"] = groups["type"]

    # Add array suffix
    result["type"] = result["type"] + array

    # Validate modifier
    if modifier and modifiers and modifier not in modifiers:
        raise ValueError(f"Invalid modifier '{modifier}' for type {abi_type}")

    comp = cast(ABIComponentIndexed, result)
    parameter_cache[cache_key] = comp
    return comp


def parse_function_signature(
    signature: str, structs: dict[str, list[ABIComponentIndexed]] | None = None
) -> ABIFunction:
    """Parse a function signature."""
    match = FUNCTION_SIGNATURE_REGEX.match(signature)
    if not match:
        raise ValueError(f"Invalid function signature: {signature}")

    groups = match.groupdict()
    params = split_parameters(groups["parameters"])

    return {
        "type": "function",
        "name": groups["name"],
        "stateMutability": groups.get("stateMutability")  # type: ignore
        or "nonpayable",
        "inputs": [
            parse_abi_parameter(p, FUNCTION_MODIFIERS, structs, "function")
            for p in params
        ],
        "outputs": (
            [
                parse_abi_parameter(p, FUNCTION_MODIFIERS, structs, "function")
                for p in split_parameters(groups.get("returns") or "")
            ]
            if groups.get("returns")
            else []
        ),
    }


def parse_event_signature(
    signature: str, structs: dict[str, list[ABIComponentIndexed]] | None = None
) -> ABIEvent:
    """Parse an event signature."""
    match = EVENT_SIGNATURE_REGEX.match(signature)
    if not match:
        raise ValueError(f"Invalid event signature: {signature}")

    groups = match.groupdict()
    params = split_parameters(groups["parameters"])

    return {
        "type": "event",
        "name": groups["name"],
        "inputs": [
            parse_abi_parameter(p, EVENT_MODIFIERS, structs, "event") for p in params
        ],
    }


def parse_error_signature(
    signature: str, structs: dict[str, list[ABIComponentIndexed]] | None = None
) -> ABIError:
    """Parse an error signature."""
    match = ERROR_SIGNATURE_REGEX.match(signature)
    if not match:
        raise ValueError(f"Invalid error signature: {signature}")

    groups = match.groupdict()
    params = split_parameters(groups["parameters"])

    return {
        "type": "error",
        "name": groups["name"],
        "inputs": [
            parse_abi_parameter(p, structs=structs, abi_type="error") for p in params
        ],
    }


def parse_constructor_signature(
    signature: str, structs: dict[str, list[ABIComponentIndexed]] | None = None
) -> ABIConstructor:
    """Parse a constructor signature."""
    match = CONSTRUCTOR_SIGNATURE_REGEX.match(signature)
    if not match:
        raise ValueError(f"Invalid constructor signature: {signature}")

    groups = match.groupdict()
    params = split_parameters(groups["parameters"])

    return {
        "type": "constructor",
        "stateMutability": groups.get("stateMutability")  # type: ignore
        or "nonpayable",
        "inputs": [
            parse_abi_parameter(p, structs=structs, abi_type="constructor")
            for p in params
        ],
    }


def parse_fallback_signature(signature: str) -> ABIFallback:
    """Parse a fallback signature."""
    match = FALLBACK_SIGNATURE_REGEX.match(signature)
    if not match:
        raise ValueError(f"Invalid fallback signature: {signature}")

    groups = match.groupdict()

    return {
        "type": "fallback",
        "stateMutability": groups.get("stateMutability")  # type: ignore
        or "nonpayable",
    }


def parse_receive_signature(signature: str) -> ABIReceive:
    """Parse a receive signature."""
    match = RECEIVE_SIGNATURE_REGEX.match(signature)
    if not match:
        raise ValueError(f"Invalid receive signature: {signature}")

    return {"type": "receive", "stateMutability": "payable"}


def parse_signature(
    signature: str, structs: dict[str, list[ABIComponentIndexed]] | None = None
) -> ABIElement:
    """
    Parse any ABI signature and return the appropriate ABI item.
    Dispatches to the correct parser based on signature type.
    """
    if structs is None:
        structs = {}

    match = SIGNATURE_PREFIX.match(signature)
    if not match:
        raise ValueError(f"Unknown signature type: {signature}")

    prefix = match.group()
    if prefix == "function":
        return parse_function_signature(signature, structs)
    elif prefix == "event":
        return parse_event_signature(signature, structs)
    elif prefix == "error":
        return parse_error_signature(signature, structs)
    elif prefix == "constructor":
        return parse_constructor_signature(signature, structs)
    elif prefix == "fallback":
        return parse_fallback_signature(signature)
    elif prefix == "receive":
        return parse_receive_signature(signature)
    else:
        raise ValueError(f"Unknown signature type: {prefix}")


def parse_abi(signatures: list[str]) -> ABI:
    """
    Parse a complete human-readable ABI interface into JSON ABI format.

    Args:
        signatures: List of human-readable signatures including functions,
                   events, errors, constructors, fallback, receive, and structs

    Returns:
        List of parsed ABI items (structs are excluded from output)

    Example:
        >>> abi = parse_abi([
        ...     'struct Foo { string name; uint256 value; }',
        ...     'function transfer(Foo foo) external',
        ...     'event Transfer(address indexed from, address indexed to, '
        ...     'uint256 amount)'
        ... ])
    """
    if not signatures:
        raise ValueError("At least one signature required")

    # First pass: extract and parse all struct definitions
    structs = parse_structs(signatures)

    # Second pass: parse all non-struct signatures with struct context
    abi = []
    for signature in signatures:
        # Skip struct definitions - they're only used for type resolution
        if is_struct_signature(signature):
            continue

        # Parse the signature with struct context
        abi_item = parse_signature(signature, structs)
        abi.append(abi_item)

    return abi
