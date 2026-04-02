import collections
import typing
from typing import Any, get_args, get_origin, get_type_hints

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode


def _get_field_abi_type(annotation: Any, field_name: str, class_name: str) -> str:
    """Return the Solidity ABI type string for a single field annotation."""
    origin = get_origin(annotation)

    if origin is typing.Annotated:
        args = get_args(annotation)
        if len(args) >= 2 and isinstance(args[1], str):
            return args[1]
        raise ValueError(
            f"Field '{field_name}' in '{class_name}' has Annotated type but "
            f"the second argument must be a Solidity type string"
        )

    if isinstance(annotation, type) and issubclass(annotation, ABIStruct):
        return "tuple"

    raise ValueError(
        f"Field '{field_name}' in '{class_name}' must use "
        f"Annotated[type, 'solidity_type'] or be an ABIStruct subclass"
    )


def _get_inner_struct(annotation: Any) -> "type[ABIStruct] | None":
    """Return the nested ABIStruct class for a field annotation, or None."""
    origin = get_origin(annotation)

    if origin is typing.Annotated:
        python_type = get_args(annotation)[0]
        if isinstance(python_type, type) and issubclass(python_type, ABIStruct):
            return python_type
        return None

    if isinstance(annotation, type) and issubclass(annotation, ABIStruct):
        return annotation

    return None


def _component_type_str(component: dict) -> str:
    """Return the ABI type string for a single ABI component dict."""
    if "components" in component:
        inner = ",".join(_component_type_str(c) for c in component["components"])
        # component["type"] is "tuple" or "tuple[]", "tuple[N]", etc.
        suffix = component["type"][5:]  # strip leading "tuple"
        return f"({inner}){suffix}"
    return component["type"]


def _build_type_str(components: list) -> str:
    """Build a full tuple type string, e.g. '(address,uint256,(bool,bytes32))'."""
    parts = [_component_type_str(c) for c in components]
    return "(" + ",".join(parts) + ")"


def _prepare_values(instance: Any, components: list) -> tuple:
    """
    Convert an ABIStruct (or any indexable) instance to a plain Python tuple
    suitable for eth_abi encoding.
    """
    values = []
    for i, comp in enumerate(components):
        val = instance[i]
        if "components" in comp:
            values.append(_prepare_values(val, comp["components"]))
        else:
            values.append(val)
    return tuple(values)


def _build_instance(cls: Any, values: Any) -> Any:
    """
    Recursively construct an ABIStruct instance from a decoded tuple of values.
    """
    hints = get_type_hints(cls, include_extras=True)
    fields = cls._fields

    kwargs = {}
    for i, field_name in enumerate(fields):
        val = values[i]
        annotation = hints[field_name]
        inner_cls = _get_inner_struct(annotation)
        if inner_cls is not None:
            val = _build_instance(inner_cls, val)
        kwargs[field_name] = val

    return cls(**kwargs)


class ABIStructMeta(type):
    """
    Metaclass for ABIStruct.  When a user defines a subclass of ABIStruct
    that has field annotations, the metaclass transparently creates a
    ``collections.namedtuple`` base so the resulting class is both a
    NamedTuple (immutable, indexable, named-attribute access) and an
    ABIStruct (encode / decode / human_readable_abi).
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple,
        namespace: dict,
    ) -> "ABIStructMeta":
        # Only special-case concrete subclasses, not ABIStruct itself.
        has_abistruct_base = any(isinstance(b, ABIStructMeta) for b in bases)
        if not has_abistruct_base:
            return super().__new__(mcs, name, bases, namespace)

        annotations = namespace.get("__annotations__", {})
        if not annotations:
            # Abstract or marker subclass with no new fields.
            return super().__new__(mcs, name, bases, namespace)

        # Build a namedtuple from the declared fields.
        nt = collections.namedtuple(  # type: ignore[misc]
            name, list(annotations.keys())
        )

        # Combine namedtuple with the ABIStruct method-carrier bases.
        abistruct_bases = [b for b in bases if isinstance(b, ABIStructMeta)]
        new_bases = (nt,) + tuple(abistruct_bases)

        new_ns = {
            k: v for k, v in namespace.items() if k not in ("__dict__", "__weakref__")
        }
        new_ns["__annotations__"] = annotations

        return type.__new__(mcs, name, new_bases, new_ns)


class ABIStruct(metaclass=ABIStructMeta):
    """
    Base class for ABI-encodable structs defined in pure Python.

    Subclass ``ABIStruct`` and annotate every field with
    ``Annotated[PythonType, 'solidity_type']``.  A nested ``ABIStruct``
    subclass may be used directly as a field type (the Solidity type is
    inferred as ``tuple``).

    The resulting class behaves like a ``NamedTuple`` (immutable, indexable,
    positional and keyword construction) and additionally provides:

    * ``encode()`` – ABI-encode the instance to ``bytes``
    * ``decode(data)`` – class method: ABI-decode ``bytes`` to an instance
    * ``human_readable_abi()`` – class method: Solidity ``struct`` definition

    Example::

        from typing import Annotated
        from eth_contract.struct import ABIStruct

        class Inner(ABIStruct):
            x: Annotated[bool, 'bool']
            y: Annotated[bytes, 'bytes32']

        class Transfer(ABIStruct):
            from_addr: Annotated[str, 'address']
            to_addr: Annotated[str, 'address']
            value: Annotated[int, 'uint256']
            memo: Annotated[str, 'string']
            inner: Inner

        tx = Transfer(
            from_addr='0x1111111111111111111111111111111111111111',
            to_addr='0x2222222222222222222222222222222222222222',
            value=10**18,
            memo='Hello, Ethereum!',
            inner=Inner(x=True, y=b'\\x01' * 32),
        )
        encoded = tx.encode()
        decoded = Transfer.decode(encoded)
        assert decoded == tx
        print(Transfer.human_readable_abi())
    """

    @classmethod
    def _abi_components(cls) -> list:
        """Return the ordered list of ABI component dicts for this struct."""
        hints = get_type_hints(cls, include_extras=True)
        fields = cls._fields  # type: ignore[attr-defined]

        components = []
        for field_name in fields:
            annotation = hints[field_name]
            abi_type = _get_field_abi_type(annotation, field_name, cls.__name__)
            inner_cls = _get_inner_struct(annotation)

            component: dict = {"name": field_name}
            if inner_cls is not None:
                component["type"] = "tuple"
                component["components"] = inner_cls._abi_components()
            else:
                component["type"] = abi_type

            components.append(component)

        return components

    def encode(self) -> bytes:
        """ABI-encode this struct instance to bytes."""
        components = self.__class__._abi_components()
        type_str = _build_type_str(components)
        values = _prepare_values(self, components)
        return abi_encode([type_str], [values])

    @classmethod
    def decode(cls, data: bytes) -> "ABIStruct":
        """ABI-decode *data* bytes and return an instance of this struct."""
        components = cls._abi_components()
        type_str = _build_type_str(components)
        (decoded,) = abi_decode([type_str], data)
        return _build_instance(cls, decoded)  # type: ignore[return-value]

    @classmethod
    def human_readable_abi(cls) -> str:
        """Return a Solidity-style struct definition string for this struct."""
        hints = get_type_hints(cls, include_extras=True)
        fields = cls._fields  # type: ignore[attr-defined]

        field_strs = []
        for field_name in fields:
            annotation = hints[field_name]
            origin = get_origin(annotation)
            if origin is typing.Annotated:
                args = get_args(annotation)
                if len(args) < 2 or not isinstance(args[1], str):
                    raise ValueError(
                        f"Field '{field_name}' in '{cls.__name__}' has Annotated "
                        f"type but the second argument must be a Solidity type string"
                    )
                solidity_type = args[1]
            elif isinstance(annotation, type) and issubclass(annotation, ABIStruct):
                solidity_type = annotation.__name__
            else:
                raise ValueError(
                    f"Cannot determine Solidity type for field '{field_name}'"
                )
            field_strs.append(f"{solidity_type} {field_name}")

        properties = "; ".join(field_strs)
        return f"struct {cls.__name__} {{ {properties}; }}"
