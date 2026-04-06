# CHIMERA Validation Experiments

## Overview

These three experiments are designed to **validate or refute** the hypothesis that voltage-stressed Bitcoin mining ASICs can function as physical reservoir computing substrates.

Based on the validation framework proposed by **Vladimir Veselov** (MIET), each experiment tests a fundamental property required for reservoir computing.

---

## Experiment Summary

| # | Experiment | Tests | Duration | Key Metric |
|---|------------|-------|----------|------------|
| 1 | **Echo State Property** | Fading Memory | ~20 min | CV variance across trials |
| 2 | **Separation Property** | Input Distinguishability | ~35 min | Trajectory distance ratio |
| 3 | **Computational Utility** | Actual Computing | ~50 min | Reservoir advantage % |

---

## Requirements

### Hardware
- Lucky Miner LV06 (BM1366 chip)
- Network connection to miner
- Stable power supply
- Ambient temperature control (if possible)

### Software
```bash
pip install numpy scipy scikit-learn
```

### Configuration
**IMPORTANT**: Edit the `CONFIG` dict in each script:
```python
CONFIG = {
    "miner_ip": "192.168.0.15",  # <-- YOUR MINER IP
    ...
}
```

---

## Experiment 1: Echo State Property (ESP)

### Purpose
Tests if the system has **"fading memory"** - that states converge regardless of prehistory.

### Method
1. Apply different "prehistory" conditions (hot/cold/stressed)
2. Then apply SAME test condition
3. Measure if timing statistics converge

### Expected Results

**If ESP HOLDS (reservoir valid):**
```
CV values after convergence:
  Trial A (hot): 1.12 ± 0.08
  Trial B (cold): 1.15 ± 0.07
  Trial C (stressed): 1.10 ± 0.09
  
ANOVA p-value: 0.67 (> 0.05) → No significant difference
VERDICT: ESP SUPPORTED ✓
```

**If ESP FAILS (not a valid reservoir):**
```
CV values after convergence:
  Trial A (hot): 1.45 ± 0.05
  Trial B (cold): 0.92 ± 0.06
  Trial C (stressed): 1.78 ± 0.12
  
ANOVA p-value: 0.002 (< 0.05) → Significant difference persists
VERDICT: ESP NOT SUPPORTED ✗
```

### Run
```bash
python exp_01_echo_state_property.py
```

---

## Experiment 2: Separation Property

### Purpose
Tests if different inputs produce **distinguishable** state-space trajectories.

### Method
1. Apply pattern A: [base → +20MHz → base → -20MHz → base]
2. Apply pattern B: [base → -20MHz → base → +20MHz → base]
3. Record multi-dimensional state at each step
4. Compute trajectory distances

### Expected Results

**If SEPARATION HOLDS:**
```
Pattern A vs B:
  Input distance: 2.83 (normalized)
  State-space distance: 5.21
  Separation ratio: 1.84x (> 1.5) ✓
  
The system AMPLIFIES input differences.
VERDICT: SEPARATION SUPPORTED ✓
```

**If SEPARATION FAILS:**
```
Pattern A vs B:
  Input distance: 2.83
  State-space distance: 1.92
  Separation ratio: 0.68x (< 1.0) ✗
  
State trajectories overlap - cannot distinguish inputs.
VERDICT: SEPARATION NOT SUPPORTED ✗
```

### Run
```bash
python exp_02_separation_property.py
```

---

## Experiment 3: Computational Utility (CRITICAL)

### Purpose
Tests if the timing dynamics contain **computational information** - can a simple model predict future states?

### Method
1. **Training**: Random frequency sequence → record states
2. **Testing**: Different random sequence → predict CV(t+1) from state(t)
3. **Compare** with baselines:
   - Naive: CV(t+1) = CV(t)
   - AR(1): Linear regression on CV only
   - Mean: CV(t+1) = average

### Expected Results

**If COMPUTATIONAL UTILITY EXISTS:**
```
Prediction Errors (NRMSE):
  Reservoir Model: 0.182
  AR(1) Baseline:  0.245
  Naive Baseline:  0.267
  
R² Score: 0.41
Reservoir Advantage vs AR(1): 25.7%

The full state vector provides ADDITIONAL information
beyond simple autoregression.
VERDICT: COMPUTATIONAL UTILITY DEMONSTRATED ✓
```

**If NO COMPUTATIONAL UTILITY:**
```
Prediction Errors (NRMSE):
  Reservoir Model: 0.251
  AR(1) Baseline:  0.248  (baseline is BETTER!)
  Naive Baseline:  0.267
  
R² Score: 0.12
Reservoir Advantage vs AR(1): -1.2%

Adding more state dimensions does NOT help prediction.
The dynamics contain no useful computational information.
VERDICT: COMPUTATIONAL UTILITY NOT DEMONSTRATED ✗
```

### Run
```bash
python exp_03_computational_utility.py
```

---

## Interpreting Results

### All Three Pass ✓ ✓ ✓
```
CONCLUSION: Strong evidence that the ASIC functions as a physical reservoir.
The system has:
  - Fading memory (ESP)
  - Input separation capability
  - Computational utility

Proceed with more complex benchmarks (Mackey-Glass, NARMA-10).
```

### Some Pass, Some Fail
```
CONCLUSION: Mixed results require investigation.

Common patterns:
- ESP passes, Separation fails → System too damped, try lower voltage
- Separation passes, Utility fails → Readout method needs refinement
- ESP fails → Convergence time too short, or system is NOT a reservoir
```

### All Three Fail ✗ ✗ ✗
```
CONCLUSION: The ASIC does NOT function as a physical reservoir
under the tested conditions.

This is a VALID scientific result. Either:
1. The hypothesis is wrong (ASICs are not suitable)
2. The operating regime needs adjustment
3. The measurement method is inadequate

Report these results honestly in the paper.
```

---

## Output Files

Each experiment produces a JSON file with complete data:

```
esp_experiment_results/
  ESP_20251219_143022.json

separation_experiment_results/
  SEP_20251219_151547.json

benchmark_experiment_results/
  BENCH_20251219_162033.json
```

These files contain:
- All raw measurements
- Computed statistics
- Analysis results
- Final verdict with reasoning

**Keep these files** - they are your evidence for the paper.

---

## Tips for Honest Results

1. **Don't cherry-pick**: Run each experiment multiple times, report ALL results
2. **Document conditions**: Temperature, time of day, pool difficulty
3. **Report failures**: A negative result is still a result
4. **Check for artifacts**: Network latency, OS scheduling, power supply noise
5. **Vary parameters**: If one regime fails, try another before concluding

---

## For the Paper

After running experiments, you can report:

```
Section: Experimental Validation

We conducted three experiments to test the fundamental properties
required for physical reservoir computing:

1. Echo State Property: [PASS/FAIL]
   - CV variance across prehistories: X.XX
   - ANOVA p-value: X.XX
   
2. Separation Property: [PASS/FAIL]
   - Mean separation ratio: X.XX
   - Statistical significance: p = X.XX
   
3. Computational Utility: [PASS/FAIL]
   - Model NRMSE: X.XXX
   - Reservoir advantage: XX.X%
   - R² score: X.XX

[Discuss implications honestly]
```

---

## Contact

- **Francisco Angulo de Lafuente** - Lead Researcher
- **Vladimir Veselov** - Theoretical Framework
- **Richard Goodman** - Code Review

---

*"The goal of science is not to prove we are right, but to find out what is true."*
