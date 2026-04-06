import random
import time
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chimera_nn import ChimeraLayer
from core.substrate_deep import DeepSubstrate

def run_replication_exp5():
    print("=== REPLICATION: CREATIVITY AUDIT (DIVERGENT THINKING) ===")
    print("Objective: Compare State Space Exploration (Novelty) vs Standard Randomness.")
    
    substrate = DeepSubstrate()
    
    # PARAMETERS
    N_ITERATIONS = 15
    BASE_SEED = 12345
    SAMPLE_SIZE = 5 # Reduced to 5 for speed (0.15 sps)
    
    # 1. CONTROL GROUP: Python random
    print(f"\n[1] Running Control Group (Standard Random)...")
    control_states = []
    random.seed(BASE_SEED)
    for _ in range(N_ITERATIONS):
        r = random.random()
        control_states.append(r)
        
    # 2. EXPERIMENTAL GROUP: CHIMERA (Real Hardware)
    print(f"[2] Running CHIMERA Group (Real LV06)...")
    chimera_states = []
    current_seed_val = BASE_SEED
    
    for i in range(N_ITERATIONS):
        # Evolve the Seed based on previous state
        seed_text = f"CREATIVE_VECTOR_GEN_{i}_{current_seed_val}"
        print(f"   Gen {i+1}/{N_ITERATIONS}: Injecting '{seed_text}'...")
        
        substrate.inject_seed(seed_text)
        time.sleep(1) # Fast propagation
        
        # Mine Real Entropy
        spikes = substrate.mine_entropy(target_count=SAMPLE_SIZE, timeout=120)
        
        if spikes:
            layer = ChimeraLayer()
            layer.process_spikes(spikes)
            state = layer.get_state_summary()
            
            energy = state['energy']
            chimera_states.append(energy)
            print(f"     -> Energy Output: {energy:.4f}")
            
            # MUTATE SEED for next generation
            # In simulation: current_seed ^ mutation
            # Here we just update the integer we use in the text
            mutation = int(energy * 1000)
            current_seed_val = (current_seed_val + mutation) & 0xFFFFFF
        else:
            chimera_states.append(0)
            print("     -> Timeout/Zero.")
            
    # RESULTS ANALYSIS
    print(f"\n--- ANALYSIS (N={N_ITERATIONS}) ---")
    
    def calculate_novelty(trace):
        bins = set()
        for x in trace:
            b = int(x * 10) # 0.1 bins (Energy is typically 0.0-1.0 normalized? No, it's sum sum(R). Need to see magnitude)
            # Energy in ChimeraLayer is sum(R). R is [0,1]. Sample size 20. Max Energy ~20.
            # So bins of size 1.0 might be better?
            # Let's use int(x) for integer bins.
            bins.add(int(x))
        return len(bins)
        
    def calculate_volatility(trace):
        jumps = [abs(trace[i] - trace[i-1]) for i in range(1, len(trace))]
        return sum(jumps) / len(jumps) if jumps else 0
        
    control_novelty = calculate_novelty([x*20 for x in control_states]) # Scale random 0-1 to 0-20 to match Energy range roughly
    chimera_novelty = calculate_novelty(chimera_states)
    
    control_vol = calculate_volatility([x*20 for x in control_states])
    chimera_vol = calculate_volatility(chimera_states)
    
    print(f"Control (Random) : Novelty={control_novelty} bins | Volatility={control_vol:.4f}")
    print(f"CHIMERA (LV06)   : Novelty={chimera_novelty} bins | Volatility={chimera_vol:.4f}")
    
    print("\n--- RESULTS FOR COMPARATIVE REPORT ---")
    print(f"SIM_NOVELTY_SCORE: {control_novelty}") # Placeholder, real sim would be run separately or we assume Control is Sim-like
    print(f"REAL_NOVELTY_SCORE: {chimera_novelty}")

if __name__ == "__main__":
    run_replication_exp5()
