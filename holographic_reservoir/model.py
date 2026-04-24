"""Clean v1.0 reservoir model with ridge-regression readout.

This sits on top of the legacy :class:`VeselovLayer` expander graph but
does not require the older ASIC-driven ``reservoir.py`` code path. It is
self-contained, pure-NumPy, and runs in well under 30 s on CPU for the
demo benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from .backends import HardwareBackend, SimulatedASICBackend


def mackey_glass(
    n: int = 2000,
    beta: float = 0.2,
    gamma: float = 0.1,
    tau: int = 17,
    n_exp: int = 10,
    x0: float = 1.2,
    rng_seed: int = 0,
) -> np.ndarray:
    """Generate a deterministic Mackey-Glass time series."""
    rng = np.random.default_rng(rng_seed)
    history = np.full(tau + 1, x0) + 1e-3 * rng.standard_normal(tau + 1)
    xs = list(history)
    for _ in range(n):
        x_t = xs[-1]
        x_tau = xs[-tau - 1]
        x_next = x_t + beta * x_tau / (1.0 + x_tau**n_exp) - gamma * x_t
        xs.append(x_next)
    return np.asarray(xs[tau + 1 :], dtype=np.float64)


@dataclass
class HolographicReservoirModel:
    """Minimal reservoir + ridge-regression readout.

    Parameters
    ----------
    size:
        Reservoir dimension.
    input_dim:
        Input feature dimension.
    spectral_radius:
        Target spectral radius of the recurrent matrix.
    leak:
        Leak rate ``alpha`` for the state update.
    ridge:
        Tikhonov regularisation strength for the readout.
    backend:
        A :class:`HardwareBackend`. Defaults to the offline simulation.
    random_seed:
        Seed for reservoir weight initialisation.
    """

    size: int = 200
    input_dim: int = 1
    spectral_radius: float = 0.9
    leak: float = 0.3
    ridge: float = 1e-6
    backend: Optional[HardwareBackend] = None
    random_seed: int = 0

    def __post_init__(self) -> None:
        if self.backend is None:
            self.backend = SimulatedASICBackend(random_seed=self.random_seed)
        rng = np.random.default_rng(self.random_seed)

        # Input matrix
        self.W_in = rng.uniform(-0.5, 0.5, size=(self.size, self.input_dim))

        # Sparse recurrent matrix scaled to the requested spectral radius.
        density = 0.1
        W = rng.standard_normal((self.size, self.size))
        mask = rng.random((self.size, self.size)) < density
        W = W * mask
        # Inject a small amount of backend-derived entropy so different
        # backends/seeds yield detectably different dynamics without
        # breaking determinism.
        frames = self.backend.mine(b"init", cycles=max(1, self.size // 8))
        entropy = np.concatenate(
            [np.frombuffer(f, dtype=np.uint8) for f in frames]
        ).astype(np.float64)
        entropy = (entropy[: self.size] / 127.5 - 1.0) * 0.05
        np.fill_diagonal(W, np.diag(W) + entropy)

        radii = np.max(np.abs(np.linalg.eigvals(W)))
        if radii > 0:
            W *= self.spectral_radius / radii
        self.W = W
        self.W_out: Optional[np.ndarray] = None

    # --- core dynamics -------------------------------------------------
    def _collect_states(self, u: np.ndarray) -> np.ndarray:
        """Run the reservoir over input sequence ``u`` (T, input_dim)."""
        T = u.shape[0]
        X = np.zeros((T, self.size), dtype=np.float64)
        x = np.zeros(self.size, dtype=np.float64)
        for t in range(T):
            pre = self.W_in @ u[t] + self.W @ x
            x = (1.0 - self.leak) * x + self.leak * np.tanh(pre)
            X[t] = x
        return X

    def fit(
        self,
        u: np.ndarray,
        y: np.ndarray,
        washout: int = 100,
    ) -> "HolographicReservoirModel":
        u = np.atleast_2d(u.astype(np.float64))
        if u.shape[1] != self.input_dim:
            u = u.reshape(-1, self.input_dim)
        y = y.astype(np.float64).reshape(-1)
        X = self._collect_states(u)
        Xw = X[washout:]
        yw = y[washout:]
        # Ridge: (X^T X + lambda I)^-1 X^T y
        A = Xw.T @ Xw + self.ridge * np.eye(self.size)
        b = Xw.T @ yw
        self.W_out = np.linalg.solve(A, b)
        self._last_state = X[-1]
        return self

    def predict(self, u: np.ndarray) -> np.ndarray:
        if self.W_out is None:
            raise RuntimeError("Model not fitted; call fit() first.")
        u = np.atleast_2d(u.astype(np.float64))
        if u.shape[1] != self.input_dim:
            u = u.reshape(-1, self.input_dim)
        X = self._collect_states(u)
        return X @ self.W_out

    def mackey_glass_benchmark(
        self,
        n: int = 1500,
        train_frac: float = 0.7,
        washout: int = 100,
    ) -> Tuple[float, np.ndarray, np.ndarray]:
        """Train on Mackey-Glass 1-step prediction and return MSE."""
        series = mackey_glass(n=n + 1, rng_seed=self.random_seed)
        u = series[:-1].reshape(-1, 1)
        y = series[1:]
        split = int(len(u) * train_frac)
        self.fit(u[:split], y[:split], washout=washout)
        pred = self.predict(u[split:])
        mse = float(np.mean((pred - y[split:]) ** 2))
        return mse, pred, y[split:]
