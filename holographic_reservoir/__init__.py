"""Holographic Reservoir Computing Framework.

Public v1.0 API.

This package exposes a clean, hardware-free default API for reservoir
computing built on a bipartite expander topology (VeselovLayer) with a
pluggable :class:`HardwareBackend`. The default backend is a pure-NumPy,
SHA-256 based :class:`SimulatedASICBackend` that needs no network and
produces deterministic outputs.

Optional real-hardware support (AxeOS ASIC over TCP) lives in
:class:`AxeOSBackend` and only activates when an endpoint is provided
and the ``[hardware]`` extras are installed.
"""

from .backends import (
    HardwareBackend,
    SimulatedASICBackend,
    AxeOSBackend,
    get_backend,
)
from .model import HolographicReservoirModel, mackey_glass

__version__ = "1.0.0"
__all__ = [
    "HardwareBackend",
    "SimulatedASICBackend",
    "AxeOSBackend",
    "get_backend",
    "HolographicReservoirModel",
    "mackey_glass",
    "__version__",
]
