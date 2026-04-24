"""Offline demo: reservoir + ridge-regression readout on Mackey-Glass.

Runs in well under 30 s on a modern CPU. No hardware, no network.
"""

from __future__ import annotations

import time

import numpy as np

from holographic_reservoir import (
    HolographicReservoirModel,
    SimulatedASICBackend,
    mackey_glass,
)


def main() -> None:
    print("Holographic Reservoir v1.0 — offline simulation demo")
    print("-" * 56)

    backend = SimulatedASICBackend(random_seed=0)
    print(f"backend           : {backend.name}")

    series = mackey_glass(n=1501, rng_seed=0)
    u = series[:-1].reshape(-1, 1)
    y = series[1:]

    model = HolographicReservoirModel(size=200, backend=backend, random_seed=0)

    t0 = time.perf_counter()
    model.fit(u[:1000], y[:1000], washout=100)
    pred = model.predict(u[1000:])
    dt = time.perf_counter() - t0

    mse = float(np.mean((pred - y[1000:]) ** 2))
    print(f"reservoir size    : {model.size}")
    print(f"train / test      : 1000 / {len(pred)} steps")
    print(f"wall time         : {dt:.2f} s")
    print(f"Mackey-Glass MSE  : {mse:.6e}")
    print("Done.")


if __name__ == "__main__":
    main()
