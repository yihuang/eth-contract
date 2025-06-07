EVM contract abstraction and ABI utilities.

The main difference from `Web3().eth.contract()` is decoupling the contract from the `Web3` instance, makes it easy to work with multiple providers, which is particularly important in today's multi-chain environment.

See the [unit tests]() for examples of how to use it.

Builtin common contract ABIs:

* ERC20

Please open issue if you want to see more ABIs included.

### TODO

* event filter arguments building.
* more tests.
* more builtin contract ABIs for convenience
  * Create2/create3 factory
  * Permit2
  * multicall
  * etc
