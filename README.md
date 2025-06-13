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

Please open issue if you want to see more ABIs included.

### TODO

* event filter arguments building.
* more tests.
* more builtin contract ABIs for convenience
  * Create2/create3 factory
  * Permit2
  * multicall
  * etc
