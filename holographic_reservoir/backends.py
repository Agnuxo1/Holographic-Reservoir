"""Hardware backend abstraction for the Holographic Reservoir.

The default :class:`SimulatedASICBackend` is pure NumPy + SHA-256 and
deterministic for a given seed. :class:`AxeOSBackend` talks to a real
AxeOS ASIC over TCP but only attempts a connection when an endpoint is
explicitly supplied.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional

import numpy as np


class HardwareBackend(ABC):
    """Abstract backend returning 32-byte entropy frames."""

    name: str = "abstract"
    available: bool = False

    @abstractmethod
    def mine(self, seed: bytes, cycles: int = 1) -> List[bytes]:
        """Return *cycles* 32-byte hash frames for *seed*."""


class SimulatedASICBackend(HardwareBackend):
    """Pure-Python, deterministic, offline substrate.

    Every frame is ``SHA-256(seed || counter || salt)`` where ``salt`` is
    derived from a fixed user-supplied seed. No sockets, no clocks, no
    hardware. Given the same ``(seed, cycles, random_seed)`` it always
    returns the same bytes — which is exactly what production tests want.
    """

    name = "simulation"
    available = True

    def __init__(self, random_seed: int = 0):
        self.random_seed = int(random_seed)
        self._salt = hashlib.sha256(
            b"holographic-reservoir-sim-" + str(self.random_seed).encode()
        ).digest()

    def mine(self, seed: bytes, cycles: int = 1) -> List[bytes]:
        if not isinstance(seed, (bytes, bytearray)):
            raise TypeError("seed must be bytes")
        seed = bytes(seed)
        out: List[bytes] = []
        for i in range(int(cycles)):
            h = hashlib.sha256(self._salt + seed + i.to_bytes(8, "big")).digest()
            out.append(h)
        return out

    def vectorise(self, frames: List[bytes]) -> np.ndarray:
        """Map hash frames to a ``(n, 4)`` float64 array in ``[-1, 1]``."""
        mat = np.zeros((len(frames), 4), dtype=np.float64)
        for i, h in enumerate(frames):
            chunks = np.frombuffer(h, dtype=">u8")  # 4 uint64
            mat[i] = (chunks.astype(np.float64) / 2**63) - 1.0
        return mat


class AxeOSBackend(HardwareBackend):
    """Optional AxeOS ASIC backend.

    Contacting real hardware is gated: the constructor requires an explicit
    endpoint and only imports :mod:`socket` lazily. If no endpoint is given
    it raises a clear error instead of silently dialling ``127.0.0.1``.
    """

    name = "axeos"

    def __init__(self, endpoint: Optional[str] = None, timeout: float = 5.0):
        if not endpoint:
            raise RuntimeError(
                "AxeOSBackend requires an explicit endpoint like 'IP:PORT'. "
                "Use SimulatedASICBackend for offline use."
            )
        host, _, port = endpoint.partition(":")
        if not host or not port:
            raise ValueError(f"Invalid endpoint {endpoint!r}; expected 'IP:PORT'.")
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self.available = True

    def mine(self, seed: bytes, cycles: int = 1) -> List[bytes]:
        import socket  # lazy

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(self.timeout)
            try:
                s.connect((self.host, self.port))
            except OSError as e:
                raise RuntimeError(
                    f"AxeOS backend could not reach {self.host}:{self.port}: {e}"
                ) from e
            s.sendall(f"BURST:{int(cycles)}\n".encode())
            expected = int(cycles) * 32
            buf = b""
            while len(buf) < expected:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
        frames = [buf[i : i + 32] for i in range(0, len(buf) - len(buf) % 32, 32)]
        if len(frames) < cycles:
            raise RuntimeError(
                f"AxeOS returned {len(frames)} frames, expected {cycles}."
            )
        return frames[:cycles]


def get_backend(
    name: str = "simulation",
    endpoint: Optional[str] = None,
    random_seed: int = 0,
) -> HardwareBackend:
    """Resolve a backend by name. Default: simulation (offline)."""
    key = (name or "simulation").lower()
    if key in ("simulation", "sim", "simulated"):
        return SimulatedASICBackend(random_seed=random_seed)
    if key in ("axeos", "hardware", "asic"):
        return AxeOSBackend(endpoint=endpoint)
    raise ValueError(f"Unknown backend: {name!r}")
