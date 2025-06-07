An EVM ABI and contract and abstraction, plus some utilities.

It's built on top of the utilities provided by web3.py, eth-utils, eth-abi, etc.

This library provides a similar abstraction to the `Web3().eth.contract()`, but decoupled from the `Web3` instance, makes it easy to work with multiple providers, which is particularly important in today's multi-chain ERA.

It's also possible to cache the parsed ABI information as a global variable, makes it more efficient at runtime.

See the [unit tests]() for examples of how to use it.

Builtin common contract ABIs:

* ERC20
* Create2 factory
* Permit2

Please open issue if you want to see more ABIs included.

### TODO

* event filter arguments building
* more tests
