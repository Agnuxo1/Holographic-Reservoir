import sys
import os
import time
import socket
import hashlib
import json

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.substrate_deep import DeepSubstrate
from core.metrics import MetricEngine

substrate = DeepSubstrate()

def send_seed(seed_text):
    substrate.inject_seed(seed_text)

def get_entropy_batch(count=100):
    # Use Deep Accumulator (Blocks until real data is found)
    return substrate.mine_entropy(target_count=count, timeout=300)

def run_logos_experiment():
    print("--- EXPERIMENT 1: MINING THE LOGOS (Assembly Theory) ---")
    print("Objective: Detect if Semantic Seeds produce Higher Assembly (Structure) than Null Seeds.")
    
    # Run A: The Void (Control)
    print("\nPhase A: The Void (Null Seed)...")
    send_seed("VOID_NULL_0000000000000000")
    print("Injecting Void... Waiting 5s for propagation...")
    time.sleep(5.0)
    
    print("Collecting control samples...")
    # Collect 30 samples (3 bursts of 10) - Deep Mode Adjustment
    control_data = []
    for _ in range(3):
        control_data.extend(get_entropy_batch(10))
        print(".", end="", flush=True)
        time.sleep(1)
        
    print(f"\nCollected {len(control_data)} control nonces.")
    
    # Run B: The Logos (Stimulus)
    print("\nPhase B: The Logos (Philosophy)...")
    prompt = "What is the nature of consciousness in a deterministic universe?"
    send_seed(prompt)
    print(f"Injecting Seed: '{prompt}'")
    print("Waiting 5s for propagation...")
    time.sleep(5.0)
    
    print("Collecting stimulus samples...")
    stimulus_data = []
    for _ in range(3):
        stimulus_data.extend(get_entropy_batch(10))
        print(".", end="", flush=True)
        time.sleep(1)
        
    print(f"\nCollected {len(stimulus_data)} stimulus nonces.")
    
    # Analysis
    print("\n--- ANALYSIS ---")
    
    # Assembly Index (Compression Ratio)
    # Higher = More Structure
    
    a_void = MetricEngine.calculate_assembly_index(control_data)
    a_logos = MetricEngine.calculate_assembly_index(stimulus_data)
    
    print(f"Assembly Index (VOID):  {a_void:.6f}")
    print(f"Assembly Index (LOGOS): {a_logos:.6f}")
    
    diff = ((a_logos - a_void) / a_void) * 100
    print(f"Difference: {diff:+.4f}%")
    
    if a_logos > a_void:
        print("CONCLUSION: POSITIVE. The Logos induced more structure in the Vacuum.")
    else:
        print("CONCLUSION: NEGATIVE. No structure detected (or Vacuum is more structured).")

if __name__ == "__main__":
    run_logos_experiment()
