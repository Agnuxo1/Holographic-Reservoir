#!/usr/bin/env python3
"""
=============================================================================
EXPERIMENT 2: SEPARATION PROPERTY TEST
=============================================================================

OBJECTIVE:
    Demonstrate that the ASIC system can distinguish between different inputs
    by mapping them to separable states in a high-dimensional space.

HYPOTHESIS:
    If the voltage-stressed ASIC functions as a physical reservoir, then:
    - Different operating conditions (close but distinct inputs)
    - Should produce DISTINGUISHABLE state vectors (timing statistics)
    - The separation in state space should be GREATER than input difference
    - The system should "amplify" small input differences

EXPERIMENTAL DESIGN:
    
    Apply a sequence of CLOSE but DISTINCT operating conditions:
    
    Input Pattern A: [400MHz] → [410MHz] → [400MHz] → [390MHz] → [400MHz]
    Input Pattern B: [400MHz] → [390MHz] → [400MHz] → [410MHz] → [400MHz]
    
    These patterns have the same average but different sequences.
    
    For each step:
    - Record multi-dimensional state vector:
      * CV of inter-arrival times
      * Histogram entropy
      * Mean timing
      * Variance of timing
      * Temperature
    
    Then compute:
    - Trajectory in state space for Pattern A
    - Trajectory in state space for Pattern B
    - Distance between trajectories

SUCCESS CRITERIA:
    - State-space distance between patterns >> input difference
    - Trajectories are statistically distinguishable (t-test p < 0.05)
    - Separation ratio > 2.0 (state distance / input distance)

FAILURE CRITERIA:
    - Trajectories overlap significantly
    - Cannot distinguish patterns statistically
    - This would indicate poor separation → limited reservoir utility

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
from scipy import stats
from scipy.spatial.distance import euclidean, cosine
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
    "step_duration_sec": 45,        # Duration at each frequency step
    "measurement_window_sec": 30,    # Window for collecting statistics
    "stabilization_delay_sec": 10,   # Wait after frequency change
    
    # Base operating point
    "base_frequency_mhz": 400,
    "base_voltage_mv": 900,
    
    # Perturbation size (small = harder test)
    "frequency_delta_mhz": 20,  # ±20 MHz perturbations
    
    # Number of repetitions
    "repetitions": 5,
    
    # Output
    "output_dir": "./separation_experiment_results",
}

# Define input patterns (sequences of frequency offsets from base)
# Pattern A and B have same mean but different temporal structure
INPUT_PATTERNS = {
    "pattern_A": {
        "sequence": [0, +1, 0, -1, 0],  # Multiplied by frequency_delta
        "description": "Up-then-down pattern"
    },
    "pattern_B": {
        "sequence": [0, -1, 0, +1, 0],  # Multiplied by frequency_delta
        "description": "Down-then-up pattern"
    },
    "pattern_C": {
        "sequence": [0, +1, +1, -1, -1],  # Different structure
        "description": "Two-up-two-down pattern"
    }
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class StateVector:
    """Multi-dimensional state measurement"""
    step_index: int
    frequency_mhz: int
    
    # State dimensions
    cv: float = 0.0
    entropy: float = 0.0
    mean_timing_ms: float = 0.0
    std_timing_ms: float = 0.0
    temperature_c: float = 0.0
    
    # Raw data
    n_shares: int = 0
    timestamps: List[float] = field(default_factory=list)
    
    def to_vector(self) -> np.ndarray:
        """Convert to numpy array for distance calculations"""
        return np.array([
            self.cv,
            self.entropy,
            self.mean_timing_ms / 1000,  # Normalize to seconds
            self.std_timing_ms / 1000,
            self.temperature_c / 100,    # Normalize
        ])


@dataclass 
class PatternTrajectory:
    """Complete trajectory for one input pattern"""
    pattern_name: str
    repetition: int
    states: List[StateVector] = field(default_factory=list)
    
    def to_matrix(self) -> np.ndarray:
        """Convert trajectory to matrix (steps × dimensions)"""
        return np.array([s.to_vector() for s in self.states])


@dataclass
class SeparationAnalysis:
    """Analysis of separation between patterns"""
    pattern_a: str
    pattern_b: str
    
    # Distances
    mean_trajectory_distance: float = 0.0
    euclidean_distances: List[float] = field(default_factory=list)
    cosine_similarities: List[float] = field(default_factory=list)
    
    # Input distance (for comparison)
    input_distance: float = 0.0
    
    # Separation ratio
    separation_ratio: float = 0.0
    
    # Statistical test
    t_statistic: float = 0.0
    p_value: float = 0.0
    
    # Verdict
    separable: bool = False


@dataclass
class SeparationExperimentResults:
    """Complete experiment results"""
    experiment_id: str
    start_timestamp: str
    config: Dict = field(default_factory=dict)
    
    # All trajectories
    trajectories: List[PatternTrajectory] = field(default_factory=list)
    
    # Pairwise separation analysis
    separation_analyses: List[SeparationAnalysis] = field(default_factory=list)
    
    # Overall verdict
    separation_validated: Optional[bool] = None
    verdict_reasoning: str = ""


# =============================================================================
# MINER INTERFACE (same as Experiment 1)
# =============================================================================

class MinerInterface:
    """Interface to Lucky Miner LV06 via AxeOS API"""
    
    def __init__(self, ip: str, port: int = 80, timeout: int = 10):
        self.base_url = f"http://{ip}:{port}"
        self.timeout = timeout
        self.share_buffer: List[float] = []
        self.last_share_count = 0
        
    def get_telemetry(self) -> Dict:
        """Get detailed telemetry"""
        try:
            for endpoint in ["/api/system/info", "/api/status", "/"]:
                try:
                    url = f"{self.base_url}{endpoint}"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=self.timeout) as response:
                        data = json.loads(response.read().decode())
                        return {
                            "frequency_mhz": data.get("frequency", 0),
                            "voltage_mv": data.get("coreVoltageActual", 
                                         data.get("voltage", 0)),
                            "temperature_c": data.get("temp", 
                                           data.get("temperature", 0)),
                            "hashrate": data.get("hashRate", 0),
                            "shares": data.get("sharesAccepted", 
                                     data.get("shares", 0)),
                        }
                except:
                    continue
            return {}
        except Exception as e:
            print(f"[WARNING] Failed to get telemetry: {e}")
            return {}
    
    def set_frequency(self, freq_mhz: int) -> bool:
        """Set mining frequency"""
        try:
            url = f"{self.base_url}/api/system"
            payload = json.dumps({"frequency": freq_mhz}).encode()
            req = urllib.request.Request(url, data=payload, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status == 200
        except Exception as e:
            print(f"[WARNING] Failed to set frequency: {e}")
            return False
    
    def record_share_event(self) -> Optional[float]:
        """Record a share event timestamp"""
        telemetry = self.get_telemetry()
        current_shares = telemetry.get("shares", 0)
        
        if current_shares > self.last_share_count:
            timestamp = time.time()
            num_new = current_shares - self.last_share_count
            self.last_share_count = current_shares
            for _ in range(num_new):
                self.share_buffer.append(timestamp)
            return timestamp
        return None
    
    def get_and_clear_shares(self) -> List[float]:
        """Get all recorded share timestamps and clear buffer"""
        shares = self.share_buffer.copy()
        self.share_buffer = []
        return shares
    
    def reset_share_counter(self):
        """Reset the share tracking"""
        telemetry = self.get_telemetry()
        self.last_share_count = telemetry.get("shares", 0)
        self.share_buffer = []


# =============================================================================
# STATISTICS
# =============================================================================

def compute_state_vector(timestamps: List[float], 
                        frequency_mhz: int,
                        temperature_c: float,
                        step_index: int) -> StateVector:
    """Compute state vector from timing data"""
    
    state = StateVector(
        step_index=step_index,
        frequency_mhz=frequency_mhz,
        n_shares=len(timestamps),
        timestamps=timestamps,
        temperature_c=temperature_c,
    )
    
    if len(timestamps) < 3:
        return state
    
    deltas = np.diff(timestamps) * 1000  # ms
    
    if len(deltas) < 2:
        state.mean_timing_ms = float(np.mean(deltas)) if len(deltas) > 0 else 0
        return state
    
    state.mean_timing_ms = float(np.mean(deltas))
    state.std_timing_ms = float(np.std(deltas))
    state.cv = state.std_timing_ms / state.mean_timing_ms if state.mean_timing_ms > 0 else 0
    
    # Histogram entropy
    hist, _ = np.histogram(deltas, bins=15, density=True)
    hist = hist[hist > 0]
    state.entropy = -np.sum(hist * np.log2(hist + 1e-10)) if len(hist) > 0 else 0
    
    return state


def compute_trajectory_distance(traj_a: PatternTrajectory, 
                                traj_b: PatternTrajectory) -> Tuple[float, List[float]]:
    """Compute distance between two trajectories"""
    
    mat_a = traj_a.to_matrix()
    mat_b = traj_b.to_matrix()
    
    # Ensure same length
    min_len = min(len(mat_a), len(mat_b))
    mat_a = mat_a[:min_len]
    mat_b = mat_b[:min_len]
    
    # Point-wise Euclidean distances
    distances = [euclidean(mat_a[i], mat_b[i]) for i in range(min_len)]
    
    # Mean trajectory distance
    mean_distance = np.mean(distances)
    
    return mean_distance, distances


def compute_input_distance(pattern_a: List[int], pattern_b: List[int], 
                          delta_mhz: int) -> float:
    """Compute normalized distance between input patterns"""
    vec_a = np.array(pattern_a) * delta_mhz
    vec_b = np.array(pattern_b) * delta_mhz
    return euclidean(vec_a, vec_b) / delta_mhz  # Normalize


# =============================================================================
# EXPERIMENT
# =============================================================================

class SeparationExperiment:
    """Separation Property Experiment"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.miner = MinerInterface(
            config["miner_ip"],
            config["miner_port"],
            config["api_timeout"]
        )
        self.results = SeparationExperimentResults(
            experiment_id=f"SEP_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_timestamp=datetime.now().isoformat(),
            config=config
        )
        os.makedirs(config["output_dir"], exist_ok=True)
    
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def collect_state(self, duration_sec: float, 
                     frequency_mhz: int,
                     step_index: int) -> StateVector:
        """Collect state vector at current operating point"""
        self.miner.reset_share_counter()
        timestamps = []
        start_time = time.time()
        
        while time.time() - start_time < duration_sec:
            self.miner.record_share_event()
            time.sleep(0.5)
        
        timestamps = self.miner.get_and_clear_shares()
        telemetry = self.miner.get_telemetry()
        
        return compute_state_vector(
            timestamps,
            frequency_mhz,
            telemetry.get("temperature_c", 0),
            step_index
        )
    
    def run_pattern(self, pattern_name: str, pattern_config: Dict,
                   repetition: int) -> PatternTrajectory:
        """Execute one input pattern and record trajectory"""
        
        trajectory = PatternTrajectory(
            pattern_name=pattern_name,
            repetition=repetition
        )
        
        sequence = pattern_config["sequence"]
        delta = self.config["frequency_delta_mhz"]
        base_freq = self.config["base_frequency_mhz"]
        
        self.log(f"  Pattern {pattern_name}: {pattern_config['description']}")
        self.log(f"  Sequence: {[base_freq + s*delta for s in sequence]}")
        
        for step_idx, offset in enumerate(sequence):
            target_freq = base_freq + offset * delta
            
            self.log(f"    Step {step_idx+1}/{len(sequence)}: {target_freq}MHz")
            
            # Set frequency
            self.miner.set_frequency(target_freq)
            time.sleep(self.config["stabilization_delay_sec"])
            
            # Collect state
            state = self.collect_state(
                self.config["measurement_window_sec"],
                target_freq,
                step_idx
            )
            trajectory.states.append(state)
            
            self.log(f"      → CV={state.cv:.3f}, Entropy={state.entropy:.2f}, "
                    f"Shares={state.n_shares}")
        
        return trajectory
    
    def analyze_separation(self) -> List[SeparationAnalysis]:
        """Analyze separation between all pattern pairs"""
        analyses = []
        
        # Group trajectories by pattern
        by_pattern = {}
        for traj in self.results.trajectories:
            if traj.pattern_name not in by_pattern:
                by_pattern[traj.pattern_name] = []
            by_pattern[traj.pattern_name].append(traj)
        
        pattern_names = list(by_pattern.keys())
        
        # Compare all pairs
        for i in range(len(pattern_names)):
            for j in range(i+1, len(pattern_names)):
                name_a = pattern_names[i]
                name_b = pattern_names[j]
                
                trajs_a = by_pattern[name_a]
                trajs_b = by_pattern[name_b]
                
                # Compute distances for all repetition pairs
                all_distances = []
                for ta in trajs_a:
                    for tb in trajs_b:
                        mean_dist, _ = compute_trajectory_distance(ta, tb)
                        all_distances.append(mean_dist)
                
                # Compute intra-pattern distances (for comparison)
                intra_distances_a = []
                for k in range(len(trajs_a)):
                    for l in range(k+1, len(trajs_a)):
                        mean_dist, _ = compute_trajectory_distance(trajs_a[k], trajs_a[l])
                        intra_distances_a.append(mean_dist)
                
                # Input distance
                input_dist = compute_input_distance(
                    INPUT_PATTERNS[name_a]["sequence"],
                    INPUT_PATTERNS[name_b]["sequence"],
                    self.config["frequency_delta_mhz"]
                )
                
                # Statistical test: are inter-pattern distances > intra-pattern?
                if len(intra_distances_a) > 1 and len(all_distances) > 1:
                    t_stat, p_val = stats.ttest_ind(all_distances, intra_distances_a)
                else:
                    t_stat, p_val = 0, 1.0
                
                # Separation ratio
                mean_inter = np.mean(all_distances) if all_distances else 0
                separation_ratio = mean_inter / input_dist if input_dist > 0 else 0
                
                analysis = SeparationAnalysis(
                    pattern_a=name_a,
                    pattern_b=name_b,
                    mean_trajectory_distance=mean_inter,
                    euclidean_distances=all_distances,
                    input_distance=input_dist,
                    separation_ratio=separation_ratio,
                    t_statistic=float(t_stat),
                    p_value=float(p_val),
                    separable=(separation_ratio > 1.5 and p_val < 0.1)
                )
                analyses.append(analysis)
        
        return analyses
    
    def run(self):
        """Execute the complete experiment"""
        self.log("=" * 60)
        self.log("EXPERIMENT 2: SEPARATION PROPERTY TEST")
        self.log("=" * 60)
        self.log(f"Base frequency: {self.config['base_frequency_mhz']}MHz")
        self.log(f"Perturbation: ±{self.config['frequency_delta_mhz']}MHz")
        self.log(f"Repetitions: {self.config['repetitions']}")
        self.log("")
        
        # Check connectivity
        telemetry = self.miner.get_telemetry()
        if not telemetry:
            self.log("[ERROR] Cannot connect to miner.")
            return None
        self.log(f"Miner connected. Current: {telemetry}")
        
        # Run all patterns
        for rep in range(self.config["repetitions"]):
            self.log(f"\n>>> REPETITION {rep+1}/{self.config['repetitions']} <<<")
            
            for pattern_name, pattern_config in INPUT_PATTERNS.items():
                trajectory = self.run_pattern(pattern_name, pattern_config, rep)
                self.results.trajectories.append(trajectory)
                time.sleep(5)  # Brief pause between patterns
        
        # Analyze separation
        self.log("\n" + "=" * 60)
        self.log("ANALYZING SEPARATION...")
        self.log("=" * 60)
        
        self.results.separation_analyses = self.analyze_separation()
        
        # Print results
        self.log("\n" + "-" * 60)
        self.log("PAIRWISE SEPARATION RESULTS")
        self.log("-" * 60)
        
        all_separable = True
        for analysis in self.results.separation_analyses:
            self.log(f"\n{analysis.pattern_a} vs {analysis.pattern_b}:")
            self.log(f"  Input distance: {analysis.input_distance:.3f}")
            self.log(f"  State-space distance: {analysis.mean_trajectory_distance:.3f}")
            self.log(f"  Separation ratio: {analysis.separation_ratio:.2f}x")
            self.log(f"  Statistical test: t={analysis.t_statistic:.2f}, p={analysis.p_value:.3f}")
            self.log(f"  Separable: {analysis.separable}")
            
            if not analysis.separable:
                all_separable = False
        
        # Overall verdict
        self.results.separation_validated = all_separable
        
        if all_separable:
            self.results.verdict_reasoning = (
                "SEPARATION PROPERTY SUPPORTED: The system successfully maps "
                "different input patterns to distinguishable state-space trajectories. "
                "The separation ratio > 1.5 indicates the system amplifies input "
                "differences, which is a key requirement for reservoir computing."
            )
        else:
            self.results.verdict_reasoning = (
                "SEPARATION PROPERTY NOT FULLY SUPPORTED: Some input patterns "
                "produce overlapping state trajectories. This may indicate: "
                "(1) The perturbation size is too small, (2) Measurement noise "
                "dominates the signal, or (3) The system does not have sufficient "
                "separation capability for reservoir computing."
            )
        
        self.log("\n" + "=" * 60)
        self.log("VERDICT")
        self.log("=" * 60)
        self.log(self.results.verdict_reasoning)
        
        # Save results
        self.save_results()
        
        return self.results
    
    def save_results(self):
        """Save results to JSON"""
        output_file = os.path.join(
            self.config["output_dir"],
            f"{self.results.experiment_id}.json"
        )
        
        results_dict = {
            "experiment_id": self.results.experiment_id,
            "start_timestamp": self.results.start_timestamp,
            "config": self.results.config,
            "trajectories": [
                {
                    "pattern_name": t.pattern_name,
                    "repetition": t.repetition,
                    "states": [asdict(s) for s in t.states]
                }
                for t in self.results.trajectories
            ],
            "separation_analyses": [asdict(a) for a in self.results.separation_analyses],
            "separation_validated": self.results.separation_validated,
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
    ║  CHIMERA VALIDATION EXPERIMENT 2                              ║
    ║  Separation Property Test                                     ║
    ║                                                               ║
    ║  This experiment tests whether the ASIC can distinguish       ║
    ║  between different input patterns - a key reservoir property. ║
    ║                                                               ║
    ║  Expected duration: ~30-40 minutes                            ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    print(f"Miner IP: {CONFIG['miner_ip']}")
    print(f"Base frequency: {CONFIG['base_frequency_mhz']}MHz")
    print(f"Perturbation: ±{CONFIG['frequency_delta_mhz']}MHz")
    print()
    
    response = input("Press ENTER to start experiment (or 'q' to quit): ")
    if response.lower() == 'q':
        print("Experiment cancelled.")
        exit(0)
    
    experiment = SeparationExperiment(CONFIG)
    results = experiment.run()
    
    if results:
        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(f"Separation Validated: {results.separation_validated}")
        print(f"See detailed results in: {CONFIG['output_dir']}/")
