"""
https://eips.ethereum.org/EIPS/eip-2935
"""

from eth_utils import to_checksum_address

SYSTEM_ADDRESS = to_checksum_address("0xfffffffffffffffffffffffffffffffffffffffe")
HISTORY_STORAGE_ADDRESS = to_checksum_address(
    "0x0000F90827F1C53a10cb7A02335B175320002935"
)
