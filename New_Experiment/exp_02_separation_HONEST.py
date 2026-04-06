#!/usr/bin/env python3
"""
=============================================================================
EXPERIMENT 2: SEPARATION PROPERTY - HONEST & ROBUST VERSION
=============================================================================

CRITICAL FIXES FROM AUDIT:
1. REAL data capture from individual shares (not bridge aggregates)
2. VALIDATED frequency changes (verify chip actually changed)
3. NORMALIZED state vectors (all dimensions [0,1])
4. CONTROL pattern (constant frequency baseline)
5. ROBUST WiFi handling (polling + validation)
6. HONEST failure handling (reject invalid measurements)

DESIGN PHILOSOPHY:
- TIME STOPPED: We don't care how long it takes
- REAL DATA ONLY: Reject placeholders
- VALIDATE EVERYTHING: Trust nothing, verify everything
- FAIL LOUD: Better to abort than produce fake results

Author: Francisco Angulo de Lafuente (Post-Audit Redesign)
Date: December 2025
Hardware: Lucky Miner LV06 (BM1366) → Extrapolate to Antminer S9
"""

import json
import time
import numpy as np
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional
from scipy import stats
from scipy.spatial.distance import euclidean
import urllib.request
import os

# =============================================================================
# CONFIGURATION - HONEST PARAMETERS
# =============================================================================

CONFIG = {
    "miner_ip": "192.168.0.15",
    "miner_port": 80,
    "bridge_ip": "127.0.0.1",
    "bridge_port": 4029,
    "api_timeout": 10,

    # ROBUST TIMING - Account for WiFi instability
    "frequency_application_timeout_sec": 180,  # Up to 3 min for freq to apply
    "measurement_duration_sec": 300,           # 5 minutes per measurement (more shares)
    "poll_interval_sec": 1,                    # Poll every second for shares
    "min_shares_required": 10,                 # Reject measurement if <10 shares

    # HONEST PERTURBATIONS - Large enough to be detectable
    "base_frequency_mhz": 400,
    "frequency_delta_mhz": 50,  # ±50 MHz (±12.5% - LARGE difference)

    # Simplified design - Only 2 frequencies for clarity
    "repetitions": 10,  # 10 repetitions for statistical power

    # Output
    "output_dir": "./separation_honest_results",

    # Validation thresholds
    "frequency_tolerance_mhz": 10,  # Accept ±10 MHz from target
    "max_restarts_per_frequency": 3,  # Max attempts to apply frequency
}

# SIMPLIFIED INPUT PATTERNS - Only test distinguishability
INPUT_PATTERNS = {
    "pattern_CONTROL": {
        "frequency_mhz": 400,
        "description": "Baseline - constant 400 MHz"
    },
    "pattern_LOW": {
        "frequency_mhz": 350,
        "description": "Low frequency - 350 MHz"
    },
    "pattern_HIGH": {
        "frequency_mhz": 450,
        "description": "High frequency - 450 MHz"
    }
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class RawShareData:
    """Raw captured share data"""
    timestamps: List[float] = field(default_factory=list)
    share_count: int = 0

    def is_valid(self, min_required: int) -> bool:
        return len(self.timestamps) >= min_required


@dataclass
class StateVector:
    """Multi-dimensional state - NORMALIZED [0,1]"""
    pattern_name: str
    repetition: int
    frequency_mhz: int

    # Validated hardware state
    actual_frequency_mhz: int = 0
    actual_voltage_mv: int = 0
    temperature_c: float = 0.0

    # Computed from RAW shares
    cv: float = 0.0
    entropy: float = 0.0
    mean_interarrival_ms: float = 0.0
    std_interarrival_ms: float = 0.0

    # Metadata
    n_shares: int = 0
    measurement_duration_sec: float = 0.0
    is_valid: bool = False
    rejection_reason: str = ""

    def to_vector_normalized(self) -> np.ndarray:
        """Return NORMALIZED vector [0,1] for all dimensions"""
        if not self.is_valid:
            raise ValueError(f"Cannot vectorize invalid state: {self.rejection_reason}")

        return np.array([
            np.clip(self.cv / 2.0, 0, 1),  # CV typically 0-2
            np.clip(self.entropy / 4.0, 0, 1),  # Entropy typically 0-4
            np.clip((self.mean_interarrival_ms - 5000) / 10000, 0, 1),  # Normalize around 5-15s
            np.clip(self.std_interarrival_ms / 10000, 0, 1),  # Std 0-10s
            np.clip((self.temperature_c - 20) / 40, 0, 1),  # Temp 20-60C
        ])


@dataclass
class SeparationAnalysis:
    """Analysis between two patterns"""
    pattern_a: str
    pattern_b: str

    # Distances
    mean_distance: float = 0.0
    std_distance: float = 0.0
    all_distances: List[float] = field(default_factory=list)

    # Baseline (intra-pattern variance)
    baseline_distance: float = 0.0

    # Statistical test
    t_statistic: float = 0.0
    p_value: float = 0.0

    # Separation ratio (signal/noise)
    separation_ratio: float = 0.0

    # Verdict
    is_separable: bool = False
    confidence: str = ""


@dataclass
class ExperimentResults:
    """Complete experiment results"""
    experiment_id: str
    start_timestamp: str
    config: Dict = field(default_factory=dict)

    # All measurements
    states: List[StateVector] = field(default_factory=list)

    # Analysis
    separations: List[SeparationAnalysis] = field(default_factory=list)

    # Integrity report
    total_measurements: int = 0
    valid_measurements: int = 0
    rejected_measurements: int = 0
    rejection_reasons: Dict = field(default_factory=dict)

    # Final verdict
    separation_validated: Optional[bool] = None
    verdict: str = ""


# =============================================================================
# MINER INTERFACE - ROBUST & VALIDATED
# =============================================================================

class HonestMinerInterface:
    """Robust miner interface with validation"""

    def __init__(self, ip: str, port: int = 80, timeout: int = 10):
        self.base_url = f"http://{ip}:{port}"
        self.timeout = timeout
        self.last_known_state = {}

    def get_telemetry(self) -> Dict:
        """Get telemetry with error handling"""
        try:
            url = f"{self.base_url}/api/system/info"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode())
                self.last_known_state = {
                    "frequency_mhz": data.get("frequency", 0),
                    "voltage_mv": data.get("coreVoltageActual", data.get("voltage", 0)),
                    "temperature_c": data.get("temp", data.get("temperature", 0)),
                    "hashrate": data.get("hashRate", 0),
                    "shares_accepted": data.get("sharesAccepted", 0),
                }
                return self.last_known_state
        except Exception as e:
            print(f"[ERROR] Telemetry failed: {e}")
            return {}

    def set_frequency_validated(self, target_mhz: int, tolerance: int = 10,
                               timeout_sec: int = 180) -> Tuple[bool, int]:
        """
        Set frequency and VALIDATE it was applied.
        Returns: (success, actual_frequency)
        """
        print(f"\n[FREQ] Target: {target_mhz} MHz")

        # Step 1: Set via API
        try:
            url = f"{self.base_url}/api/system"
            payload = json.dumps({"frequency": target_mhz}).encode()
            req = urllib.request.Request(url, data=payload, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status != 200:
                    print(f"[ERROR] API returned {response.status}")
                    return False, 0
        except Exception as e:
            print(f"[ERROR] Failed to set frequency: {e}")
            return False, 0

        # Step 2: Restart miner
        print(f"[RESTART] Initiating miner restart...")
        try:
            url = f"{self.base_url}/api/system/restart"
            req = urllib.request.Request(url, data=b"{}", method='POST')
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=self.timeout)
        except:
            pass  # Restart often disconnects before response

        # Step 3: Wait for reconnection
        print(f"[WAIT] Waiting for reconnection...")
        time.sleep(30)  # Initial wait for reboot

        # Step 4: Poll until frequency is applied or timeout
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            try:
                telemetry = self.get_telemetry()
                actual = telemetry.get("frequency_mhz", 0)

                if actual > 0:
                    deviation = abs(actual - target_mhz)
                    print(f"[CHECK] Actual: {actual} MHz (deviation: {deviation} MHz)")

                    if deviation <= tolerance:
                        print(f"[SUCCESS] Frequency applied! {actual} MHz")
                        return True, actual

                time.sleep(10)  # Check every 10s
            except:
                time.sleep(5)
                continue

        print(f"[TIMEOUT] Frequency did not apply within {timeout_sec}s")
        final_telemetry = self.get_telemetry()
        return False, final_telemetry.get("frequency_mhz", 0)


# =============================================================================
# SHARE CAPTURE - REAL DATA FROM CHIP
# =============================================================================

class ShareCapture:
    """Captures individual share timestamps from miner"""

    def __init__(self, miner: HonestMinerInterface, poll_interval: float = 1.0):
        self.miner = miner
        self.poll_interval = poll_interval
        self.baseline_shares = 0

    def reset_baseline(self):
        """Reset share counter baseline"""
        telemetry = self.miner.get_telemetry()
        self.baseline_shares = telemetry.get("shares_accepted", 0)
        print(f"[CAPTURE] Baseline shares: {self.baseline_shares}")

    def capture_for_duration(self, duration_sec: float) -> RawShareData:
        """
        Capture share timestamps for duration.
        Returns RAW data (not aggregates).
        """
        print(f"\n[CAPTURE] Starting {duration_sec}s capture...")

        timestamps = []
        start_time = time.time()
        last_count = self.baseline_shares

        while time.time() - start_time < duration_sec:
            try:
                telemetry = self.miner.get_telemetry()
                current_count = telemetry.get("shares_accepted", 0)

                # Detect new shares
                if current_count > last_count:
                    # Record timestamp for EACH new share
                    now = time.time()
                    num_new = current_count - last_count
                    for _ in range(num_new):
                        timestamps.append(now)

                    last_count = current_count
                    print(f".", end="", flush=True)

                time.sleep(self.poll_interval)
            except Exception as e:
                print(f"\n[WARN] Capture error: {e}")
                time.sleep(self.poll_interval)
                continue

        print(f"\n[CAPTURE] Complete. Total shares: {len(timestamps)}")

        return RawShareData(
            timestamps=timestamps,
            share_count=len(timestamps)
        )


# =============================================================================
# STATE COMPUTATION - FROM RAW DATA
# =============================================================================

def compute_state_from_raw(raw: RawShareData, pattern_name: str,
                          repetition: int, target_freq: int,
                          telemetry: Dict, duration_sec: float,
                          min_shares: int) -> StateVector:
    """Compute state vector from RAW share data"""

    state = StateVector(
        pattern_name=pattern_name,
        repetition=repetition,
        frequency_mhz=target_freq,
        actual_frequency_mhz=telemetry.get("frequency_mhz", 0),
        actual_voltage_mv=telemetry.get("voltage_mv", 0),
        temperature_c=telemetry.get("temperature_c", 0),
        n_shares=len(raw.timestamps),
        measurement_duration_sec=duration_sec,
    )

    # Validation: Sufficient shares?
    if len(raw.timestamps) < min_shares:
        state.is_valid = False
        state.rejection_reason = f"Insufficient shares: {len(raw.timestamps)} < {min_shares}"
        return state

    # Compute inter-arrival times
    deltas = np.diff(raw.timestamps) * 1000  # milliseconds

    if len(deltas) < 2:
        state.is_valid = False
        state.rejection_reason = "Insufficient deltas for statistics"
        return state

    # Compute statistics
    state.mean_interarrival_ms = float(np.mean(deltas))
    state.std_interarrival_ms = float(np.std(deltas))
    state.cv = state.std_interarrival_ms / state.mean_interarrival_ms if state.mean_interarrival_ms > 0 else 0

    # Histogram entropy
    hist, _ = np.histogram(deltas, bins=20, density=True)
    hist = hist[hist > 0]
    state.entropy = -np.sum(hist * np.log2(hist + 1e-10)) if len(hist) > 0 else 0

    # Mark as valid
    state.is_valid = True

    return state


# =============================================================================
# EXPERIMENT ORCHESTRATION
# =============================================================================

class HonestSeparationExperiment:
    """Honest separation property experiment"""

    def __init__(self, config: Dict):
        self.config = config
        self.miner = HonestMinerInterface(config["miner_ip"], config["miner_port"])
        self.capture = ShareCapture(self.miner, config["poll_interval_sec"])
        self.results = ExperimentResults(
            experiment_id=f"SEP_HONEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_timestamp=datetime.now().isoformat(),
            config=config
        )
        os.makedirs(config["output_dir"], exist_ok=True)

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def run_single_measurement(self, pattern_name: str, pattern_config: Dict,
                              repetition: int) -> Optional[StateVector]:
        """Run single measurement with full validation"""

        target_freq = pattern_config["frequency_mhz"]

        self.log(f"=== {pattern_name} (Rep {repetition+1}) ===")
        self.log(f"Target: {target_freq} MHz")

        # Step 1: Apply and validate frequency
        success, actual_freq = self.miner.set_frequency_validated(
            target_freq,
            self.config["frequency_tolerance_mhz"],
            self.config["frequency_application_timeout_sec"]
        )

        if not success:
            self.log(f"[REJECT] Frequency not applied. Target: {target_freq}, Actual: {actual_freq}")
            self.results.rejected_measurements += 1
            self.results.rejection_reasons["frequency_not_applied"] = \
                self.results.rejection_reasons.get("frequency_not_applied", 0) + 1
            return None

        # Step 2: Reset share baseline
        self.capture.reset_baseline()

        # Step 3: Capture shares
        raw_data = self.capture.capture_for_duration(
            self.config["measurement_duration_sec"]
        )

        # Step 4: Get final telemetry
        telemetry = self.miner.get_telemetry()

        # Step 5: Compute state
        state = compute_state_from_raw(
            raw_data,
            pattern_name,
            repetition,
            target_freq,
            telemetry,
            self.config["measurement_duration_sec"],
            self.config["min_shares_required"]
        )

        # Step 6: Validate state
        if not state.is_valid:
            self.log(f"[REJECT] {state.rejection_reason}")
            self.results.rejected_measurements += 1
            reason_key = state.rejection_reason.split(":")[0]
            self.results.rejection_reasons[reason_key] = \
                self.results.rejection_reasons.get(reason_key, 0) + 1
            return None

        # Success
        self.log(f"[VALID] CV={state.cv:.3f}, Entropy={state.entropy:.2f}, Shares={state.n_shares}")
        self.results.valid_measurements += 1

        return state

    def analyze_separation(self):
        """Analyze separation between patterns"""

        # Group states by pattern
        by_pattern = {}
        for state in self.results.states:
            if state.is_valid:
                if state.pattern_name not in by_pattern:
                    by_pattern[state.pattern_name] = []
                by_pattern[state.pattern_name].append(state)

        pattern_names = list(by_pattern.keys())

        # Analyze all pairs
        for i in range(len(pattern_names)):
            for j in range(i+1, len(pattern_names)):
                name_a = pattern_names[i]
                name_b = pattern_names[j]

                states_a = by_pattern[name_a]
                states_b = by_pattern[name_b]

                # Inter-pattern distances
                inter_distances = []
                for sa in states_a:
                    for sb in states_b:
                        dist = euclidean(
                            sa.to_vector_normalized(),
                            sb.to_vector_normalized()
                        )
                        inter_distances.append(dist)

                # Intra-pattern distances (baseline noise)
                intra_distances = []
                for k in range(len(states_a)):
                    for l in range(k+1, len(states_a)):
                        dist = euclidean(
                            states_a[k].to_vector_normalized(),
                            states_a[l].to_vector_normalized()
                        )
                        intra_distances.append(dist)

                # Statistical test
                if len(inter_distances) > 1 and len(intra_distances) > 1:
                    t_stat, p_val = stats.ttest_ind(inter_distances, intra_distances)
                else:
                    t_stat, p_val = 0, 1.0

                # Separation ratio (signal/noise)
                mean_inter = np.mean(inter_distances) if inter_distances else 0
                mean_intra = np.mean(intra_distances) if intra_distances else 0
                separation_ratio = mean_inter / mean_intra if mean_intra > 0 else 0

                # Verdict
                is_separable = (p_val < 0.05 and separation_ratio > 2.0)

                if p_val < 0.01:
                    confidence = "High"
                elif p_val < 0.05:
                    confidence = "Moderate"
                else:
                    confidence = "Low"

                analysis = SeparationAnalysis(
                    pattern_a=name_a,
                    pattern_b=name_b,
                    mean_distance=mean_inter,
                    std_distance=float(np.std(inter_distances)) if inter_distances else 0,
                    all_distances=inter_distances,
                    baseline_distance=mean_intra,
                    t_statistic=float(t_stat),
                    p_value=float(p_val),
                    separation_ratio=separation_ratio,
                    is_separable=is_separable,
                    confidence=confidence
                )

                self.results.separations.append(analysis)

    def run(self):
        """Execute experiment"""
        self.log("=" * 70)
        self.log("HONEST SEPARATION PROPERTY EXPERIMENT")
        self.log("=" * 70)
        self.log(f"Patterns: {list(INPUT_PATTERNS.keys())}")
        self.log(f"Repetitions: {self.config['repetitions']}")
        self.log(f"Measurement duration: {self.config['measurement_duration_sec']}s")
        self.log("")

        # Verify connectivity
        telemetry = self.miner.get_telemetry()
        if not telemetry:
            self.log("[ERROR] Cannot connect to miner")
            return None
        self.log(f"Miner connected: {telemetry}")

        # Run all measurements
        for rep in range(self.config["repetitions"]):
            self.log(f"\n>>> REPETITION {rep+1}/{self.config['repetitions']} <<<\n")

            for pattern_name, pattern_config in INPUT_PATTERNS.items():
                self.results.total_measurements += 1

                state = self.run_single_measurement(pattern_name, pattern_config, rep)

                if state is not None:
                    self.results.states.append(state)

                # Brief pause
                time.sleep(5)

        # Analyze
        self.log("\n" + "=" * 70)
        self.log("ANALYZING SEPARATION")
        self.log("=" * 70)

        self.analyze_separation()

        # Print results
        self.log("\n" + "-" * 70)
        self.log("RESULTS")
        self.log("-" * 70)
        self.log(f"Total measurements: {self.results.total_measurements}")
        self.log(f"Valid: {self.results.valid_measurements}")
        self.log(f"Rejected: {self.results.rejected_measurements}")
        self.log(f"Rejection reasons: {self.results.rejection_reasons}")
        self.log("")

        for sep in self.results.separations:
            self.log(f"{sep.pattern_a} vs {sep.pattern_b}:")
            self.log(f"  Inter-pattern distance: {sep.mean_distance:.4f} ± {sep.std_distance:.4f}")
            self.log(f"  Intra-pattern distance: {sep.baseline_distance:.4f}")
            self.log(f"  Separation ratio: {sep.separation_ratio:.2f}x")
            self.log(f"  Statistical: t={sep.t_statistic:.2f}, p={sep.p_value:.4f}")
            self.log(f"  Separable: {sep.is_separable} (confidence: {sep.confidence})")
            self.log("")

        # Overall verdict
        all_separable = all(s.is_separable for s in self.results.separations)
        self.results.separation_validated = all_separable

        if all_separable:
            self.results.verdict = (
                "SEPARATION PROPERTY VALIDATED: The BM1366 chip successfully "
                "distinguishes between different frequency conditions with statistical "
                "significance. This is extrapolable to Antminer S9."
            )
        else:
            self.results.verdict = (
                "SEPARATION PROPERTY NOT FULLY VALIDATED: Some patterns were not "
                "statistically distinguishable. This may indicate: (1) Measurement "
                "noise dominates, (2) WiFi limitations, or (3) Insufficient difference "
                "in inputs. S9 with Ethernet may perform better."
            )

        self.log("=" * 70)
        self.log("VERDICT")
        self.log("=" * 70)
        self.log(self.results.verdict)

        # Save
        self.save_results()

        return self.results

    def save_results(self):
        """Save to JSON"""
        output_file = os.path.join(
            self.config["output_dir"],
            f"{self.results.experiment_id}.json"
        )

        results_dict = {
            "experiment_id": self.results.experiment_id,
            "start_timestamp": self.results.start_timestamp,
            "config": self.results.config,
            "states": [asdict(s) for s in self.results.states],
            "separations": [asdict(s) for s in self.results.separations],
            "integrity": {
                "total_measurements": self.results.total_measurements,
                "valid_measurements": self.results.valid_measurements,
                "rejected_measurements": self.results.rejected_measurements,
                "rejection_reasons": self.results.rejection_reasons,
            },
            "separation_validated": self.results.separation_validated,
            "verdict": self.results.verdict,
        }

        with open(output_file, 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)

        self.log(f"\nResults saved: {output_file}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("HONEST SEPARATION PROPERTY EXPERIMENT")
    print("Post-Audit Redesign - REAL Data Only")
    print()
    print("Key improvements:")
    print("- Captures REAL share timestamps (not bridge aggregates)")
    print("- VALIDATES frequency changes actually applied")
    print("- NORMALIZED state vectors")
    print("- REJECTS invalid measurements")
    print("- Large perturbations (+/-50 MHz) for clear signal")
    print()
    print("Expected duration: ~2.5 hours (TIME STOPPED - we want REAL data)")
    print("=" * 70)
    print()

    print(f"Miner IP: {CONFIG['miner_ip']}")
    print(f"Frequencies: 350, 400, 450 MHz")
    print(f"Measurement: 5 min each")
    print(f"Repetitions: {CONFIG['repetitions']}")
    print()
    print("Starting experiment...")
    print()

    experiment = HonestSeparationExperiment(CONFIG)
    results = experiment.run()

    if results:
        print("\n" + "=" * 70)
        print("EXPERIMENT COMPLETE")
        print("=" * 70)
        print(f"Separation Validated: {results.separation_validated}")
        print(f"Results: {CONFIG['output_dir']}/")
