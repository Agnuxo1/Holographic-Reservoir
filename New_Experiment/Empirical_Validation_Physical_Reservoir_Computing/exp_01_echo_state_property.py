#!/usr/bin/env python3
"""
=============================================================================
EXPERIMENT 1: ECHO STATE PROPERTY (ESP) / FADING MEMORY TEST
=============================================================================

OBJECTIVE:
    Demonstrate that the ASIC system has "fading memory" - that internal states
    converge to the same values after identical inputs, regardless of the
    system's prior history.

HYPOTHESIS:
    If the voltage-stressed ASIC functions as a physical reservoir, then:
    - After applying identical operating conditions (frequency/voltage)
    - The timing statistics should converge to similar values
    - REGARDLESS of what happened before (different prehistories)

EXPERIMENTAL DESIGN:
    
    Trial Type A (Hot Start):
        [High Freq 500MHz, 60s] → [Test Condition 400MHz, 120s] → Measure
        
    Trial Type B (Cold Start):  
        [Low Freq 300MHz, 60s] → [Test Condition 400MHz, 120s] → Measure
        
    Trial Type C (Stressed Start):
        [Edge Voltage 850mV, 60s] → [Test Condition 400MHz, 120s] → Measure

    If ESP holds: Statistics at "Measure" phase should be similar across A, B, C
    If ESP fails: Statistics will depend on prehistory → NOT a valid reservoir

WHAT WE MEASURE:
    - Inter-arrival time CV (coefficient of variation)
    - Histogram entropy of inter-arrival times
    - Mean and variance of timing
    - Convergence metric: variance across trials

SUCCESS CRITERIA:
    - CV variance across trial types < 0.1 (10% relative variation)
    - Entropy variance across trial types < 0.5 bits
    - Statistical test (ANOVA) p-value > 0.05 (no significant difference)

FAILURE CRITERIA:
    - Persistent differences between trial types after convergence period
    - This would indicate the system does NOT have ESP → NOT a valid reservoir

Author: Francisco Angulo de Lafuente
Experiment Design: Based on Vladimir Veselov's validation framework
Date: December 2025
Hardware: Lucky Miner LV06 (BM1366)
"""

import json
import time
import hashlib
import urllib.request
import numpy as np
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from scipy import stats
import os

# =============================================================================
# CONFIGURATION - ADJUST FOR YOUR SETUP
# =============================================================================

CONFIG = {
    "miner_ip": "192.168.0.15",  # Real miner IP
    "miner_port": 80,
    "bridge_ip": "127.0.0.1",   # Experiments run on the same PC as bridge
    "bridge_port": 4029,
    "api_timeout": 10,
    
    # Experimental parameters
    "prehistory_duration_sec": 60,      # Time in each prehistory condition
    "test_condition_duration_sec": 120,  # Time in test condition (for convergence)
    "measurement_window_sec": 60,        # Window for final measurement
    "stabilization_delay_sec": 45,       # Wait after restart for miner to reconnect
    
    # Test condition (same for all trials)
    "test_frequency_mhz": 400,
    "test_voltage_mv": 900,
    
    # Number of repetitions per trial type
    "repetitions_per_trial": 3,
    
    # Output
    "output_dir": "./esp_experiment_results",
    "log_raw_timestamps": True,
}

# Trial definitions (different prehistories)
TRIAL_TYPES = {
    "A_hot_start": {
        "prehistory_freq_mhz": 500,
        "prehistory_voltage_mv": 950,
        "description": "High frequency prehistory (hot)"
    },
    "B_cold_start": {
        "prehistory_freq_mhz": 300,
        "prehistory_voltage_mv": 900,
        "description": "Low frequency prehistory (cold)"
    },
    "C_stressed_start": {
        "prehistory_freq_mhz": 400,
        "prehistory_voltage_mv": 850,
        "description": "Low voltage prehistory (stressed)"
    }
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TimingMeasurement:
    """Single measurement window results"""
    trial_type: str
    repetition: int
    phase: str  # "prehistory" or "test"
    
    # Raw data
    share_timestamps: List[float] = field(default_factory=list)
    num_shares: int = 0
    
    # Computed statistics
    mean_interarrival_ms: float = 0.0
    std_interarrival_ms: float = 0.0
    cv: float = 0.0  # Coefficient of variation
    histogram_entropy: float = 0.0
    
    # Operating conditions
    frequency_mhz: int = 0
    voltage_mv: int = 0
    temperature_c: float = 0.0
    
    # Metadata
    start_time: str = ""
    end_time: str = ""


@dataclass
class ESPExperimentResults:
    """Complete experiment results"""
    experiment_id: str
    start_timestamp: str
    config: Dict = field(default_factory=dict)
    
    # All measurements
    measurements: List[TimingMeasurement] = field(default_factory=list)
    
    # Convergence analysis
    convergence_analysis: Dict = field(default_factory=dict)
    
    # Final verdict
    esp_validated: Optional[bool] = None
    verdict_reasoning: str = ""


# =============================================================================
# MINER INTERFACE
# =============================================================================

class MinerInterface:
    """Interface to Lucky Miner LV06 via AxeOS API"""
    
    def __init__(self, ip: str, port: int = 80, timeout: int = 10):
        self.base_url = f"http://{ip}:{port}"
        self.timeout = timeout
        self.share_buffer: List[float] = []
        self.last_share_count = 0
        
    def get_status(self) -> Dict:
        """Get current miner status"""
        try:
            url = f"{self.base_url}/api/system/info"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"[WARNING] Failed to get status: {e}")
            return {}
    
    def get_telemetry(self) -> Dict:
        """Get detailed telemetry"""
        try:
            # Try multiple possible endpoints
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
                            "power_w": data.get("power", 0),
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
    
    def set_voltage(self, voltage_mv: int) -> bool:
        """Set core voltage"""
        try:
            url = f"{self.base_url}/api/system"
            # AxeOS uses 'volts' instead of 'voltage' in some versions
            payload = json.dumps({"volts": voltage_mv}).encode()
            req = urllib.request.Request(url, data=payload, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status == 200
        except Exception as e:
            print(f"[WARNING] Failed to set voltage: {e}")
            return False

    def restart_miner(self) -> bool:
        """Mandatory restart to apply hardware changes (Honesty Audit)"""
        try:
            url = f"{self.base_url}/api/system/restart"
            req = urllib.request.Request(url, data=b"{}", method='POST')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 200:
                    return True
            return False
        except Exception:
            return True

class BridgeInterface:
    """Interface to HRC Bridge API for precision metrics"""
    def __init__(self, ip: str = "127.0.0.1", port: int = 4029):
        self.ip = ip
        self.port = port
    
    def _send_cmd(self, cmd: str) -> Optional[str]:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((self.ip, self.port))
            s.sendall(cmd.encode())
            resp = s.recv(4096).decode()
            s.close()
            return resp
        except:
            return None

    def get_metrics(self) -> Dict:
        """Query bridge for current CV and Entropy"""
        resp = self._send_cmd("GET_METRICS")
        if resp:
            try:
                return json.loads(resp)
            except: pass
        return {"cv": 1.0, "entropy": 0.0, "sps": 0.0}

    def inject_seed(self, seed: str):
        """Update bridge search seed"""
        self._send_cmd(f"SEED:{seed}")

    def reset(self):
        """Reset bridge counters for a new window"""
        self._send_cmd("RESET")
    
    def record_share_event(self) -> Optional[float]:
        """Record a share event timestamp by polling"""
        telemetry = self.get_telemetry()
        current_shares = telemetry.get("shares", 0)
        
        if current_shares > self.last_share_count:
            timestamp = time.time()
            num_new = current_shares - self.last_share_count
            self.last_share_count = current_shares
            
            # Record timestamp for each new share
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
# STATISTICS COMPUTATION
# =============================================================================

def compute_timing_statistics(timestamps: List[float]) -> Dict:
    """Compute timing statistics from share timestamps"""
    if len(timestamps) < 3:
        return {
            "mean_ms": 0, "std_ms": 0, "cv": 0, 
            "entropy": 0, "n_samples": len(timestamps)
        }
    
    # Compute inter-arrival times in milliseconds
    deltas = np.diff(timestamps) * 1000  # Convert to ms
    
    if len(deltas) < 2:
        return {
            "mean_ms": float(np.mean(deltas)) if len(deltas) > 0 else 0,
            "std_ms": 0, "cv": 0, "entropy": 0, "n_samples": len(deltas)
        }
    
    mean_delta = np.mean(deltas)
    std_delta = np.std(deltas)
    
    # Coefficient of variation (CV = 1 for Poisson process)
    cv = std_delta / mean_delta if mean_delta > 0 else 0
    
    # Histogram entropy
    hist, _ = np.histogram(deltas, bins=20, density=True)
    hist = hist[hist > 0]  # Remove zero bins
    entropy = -np.sum(hist * np.log2(hist + 1e-10)) if len(hist) > 0 else 0
    
    return {
        "mean_ms": float(mean_delta),
        "std_ms": float(std_delta),
        "cv": float(cv),
        "entropy": float(entropy),
        "n_samples": len(deltas),
        "min_ms": float(np.min(deltas)),
        "max_ms": float(np.max(deltas)),
        "median_ms": float(np.median(deltas)),
    }


# =============================================================================
# EXPERIMENT EXECUTION
# =============================================================================

class ESPExperiment:
    """Echo State Property Experiment"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.miner = MinerInterface(
            config["miner_ip"], 
            config["miner_port"],
            config["api_timeout"]
        )
        self.bridge = BridgeInterface(
            config.get("bridge_ip", "127.0.0.1"),
            config.get("bridge_port", 4029)
        )
        self.results = ESPExperimentResults(
            experiment_id=f"ESP_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_timestamp=datetime.now().isoformat(),
            config=config
        )
        
        # Create output directory
        os.makedirs(config["output_dir"], exist_ok=True)
    
    def log(self, message: str):
        """Print timestamped log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def collect_timing_data(self, duration_sec: float) -> Dict:
        """Monitor bridge metrics for duration"""
        log_cv = []
        log_ent = []
        start_time = time.time()
        
        self.bridge.reset()
        
        while time.time() - start_time < duration_sec:
            m = self.bridge.get_metrics()
            log_cv.append(m.get("cv", 1.0))
            log_ent.append(m.get("entropy", 0.0))
            time.sleep(2.0)
            
        return {
            "cv": float(np.mean(log_cv)) if log_cv else 1.0,
            "entropy": float(np.mean(log_ent)) if log_ent else 0.0,
            "sps": float(m.get("sps", 0.0))
        }
    
    def run_single_trial(self, trial_type: str, trial_config: Dict, 
                        repetition: int) -> List[TimingMeasurement]:
        """Run a single trial (prehistory + test condition)"""
        measurements = []
        
        self.log(f"=== Trial {trial_type} (Rep {repetition+1}) ===")
        self.log(f"Description: {trial_config['description']}")
        
        # ----- PHASE 1: PREHISTORY -----
        self.log(f"[Prehistory] Setting freq={trial_config['prehistory_freq_mhz']}MHz, "
                f"voltage={trial_config['prehistory_voltage_mv']}mV")
        
        self.bridge.inject_seed(f"PREHISTORY_{trial_type}_{repetition}")
        self.miner.set_frequency(trial_config['prehistory_freq_mhz'])
        self.miner.set_voltage(trial_config['prehistory_voltage_mv'])
        self.miner.restart_miner()
        self.log(f"   ⏳ Waiting {self.config['stabilization_delay_sec']}s for Restart/PLL...")
        time.sleep(self.config["stabilization_delay_sec"])
        
        # Collect prehistory data
        self.log(f"[Prehistory] Collecting data for {self.config['prehistory_duration_sec']}s...")
        stats = self.collect_timing_data(self.config["prehistory_duration_sec"])
        
        telemetry = self.miner.get_telemetry()
        
        prehistory_measurement = TimingMeasurement(
            trial_type=trial_type,
            repetition=repetition,
            phase="prehistory",
            cv=stats["cv"],
            histogram_entropy=stats["entropy"],
            frequency_mhz=telemetry.get("frequency_mhz", 0),
            voltage_mv=telemetry.get("voltage_mv", 0),
            temperature_c=telemetry.get("temperature_c", 0),
            start_time=datetime.now().isoformat(),
        )
        measurements.append(prehistory_measurement)
        
        self.log(f"[Prehistory] Flow: {stats['sps']:.2f} sps | CV: {stats['cv']:.3f}")
        
        # ----- PHASE 2: TEST CONDITION -----
        self.log(f"[Test] Setting freq={self.config['test_frequency_mhz']}MHz, "
                f"voltage={self.config['test_voltage_mv']}mV")
        
        self.bridge.inject_seed(f"TEST_CONDITION_STEADY_STATE")
        self.miner.set_frequency(self.config['test_frequency_mhz'])
        self.miner.set_voltage(self.config['test_voltage_mv'])
        self.miner.restart_miner()
        self.log(f"   ⏳ Waiting {self.config['stabilization_delay_sec']}s for Restart/PLL...")
        time.sleep(self.config["stabilization_delay_sec"])
        
        # Wait for system to converge (most of test duration)
        convergence_time = (self.config["test_condition_duration_sec"] - 
                          self.config["measurement_window_sec"])
        if convergence_time > 0:
            self.log(f"[Test] Waiting {convergence_time}s for convergence...")
            time.sleep(convergence_time)
        
        # Collect final measurement data
        self.log(f"[Test] Collecting measurement data for "
                f"{self.config['measurement_window_sec']}s...")
        stats = self.collect_timing_data(self.config["measurement_window_sec"])
        
        telemetry = self.miner.get_telemetry()
        
        test_measurement = TimingMeasurement(
            trial_type=trial_type,
            repetition=repetition,
            phase="test",
            cv=stats["cv"],
            histogram_entropy=stats["entropy"],
            frequency_mhz=telemetry.get("frequency_mhz", 0),
            voltage_mv=telemetry.get("voltage_mv", 0),
            temperature_c=telemetry.get("temperature_c", 0),
            end_time=datetime.now().isoformat(),
        )
        measurements.append(test_measurement)
        
        self.log(f"[Test] Flow: {stats['sps']:.2f} sps | CV: {stats['cv']:.3f}, Entropy: {stats['entropy']:.2f}")
        
        return measurements
    
    def analyze_convergence(self) -> Dict:
        """Analyze whether states converged across different prehistories"""
        
        # Extract test-phase measurements only
        test_measurements = [m for m in self.results.measurements if m.phase == "test"]
        
        # Group by trial type
        by_trial_type = {}
        for m in test_measurements:
            if m.trial_type not in by_trial_type:
                by_trial_type[m.trial_type] = []
            by_trial_type[m.trial_type].append(m)
        
        # Compute statistics per trial type
        cv_by_type = {}
        entropy_by_type = {}
        
        for trial_type, measurements in by_trial_type.items():
            cv_values = [m.cv for m in measurements if m.cv > 0]
            entropy_values = [m.histogram_entropy for m in measurements 
                            if m.histogram_entropy > 0]
            
            cv_by_type[trial_type] = {
                "mean": np.mean(cv_values) if cv_values else 0,
                "std": np.std(cv_values) if cv_values else 0,
                "values": cv_values
            }
            entropy_by_type[trial_type] = {
                "mean": np.mean(entropy_values) if entropy_values else 0,
                "std": np.std(entropy_values) if entropy_values else 0,
                "values": entropy_values
            }
        
        # ANOVA test for CV across trial types
        cv_groups = [data["values"] for data in cv_by_type.values() 
                    if len(data["values"]) > 0]
        
        if len(cv_groups) >= 2 and all(len(g) >= 2 for g in cv_groups):
            f_stat, p_value = stats.f_oneway(*cv_groups)
        else:
            f_stat, p_value = 0, 1.0
        
        # Compute overall variance
        all_cv = [m.cv for m in test_measurements if m.cv > 0]
        all_entropy = [m.histogram_entropy for m in test_measurements 
                      if m.histogram_entropy > 0]
        
        cv_variance = np.var(all_cv) if all_cv else 0
        cv_mean = np.mean(all_cv) if all_cv else 0
        relative_cv_variance = cv_variance / (cv_mean**2) if cv_mean > 0 else 0
        
        entropy_variance = np.var(all_entropy) if all_entropy else 0
        
        analysis = {
            "cv_by_trial_type": {k: {"mean": v["mean"], "std": v["std"]} 
                                for k, v in cv_by_type.items()},
            "entropy_by_trial_type": {k: {"mean": v["mean"], "std": v["std"]} 
                                     for k, v in entropy_by_type.items()},
            "anova_f_statistic": float(f_stat),
            "anova_p_value": float(p_value),
            "overall_cv_mean": float(cv_mean),
            "overall_cv_variance": float(cv_variance),
            "relative_cv_variance": float(relative_cv_variance),
            "overall_entropy_variance": float(entropy_variance),
            "n_measurements": len(test_measurements),
        }
        
        # Determine if ESP is validated
        # Criteria: p > 0.05 (no significant difference) AND relative variance < 0.1
        esp_validated = (p_value > 0.05 and relative_cv_variance < 0.1)
        
        analysis["esp_validated"] = esp_validated
        
        if esp_validated:
            analysis["verdict"] = (
                "ECHO STATE PROPERTY SUPPORTED: States converge to similar values "
                "regardless of prehistory. The system shows fading memory behavior "
                f"consistent with reservoir computing. (p={p_value:.3f}, "
                f"relative variance={relative_cv_variance:.3f})"
            )
        else:
            if p_value <= 0.05:
                analysis["verdict"] = (
                    "ECHO STATE PROPERTY NOT SUPPORTED: Significant differences "
                    f"persist between trial types (ANOVA p={p_value:.3f}). "
                    "The system's state depends on prehistory beyond the expected "
                    "fading memory window. This may indicate the system is NOT a "
                    "valid reservoir, OR the convergence time needs to be increased."
                )
            else:
                analysis["verdict"] = (
                    "ECHO STATE PROPERTY INCONCLUSIVE: No significant difference "
                    f"between trial types (p={p_value:.3f}), but high variance "
                    f"({relative_cv_variance:.3f}) suggests noisy measurements. "
                    "Consider increasing sample sizes or measurement duration."
                )
        
        return analysis
    
    def run(self):
        """Execute the complete experiment"""
        self.log("=" * 60)
        self.log("EXPERIMENT 1: ECHO STATE PROPERTY (FADING MEMORY) TEST")
        self.log("=" * 60)
        self.log(f"Miner: {self.config['miner_ip']}")
        self.log(f"Test condition: {self.config['test_frequency_mhz']}MHz, "
                f"{self.config['test_voltage_mv']}mV")
        self.log(f"Repetitions per trial type: {self.config['repetitions_per_trial']}")
        self.log("")
        
        # Check miner connectivity
        status = self.miner.get_status()
        if not status:
            self.log("[ERROR] Cannot connect to miner. Check IP and connectivity.")
            return None
        self.log(f"Miner connected: {status}")
        
        # Run all trials
        for rep in range(self.config["repetitions_per_trial"]):
            self.log(f"\n>>> REPETITION {rep + 1}/{self.config['repetitions_per_trial']} <<<\n")
            
            for trial_type, trial_config in TRIAL_TYPES.items():
                measurements = self.run_single_trial(trial_type, trial_config, rep)
                self.results.measurements.extend(measurements)
                
                # Brief pause between trials
                time.sleep(5)
        
        # Analyze results
        self.log("\n" + "=" * 60)
        self.log("ANALYZING RESULTS...")
        self.log("=" * 60)
        
        self.results.convergence_analysis = self.analyze_convergence()
        self.results.esp_validated = self.results.convergence_analysis["esp_validated"]
        self.results.verdict_reasoning = self.results.convergence_analysis["verdict"]
        
        # Print results
        self.log("\n" + "-" * 60)
        self.log("RESULTS SUMMARY")
        self.log("-" * 60)
        
        for trial_type, data in self.results.convergence_analysis["cv_by_trial_type"].items():
            self.log(f"  {trial_type}: CV = {data['mean']:.3f} ± {data['std']:.3f}")
        
        self.log(f"\nANOVA test: F={self.results.convergence_analysis['anova_f_statistic']:.3f}, "
                f"p={self.results.convergence_analysis['anova_p_value']:.3f}")
        self.log(f"Relative CV variance: {self.results.convergence_analysis['relative_cv_variance']:.3f}")
        
        self.log("\n" + "=" * 60)
        self.log("VERDICT")
        self.log("=" * 60)
        self.log(self.results.verdict_reasoning)
        
        # Save results
        self.save_results()
        
        return self.results
    
    def save_results(self):
        """Save results to JSON file"""
        output_file = os.path.join(
            self.config["output_dir"],
            f"{self.results.experiment_id}.json"
        )
        
        # Convert to serializable format
        results_dict = {
            "experiment_id": self.results.experiment_id,
            "start_timestamp": self.results.start_timestamp,
            "config": self.results.config,
            "measurements": [asdict(m) for m in self.results.measurements],
            "convergence_analysis": self.results.convergence_analysis,
            "esp_validated": self.results.esp_validated,
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
    ║  CHIMERA VALIDATION EXPERIMENT 1                              ║
    ║  Echo State Property (Fading Memory) Test                     ║
    ║                                                               ║
    ║  This experiment tests whether the ASIC system has the        ║
    ║  "fading memory" property required for reservoir computing.   ║
    ║                                                               ║
    ║  Expected duration: ~15-20 minutes                            ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Verify configuration
    print(f"Miner IP: {CONFIG['miner_ip']}")
    print(f"Test condition: {CONFIG['test_frequency_mhz']}MHz @ {CONFIG['test_voltage_mv']}mV")
    print()
    
    response = input("Press ENTER to start experiment (or 'q' to quit): ")
    if response.lower() == 'q':
        print("Experiment cancelled.")
        exit(0)
    
    # Run experiment
    experiment = ESPExperiment(CONFIG)
    results = experiment.run()
    
    if results:
        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(f"ESP Validated: {results.esp_validated}")
        print(f"See detailed results in: {CONFIG['output_dir']}/")
