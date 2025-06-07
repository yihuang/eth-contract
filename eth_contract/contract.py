from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping, Sequence, cast

from eth_abi import encode
from eth_abi.codec import ABICodec
from eth_abi.registry import registry as default_registry
from eth_account.signers.base import BaseAccount
from eth_typing import ABI, ABIConstructor, ABIEvent, ABIFunction
from eth_utils import (abi_to_signature, filter_abi_by_name,
                       filter_abi_by_type,
                       function_signature_to_4byte_selector,
                       get_abi_input_types, get_abi_output_types,
                       get_normalized_abi_inputs, keccak)
from hexbytes import HexBytes
from web3 import AsyncWeb3
from web3._utils.events import get_event_data
from web3.exceptions import MismatchedABI
from web3.types import EventData, LogReceipt, TxParams, TxReceipt
from web3.utils.abi import (_mismatched_abi_error_diagnosis,
                            check_if_arguments_can_be_encoded)

from .utils import send_transaction


@dataclass
class ContractConstructor:
    abi: ABIConstructor

    def __call__(self, *args) -> bytes:
        """
        Call the constructor with the given arguments.
        """
        if len(args) != len(self.abi["inputs"]):
            raise ValueError(
                f"Expected {len(self.abi['inputs'])} arguments, got {len(args)}"
            )
        return encode(get_abi_input_types(self.abi), args)


@dataclass
class ContractFunction:
    abis: Sequence[ABIFunction]

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
        return self

    @property
    def data(self) -> HexBytes:
        return HexBytes(self.selector + self.encoded_args)

    async def call(self, w3: AsyncWeb3, tx: TxParams | None = None, **kwargs) -> Any:
        """
        Call the function on the contract at the given address.
        """
        if tx is None:
            tx = {}
        tx["data"] = self.data
        return_data = await w3.eth.call(tx, **kwargs)
        data = w3.codec.decode(self.output_types, return_data)
        return data[0] if len(data) == 1 else data

    async def transact(
        self, w3: AsyncWeb3, acct: BaseAccount | None, tx: TxParams | None = None
    ) -> TxReceipt:
        """
        Send a transaction to the contract with the given data.
        """
        if tx is None:
            tx = {}
        tx["data"] = self.data
        return await send_transaction(w3, acct, tx=tx)


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


class ContractFunctions(dict, Mapping[str, Sequence[ABIFunction]]):
    def __getattr__(self, name: str) -> ContractFunction:
        try:
            abis = self[name]
        except KeyError:
            raise AttributeError(f"No such function: {name}")

        return ContractFunction(abis)


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

    def __post_init__(self) -> None:
        fns: defaultdict[str, list[ABIFunction]] = defaultdict(list)
        for fn in filter_abi_by_type("function", self.abi):
            fns[fn["name"]].append(fn)
        self.fns = ContractFunctions(fns)

        self.events = ContractEvents(filter_abi_by_type("event", self.abi))
