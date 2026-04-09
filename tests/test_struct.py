from typing import Annotated

import pytest

from eth_contract import ABIStruct
from eth_contract.contract import Contract


class Inner(ABIStruct):
    x: Annotated[bool, "bool"]
    y: Annotated[bytes, "bytes32"]


class Transfer(ABIStruct):
    from_addr: Annotated[str, "address"]
    to_addr: Annotated[str, "address"]
    value: Annotated[int, "uint256"]
    memo: Annotated[str, "string"]
    inner: Inner


SAMPLE_TRANSFER = Transfer(  # type: ignore[call-arg]
    from_addr="0x1111111111111111111111111111111111111111",
    to_addr="0x2222222222222222222222222222222222222222",
    value=10**18,
    memo="Hello, Ethereum!",
    inner=Inner(x=True, y=b"\x01" * 32),  # type: ignore[call-arg]
)


class TestABIComponents:
    def test_inner_components(self):
        components = Inner._abi_components()
        assert components == [
            {"name": "x", "type": "bool"},
            {"name": "y", "type": "bytes32"},
        ]

    def test_transfer_components(self):
        components = Transfer._abi_components()
        assert components == [
            {"name": "from_addr", "type": "address"},
            {"name": "to_addr", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "memo", "type": "string"},
            {
                "name": "inner",
                "type": "tuple",
                "components": [
                    {"name": "x", "type": "bool"},
                    {"name": "y", "type": "bytes32"},
                ],
            },
        ]


class TestEncodeDecode:
    def test_inner_roundtrip(self):
        inner = Inner(x=True, y=b"\xab" * 32)
        encoded = inner.encode()
        decoded = Inner.decode(encoded)
        assert decoded == inner

    def test_transfer_roundtrip(self):
        encoded = SAMPLE_TRANSFER.encode()
        decoded = Transfer.decode(encoded)
        assert decoded == SAMPLE_TRANSFER

    def test_encode_returns_bytes(self):
        assert isinstance(SAMPLE_TRANSFER.encode(), bytes)

    def test_encode_has_content(self):
        assert len(SAMPLE_TRANSFER.encode()) > 0

    def test_nested_instance_type_after_decode(self):
        decoded = Transfer.decode(SAMPLE_TRANSFER.encode())
        assert isinstance(decoded.inner, Inner)

    def test_false_bool(self):
        inner = Inner(x=False, y=b"\x00" * 32)
        assert Inner.decode(inner.encode()) == inner

    def test_zero_uint256(self):
        tx = Transfer(
            from_addr="0x0000000000000000000000000000000000000000",
            to_addr="0x0000000000000000000000000000000000000000",
            value=0,
            memo="",
            inner=Inner(x=False, y=b"\x00" * 32),
        )
        assert Transfer.decode(tx.encode()) == tx


# ---------------------------------------------------------------------------
# Integer types
# ---------------------------------------------------------------------------


class AllInts(ABIStruct):
    u8: Annotated[int, "uint8"]
    u16: Annotated[int, "uint16"]
    u32: Annotated[int, "uint32"]
    u64: Annotated[int, "uint64"]
    u128: Annotated[int, "uint128"]
    u256: Annotated[int, "uint256"]
    i8: Annotated[int, "int8"]
    i16: Annotated[int, "int16"]
    i128: Annotated[int, "int128"]
    i256: Annotated[int, "int256"]


class TestIntegerTypes:
    def test_unsigned_max_values(self):
        inst = AllInts(
            u8=255,
            u16=65535,
            u32=2**32 - 1,
            u64=2**64 - 1,
            u128=2**128 - 1,
            u256=2**256 - 1,
            i8=127,
            i16=32767,
            i128=2**127 - 1,
            i256=2**255 - 1,
        )
        assert AllInts.decode(inst.encode()) == inst

    def test_signed_negative_values(self):
        inst = AllInts(
            u8=0,
            u16=0,
            u32=0,
            u64=0,
            u128=0,
            u256=0,
            i8=-128,
            i16=-32768,
            i128=-(2**127),
            i256=-(2**255),
        )
        assert AllInts.decode(inst.encode()) == inst

    def test_integer_components(self):
        components = AllInts._abi_components()
        types = [c["type"] for c in components]
        assert types == [
            "uint8",
            "uint16",
            "uint32",
            "uint64",
            "uint128",
            "uint256",
            "int8",
            "int16",
            "int128",
            "int256",
        ]


# ---------------------------------------------------------------------------
# Bytes types
# ---------------------------------------------------------------------------


class ByteTypes(ABIStruct):
    b1: Annotated[bytes, "bytes1"]
    b16: Annotated[bytes, "bytes16"]
    b32: Annotated[bytes, "bytes32"]
    dyn_bytes: Annotated[bytes, "bytes"]


class TestBytesTypes:
    def test_bytes_roundtrip(self):
        inst = ByteTypes(
            b1=b"\xff",
            b16=b"\xaa" * 16,
            b32=b"\xbb" * 32,
            dyn_bytes=b"\xde\xad\xbe\xef",
        )
        assert ByteTypes.decode(inst.encode()) == inst

    def test_empty_dynamic_bytes(self):
        inst = ByteTypes(
            b1=b"\x00",
            b16=b"\x00" * 16,
            b32=b"\x00" * 32,
            dyn_bytes=b"",
        )
        assert ByteTypes.decode(inst.encode()) == inst

    def test_bytes_components(self):
        components = ByteTypes._abi_components()
        types = [c["type"] for c in components]
        assert types == ["bytes1", "bytes16", "bytes32", "bytes"]


# ---------------------------------------------------------------------------
# Fixed-size arrays
# ---------------------------------------------------------------------------


class FixedArrayStruct(ABIStruct):
    uint_arr: Annotated[tuple, "uint256[3]"]
    addr_arr: Annotated[tuple, "address[2]"]
    bytes32_arr: Annotated[tuple, "bytes32[2]"]
    bool_arr: Annotated[tuple, "bool[4]"]


class TestFixedSizeArrays:
    def test_fixed_array_roundtrip(self):
        inst = FixedArrayStruct(
            uint_arr=(1, 2, 3),
            addr_arr=(
                "0x0000000000000000000000000000000000000001",
                "0x0000000000000000000000000000000000000002",
            ),
            bytes32_arr=(b"\xaa" * 32, b"\xbb" * 32),
            bool_arr=(True, False, True, False),
        )
        assert FixedArrayStruct.decode(inst.encode()) == inst

    def test_fixed_array_components(self):
        components = FixedArrayStruct._abi_components()
        types = [c["type"] for c in components]
        assert types == ["uint256[3]", "address[2]", "bytes32[2]", "bool[4]"]

    def test_fixed_array_human_readable(self):
        result = FixedArrayStruct.human_readable_abi()
        assert len(result) == 1
        assert "uint256[3] uint_arr" in result[0]
        assert "address[2] addr_arr" in result[0]
        assert "bytes32[2] bytes32_arr" in result[0]
        assert "bool[4] bool_arr" in result[0]


# ---------------------------------------------------------------------------
# Dynamic arrays
# ---------------------------------------------------------------------------


class DynArrayStruct(ABIStruct):
    uint_list: Annotated[tuple, "uint256[]"]
    str_list: Annotated[tuple, "string[]"]
    bytes_list: Annotated[tuple, "bytes[]"]
    addr_list: Annotated[tuple, "address[]"]


class TestDynamicArrays:
    def test_dynamic_array_roundtrip(self):
        inst = DynArrayStruct(
            uint_list=(10, 20, 30),
            str_list=("foo", "bar", "baz"),
            bytes_list=(b"\x01\x02", b"\x03"),
            addr_list=(
                "0x0000000000000000000000000000000000000001",
                "0x0000000000000000000000000000000000000002",
                "0x0000000000000000000000000000000000000003",
            ),
        )
        assert DynArrayStruct.decode(inst.encode()) == inst

    def test_empty_dynamic_array(self):
        inst = DynArrayStruct(
            uint_list=(),
            str_list=(),
            bytes_list=(),
            addr_list=(),
        )
        assert DynArrayStruct.decode(inst.encode()) == inst

    def test_single_element_dynamic_array(self):
        inst = DynArrayStruct(
            uint_list=(42,),
            str_list=("only",),
            bytes_list=(b"\xff",),
            addr_list=("0x0000000000000000000000000000000000000001",),
        )
        assert DynArrayStruct.decode(inst.encode()) == inst

    def test_dynamic_array_components(self):
        components = DynArrayStruct._abi_components()
        types = [c["type"] for c in components]
        assert types == ["uint256[]", "string[]", "bytes[]", "address[]"]

    def test_dynamic_array_human_readable(self):
        result = DynArrayStruct.human_readable_abi()
        assert len(result) == 1
        assert "uint256[] uint_list" in result[0]
        assert "string[] str_list" in result[0]
        assert "bytes[] bytes_list" in result[0]
        assert "address[] addr_list" in result[0]


# ---------------------------------------------------------------------------
# Multi-dimensional arrays
# ---------------------------------------------------------------------------


class MultiDimStruct(ABIStruct):
    matrix: Annotated[tuple, "uint256[][]"]
    grid: Annotated[tuple, "uint8[2][3]"]


class TestMultiDimArrays:
    def test_dynamic_matrix_roundtrip(self):
        inst = MultiDimStruct(
            matrix=((1, 2), (3, 4, 5), (6,)),
            grid=((1, 2), (3, 4), (5, 6)),
        )
        assert MultiDimStruct.decode(inst.encode()) == inst

    def test_multi_dim_components(self):
        components = MultiDimStruct._abi_components()
        types = [c["type"] for c in components]
        assert types == ["uint256[][]", "uint8[2][3]"]

    def test_multi_dim_human_readable(self):
        result = MultiDimStruct.human_readable_abi()
        assert len(result) == 1
        assert "uint256[][] matrix" in result[0]
        assert "uint8[2][3] grid" in result[0]


# ---------------------------------------------------------------------------
# Human-readable ABI
# ---------------------------------------------------------------------------


class TestHumanReadableABI:
    def test_inner_human_readable(self):
        result = Inner.human_readable_abi()
        assert result == ["struct Inner { bool x; bytes32 y; }"]

    def test_transfer_human_readable(self):
        result = Transfer.human_readable_abi()
        assert result == [
            "struct Inner { bool x; bytes32 y; }",
            "struct Transfer { "
            "address from_addr; address to_addr; uint256 value; "
            "string memo; Inner inner; "
            "}",
        ]

    def test_mixed_types_human_readable(self):
        class Misc(ABIStruct):
            n: Annotated[int, "uint8"]
            flag: Annotated[bool, "bool"]
            data: Annotated[bytes, "bytes"]
            vals: Annotated[tuple, "int256[3]"]
            items: Annotated[tuple, "address[]"]

        result = Misc.human_readable_abi()
        assert result == [
            "struct Misc { uint8 n; bool flag; bytes data; "
            "int256[3] vals; address[] items; }"
        ]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestInvalidAnnotation:
    def test_missing_solidity_type_raises(self):
        with pytest.raises(ValueError, match="must use"):

            class Bad(ABIStruct):
                x: float  # type: ignore[annotation-unchecked]

    def test_annotated_missing_string_raises(self):
        with pytest.raises(ValueError, match="second argument must be a Solidity type"):

            class Bad2(ABIStruct):
                x: Annotated[int, 42]  # non-string second arg

    def test_nested_list_of_struct_raises(self):
        """list[list[SomeStruct]] is not supported and must raise ValueError."""

        class Leaf(ABIStruct):
            v: int

        with pytest.raises(ValueError, match="multi-dimensional arrays of structs"):

            class Bad3(ABIStruct):
                nested: list[list[Leaf]]  # type: ignore[misc]

    def test_annotated_list_wrong_struct_name_raises(self):
        """Annotated[list[S], 'Other[3]'] must raise if prefix doesn't match."""

        class S(ABIStruct):
            v: int

        with pytest.raises(ValueError, match="must start with"):

            class Bad4(ABIStruct):
                items: Annotated[list[S], "Other[3]"]  # wrong struct name

    def test_annotated_list_invalid_suffix_raises(self):
        """Annotated[list[S], 'S[abc]'] must raise for non-numeric size."""

        class S2(ABIStruct):
            v: int

        with pytest.raises(ValueError, match="must be"):

            class Bad5(ABIStruct):
                items: Annotated[list[S2], "S2[abc]"]  # non-numeric suffix


class TestMetaclassSafeguards:
    def test_non_abistruct_base_raises(self):
        with pytest.raises(TypeError, match="cannot mix non-ABIStruct bases"):

            class Mixin:
                pass

            class Bad(ABIStruct, Mixin):  # type: ignore[misc]
                x: Annotated[int, "uint256"]

    def test_field_redefinition_raises(self):
        class Parent(ABIStruct):
            x: Annotated[int, "uint256"]

        with pytest.raises(TypeError, match="redefines inherited"):

            class Child(Parent):  # type: ignore[misc]
                x: Annotated[int, "uint256"]  # redefines 'x'

    def test_concrete_subclass_can_add_fields(self):
        class Base(ABIStruct):
            x: Annotated[int, "uint256"]
            y: Annotated[bool, "bool"]

        class Extended(Base):
            z: Annotated[int, "int128"]

        assert Extended._fields == ("x", "y", "z")
        inst = Extended(x=1, y=True, z=-42)
        decoded = Extended.decode(inst.encode())
        assert decoded == inst
        assert decoded.x == 1
        assert decoded.y is True
        assert decoded.z == -42
        assert Extended.human_readable_abi() == [
            "struct Extended { uint256 x; bool y; int128 z; }"
        ]

    def test_subclass_without_fields_inherits_parent(self):
        class Base(ABIStruct):
            val: Annotated[int, "uint256"]
            flag: Annotated[bool, "bool"]

        # Subclassing without adding fields is valid (e.g., for re-export /
        # specialisation without changing the struct layout).
        class Alias(Base):
            pass

        assert Alias._fields == ("val", "flag")
        inst = Alias(val=99, flag=True)
        decoded = Alias.decode(inst.encode())
        assert decoded == inst
        assert decoded.val == 99
        assert decoded.flag is True
        assert Alias.human_readable_abi() == [
            "struct Alias { uint256 val; bool flag; }"
        ]


class TestContractFromABI:
    """Test that human_readable_abi() output integrates with Contract.from_abi()."""

    def test_flat_struct_with_function(self):
        """Struct definitions from human_readable_abi() resolve correctly
        when combined with a function signature and passed to Contract.from_abi().
        """

        class Point(ABIStruct):
            x: Annotated[int, "uint256"]
            y: Annotated[int, "uint256"]

        signatures = Point.human_readable_abi() + [
            "function setPoint(Point p)",
            "function getPoint() returns (Point)",
        ]
        contract = Contract.from_abi(signatures)

        fn_set = contract.fns.setPoint.abi
        assert fn_set["inputs"] == [
            {
                "type": "tuple",
                "name": "p",
                "internalType": "struct Point",
                "components": [
                    {"type": "uint256", "name": "x"},
                    {"type": "uint256", "name": "y"},
                ],
            }
        ]

        fn_get = contract.fns.getPoint.abi
        assert fn_get["outputs"] == [
            {
                "type": "tuple",
                "internalType": "struct Point",
                "components": [
                    {"type": "uint256", "name": "x"},
                    {"type": "uint256", "name": "y"},
                ],
            }
        ]

    def test_nested_struct_with_function(self):
        """Nested struct definitions (Inner before outer) from human_readable_abi()
        resolve correctly when combined with a function signature.
        """

        class Coord(ABIStruct):
            lat: Annotated[int, "int256"]
            lon: Annotated[int, "int256"]

        class Route(ABIStruct):
            origin: Coord
            destination: Coord
            distance: Annotated[int, "uint256"]

        # human_readable_abi() returns nested structs first (Coord, then Route)
        signatures = Route.human_readable_abi() + [
            "function submitRoute(Route r)",
        ]
        contract = Contract.from_abi(signatures)

        fn = contract.fns.submitRoute.abi
        coord_components = [
            {"type": "int256", "name": "lat"},
            {"type": "int256", "name": "lon"},
        ]
        assert fn["inputs"] == [
            {
                "type": "tuple",
                "name": "r",
                "internalType": "struct Route",
                "components": [
                    {
                        "type": "tuple",
                        "name": "origin",
                        "internalType": "struct Coord",
                        "components": coord_components,
                    },
                    {
                        "type": "tuple",
                        "name": "destination",
                        "internalType": "struct Coord",
                        "components": coord_components,
                    },
                    {"type": "uint256", "name": "distance"},
                ],
            }
        ]


# ---------------------------------------------------------------------------
# Default type mappings (bool, int, str, bytes)
# ---------------------------------------------------------------------------


class DefaultMappings(ABIStruct):
    flag: bool
    amount: int
    label: str
    data: bytes


class TestDefaultTypeMappings:
    def test_components(self):
        components = DefaultMappings._abi_components()
        assert components == [
            {"name": "flag", "type": "bool"},
            {"name": "amount", "type": "uint256"},
            {"name": "label", "type": "string"},
            {"name": "data", "type": "bytes"},
        ]

    def test_roundtrip(self):
        inst = DefaultMappings(
            flag=True,
            amount=10**18,
            label="hello",
            data=b"\xde\xad",
        )
        assert DefaultMappings.decode(inst.encode()) == inst

    def test_human_readable(self):
        result = DefaultMappings.human_readable_abi()
        assert len(result) == 1
        assert "bool flag" in result[0]
        assert "uint256 amount" in result[0]
        assert "string label" in result[0]
        assert "bytes data" in result[0]

    def test_list_of_primitive(self):
        class PrimLists(ABIStruct):
            flags: list[bool]
            amounts: list[int]

        components = PrimLists._abi_components()
        assert components == [
            {"name": "flags", "type": "bool[]"},
            {"name": "amounts", "type": "uint256[]"},
        ]
        inst = PrimLists(flags=(True, False, True), amounts=(1, 2, 3))
        assert PrimLists.decode(inst.encode()) == inst


# ---------------------------------------------------------------------------
# Nested structs in containers
# ---------------------------------------------------------------------------


class ItemStruct(ABIStruct):
    id: Annotated[int, "uint256"]
    value: Annotated[int, "uint128"]


class ContainerStruct(ABIStruct):
    items: list[ItemStruct]
    fixed_items: Annotated[list[ItemStruct], "ItemStruct[2]"]
    name: Annotated[str, "string"]


class TestNestedStructInContainer:
    def test_components_dynamic_array(self):
        """list[SomeStruct] produces a tuple[] component."""
        comp = ContainerStruct._abi_components()
        items_comp = next(c for c in comp if c["name"] == "items")
        assert items_comp["type"] == "tuple[]"
        assert items_comp["components"] == ItemStruct._abi_components_cache

    def test_components_fixed_array(self):
        """Annotated[list[SomeStruct], 'SomeStruct[N]'] produces tuple[N]."""
        comp = ContainerStruct._abi_components()
        fixed_comp = next(c for c in comp if c["name"] == "fixed_items")
        assert fixed_comp["type"] == "tuple[2]"
        assert fixed_comp["components"] == ItemStruct._abi_components_cache

    def test_dynamic_array_roundtrip(self):
        items = (
            ItemStruct(id=1, value=100),
            ItemStruct(id=2, value=200),
            ItemStruct(id=3, value=300),
        )
        inst = ContainerStruct(
            items=items,
            fixed_items=(ItemStruct(id=10, value=10), ItemStruct(id=20, value=20)),
            name="test",
        )
        decoded = ContainerStruct.decode(inst.encode())
        assert decoded == inst

    def test_empty_dynamic_array(self):
        inst = ContainerStruct(
            items=(),
            fixed_items=(ItemStruct(id=0, value=0), ItemStruct(id=1, value=1)),
            name="",
        )
        decoded = ContainerStruct.decode(inst.encode())
        assert decoded == inst

    def test_inner_struct_type_after_decode(self):
        items = (ItemStruct(id=7, value=77),)
        inst = ContainerStruct(
            items=items,
            fixed_items=(ItemStruct(id=1, value=1), ItemStruct(id=2, value=2)),
            name="typed",
        )
        decoded = ContainerStruct.decode(inst.encode())
        assert isinstance(decoded.items[0], ItemStruct)
        assert isinstance(decoded.fixed_items[0], ItemStruct)

    def test_dynamic_array_standalone(self):
        """A struct with only a list[Inner] field."""

        class Wrapper(ABIStruct):
            inners: list[ItemStruct]

        inst = Wrapper(
            inners=(
                ItemStruct(id=1, value=11),
                ItemStruct(id=2, value=22),
            )
        )
        decoded = Wrapper.decode(inst.encode())
        assert decoded == inst
        assert all(isinstance(e, ItemStruct) for e in decoded.inners)

    def test_human_readable_abi_dynamic_array(self):
        """list[Inner] → 'Inner[] fieldname' in the struct definition."""
        result = ContainerStruct.human_readable_abi()
        # ItemStruct definition must come first
        assert result[0] == "struct ItemStruct { uint256 id; uint128 value; }"
        assert "ItemStruct[] items" in result[1]

    def test_human_readable_abi_fixed_array(self):
        """Annotated[list[Inner], 'Inner[2]'] → 'Inner[2] fieldname'."""
        result = ContainerStruct.human_readable_abi()
        assert "ItemStruct[2] fixed_items" in result[1]

    def test_type_str_dynamic_array(self):
        """list[ItemStruct] encodes as (uint256,uint128)[] in ABI type string."""
        from eth_contract.struct import _component_type_str

        comp = ContainerStruct._abi_components()
        items_comp = next(c for c in comp if c["name"] == "items")
        assert _component_type_str(items_comp) == "(uint256,uint128)[]"

    def test_type_str_fixed_array(self):
        """Annotated[list[ItemStruct], 'ItemStruct[2]'] → (uint256,uint128)[2]."""
        from eth_contract.struct import _component_type_str

        comp = ContainerStruct._abi_components()
        fixed_comp = next(c for c in comp if c["name"] == "fixed_items")
        assert _component_type_str(fixed_comp) == "(uint256,uint128)[2]"
