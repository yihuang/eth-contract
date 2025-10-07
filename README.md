EVM contract abstraction and ABI utilities.

The main difference from `Web3().eth.contract()` is decoupling the contract from the `Web3` instance, makes it easy to work with multiple providers, which is particularly important in today's multi-chain environment.

See the [unit tests](https://github.com/yihuang/eth-contract/blob/main/eth_contract/test_contract.py) for examples of how to use it.

Builtin common contract ABIs:

* ERC20
* CREATE2 factory (0x4e59b44847b379578588920ca78fbf26c0b4956c)
  include cli utility to deploy contract using the factory, `python -m eth_contract.create2 --help`.
* createx factory (https://github.com/pcaversaccio/createx)
  include cli utility to deploy contract with create3, `python -m eth_contract.create3 --help`.
* multicall3 (https://github.com/mds1/multicall3)
* weth (https://github.com/gnosis/canonical-weth)
* ERC-4337 EntryPoint (v0.7 and v0.8) for account abstraction
* Parser of human readable abi (https://abitype.dev/api/human).

Please open issue if you want to see more ABIs included.

### TODO

* event filter arguments building.
* more tests.
* more builtin contract ABIs for convenience
  * permit2
  * etc

## Project Setup

1. Install [nix](https://nixos.org/download/)
2. Install [direnv](https://direnv.net/) and [nix-direnv](https://github.com/nix-community/nix-direnv)
3. `uv sync --frozen` to install all dependencies. (Without `--fronzen`, [`uv` version after v0.6.15 modifies the `uv.lock`](https://github.com/dependabot/dependabot-core/issues/12127))
4. `pytest` to run all tests

If you are able to run all tests, you are ready to go!
