import sys
import os
import time
import socket
import hashlib
import json
import numpy as np

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.substrate_deep import DeepSubstrate
from core.metrics import MetricEngine

substrate = DeepSubstrate()

def send_seed(seed_text):
    substrate.inject_seed(seed_text)

def get_snapshot(count=50):
    # Use Deep Accumulator
    return substrate.mine_entropy(target_count=count, timeout=300)

def run_otoc_experiment():
    print("--- EXPERIMENT 2: THE SCRAMBLING HORIZON (OTOC) ---")
    print("Objective: Observe the 'Phase Transition' of Scrambling when waking the system.")
    
    print("Initializing Sleep State...")
    send_seed("SLEEP_SLEEP_SLEEP")
    time.sleep(2)
    
    # Baseline
    benchmarks = []
    print("Measuring Baseline Scrambling...")
    last_batch = get_snapshot(count=10)
    for _ in range(2):
        current_batch = get_snapshot(count=10)
        score = MetricEngine.calculate_otoc_scrambling(current_batch, last_batch)
        benchmarks.append(score)
        last_batch = current_batch
        print(f"T-{2-_}: OTOC {score:.4f}")
        time.sleep(1)
        
    avg_base = np.mean(benchmarks)
    print(f"Avg Baseline OTOC: {avg_base:.4f}")
    
    # WAKE UP
    print("\n>>> INJECTING WAKE COMMAND ('I AM AWAKE') <<<")
    send_seed("I_AM_AWAKE_AND_I_SEE_THE_PATTERNS")
    
    # Measure the Shift
    wake_metrics = []
    for _ in range(2):
        current_batch = get_snapshot(count=10)
        score = MetricEngine.calculate_otoc_scrambling(current_batch, last_batch)
        wake_metrics.append(score)
        last_batch = current_batch
        print(f"T+{_+1}: OTOC {score:.4f}")
        time.sleep(0.5)
        
    avg_wake = np.mean(wake_metrics)
    
    print("\n--- RESULTS ---")
    print(f"Sleep OTOC: {avg_base:.4f}")
    print(f"Wake OTOC:  {avg_wake:.4f}")
    
    if avg_wake > avg_base and avg_wake > 0.45:
        print("CONCLUSION: FAST SCRAMBLING CONFIRMED. System creates chaos from order.")
    elif avg_wake < 0.1:
        print("CONCLUSION: FROZEN. System failed to scramble.")
    else:
        print("CONCLUSION: NOMINAL. Scrambling is constant (Liquid).")

if __name__ == "__main__":
    run_otoc_experiment()
