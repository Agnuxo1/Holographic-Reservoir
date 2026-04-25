# Holographic Reservoir Computing Framework (Simulation + Optional ASIC Hardware)

[![PyPI](https://img.shields.io/pypi/v/holographic-reservoir.svg)](https://pypi.org/project/holographic-reservoir/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

A pure-Python reservoir computing framework built on a bipartite expander
graph (the "Veselov layer") with a pluggable hardware backend. The default
backend is a deterministic SHA-256 based **simulation** — no network, no
ASIC, no external services. Optional AxeOS ASIC hardware is supported but
strictly opt-in.

## Install

```bash
pip install holographic-reservoir
```

Optional hardware extras:

```bash
pip install "holographic-reservoir[hardware]"
```

## Quickstart (three commands, no hardware)

```bash
holographic-reservoir info
holographic-reservoir demo
holographic-reservoir benchmark --size 200 --n 1500
```

Programmatic use:

```python
from holographic_reservoir import HolographicReservoirModel, mackey_glass

series = mackey_glass(n=1501, rng_seed=0)
u, y = series[:-1].reshape(-1, 1), series[1:]

model = HolographicReservoirModel(size=200, random_seed=0)
model.fit(u[:1000], y[:1000], washout=100)
mse = ((model.predict(u[1000:]) - y[1000:]) ** 2).mean()
print(f"MSE = {mse:.3e}")
```

## Honest scope

- **Hardware backend is optional.** The default is a pure-Python
  simulation using deterministic SHA-256 entropy; it runs anywhere Python
  3.10+ runs and needs only NumPy. The AxeOS backend is activated only
  when you pass `--hardware axeos --endpoint IP:PORT` and connects to a
  real miner only in that case.
- **The paper in `docs/papers/` is a research preprint, NOT a
  peer-reviewed IEEE publication.** Treat it as an author preprint /
  technical report. No peer-review status should be inferred from its
  formatting.
- **Research artefacts** (legacy experiment scripts, HTML drafts,
  hardware telemetry reports) are preserved in `archive/` and
  `experiments/` for transparency and are not part of the v1.0 API.

## Architecture

```
holographic_reservoir/
├── backends.py   # HardwareBackend, SimulatedASICBackend, AxeOSBackend
├── model.py      # HolographicReservoirModel + Mackey-Glass generator
├── cli.py        # demo / benchmark / info subcommands
└── core/         # Legacy VeselovLayer expander graph (backcompat shim)
```

## CLI

| Command | Purpose |
|---|---|
| `holographic-reservoir info` | Show version and backend availability. |
| `holographic-reservoir demo` | Offline Mackey-Glass demo, prints MSE. |
| `holographic-reservoir benchmark` | Mackey-Glass MSE benchmark. |

Flags (all subcommands): `--hardware {simulation,axeos}`,
`--endpoint IP:PORT`, `--seed`, `--size`, `--n`.

## Author and credits

Copyright 2026 **Francisco Angulo de Lafuente** (`agnuxo1@gmail.com`).
Released under the Apache License 2.0.

Contains legacy research code from the CHIMERA / HRC experiments by the
same author. Co-authors and collaborators credited in individual research
artefacts under `docs/papers/` retain their attribution.

## License

Apache-2.0. See [`LICENSE`](LICENSE).

---

## Related projects

Part of the [@Agnuxo1](https://github.com/Agnuxo1) v1.0.0 open-source catalog (April 2026).

**AgentBoot constellation** — agents and research loops
- [AgentBoot](https://github.com/Agnuxo1/AgentBoot) — Conversational AI agent for bare-metal hardware detection and OS install.
- [autoresearch-nano](https://github.com/Agnuxo1/autoresearch) — nanoGPT-based autonomous ML research loop.
- [The Living Agent](https://github.com/Agnuxo1/The-Living-Agent) — 16x16 Chess-Grid autonomous research agent.
- [benchclaw-integrations](https://github.com/Agnuxo1/benchclaw-integrations) — Agent-framework adapters for the BenchClaw API.

**CHIMERA / neuromorphic constellation** — GPU-native scientific computing
- [NeuroCHIMERA](https://github.com/Agnuxo1/NeuroCHIMERA__GPU-Native_Neuromorphic_Consciousness) — GPU-native neuromorphic framework on OpenGL compute shaders.
- [ASIC-RAG-CHIMERA](https://github.com/Agnuxo1/ASIC-RAG-CHIMERA) — GPU simulation of a SHA-256 hash engine wired into a RAG pipeline.
- [QESN-MABe](https://github.com/Agnuxo1/QESN_MABe_V2_REPO) — Quantum-inspired Echo State Network on a 2D lattice (classical).
- [ARC2-CHIMERA](https://github.com/Agnuxo1/ARC2_CHIMERA) — Research PoC: OpenGL primitives for symbolic reasoning.
- [Quantum-GPS](https://github.com/Agnuxo1/Quantum-GPS-Unified-Navigation-System) — Quantum-inspired GPU navigator (classical Eikonal solver).
