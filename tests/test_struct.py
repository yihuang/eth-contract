from typing import Annotated

import pytest

from eth_contract.struct import ABIStruct


class Inner(ABIStruct):
    x: Annotated[bool, "bool"]
    y: Annotated[bytes, "bytes32"]


class Transfer(ABIStruct):
    from_addr: Annotated[str, "address"]
    to_addr: Annotated[str, "address"]
    value: Annotated[int, "uint256"]
    memo: Annotated[str, "string"]
    inner: Inner


SAMPLE_TRANSFER = Transfer(
    from_addr="0x1111111111111111111111111111111111111111",
    to_addr="0x2222222222222222222222222222222222222222",
    value=10**18,
    memo="Hello, Ethereum!",
    inner=Inner(x=True, y=b"\x01" * 32),
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


class TestHumanReadableABI:
    def test_inner_human_readable(self):
        result = Inner.human_readable_abi()
        assert result == "struct Inner { bool x; bytes32 y; }"

    def test_transfer_human_readable(self):
        result = Transfer.human_readable_abi()
        assert result == (
            "struct Transfer { "
            "address from_addr; address to_addr; uint256 value; "
            "string memo; Inner inner; "
            "}"
        )


class TestInvalidAnnotation:
    def test_missing_solidity_type_raises(self):
        with pytest.raises(ValueError, match="must use"):

            class Bad(ABIStruct):
                x: int  # type: ignore[assignment]

            Bad._abi_components()

    def test_annotated_missing_string_raises(self):
        with pytest.raises(ValueError, match="second argument must be a Solidity type"):

            class Bad2(ABIStruct):
                x: Annotated[int, 42]  # non-string second arg

            Bad2._abi_components()
