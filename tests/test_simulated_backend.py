"""Tests for the offline SimulatedASICBackend."""

import hashlib

import pytest

from holographic_reservoir.backends import (
    AxeOSBackend,
    SimulatedASICBackend,
    get_backend,
)


def test_determinism():
    a = SimulatedASICBackend(random_seed=42).mine(b"hello", cycles=8)
    b = SimulatedASICBackend(random_seed=42).mine(b"hello", cycles=8)
    assert a == b


def test_seed_changes_output():
    a = SimulatedASICBackend(random_seed=1).mine(b"x", cycles=4)
    b = SimulatedASICBackend(random_seed=2).mine(b"x", cycles=4)
    assert a != b


def test_shape_and_types():
    frames = SimulatedASICBackend(0).mine(b"seed", cycles=5)
    assert len(frames) == 5
    assert all(isinstance(f, bytes) and len(f) == 32 for f in frames)


def test_known_value():
    backend = SimulatedASICBackend(random_seed=0)
    salt = hashlib.sha256(b"holographic-reservoir-sim-0").digest()
    expected = hashlib.sha256(salt + b"abc" + (0).to_bytes(8, "big")).digest()
    assert backend.mine(b"abc", cycles=1)[0] == expected


def test_vectorise_range():
    backend = SimulatedASICBackend(0)
    frames = backend.mine(b"s", cycles=16)
    mat = backend.vectorise(frames)
    assert mat.shape == (16, 4)
    assert mat.min() >= -1.0 - 1e-9
    assert mat.max() <= 1.0 + 1e-9


def test_get_backend_default_is_simulation():
    assert isinstance(get_backend(), SimulatedASICBackend)
    assert isinstance(get_backend("sim"), SimulatedASICBackend)


def test_axeos_requires_endpoint():
    with pytest.raises(RuntimeError):
        AxeOSBackend(endpoint=None)
    with pytest.raises(ValueError):
        AxeOSBackend(endpoint="notvalid")


def test_seed_type_checked():
    with pytest.raises(TypeError):
        SimulatedASICBackend(0).mine("not-bytes", cycles=1)  # type: ignore[arg-type]
