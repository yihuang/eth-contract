import socket
import subprocess
import time
from typing import Generator

import pytest
from web3 import AsyncHTTPProvider, AsyncWeb3

PORT = 9545


def wait_port(port: int, host: str = "localhost", timeout: float = 10.0) -> None:
    """Wait until a port is open on the given host."""
    start_time = time.perf_counter()
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except (socket.timeout, ConnectionRefusedError):
            if time.perf_counter() - start_time >= timeout:
                raise TimeoutError(
                    f"Timed out waiting for port {port} on {host} after "
                    f"{timeout} seconds"
                )
            time.sleep(0.1)


@pytest.fixture(scope="session")
def w3() -> Generator[AsyncWeb3, None, None]:
    anvil = subprocess.Popen(
        [
            "anvil",
            "--fork-url",
            "https://eth-mainnet.public.blastapi.io",
            "--fork-block-number",
            "18000000",
            "--port",
            str(PORT),
        ]
    )

    try:
        wait_port(PORT)
    except TimeoutError:
        anvil.terminate()
        raise
    yield AsyncWeb3(AsyncHTTPProvider(f"http://localhost:{PORT}"))
    anvil.terminate()
