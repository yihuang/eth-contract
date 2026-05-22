from __future__ import annotations

import itertools
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence, cast

from eth_abi.codec import ABICodec
from eth_abi.registry import registry as default_registry
from eth_account.signers.base import BaseAccount
from eth_typing import (
    ABI,
    ABIComponent,
    ABIConstructor,
    ABIEvent,
    ABIFunction,
    ChecksumAddress,
)
from eth_utils import (
    abi_to_signature,
    filter_abi_by_name,
    filter_abi_by_type,
    function_signature_to_4byte_selector,
    get_abi_input_types,
    get_abi_output_types,
    get_normalized_abi_inputs,
    keccak,
)
from eth_utils.toolz import assoc, merge
from hexbytes import HexBytes
from typing_extensions import Unpack
from web3 import AsyncWeb3
from web3._utils.events import get_event_data
from web3._utils.filters import construct_event_filter_params
from web3.exceptions import MismatchedABI
from web3.types import (
    BlockIdentifier,
    EventData,
    FilterParams,
    LogReceipt,
    StateOverride,
    TxParams,
    TxReceipt,
)
from web3.utils.abi import (
    _mismatched_abi_error_diagnosis,
    check_if_arguments_can_be_encoded,
)

from .human import (
    parse_abi,
    parse_event_signature,
    parse_function_signature,
    parse_structs,
    process_multiline,
)
from .struct import ABIStruct, _build_instance
from .utils import send_transaction

_abi_codec = ABICodec(default_registry)


def _split_array_suffix(type_str: str) -> tuple[str, bool]:
    """Strip the outermost array suffix from *type_str*.

    Returns ``(inner_type, is_array)`` where *inner_type* has one less
    array dimension.

    >>> _split_array_suffix("struct Test[][]")
    ("struct Test[]", True)
    >>> _split_array_suffix("tuple[]")
    ("tuple", True)
    >>> _split_array_suffix("tuple[3]")
    ("tuple", True)
    >>> _split_array_suffix("tuple[][]")
    ("tuple[]", True)
    >>> _split_array_suffix("tuple")
    ("tuple", False)
    """
    bracket = type_str.rfind("[")
    if bracket >= 0:
        return type_str[:bracket], True
    return type_str, False


def _decode_abi_structs(
    value: Any,
    abi_types: Sequence[ABIComponent],
    structs: dict[str, type[ABIStruct]],
) -> Any:
    """
    Recursively convert decoded tuples into ABIStruct instances.

    Uses the ``internalType`` field in each ABI component (e.g.
    ``"struct Point"``) to look up the corresponding ABIStruct class
    from *structs*, then calls ``_build_instance`` to construct it.

    Structs referenced in the ABI but missing from *structs* are
    silently left as plain tuples or lists.
    """

    def _process(val: Any, abi_type: ABIComponent) -> Any:
        # 1. Array: strip one level, recurse on each element
        inner_type, is_array = _split_array_suffix(abi_type["type"])
        if is_array:
            inner_abi: ABIComponent = dict(abi_type, type=inner_type)  # type: ignore
            internal: str | None = abi_type.get("internalType")  # type: ignore
            if internal is not None:
                inner_internal, _ = _split_array_suffix(internal)
                inner_abi["internalType"] = inner_internal  # type: ignore
            return tuple(_process(item, inner_abi) for item in val)

        # 2. Named struct (no array suffix at this point)
        internal_type: str | None = abi_type.get("internalType")  # type: ignore
        if internal_type is not None and internal_type.startswith("struct "):
            raw_name = internal_type[len("struct ") :]
            cls = structs.get(raw_name)
            if cls is not None:
                return _build_instance(cls, val)
            return val

        # 3. Anonymous tuple
        if "components" in abi_type:
            return tuple(_process(v, c) for v, c in zip(val, abi_type["components"]))

        return val

    return tuple(_process(v, t) for v, t in zip(value, abi_types))


def _normalize_structs(
    structs: list[type[ABIStruct]] | dict[str, type[ABIStruct]] | None,
) -> dict[str, type[ABIStruct]]:
    if structs is None:
        return {}
    if isinstance(structs, dict):
        return structs
    return {s.__name__: s for s in structs}


@dataclass
class ContractConstructor:
    abi: ABIConstructor

    def __post_init__(self) -> None:
        self.input_types = get_abi_input_types(self.abi)

    def __call__(self, *args, **kwargs) -> ContractConstructor:
        """
        Call the constructor with the given arguments.
        """
        self.arguments = get_normalized_abi_inputs(self.abi, *args, **kwargs)
        self.data = _abi_codec.encode(self.input_types, self.arguments)
        return self


@dataclass
class ContractFunction:
    abis: Sequence[ABIFunction]
    parent: Contract | None = None
    structs: dict[str, type[ABIStruct]] = field(default_factory=dict)

    @classmethod
    def from_abi(
        cls,
        i: ABIFunction | str,
        structs: list[type[ABIStruct]] | dict[str, type[ABIStruct]] | None = None,
    ) -> ContractFunction:
        """
        Create a ContractFunction from an ABI or human-readable signature.

        Args:
            i: An ABIFunction dict or a human-readable function signature.
            structs: Optional list of ABIStruct subclasses referenced by the
                signature.  Their definitions are auto-injected so that
                ``decode()`` returns ABIStruct instances.

        Example::

            fn = ContractFunction.from_abi(
                "function getPoint() returns (Point)",
                structs=[Point],
            )
            fn.decode(data)  #  Point(x=1, y=2)
        """
        struct_map = _normalize_structs(structs)
        if isinstance(i, str):
            parsed_structs = None
            if struct_map:
                parsed_structs = parse_structs(
                    itertools.chain(
                        *(s.human_readable_abi() for s in struct_map.values())
                    )
                )
            abi = parse_function_signature(process_multiline(i), structs=parsed_structs)
        else:
            abi = i
        assert abi["type"] == "function"
        return cls([abi], structs=struct_map)

    def __post_init__(self) -> None:
        self._resolve_to(self.abis[0])

    def _resolve_to(self, abi: ABIFunction) -> None:
        """
        resolve to one of the overloaded functions,
        the abi should be one of the `self.abis`
        """
        self.abi = abi
        self.input_types = get_abi_input_types(abi)
        self.output_types = get_abi_output_types(abi)
        self.signature = abi_to_signature(abi)
        self.selector = function_signature_to_4byte_selector(self.signature)

    @property
    def name(self) -> str:
        return self.abi["name"]

    def __call__(self, *args, **kwargs) -> ContractFunction:
        """
        Call the function with the given arguments,
        resolve to one of an overloaded functions.
        """
        if len(self.abis) == 1:
            matched = self.abis
        else:
            matched = [
                abi
                for abi in self.abis
                if check_if_arguments_can_be_encoded(abi, *args, **kwargs)
            ]

        if len(matched) != 1:
            error_diagnosis = _mismatched_abi_error_diagnosis(
                self.name,
                self.abis,
                len(matched),
                len(args) + len(kwargs),
                *args,
                **kwargs,
            )
            raise MismatchedABI(error_diagnosis)

        self = copy(self)
        self._resolve_to(matched[0])
        self.arguments = get_normalized_abi_inputs(self.abi, *args, **kwargs)
        self.encoded_args = _abi_codec.encode(self.input_types, self.arguments)
        self.data = HexBytes(self.selector + self.encoded_args)
        return self

    async def call(
        self,
        w3: AsyncWeb3,
        block_identifier: BlockIdentifier | None = None,
        state_override: StateOverride | None = None,
        ccip_read_enabled: bool | None = None,
        structs: list[type[ABIStruct]] | None = None,
        **tx: Unpack[TxParams],
    ) -> Any:
        """
        Call the function on the contract at the given address.

        Args:
            w3: An async Web3 instance.
            block_identifier: Block at which to call.
            state_override: State override map.
            ccip_read_enabled: Whether CCIP read is enabled.
            structs: Optional list of ABIStruct subclasses.  When provided,
                decoded return values will be converted to ABIStruct instances
                instead of plain tuples.
            **tx: Transaction parameters (to, gas, etc.).
        """
        if self.parent is not None:
            tx = merge(self.parent.tx, tx)
        return_data = await w3.eth.call(
            transaction=assoc(tx, "data", self.data),
            block_identifier=block_identifier,
            state_override=state_override,
            ccip_read_enabled=ccip_read_enabled,
        )
        return self.decode(return_data, structs=structs)

    def decode(
        self,
        data: bytes,
        codec: ABICodec | None = None,
        structs: list[type[ABIStruct]] | dict[str, type[ABIStruct]] | None = None,
    ) -> Any:
        """Decode return data against :attr:`output_types`.

        Args:
            data: The raw return data bytes.
            codec: Optional custom ABICodec.
            structs: Optional list of ABIStruct subclasses.  When provided,
                decoded tuples are converted to ABIStruct instances.

        Returns:
            The decoded value (plain tuple by default, or ABIStruct instance
            when *structs* matches the ABI's ``internalType``).
        """
        codec = codec or _abi_codec
        result = codec.decode(self.output_types, data)

        structs_map = _normalize_structs(structs) or self.structs
        if not structs_map and self.parent:
            structs_map = self.parent.structs
        if structs_map:
            result = _decode_abi_structs(
                result, self.abi.get("outputs", []), structs_map
            )

        return result[0] if len(result) == 1 else result

    def decode_input(
        self,
        data: bytes,
        codec: ABICodec | None = None,
        structs: list[type[ABIStruct]] | dict[str, type[ABIStruct]] | None = None,
    ) -> Any:
        """Decode full calldata (selector + args) against the matching overload.

        The leading 4 bytes select which overload to decode against;
        :class:`ValueError` is raised if no overload's selector matches.
        Body-only payloads are rejected because a first arg whose bytes
        equal the selector would be indistinguishable from a full call.

        Args:
            data: The calldata bytes (4-byte selector + encoded args).
            codec: Optional custom ABICodec.
            structs: Optional list of ABIStruct subclasses.  When provided,
                decoded struct arguments are converted to ABIStruct instances.
        """
        codec = codec or _abi_codec

        structs_map = _normalize_structs(structs) or self.structs
        if not structs_map and self.parent:
            structs_map = self.parent.structs

        leading = data[:4]
        overloads = [
            (function_signature_to_4byte_selector(abi_to_signature(abi)), abi)
            for abi in self.abis
        ]
        for sel, abi in overloads:
            if sel == leading:
                result = codec.decode(get_abi_input_types(abi), data[4:])
                if structs_map:
                    result = _decode_abi_structs(
                        result, abi.get("inputs", []), structs_map
                    )
                return result[0] if len(result) == 1 else result
        expected = ", ".join("0x" + s.hex() for s, _ in overloads)
        raise ValueError(
            f"selector mismatch for {self.signature}: "
            f"got 0x{leading.hex()}, expected one of [{expected}]"
        )

    async def transact(
        self, w3: AsyncWeb3, acct: BaseAccount | ChecksumAddress, **tx: Unpack[TxParams]
    ) -> TxReceipt:
        """
        Send a transaction to the contract with the given data.
        """
        if self.parent is not None:
            tx = merge(self.parent.tx, tx)
        return await send_transaction(w3, acct, **assoc(tx, "data", self.data))


@dataclass
class ContractEvent:
    abi: ABIEvent

    def __post_init__(self):
        self.signature = abi_to_signature(self.abi)
        self.input_types = get_abi_input_types(self.abi)
        self._topic = None

    @classmethod
    def from_abi(cls, i: ABIEvent | str) -> ContractEvent:
        if isinstance(i, str):
            abi = parse_event_signature(process_multiline(i))
        else:
            abi = i
        assert abi["type"] == "event"
        return cls(abi)

    @property
    def name(self) -> str:
        return self.abi["name"]

    @property
    def topic(self) -> HexBytes:
        if self._topic is None:
            self._topic = keccak(text=self.signature)
        return self._topic

    def build_filter(
        self,
        address: ChecksumAddress | list[ChecksumAddress] | None = None,
        argument_filters: dict[str, Any] | None = None,
        from_block: BlockIdentifier | None = None,
        to_block: BlockIdentifier | None = None,
    ) -> FilterParams:
        """
        Build filter parameters suitable for ``eth_getLogs``.

        Args:
            address: Contract address or list of addresses to filter by.
            argument_filters: Mapping of indexed argument names to values to
                filter on (e.g. ``{"from": "0x..."}``)
            from_block: Starting block (inclusive). Defaults to the node's
                default when omitted.
            to_block: Ending block (inclusive). Defaults to the node's default
                when omitted.

        Returns:
            A :class:`~web3.types.FilterParams` dict ready to be passed to
            ``w3.eth.get_logs()``.

        Raises:
            ValueError: If any key in ``argument_filters`` is not an indexed
                parameter of this event.
        """
        if argument_filters:
            indexed_names = {
                param["name"]
                for param in self.abi.get("inputs", [])
                if param.get("indexed", False)
            }
            for key in argument_filters:
                if key not in indexed_names:
                    raise ValueError(
                        f"Argument '{key}' is not an indexed parameter of event "
                        f"'{self.name}'. Only indexed parameters can be used as "
                        f"filter arguments. Indexed parameters: {sorted(indexed_names)}"
                    )
        _data_filters, filter_params = construct_event_filter_params(
            self.abi,
            _abi_codec,
            contract_address=address,
            argument_filters=argument_filters,
            from_block=from_block,
            to_block=to_block,
        )
        return filter_params

    async def get_logs(
        self,
        w3: AsyncWeb3,
        address: ChecksumAddress | list[ChecksumAddress] | None = None,
        argument_filters: dict[str, Any] | None = None,
        from_block: BlockIdentifier | None = None,
        to_block: BlockIdentifier | None = None,
    ) -> list[EventData]:
        """
        Fetch and decode matching logs from the chain.

        Calls ``eth_getLogs`` using the filter built by :meth:`build_filter`
        and decodes each returned log with :meth:`parse_log`.

        Args:
            w3: An async Web3 instance.
            address: Contract address or list of addresses to filter by.
            argument_filters: Mapping of indexed argument names to filter
                values (e.g. ``{"from": "0x..."}``)
            from_block: Starting block (inclusive).
            to_block: Ending block (inclusive).

        Returns:
            List of decoded :class:`~web3.types.EventData` entries.
        """
        filter_params = self.build_filter(
            address=address,
            argument_filters=argument_filters,
            from_block=from_block,
            to_block=to_block,
        )
        logs = await w3.eth.get_logs(filter_params)
        return self.parse_logs(logs, codec=w3.codec)

    def parse_log(
        self, log: LogReceipt, codec: ABICodec | None = None
    ) -> EventData | None:
        try:
            return get_event_data(codec or _abi_codec, self.abi, log)
        except MismatchedABI:
            return None

    def parse_logs(
        self, logs: Sequence[LogReceipt], codec: ABICodec | None = None
    ) -> list[EventData]:
        return [
            decoded
            for log in logs
            if (decoded := self.parse_log(log, codec=codec)) is not None
        ]


@dataclass
class ContractFunctions:
    _abis: Mapping[str, Sequence[ABIFunction]]
    _parent: Contract | None = None
    _functions: dict[str, ContractFunction] = field(default_factory=dict)

    def __getattr__(self, name: str) -> ContractFunction:
        try:
            return self._functions[name]
        except KeyError:
            if not self._abis.get(name):
                raise AttributeError(f"No such function: {name}")
            abis = self._abis[name]

            fn = ContractFunction(abis, parent=self._parent)
            self._functions[name] = fn
            return fn


@dataclass
class ContractEvents:
    abis: Sequence[ABIEvent]

    def __getattr__(self, name: str) -> ContractEvent:
        candidates = filter_abi_by_name(name, self.abis)
        if len(candidates) == 0:
            raise ValueError(f"No such event: {name}")
        if len(candidates) > 1:
            raise ValueError(f"Multiple events found with name: {name}")
        return ContractEvent(cast(ABIEvent, candidates[0]))

    def sig(self, signature: str) -> ContractEvent:
        for abi in self.abis:
            if abi_to_signature(abi) == signature:
                return ContractEvent(abi)
        raise ValueError(f"No such event signature: {signature}")


@dataclass
class Contract:
    abi: ABI
    tx: TxParams = field(default_factory=lambda: TxParams())
    structs: dict[str, type[ABIStruct]] = field(default_factory=dict)

    receive: ContractFunction | None = None
    fallback: ContractFunction | None = None

    def __post_init__(self) -> None:
        abis: defaultdict[str, list[ABIFunction]] = defaultdict(list)
        for fn in filter_abi_by_type("function", self.abi):
            abis[fn["name"]].append(fn)
        self.fns = ContractFunctions(abis, self)

        self.events = ContractEvents(filter_abi_by_type("event", self.abi))

        self.constructor: ContractConstructor | None = None
        ctor = filter_abi_by_type("constructor", self.abi)
        if ctor:
            self.constructor = ContractConstructor(ctor[0])

        if filter_abi_by_type("receive", self.abi):
            self.receive = ContractFunction([{"type": "function", "name": "receive"}])

        if filter_abi_by_type("fallback", self.abi):
            self.fallback = ContractFunction([{"type": "function", "name": "fallback"}])

    def __call__(self, **tx: Unpack[TxParams]) -> Contract:
        """
        Bind contract to different transaction parameters.
        """
        return Contract(self.abi, structs=self.structs, tx=merge(self.tx, tx))

    def with_structs(self, structs: list[type[ABIStruct]]) -> Contract:
        """
        Return a new Contract with the given ABIStruct subclasses merged in.

        The struct definitions are auto-injected and decode results
        are automatically converted to ABIStruct instances.
        """
        structs_map = {s.__name__: s for s in structs}
        return Contract(self.abi, structs={**self.structs, **structs_map}, tx=self.tx)

    @classmethod
    def from_abi(
        cls,
        abi_or_signatures: ABI | list[str],
        *,
        structs: list[type[ABIStruct]] | dict[str, type[ABIStruct]] | None = None,
        **kwargs: Unpack[TxParams],
    ) -> Contract:
        """
        Create a Contract instance from ABI or human-readable signatures.

        Args:
            abi_or_signatures: Either a parsed ABI or list of human-readable signatures
            structs: Optional list of ABIStruct subclasses. Their struct definitions
                are auto-injected before the signatures, and decoded tuples are
                automatically converted to ABIStruct instances on decode.
            **kwargs: Optional transaction parameters

        Returns:
            Contract instance with parsed ABI

        Example:
            >>> contract = Contract.from_abi([
            ...     'function transfer(address to, uint256 amount) external',
            ...     'function getPoint() returns (Point)',
            ... ], structs=[Point])
            >>> result = await contract.fns.getPoint().call(w3)
            >>> isinstance(result, Point)  # True
        """
        assert isinstance(abi_or_signatures, list)
        struct_map = _normalize_structs(structs)
        if abi_or_signatures and isinstance(abi_or_signatures[0], str):
            extra_defs: list[str] = list(
                itertools.chain(*(s.human_readable_abi() for s in struct_map.values()))
            )
            abi = parse_abi(extra_defs + abi_or_signatures)
        else:
            abi = abi_or_signatures  # type: ignore
        return cls(abi=abi, structs=struct_map, tx=kwargs)


if __name__ == "__main__":
    # cli to list all abi signatures in the contract abi
    import json
    import sys
    from pathlib import Path

    if len(sys.argv) != 2:
        print("Usage: python contract.py <path_to_abi.json>")
        sys.exit(1)

    abi_path = Path(sys.argv[1])
    if not abi_path.exists():
        print(f"ABI file not found: {abi_path}")
        sys.exit(1)

    abi = json.loads(abi_path.read_text())
    if isinstance(abi, dict):
        abi = abi["abi"]

    contract = Contract(abi)
    if contract.constructor:
        print(f"constructor\t{abi_to_signature(contract.constructor.abi)}")
    for fn_name, fns in contract.fns._abis.items():
        for fn in fns:
            print(f"function\t{abi_to_signature(fn)}")
    for event in contract.events.abis:
        print(f"event\t{abi_to_signature(event)}")
    for abi in filter_abi_by_type("error", contract.abi):
        print(f"error\t{abi_to_signature(abi)}")
