# Copilot Instructions for eth-contract

## Project Overview

`eth-contract` is an EVM contract abstraction library that decouples contract interactions from `Web3` instances. This makes it easy to work with the same contract definition across multiple blockchain providers or networks. It also includes a suite of utilities for ABI parsing, deployment, batch calls, and ERC-4337 account abstraction.

**Package**: `eth_contract`  
**Python**: Library supports Python >=3.9 (dev environment uses 3.12; see `.python-version`)  
**Key dependency**: `web3>=7.12.0`

---

## Repository Structure

```
eth-contract/
├── eth_contract/              # Main package
│   ├── __init__.py            # Public API exports
│   ├── contract.py            # Core Contract/ContractFunction/ContractEvent abstractions
│   ├── human.py               # Human-readable Solidity ABI parser
│   ├── utils.py               # Transaction helpers, account management, deploy utilities
│   ├── erc20.py               # Pre-configured ERC20 contract instance
│   ├── create2.py             # CREATE2 deterministic deployment
│   ├── create3.py             # CREATE3 deployment via CreateX factory
│   ├── multicall3.py          # Multicall3 batch call utilities
│   ├── entrypoint.py          # ERC-4337 EntryPoint v0.7 & v0.8
│   ├── deploy_utils.py        # Pre-deploy well-known contracts from pre-signed transactions
│   ├── slots.py               # EVM trace-based ERC20 storage slot analysis
│   ├── weth.py                # WETH contract
│   ├── history_storage.py     # EIP-2935 block history storage
│   ├── abis/                  # Built-in ABI JSON files (erc20, multicall3, createx, weth)
│   ├── deployments/           # Pre-built deployment artifacts (WETH9, EntryPoint07/08)
│   └── txs/                   # Pre-signed deployment transactions (create2, multicall3, createx)
├── tests/
│   ├── conftest.py            # Pytest fixtures: Anvil node setup, test accounts
│   ├── test_contract.py       # Contract abstraction tests
│   ├── test_contract_function.py
│   ├── test_human.py          # Human-readable ABI parser tests
│   ├── test_erc20.py
│   ├── test_abi.py
│   ├── test_slots.py
│   ├── trace.py               # EVM trace helper utilities for tests
│   ├── contracts.py           # Test contract definitions and artifacts
│   └── contracts/             # Test contract compiled artifacts
├── pyproject.toml             # Build config, dependencies, tool settings
├── uv.lock                    # Frozen dependency lock (do not edit manually)
├── .flake8                    # max-line-length=88, extend-ignore=E203
├── .python-version            # 3.12
├── .envrc.example             # Nix + direnv dev environment template
└── .github/workflows/python-package.yml  # CI: lint → typecheck → test
```

---

## Development Environment Setup

The project uses [Nix](https://nixos.org/) + [direnv](https://direnv.net/) for a reproducible environment, and [uv](https://github.com/astral-sh/uv) for Python dependency management.

```bash
# 1. Install Nix and direnv (see README for links)
cp .envrc.example .envrc
direnv allow

# 2. Install Python dependencies (MUST use --frozen to avoid modifying uv.lock)
uv sync --frozen

# 3. Run tests to verify setup
pytest -s -vvv
```

> **Important**: Always use `uv sync --frozen`. Running `uv sync` without `--frozen` on uv versions after v0.6.15 will modify `uv.lock`, which should not be committed unless intentionally updating dependencies.

Tests require [Anvil](https://book.getfoundry.sh/reference/anvil/) (the Foundry local node), which is installed through the Nix environment.

---

## Testing

Tests use an **Anvil** local Ethereum node as the backend. Chain-backed fixtures (`w3`, `fork_w3`) are async and session-scoped; other fixtures (for example, accounts) are synchronous but also session-scoped.

```bash
pytest                                            # Run all tests
pytest -s -vvv                                    # Verbose with print output
pytest tests/test_contract.py                     # Single file
pytest tests/test_contract.py::ClassName::test_fn # Single test
```

### Key test fixtures (from `tests/conftest.py`)

| Fixture | Description |
|---|---|
| `w3` | Local Anvil node (port 9545, Prague hardfork, chain-id 1337) with pre-deployed contracts |
| `fork_w3` | Mainnet fork (port 10545, block 18,000,000) with same pre-deploys |
| `test_accounts` | 5 pre-funded `BaseAccount` objects from deterministic mnemonic |

**Test mnemonic**: `body bag bird mix language evidence what liar reunion wire lesson evolve`  
**BIP44 path**: `m/44'/60'/0'/0/{0..4}`

### Async tests

All tests interacting with the chain must use `pytest-asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_something(w3, test_accounts):
    ...
```

---

## Linting, Formatting, and Type Checking

```bash
black .       # Auto-format (line-length: 88)
isort .       # Sort imports (profile: black)
flake8        # Lint (max-line-length: 88, extend-ignore: E203)
mypy .        # Type check
```

CI runs flake8 and mypy as separate steps (even on test failure, via `if: success() || failure()`).

---

## Core Architecture

### `Contract` class (`eth_contract/contract.py`)

The main abstraction. Decouples contract definitions (ABI + optional default tx params) from any specific Web3 instance.

```python
from eth_contract.contract import Contract

# Create from human-readable signatures
c = Contract.from_abi([
    "function balanceOf(address) view returns (uint256)",
    "event Transfer(address indexed from, address indexed to, uint256 value)",
])

# Bind to a specific address for calls
c_at = c(to="0xTokenAddress...")

# Async call (read-only)
balance = await c_at.fns.balanceOf(user_address).call(w3)

# Async transaction
receipt = await c_at.fns.transfer(recipient, amount).transact(w3, account)
```

**Key classes**:
- `Contract`: Top-level contract; holds ABI and default `TxParams`
- `ContractFunction`: Represents a contract function; callable to resolve overloads
- `ContractEvent`: Represents an event; has `.topic` and `.parse_log(log)`
- `ContractFunctions`: Lazy collection (`contract.fns.functionName`)
- `ContractEvents`: Lazy collection (`contract.events.EventName`)
- `ContractConstructor`: Encodes constructor arguments

**Transaction binding**: Calling `contract(**tx_params)` returns a new contract bound to those params. Functions inherit the parent contract's tx params.

### Human-readable ABI parser (`eth_contract/human.py`)

Parses Solidity-style function/event/error/struct signatures into JSON ABI dicts. Implements the [abitype human-readable ABI spec](https://abitype.dev/api/human).

```python
from eth_contract.human import parse_abi

abi = parse_abi([
    "function transfer(address to, uint256 amount) returns (bool)",
    "event Transfer(address indexed from, address indexed to, uint256 amount)",
    "struct Token { address addr; uint256 decimals; }",
])
```

Supports: nested tuples, struct resolution, type shorthand (`int` → `int256`), all Solidity modifiers.

### Transaction utilities (`eth_contract/utils.py`)

```python
from eth_contract.utils import send_transaction, send_transactions, transfer, balance_of

# Send single transaction
receipt = await send_transaction(w3, account, to=addr, value=amount)

# Batch transactions with automatic nonce management
receipts = await send_transactions(w3, [tx1, tx2, tx3], account=account)

# ERC20 or native transfer
await transfer(w3, token_address, sender, receiver, amount)
await transfer(w3, None, sender, receiver, amount)  # native ETH

# Balance query
bal = await balance_of(w3, token_address, address)
bal = await balance_of(w3, None, address)  # native ETH
```

### Deployment utilities

```python
from eth_contract.create2 import create2_deploy, create2_address
from eth_contract.create3 import create3_deploy, create3_address
from eth_contract.utils import get_initcode

# Deterministic address calculation
addr = create2_address(initcode, salt=0)

# Deploy
addr = await create2_deploy(w3, account, initcode, salt=0)
addr = await create3_deploy(w3, account, initcode, salt=0)

# With constructor args
initcode = get_initcode(artifact, arg1, arg2)
```

**CLI tools**:
```bash
python -m eth_contract.create2 artifact.json [ctor_args...] --salt 0 --rpc-url http://...
python -m eth_contract.create3 artifact.json [ctor_args...] --salt 0 --rpc-url http://...
python -m eth_contract.contract abi.json  # List all signatures in an ABI file
```

### Multicall3 batch calls (`eth_contract/multicall3.py`)

```python
from eth_contract.multicall3 import multicall

results = await multicall(w3, [
    (addr1, fn1),
    (addr2, fn2),
])
```

### ERC20 storage slot analysis (`eth_contract/slots.py`)

Used to detect where a token stores balances/allowances (for state overrides/simulation):

```python
from eth_contract.slots import parse_balance_slot, parse_allowance_slot

slot = parse_balance_slot(token_addr, user_addr, traces)
slot = parse_allowance_slot(token_addr, user_addr, spender_addr, traces)
```

---

## Pre-configured Contract Instances

The package provides ready-to-use contract instances for common contracts:

```python
from eth_contract.erc20 import ERC20
from eth_contract.multicall3 import MULTICALL3, MULTICALL3_ADDRESS
from eth_contract.weth import WETH, WETH9_ARTIFACT
from eth_contract.entrypoint import ENTRYPOINT07, ENTRYPOINT08
```

Usage pattern:
```python
balance = await ERC20.fns.balanceOf(address).call(w3, to=token_address)
```

---

## Code Conventions

- **Async-first**: All blockchain interactions are async (`async def`, `await`, `AsyncWeb3`)
- **Type hints**: Use `eth_typing` and `web3.types` types (`ChecksumAddress`, `TxParams`, `TxReceipt`, `Wei`, etc.)
- **Line length**: 88 characters (Black default)
- **Import order**: `isort` with `profile = "black"`
- **Error handling**: Use assertions for configuration validation; `try/except` with detailed error info for ABI mismatch
- **Lazy loading**: `ContractFunctions`/`ContractEvents` create instances on first access via `__getattr__`
- **Composition**: Functions and utilities are module-level, not nested in classes where avoidable
- **No mutable state**: Transaction params are merged immutably (`merge(self.parent.tx, tx)`)

---

## CI/CD (`.github/workflows/python-package.yml`)

The CI pipeline runs on push/PR to `main`:
1. Set up Nix environment (DeterminateSystems/determinate-nix-action)
2. Install direnv with Nix profile
3. `uv sync` (without `--frozen` — CI intentionally allows the lock file to be refreshed on each run)
4. Run `flake8` (continues on failure)
5. Run `mypy` (continues on failure)
6. Run `pytest -s -vvv` (continues on failure)

**Local vs CI difference**: CI runs `uv sync` without `--frozen`, which can silently update `uv.lock` on uv versions after v0.6.15. **Always use `uv sync --frozen` locally** to keep `uv.lock` stable and avoid unintentional lock file changes in your commits. Only omit `--frozen` when you explicitly intend to update dependencies.

---

## Common Task Patterns

### Adding a new built-in contract

1. Add ABI JSON to `eth_contract/abis/` (if applicable)
2. Create `eth_contract/newcontract.py` following the pattern in `erc20.py` or `weth.py`
3. Export from `eth_contract/__init__.py`
4. Add tests in `tests/test_newcontract.py`

### Adding a new human-readable ABI feature

1. Edit `eth_contract/human.py`
2. Add corresponding test cases to `tests/test_human.py` (this file has extensive parametrized tests)
3. Run: `pytest tests/test_human.py -s -vvv`

### Working with contract functions in tests

```python
# Read-only call
result = await contract.fns.someFunction(arg1).call(w3, to=contract_address)

# State-changing transaction
receipt = await contract.fns.someFunction(arg1).transact(w3, account, to=contract_address)

# Decode raw return data
decoded = contract.fns.someFunction.decode(raw_bytes)
```

### Deploying a test contract

```python
from eth_contract.utils import get_initcode
from eth_contract.deploy_utils import ensure_deployed_by_create2

artifact = {"abi": [...], "bytecode": {"object": "0x..."}}
address = await ensure_deployed_by_create2(w3, account, get_initcode(artifact))
```

### Running a local dev node with pre-deployed contracts

```bash
python -m tests.conftest  # Starts Anvil with all pre-deployed contracts and prints accounts
```

---

## Important Addresses

| Contract | Address |
|---|---|
| CREATE2 factory (Arachnid) | `0x4e59b44847b379578588920ca78fbf26c0b4956c` |
| Multicall3 | `0xcA11bde05977b3631167028862bE2a173976CA11` |
| CreateX factory | `0xba5Ed099633D3B313e4D5F7bdc1305d3c28ba5Ed` |
| EIP-2935 history storage | `0x0000F90827F1C53a10cb7A02335B175320002935` |
