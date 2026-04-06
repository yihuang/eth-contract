# eth-contract

EVM contract abstraction and ABI utilities for Python.

The core design principle: **decouple contract definitions from `Web3` instances**. Build calldata as pure functions, compose contract calls freely, and only bind to a provider at the moment of execution. This makes it easy to work with multiple chains/providers and to compose calls with multicall or other routers.

## Installation

```bash
pip install eth-contract
```

## Patterns

### 1. Pythonic ABI Definitions

Stop writing unreadable JSON ABI files or relying on the Solidity compiler to get an ABI. Define your contract interface directly in Python.

#### Human-Readable ABIs

Pass Solidity-style signature strings to `Contract.from_abi`. The library parses them into a full JSON ABI at runtime:

```python
from eth_contract import Contract

ERC20 = Contract.from_abi([
    "function transfer(address to, uint256 amount) returns (bool)",
    "function balanceOf(address owner) view returns (uint256)",
    "function approve(address spender, uint256 amount) returns (bool)",
    "event Transfer(address indexed from, address indexed to, uint256 amount)",
    "event Approval(address indexed owner, address indexed spender, uint256 amount)",
])
```

Structs are supported too — define them inline and reference them from functions and events:

```python
Router = Contract.from_abi([
    "struct ExactInputSingleParams {"
    "  address tokenIn;"
    "  address tokenOut;"
    "  uint24 fee;"
    "  address recipient;"
    "  uint256 amountIn;"
    "  uint256 amountOutMinimum;"
    "  uint160 sqrtPriceLimitX96;"
    "}",
    "function exactInputSingle(ExactInputSingleParams params) payable returns (uint256 amountOut)",
])
```

#### Type-Annotated ABI Structs

For richer Python integration, define structs as typed Python classes using `ABIStruct`. Fields are annotated with `Annotated[PythonType, 'solidity_type']`. The class behaves like a `NamedTuple` and provides `encode()` / `decode()` / `human_readable_abi()` for free:

```python
from typing import Annotated
from eth_contract import ABIStruct, Contract

class SwapParams(ABIStruct):
    token_in:  Annotated[str,  'address']
    token_out: Annotated[str,  'address']
    fee:       Annotated[int,  'uint24']
    recipient: Annotated[str,  'address']
    amount_in: Annotated[int,  'uint256']
    amount_out_minimum: Annotated[int, 'uint256']

# Generate the human-readable ABI fragment automatically
print(SwapParams.human_readable_abi())
# ['struct SwapParams { address token_in; address token_out; uint24 fee; ... }']

# Build the contract using the generated struct definition
Router = Contract.from_abi(
    SwapParams.human_readable_abi() + [
        "function exactInputSingle(SwapParams params) payable returns (uint256 amountOut)",
    ]
)
```

`ABIStruct` supports nesting — use another `ABIStruct` subclass directly as a field type:

```python
class Inner(ABIStruct):
    x: Annotated[bool, 'bool']
    y: Annotated[bytes, 'bytes32']

class Outer(ABIStruct):
    value: Annotated[int, 'uint256']
    inner: Inner  # nested struct, no Annotated needed

encoded = Outer(value=42, inner=Inner(x=True, y=b'\x01' * 32)).encode()
decoded = Outer.decode(encoded)
```

---

### 2. Web3-Agnostic Calldata Building

Building calldata is a **pure function** — no Web3 instance required. Bind an address or transaction parameters to a contract with `contract(to=..., ...)`, then call functions to produce encoded calldata. The actual Web3 provider is only provided at the point of execution (`.call()` or `.transact()`).

```python
from eth_contract import Contract

ERC20 = Contract.from_abi([
    "function transfer(address to, uint256 amount) returns (bool)",
    "function balanceOf(address owner) view returns (uint256)",
])

token = ERC20(to="0xTokenAddress...")

# Build calldata without any Web3 instance
calldata = token.fns.transfer("0xRecipient...", 10**18).data
# HexBytes('0xa9059cbb...')

# Execute only when you have a provider
balance = await token.fns.balanceOf("0xUser...").call(w3)
receipt = await token.fns.transfer("0xRecipient...", 10**18).transact(w3, account)
```

Because calldata building is decoupled from execution, the same `ContractFunction` object can be passed to **multicall** or any other batching mechanism:

```python
from eth_contract.multicall3 import multicall
from eth_contract import ERC20

USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
users = ["0xUser1...", "0xUser2..."]

# Build all calls without a provider
calls = [(USDC, ERC20.fns.balanceOf(user)) for user in users]
calls += [(WETH, ERC20.fns.balanceOf(user)) for user in users]

# Execute all calls in a single RPC round-trip
results = await multicall(w3, calls)
```

Contracts can be rebound to different addresses or parameters on the fly:

```python
# Base contract definition (no address bound)
ERC20 = Contract.from_abi(["function balanceOf(address) view returns (uint256)"])

# Bind to a specific token address
usdc = ERC20(to="0xUSDC...")
weth = ERC20(to="0xWETH...")

# Both share the same ABI, different addresses
usdc_balance = await usdc.fns.balanceOf(user).call(w3)
weth_balance = await weth.fns.balanceOf(user).call(w3)
```

---

### 3. Built-In Utility ABIs

No need to copy-paste ABIs for common contracts. `eth-contract` ships ready-to-use instances:

```python
from eth_contract import ERC20
from eth_contract.multicall3 import MULTICALL3, multicall
from eth_contract.weth import WETH
from eth_contract.entrypoint import ENTRYPOINT07, ENTRYPOINT08
```

#### ERC20

```python
from eth_contract import ERC20

token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC

balance = await ERC20.fns.balanceOf(user).call(w3, to=token)
receipt = await ERC20.fns.transfer(recipient, amount).transact(w3, account, to=token)
```

#### Multicall3

Batch many read calls into one RPC request:

```python
from eth_contract import ERC20
from eth_contract.multicall3 import multicall

tokens = ["0xUSDC...", "0xWETH...", "0xDAI..."]
calls = [(token, ERC20.fns.balanceOf(user)) for token in tokens]
balances = await multicall(w3, calls)
# [usdc_balance, weth_balance, dai_balance]
```

#### WETH

```python
from eth_contract.weth import WETH

weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
receipt = await WETH.fns.deposit().transact(w3, account, to=weth_address, value=10**18)
```

#### Deterministic Deployment (CREATE2 / CREATE3)

```python
from eth_contract.create2 import create2_deploy, create2_address
from eth_contract.create3 import create3_deploy, create3_address
from eth_contract.utils import get_initcode

initcode = get_initcode(artifact)              # from a compiled artifact dict
salt = 0

address = create2_address(initcode, salt=salt) # compute address before deploying
address = await create2_deploy(w3, account, initcode, salt=salt)
```

CLI tools for deployment:

```bash
python -m eth_contract.create2 artifact.json [ctor_args...] --salt 0 --rpc-url http://...
python -m eth_contract.create3 artifact.json [ctor_args...] --salt 0 --rpc-url http://...
python -m eth_contract.contract abi.json      # list all signatures in an ABI file
```

---

## Utility Helpers

```python
from eth_contract.utils import send_transaction, send_transactions, transfer, balance_of

# Single transaction
receipt = await send_transaction(w3, account, to=addr, data=calldata)

# Batch with automatic nonce management
receipts = await send_transactions(w3, [tx1, tx2, tx3], account=account)

# ERC20 or native transfer (pass None / ZERO_ADDRESS for native ETH)
await transfer(w3, token_address, sender, receiver, amount)
await transfer(w3, ZERO_ADDRESS, sender, receiver, amount)  # native ETH

# Balance query
bal = await balance_of(w3, token_address, address)
bal = await balance_of(w3, ZERO_ADDRESS, address)  # native ETH
```

---

## Built-In Contracts Summary

| Contract | Import |
|---|---|
| ERC20 | `from eth_contract import ERC20` |
| Multicall3 | `from eth_contract.multicall3 import MULTICALL3, multicall` |
| WETH | `from eth_contract.weth import WETH` |
| ERC-4337 EntryPoint v0.7 | `from eth_contract.entrypoint import ENTRYPOINT07` |
| ERC-4337 EntryPoint v0.8 | `from eth_contract.entrypoint import ENTRYPOINT08` |
| CREATE2 factory | `from eth_contract.create2 import create2_deploy` |
| CreateX (CREATE3) | `from eth_contract.create3 import create3_deploy` |

Please open an issue if you want to see more ABIs included.

---

## Project Setup

1. Install [nix](https://nixos.org/download/)
2. Install [direnv](https://direnv.net/) and [nix-direnv](https://github.com/nix-community/nix-direnv)
3. `uv sync --frozen` to install all dependencies. (Without `--frozen`, [`uv` version after v0.6.15 modifies the `uv.lock`](https://github.com/dependabot/dependabot-core/issues/12127))
4. `pytest` to run all tests

If you are able to run all tests, you are ready to go!
