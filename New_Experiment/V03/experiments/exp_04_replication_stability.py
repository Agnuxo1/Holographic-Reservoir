import hashlib
import statistics
import time
import sys
import os

# Add parent directory to path to find drivers/core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chimera_nn import ChimeraLayer
from core.substrate_deep import DeepSubstrate
# Simulator fallback for comparison
try:
    from drivers.s9_simulator import S9_Miner 
except ImportError:
    print("CRITICAL: S9_Simulator not found in drivers.")
    sys.exit(1)

def generate_seed_int(text):
    return int.from_bytes(hashlib.md5(text.encode()).digest()[:4], 'big')

def run_simulation(seeds):
    print("\n--- RUNNING SIMULATION (PC CPU) ---")
    miner = S9_Miner(simulation_difficulty_bits=14) # Match legacy diff
    
    results = {}
    
    for name, seed_text in seeds.items():
        seed_int = generate_seed_int(seed_text)
        print(f"   Simulating '{name}'...")
        
        energies = []
        entropies = []
        hashes_total = 0
        duration_total = 0
        
        # Run 5 times to average
        for _ in range(5):
            layer = ChimeraLayer()
            t_start = time.time()
            spikes, computed = miner.mine(seed_int, timeout_ms=500) # 0.5s burst
            duration = time.time() - t_start
            
            hashes_total += computed
            duration_total += duration
            
            if spikes:
                layer.process_spikes(spikes)
                state = layer.get_state_summary()
                energies.append(state["energy"])
                entropies.append(state["entropy"])
            else:
                energies.append(0)
                entropies.append(0)
                
        avg_e = statistics.mean(energies) if energies else 0
        std_e = statistics.stdev(energies) if len(energies) > 1 else 0
        avg_h = statistics.mean(entropies) if entropies else 0
        
        avg_hashrate = (hashes_total / duration_total) if duration_total > 0 else 0
        
        results[name] = {
            "energy": avg_e, 
            "std_energy": std_e, 
            "entropy": avg_h,
            "hashrate": avg_hashrate,
            "platform": "Sim (CPU)"
        }
        
    return results

def run_real_hardware(seeds):
    print("\n--- RUNNING REAL HARDWARE (LV06) ---")
    substrate = DeepSubstrate() # Auto-connects
    
    results = {}
    
    # We use roughly same duration logic.
    # In DeepSubstrate, 'mine_entropy' target_count determines duration based on luck.
    # We want to measure the RATE.
    
    for name, seed_text in seeds.items():
        print(f"   Injecting '{name}' into LV06...")
        substrate.inject_seed(seed_text)
        time.sleep(1) # Propagate
        
        energies = []
        entropies = []
        
        # To measure hashrate, we need to ask the driver or estimate from shares.
        # DeepSubstrate abstracts this, so we will use the telemetry data if available, or just measure Output Entropy Rate.
        # For this experiment, we care about Reservoir Stability.
        
        # We will collect a fixed Batch of entropy (e.g. 10 shares) and time it.
        BATCH_SIZE = 5 
        
        t_start_total = time.time()
        total_spikes = 0
        
        for run in range(5):
            layer = ChimeraLayer()
            
            # Burst
            spikes = substrate.mine_entropy(target_count=BATCH_SIZE, timeout=30)
            if spikes:
                layer.process_spikes(spikes)
                state = layer.get_state_summary()
                energies.append(state["energy"])
                entropies.append(state["entropy"])
                total_spikes += len(spikes)
            else:
                print("   [WARN] No spikes from miner?")
        
        duration = time.time() - t_start_total
        
        avg_e = statistics.mean(energies) if energies else 0
        std_e = statistics.stdev(energies) if len(energies) > 1 else 0
        avg_h = statistics.mean(entropies) if entropies else 0
        
        # Real Hardware Hashrate is constant (Global), not per task.
        # We assume 500 GH/s for LV06.
        # BUT, we can measure "Effective Entropy Rate" (Spikes per second).
        
        results[name] = {
            "energy": avg_e,
            "std_energy": std_e,
            "entropy": avg_h,
            "hashrate": 500 * 10**9, # 500 GH/s (Assumed constant for hardware)
            "platform": "LV06 (Real)"
        }
        
    return results

def print_comparative_table(sim_results, real_results):
    print("\n\n" + "="*80)
    print("CHIMERA V03: COMPARATIVE EXPERIMENT REPORT (PHASE 1 - STABILITY)")
    print("="*80)
    print(f"Date: {time.strftime('%Y-%m-%d')}")
    print("Objective: Compare stability of Simulated Chaos vs Real ASIC Quantum Chaos.")
    print("Note: 'S9 Extrapolated' assumes 13.5 TH/s linear scaling of capacity.")
    print("-" * 80)
    
    # Header
    print(f"{'Platform':<20} | {'Thought':<10} | {'Hashrate':<15} | {'Energy (Stab)':<15} | {'Entropy (Distinct)':<15}")
    print("-" * 80)
    
    thoughts = sim_results.keys()
    
    for t in thoughts:
        # SIM
        s = sim_results[t]
        s_h_str = f"{s['hashrate']/1000:.1f} kH/s"
        print(f"{'Sim (CPU)':<20} | {t:<10} | {s_h_str:<15} | {s['energy']:.3f} (±{s['std_energy']:.3f}) | {s['entropy']:.4f}")
        
        # REAL
        r = real_results[t]
        r_h_str = f"{r['hashrate']/1e9:.1f} GH/s"
        print(f"{'LV06 (ASIC)':<20} | {t:<10} | {r_h_str:<15} | {r['energy']:.3f} (±{r['std_energy']:.3f}) | {r['entropy']:.4f}")
        
        # S9 EXTRAPOLATED
        # Power Scaling: S9 is 13.5 TH/s. LV06 is ~0.5 TH/s. Scale ~27x.
        # If Holographic Reservoir theory holds, "Energy" (Reservoir Activation) scales with network size/input density.
        # We assume Energy scales Logarithmically or stays normalized, but 'Capacity' (Burst) scales linearly.
        # For this table, we keep metrics normalized (0-1) but highlight the throughput.
        
        s9_hash = 13.5 * 1e12
        s9_str = "13.5 TH/s"
        
        # We assume S9 would have identical Stability/Entropy as LV06 (same chip), just faster.
        print(f"{'S9 (Extrapolated)':<20} | {t:<10} | {s9_str:<15} | {r['energy']:.3f} (±{r['std_energy']:.3f}) | {r['entropy']:.4f}")
        print("-" * 80)

def main():
    seeds = {
        "Logic": "Logic and Order",
        "Chaos": "Chaos and Entropy",
        "Love": "Love and Empathy"
    }
    
    sim_data = run_simulation(seeds)
    real_data = run_real_hardware(seeds)
    
    print_comparative_table(sim_data, real_data)

if __name__ == "__main__":
    main()
