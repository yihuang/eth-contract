"""Tests for decoding contract return/input values as ABIStruct instances.

API::

    CONTRACT = Contract.from_abi(
        ["function test(Point p)", "function getPoint() returns (Point)"],
        structs=[Point],
    )
    # CONTRACT.fns.getPoint.decode(data)  →  Point instance
    # CONTRACT.fns.getPoint.decode_input(data)  →  Point instance
"""

from typing import Annotated

import pytest

from eth_contract import ABIStruct
from eth_contract.contract import Contract, ContractFunction

# ---------------------------------------------------------------------------
# Test struct definitions
# ---------------------------------------------------------------------------


class Point(ABIStruct):
    x: Annotated[int, "uint256"]
    y: Annotated[int, "uint256"]


class Coord(ABIStruct):
    lat: Annotated[int, "int256"]
    lon: Annotated[int, "int256"]


class Route(ABIStruct):
    origin: Coord
    destination: Coord
    distance: Annotated[int, "uint256"]


class Item(ABIStruct):
    id: Annotated[int, "uint256"]
    name: Annotated[str, "string"]


# ---------------------------------------------------------------------------
# from_abi integration
# ---------------------------------------------------------------------------


class TestFromABI:
    """structs=[...] parameter in Contract.from_abi()."""

    def test_structs_provided_inline(self):
        """Pass structs directly to from_abi. struct definitions are auto-injected."""
        contract = Contract.from_abi(
            ["function getPoint() returns (Point)"],
            structs=[Point],
        )
        fn = contract.fns.getPoint

        # ABI should have proper tuple outputs with internalType
        assert fn.abi["outputs"][0]["internalType"] == "struct Point"
        assert fn.abi["outputs"][0]["type"] == "tuple"
        assert fn.abi["outputs"][0]["components"] == [
            {"name": "x", "type": "uint256"},
            {"name": "y", "type": "uint256"},
        ]

        # Decode returns Point instance
        data = Point(x=1, y=2).encode()
        result = fn.decode(data)
        assert isinstance(result, Point)
        assert result == Point(x=1, y=2)

    def test_nested_structs_inline(self):
        """Nested structs are resolved automatically."""
        contract = Contract.from_abi(
            ["function getRoute() returns (Route)"],
            structs=[Route],  # Route references Coord → auto-included
        )
        fn = contract.fns.getRoute
        route = Route(
            origin=Coord(lat=10, lon=20),
            destination=Coord(lat=30, lon=40),
            distance=100,
        )
        data = route.encode()
        result = fn.decode(data)
        assert isinstance(result, Route)
        assert isinstance(result.origin, Coord)
        assert isinstance(result.destination, Coord)
        assert result == route

    def test_multiple_structs(self):
        """Multiple struct classes in the list work correctly."""
        contract = Contract.from_abi(
            ["function getBoth() returns (Point, Coord)"],
            structs=[Point, Coord],
        )
        fn = contract.fns.getBoth
        from eth_abi import encode as abi_encode

        raw = abi_encode(["(uint256,uint256)", "(int256,int256)"], [(1, 2), (10, 20)])
        result = fn.decode(raw)
        assert isinstance(result, tuple)
        assert isinstance(result[0], Point)
        assert isinstance(result[1], Coord)

    def test_struct_array_output(self):
        """Struct arrays (tuple[], tuple[N]) in outputs."""
        contract = Contract.from_abi(
            ["function getItems() returns (Item[])"],
            structs=[Item],
        )
        fn = contract.fns.getItems
        from eth_abi import encode as abi_encode

        raw = abi_encode(["(uint256,string)[]"], [((1, "a"), (2, "b"))])
        result = fn.decode(raw)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(i, Item) for i in result)
        assert result == (Item(id=1, name="a"), Item(id=2, name="b"))

    def test_decode_input_with_structs(self):
        """decode_input returns ABIStruct for struct arguments."""
        contract = Contract.from_abi(
            ["function setPoint(Point)"],
            structs=[Point],
        )
        fn = contract.fns.setPoint
        point = Point(x=7, y=8)
        calldata = fn(point).data
        result = fn.decode_input(calldata)
        assert isinstance(result, Point)
        assert result == point

    def test_decode_input_mixed_args(self):
        """Struct and primitive arguments together."""
        contract = Contract.from_abi(
            ["function addItem(Item, uint256)"],
            structs=[Item],
        )
        fn = contract.fns.addItem
        item = Item(id=5, name="widget")
        calldata = fn(item, 3).data
        result = fn.decode_input(calldata)
        assert isinstance(result, tuple)
        assert isinstance(result[0], Item)
        assert result[0] == item
        assert result[1] == 3

    def test_preserve_existing_human_readable_pattern(self):
        """The old pattern where user manually includes struct defs still works."""
        contract = Contract.from_abi(
            Point.human_readable_abi() + ["function getPoint() returns (Point)"],
        )
        fn = contract.fns.getPoint
        data = Point(x=1, y=2).encode()
        result = fn.decode(data)
        assert isinstance(result, tuple)  # no struct mapping → plain tuple
        assert result == (1, 2)

    def test_overloaded_function_with_struct(self):
        """Overloaded functions resolve selector and decode struct args."""
        contract = Contract.from_abi(
            [
                "function setPoint(uint256)",
                "function setPoint(Point)",
            ],
            structs=[Point],
        )
        fn = contract.fns.setPoint

        # Primitive overload
        assert fn(42).decode_input(fn(42).data) == 42

        # Struct overload
        point = Point(x=99, y=200)
        result = fn(point).decode_input(fn(point).data)
        assert isinstance(result, Point)
        assert result == point

    def test_call_method_passes_structs(self):
        """call() should also produce ABIStruct instances."""
        contract = Contract.from_abi(
            ["function getPoint() returns (Point)"],
            structs=[Point],
        )
        fn = contract.fns.getPoint
        data = Point(x=5, y=6).encode()

        import eth_contract.contract as cmod

        old_codec = cmod._abi_codec

        class FakeWeb3:
            class eth:
                @staticmethod
                async def call(transaction, **kw):
                    return data

            codec = old_codec

        import asyncio

        result = asyncio.run(fn().call(FakeWeb3()))
        assert isinstance(result, Point)
        assert result == Point(x=5, y=6)

    def test_without_structs_still_works(self):
        """Not passing structs is backward-compatible (plain tuples)."""
        contract = Contract.from_abi(
            ["function getPoint() returns (Point)"],
            structs=[Point],
        )
        fn = contract.fns.getPoint
        data = Point(x=1, y=2).encode()
        result = fn.decode(data)
        assert isinstance(result, Point)

    def test_contract_call_preserves_tx(self):
        """Binding tx params (via __call__) preserves structs."""
        contract = Contract.from_abi(
            ["function getPoint() returns (Point)"],
            structs=[Point],
        )
        contract = contract(to="0x0000000000000000000000000000000000000001")
        fn = contract.fns.getPoint
        data = Point(x=3, y=4).encode()
        result = fn.decode(data)
        assert isinstance(result, Point)
        assert result == Point(x=3, y=4)
        assert contract.tx.get("to") == "0x0000000000000000000000000000000000000001"

    def test_contract_function_from_abi_with_structs(self):
        """ContractFunction.from_abi also accepts structs."""
        fn = ContractFunction.from_abi(
            "function getPoint() returns (Point)",
            structs=[Point],
        )
        assert fn.abi["outputs"][0]["internalType"] == "struct Point"
        assert fn.abi["outputs"][0]["type"] == "tuple"

        data = Point(x=1, y=2).encode()
        result = fn.decode(data)
        assert isinstance(result, Point)
        assert result == Point(x=1, y=2)

    def test_contract_function_from_abi_nested_structs(self):
        """Nested structs via ContractFunction.from_abi."""
        fn = ContractFunction.from_abi(
            "function getRoute() returns (Route)",
            structs=[Route],
        )
        route = Route(
            origin=Coord(lat=10, lon=20),
            destination=Coord(lat=30, lon=40),
            distance=100,
        )
        data = route.encode()
        result = fn.decode(data)
        assert isinstance(result, Route)
        assert isinstance(result.origin, Coord)

    def test_contract_function_from_abi_decode_input(self):
        """ContractFunction.from_abi with structs for decode_input."""
        fn = ContractFunction.from_abi(
            "function setPoint(Point)",
            structs=[Point],
        )
        point = Point(x=7, y=8)
        calldata = fn(point).data
        result = fn.decode_input(calldata)
        assert isinstance(result, Point)
        assert result == point


# ---------------------------------------------------------------------------
# Manual decode (structs= kwarg on decode / decode_input)
# ---------------------------------------------------------------------------


class TestManualDecodeKwarg:
    """Pass structs directly to decode()/decode_input() without contract-level structs."""

    def test_decode_with_structs_kwarg(self):
        """decode(structs={...}) works when called manually."""
        contract = Contract.from_abi(
            Point.human_readable_abi() + ["function getPoint() returns (Point)"],
        )
        fn = contract.fns.getPoint
        data = Point(x=10, y=20).encode()
        result = fn.decode(data, structs={"Point": Point})
        assert isinstance(result, Point)
        assert result == Point(x=10, y=20)

    def test_decode_input_with_structs_kwarg(self):
        contract = Contract.from_abi(
            Point.human_readable_abi() + ["function setPoint(Point)"],
        )
        fn = contract.fns.setPoint
        point = Point(x=7, y=8)
        calldata = fn(point).data
        result = fn.decode_input(calldata, structs={"Point": Point})
        assert isinstance(result, Point)
        assert result == point

    def test_nested_with_structs_kwarg(self):
        contract = Contract.from_abi(
            Route.human_readable_abi() + ["function getRoute() returns (Route)"],
        )
        fn = contract.fns.getRoute
        route = Route(
            origin=Coord(lat=1, lon=2), destination=Coord(lat=3, lon=4), distance=99
        )
        data = route.encode()
        result = fn.decode(data, structs={"Route": Route, "Coord": Coord})
        assert isinstance(result, Route)
        assert isinstance(result.origin, Coord)
        assert isinstance(result.destination, Coord)

    def test_empty_structs_kwarg_returns_tuple(self):
        """Empty structs mapping → plain tuple (unchanged behaviour)."""
        contract = Contract.from_abi(
            Point.human_readable_abi() + ["function getPoint() returns (Point)"],
        )
        fn = contract.fns.getPoint
        data = Point(x=1, y=2).encode()
        result = fn.decode(data, structs={})
        assert isinstance(result, tuple)
        assert result == (1, 2)

    def test_partial_structs_kwarg(self):
        """Only convert the structs we know about, leave others as tuples."""
        contract = Contract.from_abi(
            Item.human_readable_abi()
            + Point.human_readable_abi()
            + ["function getItemAndPoint() returns (Item, Point)"],
        )
        fn = contract.fns.getItemAndPoint
        from eth_abi import encode as abi_encode

        raw = abi_encode(
            ["(uint256,string)", "(uint256,uint256)"], [(1, "a"), (10, 20)]
        )
        result = fn.decode(raw, structs={"Item": Item})
        # Item should be converted, Point remains tuple
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], Item)
        assert result[0] == Item(id=1, name="a")
        assert isinstance(result[1], tuple)
        assert result[1] == (10, 20)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TestErrors:
    def test_empty_structs_skips_conversion(self):
        """structs={} means no conversion at all → plain tuple."""
        contract = Contract.from_abi(
            Point.human_readable_abi() + ["function getPoint() returns (Point)"],
        )
        fn = contract.fns.getPoint
        data = Point(x=1, y=2).encode()
        result = fn.decode(data, structs={})
        assert isinstance(result, tuple)
        assert result == (1, 2)

    def test_decode_without_structs_on_contract_with_structs(self):
        """Contract has structs, but decode(structs=None) still converts."""
        contract = Contract.from_abi(
            ["function getPoint() returns (Point)"],
            structs=[Point],
        )
        fn = contract.fns.getPoint
        data = Point(x=1, y=2).encode()
        result = fn.decode(data)  # uses parent's structs
        assert isinstance(result, Point)

    def test_decode_input_without_structs_falls_back_to_parent(self):
        contract = Contract.from_abi(
            ["function setPoint(Point)"],
            structs=[Point],
        )
        fn = contract.fns.setPoint
        point = Point(x=3, y=4)
        calldata = fn(point).data
        result = fn.decode_input(calldata)  # uses parent's structs
        assert isinstance(result, Point)
