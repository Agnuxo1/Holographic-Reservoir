"""Command-line interface for the Holographic Reservoir framework.

Subcommands
-----------
demo        Run the offline Mackey-Glass simulation demo.
benchmark   Fit + evaluate the reservoir on Mackey-Glass and print MSE.
info        Show version and backend availability.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .backends import AxeOSBackend, SimulatedASICBackend, get_backend
from .model import HolographicReservoirModel


def _make_backend(args):
    if args.hardware and args.hardware != "simulation":
        return get_backend(args.hardware, endpoint=args.endpoint,
                           random_seed=args.seed)
    return SimulatedASICBackend(random_seed=args.seed)


def cmd_demo(args) -> int:
    backend = _make_backend(args)
    print(f"[holographic-reservoir] backend = {backend.name}")
    model = HolographicReservoirModel(
        size=args.size, backend=backend, random_seed=args.seed
    )
    mse, _, _ = model.mackey_glass_benchmark(n=args.n)
    print(f"Mackey-Glass MSE (n={args.n}, size={args.size}): {mse:.6e}")
    return 0


def cmd_benchmark(args) -> int:
    backend = _make_backend(args)
    model = HolographicReservoirModel(
        size=args.size, backend=backend, random_seed=args.seed
    )
    mse, _, _ = model.mackey_glass_benchmark(n=args.n)
    print(f"backend={backend.name} size={args.size} n={args.n} mse={mse:.6e}")
    return 0


def cmd_info(args) -> int:
    print(f"holographic-reservoir {__version__}")
    print(f"  simulation backend: available (pure NumPy + SHA-256)")
    try:
        AxeOSBackend(endpoint="0.0.0.0:0")  # validates configuration without connecting
        hw = "configured (opt-in; connection is tested only when used)"
    except Exception:
        hw = "unavailable (requires --hardware axeos --endpoint IP:PORT)"
    print(f"  axeos backend:      {hw}")
    print("  default:            simulation (no network, no hardware)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="holographic-reservoir",
        description="Holographic Reservoir Computing (simulation + optional ASIC).",
    )
    p.add_argument("--version", action="version",
                   version=f"holographic-reservoir {__version__}")

    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--hardware", default="simulation",
                        choices=["simulation", "axeos"],
                        help="Backend to use (default: simulation).")
        sp.add_argument("--endpoint", default=None,
                        help="IP:PORT for --hardware axeos.")
        sp.add_argument("--seed", type=int, default=0, help="Random seed.")
        sp.add_argument("--size", type=int, default=200,
                        help="Reservoir size (default 200).")
        sp.add_argument("--n", type=int, default=1500,
                        help="Time-series length (default 1500).")

    d = sub.add_parser("demo", help="Run the offline simulation demo.")
    common(d)
    d.set_defaults(func=cmd_demo)

    b = sub.add_parser("benchmark", help="Mackey-Glass MSE benchmark.")
    common(b)
    b.set_defaults(func=cmd_benchmark)

    i = sub.add_parser("info", help="Show version and backend availability.")
    i.set_defaults(func=cmd_info)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
