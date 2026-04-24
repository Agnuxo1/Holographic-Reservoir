"""Tests for the v1.0 reservoir model on Mackey-Glass."""

import numpy as np

from holographic_reservoir import HolographicReservoirModel, mackey_glass


def test_mackey_glass_shape():
    series = mackey_glass(n=200, rng_seed=0)
    assert series.shape == (200,)
    assert np.all(np.isfinite(series))


def test_mackey_glass_deterministic():
    a = mackey_glass(n=500, rng_seed=7)
    b = mackey_glass(n=500, rng_seed=7)
    assert np.allclose(a, b)


def test_fit_predict_shape():
    model = HolographicReservoirModel(size=80, random_seed=0)
    series = mackey_glass(n=600, rng_seed=0)
    u = series[:-1].reshape(-1, 1)
    y = series[1:]
    model.fit(u[:400], y[:400], washout=50)
    pred = model.predict(u[400:])
    assert pred.shape == (len(u) - 400,)


def test_mackey_glass_mse_threshold():
    model = HolographicReservoirModel(size=200, random_seed=0)
    mse, pred, target = model.mackey_glass_benchmark(n=1200)
    assert pred.shape == target.shape
    # One-step Mackey-Glass prediction: a small reservoir with ridge readout
    # should comfortably stay under 0.1 MSE on the normalised series.
    assert mse < 1e-1, f"MSE too high: {mse}"
