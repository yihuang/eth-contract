from typing import Annotated

import pytest

from eth_contract import ABIStruct


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
                x: int  # type: ignore[annotation-unchecked]

    def test_annotated_missing_string_raises(self):
        with pytest.raises(ValueError, match="second argument must be a Solidity type"):

            class Bad2(ABIStruct):
                x: Annotated[int, 42]  # non-string second arg


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
