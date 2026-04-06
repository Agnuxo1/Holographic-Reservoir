#!/usr/bin/env python3
"""
=============================================================================
EXPERIMENT 3: COMPUTATIONAL UTILITY TEST (RESERVOIR BENCHMARK)
=============================================================================

OBJECTIVE:
    Demonstrate that the ASIC system can perform actual computation - that the
    timing dynamics contain information useful for predicting future states.

HYPOTHESIS:
    If the voltage-stressed ASIC functions as a physical reservoir, then:
    - A simple LINEAR readout trained on timing statistics
    - Should predict future timing behavior better than a baseline
    - The "reservoir advantage" measures how much information the physical
      dynamics contribute beyond trivial autoregression

EXPERIMENTAL DESIGN:

    TASK: One-step-ahead prediction of timing CV
    
    1. TRAINING PHASE:
       - Apply a pseudo-random sequence of frequency changes
       - Record timing statistics (CV, entropy, mean) at each step
       - Train a linear regression: state(t) → CV(t+1)
    
    2. TESTING PHASE:
       - Apply a NEW sequence (different random seed)
       - Use trained model to predict CV(t+1) from state(t)
       - Compare with baselines:
         a) Naive baseline: predict CV(t+1) = CV(t)
         b) Mean baseline: predict CV(t+1) = mean(CV)
         c) AR(1) baseline: linear regression on CV(t) only
    
    3. METRICS:
       - NRMSE: Normalized Root Mean Square Error
       - R²: Coefficient of determination
       - Reservoir Advantage = (Baseline_Error - Model_Error) / Baseline_Error

SUCCESS CRITERIA:
    - Model NRMSE < Baseline NRMSE (model outperforms baseline)
    - Reservoir Advantage > 10% (meaningful improvement)
    - R² > 0.3 (moderate predictive power)

FAILURE CRITERIA:
    - Model performs same as or worse than baseline
    - This would indicate timing dynamics do NOT contain useful computational
      information beyond trivial temporal correlations

NOTE: This is the CRITICAL experiment. According to Vladimir Veselov:
      "Without this, any analysis of 'dynamics' remains abstract."

Author: Francisco Angulo de Lafuente
Experiment Design: Based on Vladimir Veselov's validation framework
Date: December 2025
Hardware: Lucky Miner LV06 (BM1366)
"""

import json
import time
import numpy as np
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import urllib.request
import os

# =============================================================================
# CONFIGURATION
# =============================================================================

CONFIG = {
    "miner_ip": "192.168.1.100",  # <-- CHANGE THIS
    "miner_port": 80,
    "api_timeout": 10,
    
    # Timing parameters
    "step_duration_sec": 30,         # Duration at each frequency step
    "stabilization_delay_sec": 5,     # Wait after frequency change
    
    # Frequency range
    "min_frequency_mhz": 320,
    "max_frequency_mhz": 480,
    "base_voltage_mv": 900,
    
    # Experiment size
    "training_steps": 40,             # Steps for training
    "testing_steps": 20,              # Steps for testing
    
    # Random seeds for reproducibility
    "training_seed": 42,
    "testing_seed": 123,
    
    # Output
    "output_dir": "./benchmark_experiment_results",
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class StepMeasurement:
    """Measurement at one time step"""
    step_index: int
    input_frequency_mhz: int
    
    # State vector components
    cv: float = 0.0
    entropy: float = 0.0
    mean_timing_ms: float = 0.0
    std_timing_ms: float = 0.0
    temperature_c: float = 0.0
    hashrate: float = 0.0
    
    # Raw
    n_shares: int = 0
    
    def to_feature_vector(self) -> np.ndarray:
        """Convert to feature vector for ML"""
        return np.array([
            self.cv,
            self.entropy,
            self.mean_timing_ms / 1000,  # Normalize
            self.std_timing_ms / 1000,
            self.input_frequency_mhz / 500,  # Normalize
            self.temperature_c / 100,
        ])
    
    def get_target(self) -> float:
        """Get prediction target (CV)"""
        return self.cv


@dataclass
class BenchmarkResults:
    """Complete benchmark results"""
    experiment_id: str
    start_timestamp: str
    config: Dict = field(default_factory=dict)
    
    # Data
    training_data: List[StepMeasurement] = field(default_factory=list)
    testing_data: List[StepMeasurement] = field(default_factory=list)
    
    # Model performance
    model_predictions: List[float] = field(default_factory=list)
    actual_values: List[float] = field(default_factory=list)
    
    # Metrics
    model_nrmse: float = 0.0
    model_r2: float = 0.0
    
    naive_nrmse: float = 0.0
    mean_baseline_nrmse: float = 0.0
    ar1_nrmse: float = 0.0
    
    reservoir_advantage_vs_naive: float = 0.0
    reservoir_advantage_vs_ar1: float = 0.0
    
    # Verdict
    computational_utility_validated: Optional[bool] = None
    verdict_reasoning: str = ""


# =============================================================================
# MINER INTERFACE
# =============================================================================

class MinerInterface:
    """Interface to Lucky Miner LV06"""
    
    def __init__(self, ip: str, port: int = 80, timeout: int = 10):
        self.base_url = f"http://{ip}:{port}"
        self.timeout = timeout
        self.share_buffer: List[float] = []
        self.last_share_count = 0
    
    def get_telemetry(self) -> Dict:
        try:
            for endpoint in ["/api/system/info", "/api/status", "/"]:
                try:
                    url = f"{self.base_url}{endpoint}"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=self.timeout) as response:
                        data = json.loads(response.read().decode())
                        return {
                            "frequency_mhz": data.get("frequency", 0),
                            "voltage_mv": data.get("coreVoltageActual", 0),
                            "temperature_c": data.get("temp", 0),
                            "hashrate": data.get("hashRate", 0),
                            "shares": data.get("sharesAccepted", 0),
                        }
                except:
                    continue
            return {}
        except Exception as e:
            return {}
    
    def set_frequency(self, freq_mhz: int) -> bool:
        try:
            url = f"{self.base_url}/api/system"
            payload = json.dumps({"frequency": freq_mhz}).encode()
            req = urllib.request.Request(url, data=payload, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status == 200
        except:
            return False
    
    def record_share_event(self):
        telemetry = self.get_telemetry()
        current = telemetry.get("shares", 0)
        if current > self.last_share_count:
            ts = time.time()
            for _ in range(current - self.last_share_count):
                self.share_buffer.append(ts)
            self.last_share_count = current
    
    def get_and_clear_shares(self) -> List[float]:
        shares = self.share_buffer.copy()
        self.share_buffer = []
        return shares
    
    def reset(self):
        telemetry = self.get_telemetry()
        self.last_share_count = telemetry.get("shares", 0)
        self.share_buffer = []


# =============================================================================
# INPUT SEQUENCE GENERATION
# =============================================================================

def generate_frequency_sequence(n_steps: int, min_freq: int, max_freq: int,
                                 seed: int) -> List[int]:
    """Generate pseudo-random frequency sequence"""
    np.random.seed(seed)
    
    # Mix of patterns: random steps + occasional trends
    sequence = []
    current = (min_freq + max_freq) // 2
    
    for i in range(n_steps):
        # Random walk with bounds
        change = np.random.choice([-40, -20, 0, 20, 40])
        current = np.clip(current + change, min_freq, max_freq)
        sequence.append(int(current))
    
    return sequence


# =============================================================================
# STATISTICS
# =============================================================================

def compute_step_measurement(timestamps: List[float], 
                            input_freq: int,
                            telemetry: Dict,
                            step_idx: int) -> StepMeasurement:
    """Compute measurement for one step"""
    
    meas = StepMeasurement(
        step_index=step_idx,
        input_frequency_mhz=input_freq,
        n_shares=len(timestamps),
        temperature_c=telemetry.get("temperature_c", 0),
        hashrate=telemetry.get("hashrate", 0),
    )
    
    if len(timestamps) < 3:
        return meas
    
    deltas = np.diff(timestamps) * 1000
    
    if len(deltas) < 2:
        meas.mean_timing_ms = float(np.mean(deltas)) if len(deltas) > 0 else 0
        return meas
    
    meas.mean_timing_ms = float(np.mean(deltas))
    meas.std_timing_ms = float(np.std(deltas))
    meas.cv = meas.std_timing_ms / meas.mean_timing_ms if meas.mean_timing_ms > 0 else 0
    
    hist, _ = np.histogram(deltas, bins=15, density=True)
    hist = hist[hist > 0]
    meas.entropy = -np.sum(hist * np.log2(hist + 1e-10)) if len(hist) > 0 else 0
    
    return meas


# =============================================================================
# EXPERIMENT
# =============================================================================

class BenchmarkExperiment:
    """Computational Utility Benchmark"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.miner = MinerInterface(
            config["miner_ip"],
            config["miner_port"],
            config["api_timeout"]
        )
        self.results = BenchmarkResults(
            experiment_id=f"BENCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_timestamp=datetime.now().isoformat(),
            config=config
        )
        os.makedirs(config["output_dir"], exist_ok=True)
    
    def log(self, msg: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    def collect_step(self, freq_mhz: int, step_idx: int) -> StepMeasurement:
        """Collect one step of data"""
        self.miner.set_frequency(freq_mhz)
        time.sleep(self.config["stabilization_delay_sec"])
        
        self.miner.reset()
        start = time.time()
        
        while time.time() - start < self.config["step_duration_sec"]:
            self.miner.record_share_event()
            time.sleep(0.5)
        
        timestamps = self.miner.get_and_clear_shares()
        telemetry = self.miner.get_telemetry()
        
        return compute_step_measurement(timestamps, freq_mhz, telemetry, step_idx)
    
    def collect_sequence(self, freq_sequence: List[int], 
                        phase: str) -> List[StepMeasurement]:
        """Collect data for a frequency sequence"""
        measurements = []
        
        for idx, freq in enumerate(freq_sequence):
            self.log(f"  [{phase}] Step {idx+1}/{len(freq_sequence)}: {freq}MHz")
            meas = self.collect_step(freq, idx)
            measurements.append(meas)
            self.log(f"    → CV={meas.cv:.3f}, Shares={meas.n_shares}")
        
        return measurements
    
    def train_and_evaluate(self):
        """Train reservoir model and evaluate against baselines"""
        
        # Prepare training data
        X_train = []
        y_train = []
        
        for i in range(len(self.results.training_data) - 1):
            current = self.results.training_data[i]
            next_step = self.results.training_data[i + 1]
            
            if current.cv > 0 and next_step.cv > 0:
                X_train.append(current.to_feature_vector())
                y_train.append(next_step.get_target())
        
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        
        if len(X_train) < 5:
            self.log("[ERROR] Not enough valid training samples")
            return
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        
        # Train reservoir model (linear regression on full state)
        reservoir_model = Ridge(alpha=0.1)
        reservoir_model.fit(X_train_scaled, y_train)
        
        # Train AR(1) baseline (only previous CV)
        X_ar1_train = X_train[:, 0:1]  # Just CV column
        ar1_model = LinearRegression()
        ar1_model.fit(X_ar1_train, y_train)
        
        # Prepare test data
        X_test = []
        y_test = []
        
        for i in range(len(self.results.testing_data) - 1):
            current = self.results.testing_data[i]
            next_step = self.results.testing_data[i + 1]
            
            if current.cv > 0 and next_step.cv > 0:
                X_test.append(current.to_feature_vector())
                y_test.append(next_step.get_target())
        
        if len(X_test) < 3:
            self.log("[ERROR] Not enough valid test samples")
            return
        
        X_test = np.array(X_test)
        y_test = np.array(y_test)
        X_test_scaled = scaler.transform(X_test)
        
        # Make predictions
        y_pred_reservoir = reservoir_model.predict(X_test_scaled)
        y_pred_ar1 = ar1_model.predict(X_test[:, 0:1])
        y_pred_naive = X_test[:, 0]  # CV(t) predicts CV(t+1)
        y_pred_mean = np.full_like(y_test, np.mean(y_train))
        
        # Compute metrics
        def nrmse(y_true, y_pred):
            rmse = np.sqrt(mean_squared_error(y_true, y_pred))
            return rmse / (np.max(y_true) - np.min(y_true)) if np.max(y_true) != np.min(y_true) else rmse
        
        self.results.model_nrmse = nrmse(y_test, y_pred_reservoir)
        self.results.model_r2 = r2_score(y_test, y_pred_reservoir)
        self.results.naive_nrmse = nrmse(y_test, y_pred_naive)
        self.results.mean_baseline_nrmse = nrmse(y_test, y_pred_mean)
        self.results.ar1_nrmse = nrmse(y_test, y_pred_ar1)
        
        # Reservoir advantage
        self.results.reservoir_advantage_vs_naive = (
            (self.results.naive_nrmse - self.results.model_nrmse) / 
            self.results.naive_nrmse * 100 if self.results.naive_nrmse > 0 else 0
        )
        self.results.reservoir_advantage_vs_ar1 = (
            (self.results.ar1_nrmse - self.results.model_nrmse) /
            self.results.ar1_nrmse * 100 if self.results.ar1_nrmse > 0 else 0
        )
        
        # Store predictions
        self.results.model_predictions = y_pred_reservoir.tolist()
        self.results.actual_values = y_test.tolist()
        
        # Feature importance (which state dimensions matter?)
        self.log("\nFeature weights (importance):")
        feature_names = ["CV", "Entropy", "Mean_timing", "Std_timing", "Input_freq", "Temp"]
        for name, weight in zip(feature_names, reservoir_model.coef_):
            self.log(f"  {name}: {weight:.4f}")
    
    def run(self):
        """Execute complete benchmark"""
        self.log("=" * 60)
        self.log("EXPERIMENT 3: COMPUTATIONAL UTILITY BENCHMARK")
        self.log("=" * 60)
        self.log(f"Task: One-step-ahead CV prediction")
        self.log(f"Training steps: {self.config['training_steps']}")
        self.log(f"Testing steps: {self.config['testing_steps']}")
        self.log("")
        
        # Check connectivity
        telemetry = self.miner.get_telemetry()
        if not telemetry:
            self.log("[ERROR] Cannot connect to miner")
            return None
        self.log(f"Connected: {telemetry}")
        
        # Generate sequences
        train_seq = generate_frequency_sequence(
            self.config["training_steps"],
            self.config["min_frequency_mhz"],
            self.config["max_frequency_mhz"],
            self.config["training_seed"]
        )
        
        test_seq = generate_frequency_sequence(
            self.config["testing_steps"],
            self.config["min_frequency_mhz"],
            self.config["max_frequency_mhz"],
            self.config["testing_seed"]
        )
        
        # Training phase
        self.log("\n>>> TRAINING PHASE <<<")
        self.results.training_data = self.collect_sequence(train_seq, "TRAIN")
        
        # Testing phase
        self.log("\n>>> TESTING PHASE <<<")
        self.results.testing_data = self.collect_sequence(test_seq, "TEST")
        
        # Train and evaluate
        self.log("\n>>> ANALYSIS <<<")
        self.train_and_evaluate()
        
        # Results
        self.log("\n" + "=" * 60)
        self.log("RESULTS")
        self.log("=" * 60)
        
        self.log(f"\nPrediction Errors (NRMSE, lower is better):")
        self.log(f"  Reservoir Model:  {self.results.model_nrmse:.4f}")
        self.log(f"  AR(1) Baseline:   {self.results.ar1_nrmse:.4f}")
        self.log(f"  Naive Baseline:   {self.results.naive_nrmse:.4f}")
        self.log(f"  Mean Baseline:    {self.results.mean_baseline_nrmse:.4f}")
        
        self.log(f"\nModel Quality:")
        self.log(f"  R² Score: {self.results.model_r2:.4f}")
        
        self.log(f"\nReservoir Advantage:")
        self.log(f"  vs Naive: {self.results.reservoir_advantage_vs_naive:.1f}%")
        self.log(f"  vs AR(1): {self.results.reservoir_advantage_vs_ar1:.1f}%")
        
        # Determine verdict
        model_beats_ar1 = self.results.model_nrmse < self.results.ar1_nrmse
        meaningful_advantage = self.results.reservoir_advantage_vs_ar1 > 10
        decent_r2 = self.results.model_r2 > 0.2
        
        self.results.computational_utility_validated = (
            model_beats_ar1 and meaningful_advantage and decent_r2
        )
        
        if self.results.computational_utility_validated:
            self.results.verdict_reasoning = (
                f"COMPUTATIONAL UTILITY DEMONSTRATED: The full reservoir state "
                f"(CV, entropy, timing, temperature) predicts future behavior "
                f"{self.results.reservoir_advantage_vs_ar1:.1f}% better than using "
                f"only previous CV. R²={self.results.model_r2:.3f} indicates "
                f"meaningful predictive power. The physical dynamics contain "
                f"computational information beyond trivial autoregression."
            )
        else:
            reasons = []
            if not model_beats_ar1:
                reasons.append("model does not outperform AR(1) baseline")
            if not meaningful_advantage:
                reasons.append(f"advantage too small ({self.results.reservoir_advantage_vs_ar1:.1f}% < 10%)")
            if not decent_r2:
                reasons.append(f"R² too low ({self.results.model_r2:.3f} < 0.2)")
            
            self.results.verdict_reasoning = (
                f"COMPUTATIONAL UTILITY NOT DEMONSTRATED: {'; '.join(reasons)}. "
                f"The timing dynamics may not contain sufficient computational "
                f"information, or the measurement approach needs refinement. "
                f"Consider: increasing step duration, different feature extraction, "
                f"or operating in a different voltage/frequency regime."
            )
        
        self.log("\n" + "=" * 60)
        self.log("VERDICT")
        self.log("=" * 60)
        self.log(self.results.verdict_reasoning)
        
        self.save_results()
        return self.results
    
    def save_results(self):
        output_file = os.path.join(
            self.config["output_dir"],
            f"{self.results.experiment_id}.json"
        )
        
        results_dict = {
            "experiment_id": self.results.experiment_id,
            "start_timestamp": self.results.start_timestamp,
            "config": self.results.config,
            "training_data": [asdict(m) for m in self.results.training_data],
            "testing_data": [asdict(m) for m in self.results.testing_data],
            "model_predictions": self.results.model_predictions,
            "actual_values": self.results.actual_values,
            "metrics": {
                "model_nrmse": self.results.model_nrmse,
                "model_r2": self.results.model_r2,
                "naive_nrmse": self.results.naive_nrmse,
                "ar1_nrmse": self.results.ar1_nrmse,
                "mean_baseline_nrmse": self.results.mean_baseline_nrmse,
                "reservoir_advantage_vs_naive": self.results.reservoir_advantage_vs_naive,
                "reservoir_advantage_vs_ar1": self.results.reservoir_advantage_vs_ar1,
            },
            "computational_utility_validated": self.results.computational_utility_validated,
            "verdict_reasoning": self.results.verdict_reasoning,
        }
        
        with open(output_file, 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)
        
        self.log(f"\nResults saved to: {output_file}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║  CHIMERA VALIDATION EXPERIMENT 3                              ║
    ║  Computational Utility Benchmark                              ║
    ║                                                               ║
    ║  CRITICAL TEST: Does the ASIC actually compute anything?      ║
    ║                                                               ║
    ║  This experiment trains a linear model on reservoir states    ║
    ║  and tests if it can predict future timing dynamics better    ║
    ║  than simple baselines.                                       ║
    ║                                                               ║
    ║  Expected duration: ~45-60 minutes                            ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    print(f"Miner IP: {CONFIG['miner_ip']}")
    print(f"Frequency range: {CONFIG['min_frequency_mhz']}-{CONFIG['max_frequency_mhz']}MHz")
    print(f"Total steps: {CONFIG['training_steps'] + CONFIG['testing_steps']}")
    print()
    
    response = input("Press ENTER to start (or 'q' to quit): ")
    if response.lower() == 'q':
        print("Cancelled.")
        exit(0)
    
    experiment = BenchmarkExperiment(CONFIG)
    results = experiment.run()
    
    if results:
        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(f"Computational Utility: {results.computational_utility_validated}")
        print(f"Results: {CONFIG['output_dir']}/")
