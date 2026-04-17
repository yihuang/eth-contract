from __future__ import annotations

from collections import defaultdict
from copy import copy
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence, cast

from eth_abi.codec import ABICodec
from eth_abi.registry import registry as default_registry
from eth_account.signers.base import BaseAccount
from eth_typing import ABI, ABIConstructor, ABIEvent, ABIFunction, ChecksumAddress
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
    process_multiline,
)
from .utils import send_transaction

_abi_codec = ABICodec(default_registry)


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

    @classmethod
    def from_abi(cls, i: ABIFunction | str) -> ContractFunction:
        if isinstance(i, str):
            abi = parse_function_signature(process_multiline(i))
        else:
            abi = i
        assert abi["type"] == "function"
        return cls([abi])

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
        **tx: Unpack[TxParams],
    ) -> Any:
        """
        Call the function on the contract at the given address.
        """
        if self.parent is not None:
            tx = merge(self.parent.tx, tx)
        return_data = await w3.eth.call(
            transaction=assoc(tx, "data", self.data),
            block_identifier=block_identifier,
            state_override=state_override,
            ccip_read_enabled=ccip_read_enabled,
        )
        return self.decode(return_data)

    def decode(self, data: bytes, codec: ABICodec | None = None) -> Any:
        codec = codec or _abi_codec
        result = codec.decode(self.output_types, data)
        return result[0] if len(result) == 1 else result

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
        results: list[EventData] = []
        for log in logs:
            decoded = self.parse_log(log, codec=w3.codec)
            if decoded is not None:
                results.append(decoded)
        return results

    def parse_log(
        self, log: LogReceipt, codec: ABICodec | None = None
    ) -> EventData | None:
        try:
            return get_event_data(codec or _abi_codec, self.abi, log)
        except MismatchedABI:
            return None


@dataclass
class ContractFunctions:
    _abis: Mapping[str, Sequence[ABIFunction]]
    _parent: Contract | None = None
    _functions: dict[str, ContractFunction] = field(default_factory=dict)

    def __getattr__(self, name: str) -> ContractFunction:
        try:
            return self._functions[name]
        except KeyError:
            try:
                abis = self._abis[name]
            except KeyError:
                raise AttributeError(f"No such function: {name}")

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
        return Contract(self.abi, tx=merge(self.tx, tx))

    @classmethod
    def from_abi(
        cls, abi_or_signatures: ABI | list[str], **kwargs: Unpack[TxParams]
    ) -> Contract:
        """
        Create a Contract instance from ABI or human-readable signatures.

        Args:
            abi_or_signatures: Either a parsed ABI or list of human-readable signatures
            **kwargs: Optional transaction parameters

        Returns:
            Contract instance with parsed ABI

        Example:
            >>> # From human-readable signatures
            >>> contract = Contract.from_abi([
            ...     'function transfer(address to, uint256 amount) external',
            ...     'event Transfer(address indexed from, address indexed to, '
            ...     'uint256 amount)'
            ... ])
            >>>
            >>> # From parsed ABI
            >>> contract = Contract.from_abi([
            ...     {"type": "function", "name": "transfer", "inputs": [...]}
            ... ])
        """
        assert isinstance(abi_or_signatures, list)
        if isinstance(abi_or_signatures[0], str):
            abi = parse_abi(abi_or_signatures)
        else:
            abi = abi_or_signatures  # type: ignore
        return cls(abi=abi, tx=kwargs)


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
