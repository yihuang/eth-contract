"""Tests for decoding contract return/input values as ABIStruct instances.

API::

    CONTRACT = Contract.from_abi(
        ["function test(Point p)", "function getPoint() returns (Point)"],
        structs=[Point],
    )
    # CONTRACT.fns.getPoint.decode(data)  →  Point instance
    # CONTRACT.fns.getPoint.decode_input(data)  →  Point instance
"""

import asyncio
from typing import Annotated, cast

import pytest
from eth_abi import encode as abi_encode
from eth_typing import ABI

import eth_contract.contract
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


class Values(ABIStruct):
    constructorAmount: Annotated[int, "uint256"]
    initCallAmount: Annotated[int, "uint256"]


class NsTest(ABIStruct):
    value: Annotated[int, "uint256"]


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

        raw = abi_encode(["(uint256,string)[]"], [((1, "a"), (2, "b"))])
        result = fn.decode(raw)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(i, Item) for i in result)
        assert result == (Item(id=1, name="a"), Item(id=2, name="b"))

    def test_multi_dimensional_struct_array(self):
        """Struct[][] — multi-dimensional struct array."""
        contract = Contract.from_abi(
            [
                "struct Point { uint256 x; uint256 y; }",
                "function getMatrix() returns (Point[][])",
            ],
            structs=[Point],
        )
        fn = contract.fns.getMatrix

        raw = abi_encode(
            ["(uint256,uint256)[][]"],
            [(((1, 2), (3, 4)), ((5, 6),))],
        )
        result = fn.decode(raw)
        assert isinstance(result, tuple)
        assert len(result) == 2
        # Each outer element is an array of Points
        inner = result[0]
        assert isinstance(inner, tuple)
        assert len(inner) == 2
        assert isinstance(inner[0], Point)
        assert inner[0] == Point(x=1, y=2)
        assert isinstance(inner[1], Point)
        assert inner[1] == Point(x=3, y=4)
        # Second outer element
        inner2 = result[1]
        assert len(inner2) == 1
        assert isinstance(inner2[0], Point)
        assert inner2[0] == Point(x=5, y=6)

    def test_multi_dimensional_fixed_struct_array(self):
        """Struct[2][3] — multi-dimensional fixed-size struct array."""
        contract = Contract.from_abi(
            [
                "struct Point { uint256 x; uint256 y; }",
                "function getGrid() returns (Point[2][3])",
            ],
            structs=[Point],
        )
        fn = contract.fns.getGrid

        raw = abi_encode(
            ["(uint256,uint256)[2][3]"],
            [(((1, 2), (3, 4)), ((5, 6), (7, 8)), ((9, 10), (11, 12)))],
        )
        result = fn.decode(raw)
        # 3 outer rows, each with 2 Points
        assert isinstance(result, tuple)
        assert len(result) == 3
        for row in result:
            assert isinstance(row, tuple)
            assert len(row) == 2
            for pt in row:
                assert isinstance(pt, Point)

    def test_anonymous_tuple_array_with_nested_struct(self):
        """Anonymous tuple[] where each element contains a struct."""
        contract = Contract.from_abi(
            [
                "struct Point { uint256 x; uint256 y; }",
                "function getPoints() returns ((Point,bool)[])",
            ],
            structs=[Point],
        )
        fn = contract.fns.getPoints

        raw = abi_encode(
            ["((uint256,uint256),bool)[]"],
            [(((1, 2), True), ((3, 4), False))],
        )
        result = fn.decode(raw)
        assert isinstance(result, tuple)
        assert len(result) == 2
        # Each element should be a (Point, bool) tuple
        assert isinstance(result[0][0], Point)
        assert result[0][0] == Point(x=1, y=2)
        assert result[0][1] is True
        assert isinstance(result[1][0], Point)
        assert result[1][0] == Point(x=3, y=4)
        assert result[1][1] is False

    def test_multi_dimensional_anonymous_tuple_array(self):
        """(Struct,bool)[][] — multi-dimensional anonymous tuple array."""
        contract = Contract.from_abi(
            [
                "struct Point { uint256 x; uint256 y; }",
                "function getMatrix() returns ((Point,bool)[][])",
            ],
            structs=[Point],
        )
        fn = contract.fns.getMatrix

        raw = abi_encode(
            ["((uint256,uint256),bool)[][]"],
            [((((1, 2), True), ((3, 4), False)), (((5, 6), True),))],
        )
        result = fn.decode(raw)
        # result[0] is the first outer array: ((1,2),True), ((3,4),False)
        inner = result[0]
        assert isinstance(inner, tuple)
        assert len(inner) == 2
        # Each inner element should be a (Point, bool) tuple
        assert isinstance(inner[0][0], Point)
        assert inner[0][0] == Point(x=1, y=2)
        assert inner[0][1] is True
        assert isinstance(inner[1][0], Point)
        assert inner[1][0] == Point(x=3, y=4)
        assert inner[1][1] is False
        # result[1] is the second outer array: ((5,6),True)
        inner2 = result[1]
        assert len(inner2) == 1
        assert isinstance(inner2[0][0], Point)
        assert inner2[0][0] == Point(x=5, y=6)
        assert inner2[0][1] is True

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

        old_codec = eth_contract.contract._abi_codec

        class FakeWeb3:
            class eth:
                @staticmethod
                async def call(transaction, **kw):
                    return data

            codec = old_codec

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

    def test_namespaced_struct_name(self):
        """internalType with dotted name like "struct Domain.Test"."""

        class NsTest(ABIStruct):
            value: Annotated[int, "uint256"]

        # Manually craft ABI with dotted internalType
        abi = [
            {
                "type": "function",
                "name": "getTest",
                "inputs": [],
                "outputs": [
                    {
                        "type": "tuple",
                        "internalType": "struct Domain.Test",
                        "components": [{"type": "uint256", "name": "value"}],
                    }
                ],
            }
        ]
        contract = Contract(abi=cast(ABI, abi), structs={"Domain.Test": NsTest})
        fn = contract.fns.getTest
        instance = NsTest(value=42)
        result = fn.decode(instance.encode())
        assert isinstance(result, NsTest)
        assert result == instance


# ---------------------------------------------------------------------------
# Manual decode (structs= kwarg on decode / decode_input)
# ---------------------------------------------------------------------------


class TestManualDecodeKwarg:
    """
    Pass structs directly to decode()/decode_input() without contract-level structs.
    """

    def test_decode_with_structs_kwarg(self):
        """decode(structs=[...]) works when called manually."""
        contract = Contract.from_abi(
            Point.human_readable_abi() + ["function getPoint() returns (Point)"],
        )
        fn = contract.fns.getPoint
        data = Point(x=10, y=20).encode()
        result = fn.decode(data, structs=[Point])
        assert isinstance(result, Point)
        assert result == Point(x=10, y=20)

    def test_decode_input_with_structs_kwarg(self):
        contract = Contract.from_abi(
            Point.human_readable_abi() + ["function setPoint(Point)"],
        )
        fn = contract.fns.setPoint
        point = Point(x=7, y=8)
        calldata = fn(point).data
        result = fn.decode_input(calldata, structs=[Point])
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
        result = fn.decode(data, structs=[Route, Coord])
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
        result = fn.decode(data, structs=[])
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

        raw = abi_encode(
            ["(uint256,string)", "(uint256,uint256)"], [(1, "a"), (10, 20)]
        )
        result = fn.decode(raw, structs=[Item])
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
        """structs=[] means no conversion at all → plain tuple."""
        contract = Contract.from_abi(
            Point.human_readable_abi() + ["function getPoint() returns (Point)"],
        )
        fn = contract.fns.getPoint
        data = Point(x=1, y=2).encode()
        result = fn.decode(data, structs=[])
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

    def test_empty_structs_overrides_contract_structs(self):
        contract = Contract.from_abi(
            ["function getPoint() returns (Point)", "function setPoint(Point)"],
            structs=[Point],
        )
        set_point = contract.fns.setPoint
        out = contract.fns.getPoint.decode(Point(x=1, y=2).encode(), structs=[])
        inp = set_point.decode_input(set_point(Point(x=3, y=4)).data, structs=[])

        assert type(out) is tuple and type(inp) is tuple  # neither converted
        assert (out, inp) == ((1, 2), (3, 4))


def _namespaced_fn(return_type: str) -> ContractFunction:
    fn = Contract.from_abi(
        [f"function get() returns ({return_type})"], structs=[Values]
    ).fns.get
    cast(dict, fn.abi["outputs"][0])["internalType"] = f"struct CreateX.{return_type}"
    return fn


class TestNamespacedInternalType:
    def test_qualified_struct(self):
        fn = _namespaced_fn("Values")
        raw = abi_encode(["(uint256,uint256)"], [(1, 2)])
        result = fn.decode(raw)
        assert isinstance(result, Values)
        assert result == Values(constructorAmount=1, initCallAmount=2)

    def test_qualified_struct_array(self):
        fn = _namespaced_fn("Values[]")
        raw = abi_encode(["(uint256,uint256)[]"], [[(1, 2), (3, 4)]])
        result = fn.decode(raw)
        assert all(isinstance(v, Values) for v in result)
        assert result == (
            Values(constructorAmount=1, initCallAmount=2),
            Values(constructorAmount=3, initCallAmount=4),
        )

    @pytest.mark.parametrize(
        "structs",
        [
            pytest.param(
                {"Foo.Values": Values, "Bar.Values": Values}, id="multi-qualified"
            ),
            pytest.param(
                {"Values": Values, "Foo.Values": Values}, id="bare-and-qualified"
            ),
            pytest.param({"Foo.Values": Values}, id="qualified-only"),
        ],
    )
    def test_bare_fallback_suppressed(self, structs):
        fn = Contract.from_abi(
            ["function get() returns ((uint256,uint256))"], structs=structs
        ).fns.get
        cast(dict, fn.abi["outputs"][0])["internalType"] = "struct Other.Values"
        assert fn.decode(abi_encode(["(uint256,uint256)"], [(1, 2)])) == (1, 2)
