import io
import json
from contextlib import redirect_stdout
from typing import Unpack

import pyrevm
from web3.types import TxParams

from eth_contract.utils import ZERO_ADDRESS


def trace_call(vm: pyrevm.EVM, **tx: Unpack[TxParams]) -> list[dict]:
    """
    Capture and parse traces from a pyrevm message call.
    """
    with redirect_stdout(io.StringIO()) as out:
        vm.message_call(
            caller=tx.get("from", ZERO_ADDRESS),  # type: ignore
            to=tx.get("to", ""),  # type: ignore
            calldata=tx.get("data"),  # type: ignore
            value=tx.get("value", 0),
        )

    out.seek(0)
    traces = []
    for line in out.readlines():
        try:
            trace_item = json.loads(line)
            traces.append(trace_item)
        except json.JSONDecodeError:
            continue

    return traces
