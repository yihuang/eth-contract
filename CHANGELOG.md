# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-04-10

### Added

- `ABIStruct` base class for defining Solidity-compatible ABI tuples/structs in pure Python using
  type annotations, with built-in ABI encode/decode and human-readable output (#32).
- Support for nested structs inside containers in `ABIStruct` (e.g. `list[Inner]` → `tuple[]`),
  plus default ABI type mappings so common primitives (`bool`, `int`, `str`, `bytes`, `list[...]`)
  no longer require explicit `Annotated` annotations (#38).
- `ContractEvent.build_filter()` to construct `eth_getLogs` filter parameters, and
  `ContractEvent.get_logs()` to fetch and decode logs from the chain (#30).

### Changed

- README completely rewritten to showcase library patterns (human-readable ABIs, `ABIStruct`,
  web3-agnostic calldata building, utility contracts) for both human readers and LLM agents (#34).

### Fixed

- Added `py.typed` marker file so that type checkers (mypy, pyright, etc.) treat the package as
  typed, in compliance with PEP 561 (#36).

## [0.3.0] - 2025-12-26

### Added

- Human-readable ABI: support for event signatures (`event Transfer(...)`) (#27).
- Human-readable ABI: support for multiline strings (#26).
- Human-readable ABI: strip whitespace from individual signatures (#25).
- Multicall3: allow customizing `eth_call` options (block number, state overrides, etc.) (#24).

## [0.2.0] - 2025-10-20

### Added

- Human-readable ABI: full coverage of the [abitype human-readable ABI spec](https://abitype.dev/api/human),
  including tuple/struct outputs and verbose-mode regex rewrite (#15, #16, #19).
- ERC-4337 `EntryPoint` v0.7 and v0.8 contract instances (#11).
- Storage slot detection utilities (`parse_balance_slot`, `parse_allowance_slot`, `parse_supply_slot`)
  for ERC-20 token state analysis (#12, #18).
- `ensure_deployed_by_create3` deployment helper (#9).
- `increaseAllowance` / `decreaseAllowance` on ERC-20 (#8).
- Extra transaction params (gas, price) on `transfer` and other ERC-20 helpers (#7).
- WETH9 contract instance and deploy helper (#5, #13).
- `trace_call` is now importable without requiring the optional `pyrevm` dependency (#21).

### Fixed

- `ContractFunction` instances are now safely cacheable (shallow copy before mutation) (#10).

## [0.1.0] - 2025-07-30

### Added

- Initial release: `Contract` abstraction decoupled from `Web3` instances.
- Human-readable ABI parser (`parse_abi`).
- ERC-20 utility contract (`ERC20`).
- CREATE2 / CREATE3 deterministic deployment helpers.
- Multicall3 batch call support.
- Deploy utilities for pre-signed well-known contracts (CREATE2 factory, Multicall3, CreateX).
- CI: Black, isort, flake8, mypy, and pytest via Nix + direnv (#4).
