from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence, cast

from eth_abi import encode
from eth_abi.codec import ABICodec
from eth_abi.registry import registry as default_registry
from eth_account.signers.base import BaseAccount
from eth_typing import (ABI, ABIConstructor, ABIEvent, ABIFunction,
                        ChecksumAddress)
from eth_utils import (abi_to_signature, filter_abi_by_name,
                       filter_abi_by_type,
                       function_signature_to_4byte_selector,
                       get_abi_input_types, get_abi_output_types,
                       get_normalized_abi_inputs, keccak)
from eth_utils.toolz import assoc, merge
from hexbytes import HexBytes
from typing_extensions import Unpack
from web3 import AsyncWeb3
from web3._utils.events import get_event_data
from web3.exceptions import MismatchedABI
from web3.types import (BlockIdentifier, EventData, LogReceipt, StateOverride,
                        TxParams, TxReceipt)
from web3.utils.abi import (_mismatched_abi_error_diagnosis,
                            check_if_arguments_can_be_encoded)

from .utils import send_transaction


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
        self.data = encode(self.input_types, self.arguments)
        return self


@dataclass
class ContractFunction:
    abis: Sequence[ABIFunction]
    parent: Contract | None = None

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

        self._resolve_to(matched[0])
        self.arguments = get_normalized_abi_inputs(self.abi, *args, **kwargs)
        self.encoded_args = encode(self.input_types, self.arguments)
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
        return self.decode(return_data, codec=w3.codec)

    def decode(self, data: bytes, codec=None) -> Any:
        codec = codec or ABICodec(default_registry)
        data = codec.decode(self.output_types, data)
        return data[0] if len(data) == 1 else data

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

    @property
    def name(self) -> str:
        return self.abi["name"]

    @property
    def topic(self) -> HexBytes:
        if self._topic is None:
            self._topic = keccak(text=self.signature)
        return self._topic

    def parse_log(self, log: LogReceipt) -> EventData | None:
        try:
            return get_event_data(ABICodec(default_registry), self.abi, log)
        except MismatchedABI:
            return None


@dataclass
class ContractFunctions:
    abis: Mapping[str, Sequence[ABIFunction]]
    parent: Contract | None = None

    def __getattr__(self, name: str) -> ContractFunction:
        try:
            abis = self.abis[name]
        except KeyError:
            raise AttributeError(f"No such function: {name}")

        return ContractFunction(abis, parent=self.parent)


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
    for fn_name, fns in contract.fns.abis.items():
        for fn in fns:
            print(f"function\t{abi_to_signature(fn)}")
    for event in contract.events.abis:
        print(f"event\t{abi_to_signature(event)}")
    for abi in filter_abi_by_type("error", contract.abi):
        print(f"error\t{abi_to_signature(abi)}")
