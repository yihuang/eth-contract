# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an EVM contract abstraction library that provides decoupled contract interactions from Web3 instances, making it easier to work with multiple blockchain providers. The main components include:

- **Contract**: Core contract abstraction class (`eth_contract/contract.py`)
- **ERC20**: ERC20 token contract utilities (`eth_contract/erc20.py`)
- **CREATE2/CREATE3**: Contract deployment utilities (`eth_contract/create2.py`, `eth_contract/create3.py`)
- **Multicall3**: Batch call utilities (`eth_contract/multicall3.py`)
- **EntryPoint**: ERC-4337 entry point contracts (`eth_contract/entrypoint.py`)
- **Deployment Utilities**: Pre-deployed contract management (`eth_contract/deploy_utils.py`)

## Development Commands

### Setup
```bash
uv sync --frozen  # Install dependencies with frozen lockfile
```

### Testing
```bash
pytest            # Run all tests
pytest -s -vvv    # Run tests with verbose output
pytest tests/test_contract.py::test_specific_function  # Run specific test
```

### Linting & Formatting
```bash
black .           # Format code
isort .           # Sort imports
flake8            # Lint code
mypy .            # Type checking
```

### Building
```bash
python -m build   # Build package
```

## Key Architecture

- **Async-first**: All operations use async/await patterns
- **Provider-agnostic**: Contracts are decoupled from Web3 instances
- **ABI utilities**: Built-in support for common contract ABIs (ERC20, CREATE2, Multicall3, WETH)
- **Deployment helpers**: Utilities for deploying contracts via CREATE2/CREATE3 factories

## Testing Environment

Tests use Anvil (local Ethereum node) with pre-deployed contracts:
- CREATE2 factory at `0x4e59b44847b379578588920ca78fbf26c0b4956c`
- Multicall3 contracts
- ERC-4337 EntryPoint contracts (v0.7 and v0.8)
- WETH9 contract

Test fixtures are defined in `tests/conftest.py` and provide:
- `w3`: Local Anvil instance
- `fork_w3`: Mainnet fork instance
- `test_accounts`: Pre-funded test accounts

## Common Patterns

1. **Contract Interaction**: Use `Contract` class with ABI and address
2. **Deployment**: Use `create2_deploy` or `create3_deploy` utilities
3. **Batch Calls**: Use `multicall3` for efficient batch operations
4. **ERC20 Operations**: Use `ERC20` class for token interactions

## Important Files

- `eth_contract/contract.py`: Core contract abstraction
- `eth_contract/utils.py`: Utility functions and transaction helpers
- `tests/conftest.py`: Test configuration and fixtures
- `pyproject.toml`: Project configuration and dependencies
