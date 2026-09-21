"""Smoke tests for the CLI entry point."""

import io
import contextlib

import pytest

from holographic_reservoir.cli import main


def _run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_cli_info():
    rc, out = _run(["info"])
    assert rc == 0
    assert "holographic-reservoir" in out
    assert "simulation" in out
    assert "unexpected" not in out
    assert "configured" in out


def test_cli_demo_small():
    rc, out = _run(["demo", "--size", "60", "--n", "400"])
    assert rc == 0
    assert "Mackey-Glass MSE" in out


def test_cli_benchmark_small():
    rc, out = _run(["benchmark", "--size", "60", "--n", "400"])
    assert rc == 0
    assert "mse=" in out


def test_cli_axeos_requires_endpoint():
    with pytest.raises(RuntimeError):
        _run(["demo", "--hardware", "axeos"])
