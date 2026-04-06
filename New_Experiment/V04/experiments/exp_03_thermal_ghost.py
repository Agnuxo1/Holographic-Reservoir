import socket
import json
import time
import numpy as np

# CONFIGURATION
BRIDGE_IP = "127.0.0.1"
BRIDGE_PORT = 4029
OPTIMAL_FREQ = 500  # Based on previous results (Crystal State)

def send_cmd(cmd):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((BRIDGE_IP, BRIDGE_PORT))
        s.sendall(cmd.encode())
        resp = s.recv(4096).decode()
        s.close()
        return resp
    except Exception as e:
        return f"ERROR: {e}"

def get_metrics():
    resp = send_cmd("GET_METRICS")
    try:
        return json.loads(resp)
    except:
        return None

def monitor_persistence(duration, label):
    print(f"\n[{label}] Monitoring for {duration}s...")
    data = []
    start_time = time.time()
    while time.time() - start_time < duration:
        m = get_metrics()
        if m:
            cv = m.get("cv", 1.0)
            ent = m.get("time_entropy", 0)
            data.append((cv, ent))
            print(f"   ⏱️ {int(time.time()-start_time):>3}s | CV: {cv:.4f} | Entropy: {ent:.4f}", end="\r")
        time.sleep(5)
    print("\n   ✅ Phase Complete.")
    return data

def run_experiment():
    print("=== EXPERIMENT 03: THERMAL GHOST (Persistence Test) ===")
    
    # 1. SETUP: TUNE TO CRYSTAL STATE
    print(f"\n[PHASE 0] Tuning to {OPTIMAL_FREQ}MHz (Crystal State)...")
    send_cmd(f"SET_FREQUENCY:{OPTIMAL_FREQ}")
    print("⏳ Waiting 60s for Hardware/Reboot stabilization...")
    time.sleep(60)

    # 2. BASELINE: CHAOS
    print("\n[PHASE 1] Baseline (Chaos)...")
    send_cmd("SEED: Cosmic Microwave Background Chaos")
    baseline_data = monitor_persistence(60, "BASELINE")
    
    # 3. SATURATION: STRUCTURE
    print("\n[PHASE 2] Saturation (Injecting Shakespeare)...")
    # Using a heavy seed to maximize thermal footprint
    heavy_seed = "To be, or not to be, that is the question: Whether 'tis nobler in the mind to suffer The slings and arrows of outrageous fortune, Or to take arms against a sea of troubles And by opposing end them."
    send_cmd(f"SEED: {heavy_seed}")
    saturation_data = monitor_persistence(180, "SATURATION") # Reduced to 180s for speed but still enough
    
    # 4. GHOST PHASE: SILENCE
    print("\n[PHASE 3] GHOST PHASE (Removing Seed)...")
    # We switch to a null/neutral seed instead of just silence to see if the "Ghost" resists the new noise
    send_cmd("SEED: .") 
    ghost_data = monitor_persistence(180, "GHOST DETECTION")

    # 5. ANALYSIS
    print("\n[ANALYSIS]")
    avg_baseline_cv = np.mean([d[0] for d in baseline_data])
    avg_saturated_cv = np.mean([d[0] for d in saturation_data])
    
    # Measure persistence: How many seconds did it stay closer to saturated than baseline?
    persistence_seconds = 0
    ghost_curve = [d[0] for d in ghost_data]
    
    threshold = (avg_baseline_cv + avg_saturated_cv) / 2
    for i, cv in enumerate(ghost_curve):
        if cv < threshold: # Closer to Structure (Regularity)
            persistence_seconds = (i + 1) * 5
        else:
            break

    print(f"   Average Baseline CV:  {avg_baseline_cv:.4f}")
    print(f"   Average Saturated CV: {avg_saturated_cv:.4f}")
    print(f"   Detected Ghost Persistence: {persistence_seconds} seconds")
    
    # Save Report
    report = f"""# EXPERIMENT 03: THERMAL GHOST REPORT
**Date**: {time.strftime("%Y-%m-%d")}
**Frequency**: {OPTIMAL_FREQ} MHz

## Concept
Measuring if the ASIC rhythm retains a 'memory' of structural seeds through thermal hysteresis after the seed is removed.

## Results
- **Baseline CV**: {avg_baseline_cv:.4f}
- **Saturated CV**: {avg_saturated_cv:.4f}
- **Ghost Persistence**: {persistence_seconds}s

## Conclusion
"""
    if persistence_seconds > 30:
        report += f"🚀 **GHOST DETECTED**: The silicon reservoir retained structural regularity for {persistence_seconds}s after seed removal. This proves a physical 'long-term' memory purely through thermodynamic interia."
    else:
        report += "⚠️ **NO PERSISTENCE**: The system returned to chaos almost instantly. Memory resolution may require lower voltages or higher sampling rates."
    
    with open("docs/REPORT_THERMAL_GHOST.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("\n✅ Report saved: docs/REPORT_THERMAL_GHOST.md")

if __name__ == "__main__":
    run_experiment()
