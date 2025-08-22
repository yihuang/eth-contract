"""
Utilities to parse erc20 slots from trace result.

To override erc20 balance or allowance value for arbitrary account in eth_call, we need
to know the storage slot of the mappings, erc20 don't standardize these things, normally
we have to find it in the solc compiler output, but we can't do that for arbitrary
tokens without their source code.

The solution here is to parse the trace result of `balanceOf` or `allowance` calls to
find out the storage slots.

This implementation here is inspired by the `token-bss` project[1].

References:

[1]. https://github.com/halo3mic/token-bss
[2]. https://hackmd.io/@oS7_rZFHQnCFw_lsRei3nw/HJN1rQWmA
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from eth_utils import keccak
from hexbytes import HexBytes


def get_op_name(log: dict) -> str:
    return log.get("opName") or log["op"]


def get_memory(log: dict) -> bytes:
    mem = log["memory"]
    if isinstance(mem, str):
        return HexBytes(mem)
    return b"".join([bytes.fromhex(i) for i in mem])


@dataclass
class MappingSlot:
    slot: bytes
    is_solidity: bool = True  # otherwise vyper

    def __init__(self, slot: bytes | int, is_solidity: bool = True) -> None:
        if isinstance(slot, int):
            slot = slot.to_bytes(32, "big")
        if len(slot) != 32:
            raise ValueError("slot must be 32 bytes")
        self.slot = slot
        self.is_solidity = is_solidity

    def value(self, key: bytes) -> MappingSlot:
        "compute the value storage slot for the given key"
        v0, v1 = key.rjust(32, b"\x00"), self.slot
        if self.is_solidity:
            slot = keccak(v0 + v1)
        else:
            slot = keccak(v1 + v0)
        return MappingSlot(slot, self.is_solidity)


def parse_mapping_reads(
    top_contract: bytes, traces: Iterable[dict]
) -> Iterable[tuple[bytes, bytes, bytes, bytes]]:
    """
    parse the mapping reads from the traces.

    for example: `balances[user]` is compiled to:

    ```
    slot = KECCAK256(v0 | v1)
    SLOAD(slot)
    ```

    we parse the opcodes and return `[(contract, v0, v1, slot)]`

    in solidity, v0 is the map key, v1 is the index of the mapping field,
    in vyper, v1 is the map key, v0 is the index of the mapping field.
    """
    # stack to track current calling contract, `depth -> contract address`
    contracts: dict[int, bytes] = {1: top_contract}
    # record pre-image of hash operation
    hashed: dict[bytes, tuple[bytes, bytes]] = {}
    # temporarily record the pre-image, will be paired with the hash result in next step
    tmp_pre_image: tuple[bytes, bytes] | None = None
    for step in traces:
        if "stack" not in step:
            continue

        stack = step["stack"]

        if tmp_pre_image is not None:
            # the hash result is at the top of the stack of next op
            hashed[HexBytes(stack[-1])] = tmp_pre_image
            tmp_pre_image = None

        op = get_op_name(step)
        if op == "KECCAK256":
            # compute the storage slot for the mapping key
            size, offset = int(stack[-2], 16), int(stack[-1], 16)
            if size != 64:
                continue
            mem = get_memory(step)[offset : offset + 64]
            tmp_pre_image = mem[:32], mem[32:]
        elif op == "SLOAD":
            slot = HexBytes(stack[-1])
            try:
                v0, v1 = hashed[slot]
            except KeyError:
                continue

            # we are reading from a slot which is result of hashing two values
            # likely a read from a map
            contract = contracts[step["depth"]]
            yield (contract, v0, v1, slot)
        elif op in ("CALL", "STATICCALL"):
            contracts[step["depth"] + 1] = HexBytes(stack[-2])[-20:]
        elif op == "DELEGATECALL":
            depth = step["depth"]
            contracts[depth + 1] = contracts[depth]


def parse_nested_mapping_reads(
    top_contract: bytes, traces: Iterable[dict]
) -> Iterable[tuple[bytes, bytes, bytes, bytes, bytes]]:
    """
    parse the nested mapping reads from the traces.

    for example: `allowances[user][spender]` is compiled to:

    ```
    tmp = KECCAK256(v0 | v1)
    slot = KECCAK256(v2 | tmp) # or KECCAK256(tmp | v2)
    SLOAD(slot)
    ```

    we'll parse the opcodes and return `[(contract, v0, v1, v2, slot)]`

    in solidity, v0 is the user, v1 is the index of the mapping field,
    in vyper, v1 is the user, v0 is the index of the mapping field.
    v2 should always be the spender.
    """

    # stack to track current calling contract
    contracts: dict[int, bytes] = {1: top_contract}
    # record pre-image of hash operation
    hashed: dict[bytes, tuple[bytes, bytes]] = {}
    # temporarily record the pre-image, will be paired with the hash result in next step
    tmp_pre_image: tuple[bytes, bytes] | None = None
    for step in traces:
        if "stack" not in step:
            continue

        stack = step["stack"]

        if tmp_pre_image is not None:
            # the hash result is at the top of the stack of next op
            hashed[HexBytes(stack[-1])] = tmp_pre_image
            tmp_pre_image = None

        op = get_op_name(step)
        if op == "KECCAK256":
            # compute the storage slot for the mapping key
            size, offset = int(stack[-2], 16), int(stack[-1], 16)
            if size != 64:
                continue
            mem = get_memory(step)[offset : offset + 64]
            tmp_pre_image = mem[:32], mem[32:]
        elif op == "SLOAD":
            slot = HexBytes(stack[-1])
            try:
                n0, n1 = hashed[slot]
            except KeyError:
                continue

            # check nested mapping read
            try:
                v0, v1 = hashed[n0]
                v2 = n1
            except KeyError:
                try:
                    v0, v1 = hashed[n1]
                    v2 = n0
                except KeyError:
                    continue

            # we are reading from a slot which is result of hashing two values
            # likely a read from a map
            contract = contracts[step["depth"]]
            yield (contract, v0, v1, v2, slot)
        elif op in ("CALL", "STATICCALL"):
            contracts[step["depth"] + 1] = HexBytes(stack[-2])[-20:]
        elif op == "DELEGATECALL":
            depth = step["depth"]
            contracts[depth + 1] = contracts[depth]


def parse_balance_slot(
    token: bytes, user: bytes, traces: Iterable[dict]
) -> MappingSlot | None:
    """
    detect the balance slot of token contract with a `balanceOf(user)` trace result
    """
    user = user.rjust(32, b"\x00")
    for contract, v0, v1, slot in parse_mapping_reads(token, traces):
        if contract != token:
            continue

        if v0 == user:
            return MappingSlot(v1, True)
        elif v1 == user:
            return MappingSlot(v0, False)
    return None


def parse_allowance_slot(
    token: bytes, user: bytes, spender: bytes, traces: Iterable[dict]
) -> MappingSlot | None:
    """
    detect the balance slot of token contract with a `allowance[user][spender]` trace result
    """
    user = user.rjust(32, b"\x00")
    spender = spender.rjust(32, b"\x00")
    for contract, v0, v1, v2, slot in parse_nested_mapping_reads(token, traces):
        if contract != token:
            continue

        if v2 != spender:
            continue

        if v0 == user:
            return MappingSlot(v1, True)
        elif v1 == user:
            return MappingSlot(v0, False)
    return None


def parse_batch_allowance_slot(
    tokens: set[bytes], user: bytes, spender: bytes, traces: Iterable[dict]
) -> dict[bytes, MappingSlot]:
    """
    the trace is generated with a multicall of `allowance(user, spender)`
    """
    top_contract = b"\x00" * 20  # placeholder for top contract
    user = user.rjust(32, b"\x00")
    spender = spender.rjust(32, b"\x00")

    result = {}
    for contract, v0, v1, v2, slot in parse_nested_mapping_reads(top_contract, traces):
        if contract not in tokens:
            continue

        if v2 != spender:
            continue

        if v0 == user:
            result[contract] = MappingSlot(v1, True)
        elif v1 == user:
            result[contract] = MappingSlot(v0, False)

    return result


def parse_batch_balance_slot(
    tokens: set[bytes], user: bytes, traces: Iterable[dict]
) -> dict[bytes, MappingSlot]:
    """
    the trace is generated with a multicall of `balanceOf(user)`
    """
    top_contract = b"\x00" * 20  # placeholder for top contract
    user = user.rjust(32, b"\x00")

    result = {}
    for contract, v0, v1, slot in parse_mapping_reads(top_contract, traces):
        if contract not in tokens:
            continue

        if v0 == user:
            result[contract] = MappingSlot(v1, True)
        elif v1 == user:
            result[contract] = MappingSlot(v0, False)

    return result
