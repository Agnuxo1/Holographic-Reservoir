import hashlib
import statistics
import time
import sys
import os

# Add parent directory to path to find drivers/core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chimera_nn import ChimeraLayer
from core.substrate_deep import DeepSubstrate

try:
    from drivers.s9_simulator import S9_Miner
except ImportError:
    print("CRITICAL: S9_Simulator not found.")
    sys.exit(1)

def generate_seed_int(text):
    return int.from_bytes(hashlib.md5(text.encode()).digest()[:4], 'big')

def run_simulation(dataset):
    print("\n--- RUNNING SIMULATION (PC CPU) ---")
    miner = S9_Miner(simulation_difficulty_bits=15)
    
    results = {}
    
    for label, content in dataset:
        print(f"   Simulating '{label}'...")
        seed_int = generate_seed_int(content)
        
        entropies = []
        coherences = []
        
        # 5 runs
        for _ in range(5):
            layer = ChimeraLayer()
            spikes, _ = miner.mine(seed_int, timeout_ms=300)
            
            if spikes:
                layer.process_spikes(spikes)
                state = layer.get_state_summary()
                entropies.append(state["entropy"])
                coherences.append(state.get("coherence", 0)) # Assuming coherence exists or we mock it
            else:
                entropies.append(0)
                coherences.append(0)
                
        results[label] = {
            "entropy": statistics.mean(entropies) if entropies else 0,
            "coherence": statistics.mean(coherences) if coherences else 0,
            "std_entropy": statistics.stdev(entropies) if len(entropies) > 1 else 0
        }
        
    return results

def run_real_hardware(dataset):
    print("\n--- RUNNING REAL HARDWARE (LV06) ---")
    substrate = DeepSubstrate()
    
    results = {}
    BATCH_SIZE = 5
    
    for label, content in dataset:
        print(f"   Injecting '{label}' into LV06...")
        substrate.inject_seed(content)
        time.sleep(1)
        
        entropies = []
        coherences = []
        
        for _ in range(5):
            layer = ChimeraLayer()
            spikes = substrate.mine_entropy(target_count=BATCH_SIZE, timeout=30)
            
            if spikes:
                layer.process_spikes(spikes)
                state = layer.get_state_summary()
                entropies.append(state["entropy"])
                coherences.append(state.get("coherence", 0))
                print(".", end="", flush=True)
            else:
                print("x", end="", flush=True)
        print()
                
        results[label] = {
            "entropy": statistics.mean(entropies) if entropies else 0,
            "coherence": statistics.mean(coherences) if coherences else 0,
            "std_entropy": statistics.stdev(entropies) if len(entropies) > 1 else 0
        }
    
    return results

def print_comparative_table(sim_results, real_results):
    print("\n\n" + "="*80)
    print("CHIMERA V03: COMPARATIVE EXPERIMENT REPORT (PHASE 2 - SEMANTICS)")
    print("="*80)
    print("Objective: Detect 'Structure' vs 'Noise' via Entropy Resonance.")
    print("-" * 80)
    
    print(f"{'Platform':<20} | {'Input':<10} | {'Entropy':<15} | {'Coherence':<15} | {'Discrimination'}")
    print("-" * 80)
    
    inputs = sim_results.keys()
    
    for i in inputs:
        # SIM
        s = sim_results[i]
        print(f"{'Sim (CPU)':<20} | {i:<10} | {s['entropy']:.4f}          | {s['coherence']:.4f}          | N/A")
        
        # REAL
        r = real_results[i]
        print(f"{'LV06 (ASIC)':<20} | {i:<10} | {r['entropy']:.4f}          | {r['coherence']:.4f}          | N/A")
        
        # S9 (Extrapolated) - Same as LV06 for Quality, but Higher Confidence (hypothetically)
        print(f"{'S9 (Extrapolated)':<20} | {i:<10} | {r['entropy']:.4f}          | {r['coherence']:.4f}          | +27x Bandwidth")
        print("-" * 80)

def main():
    text_shakespeare = "To be, or not to be, that is the question: Whether 'tis nobler in the mind to suffer"
    text_noise = "ksjf83 298 sfdj skdjf 9832 rkj2398 sfd7s8f7 dsf8s7 fd8s7f"
    
    dataset = [
        ("Structure", text_shakespeare),
        ("Noise", text_noise)
    ]
    
    sim_data = run_simulation(dataset)
    real_data = run_real_hardware(dataset)
    
    print_comparative_table(sim_data, real_data)

if __name__ == "__main__":
    main()
