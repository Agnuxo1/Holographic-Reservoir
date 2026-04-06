import time
import socket
import json
import statistics

# CONFIGURATION
BRIDGE_IP = "127.0.0.1"
BRIDGE_API_PORT = 4029

def send_bridge_cmd(cmd):
    """Sends a raw command to the bridge API."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((BRIDGE_IP, BRIDGE_API_PORT))
        s.sendall(cmd.encode())
        data = s.recv(4096).decode()
        s.close()
        return data
    except Exception as e:
        print(f"   [WARN] Bridge API Error ({cmd}): {e}")
        return None

def set_frequency(MHz):
    """Sets the ASIC frequency via Bridge (Stratum Relay)."""
    print(f"   🧠 Tuning Frequency: {MHz} MHz...")
    send_bridge_cmd(f"SET_FREQUENCY:{MHz}")
    print("   ⏳ Waiting 30s for PLL Stabilization...")
    time.sleep(30) 

def get_metrics():
    """Queries current CV and Entropy."""
    resp = send_bridge_cmd("GET_METRICS")
    if resp:
        try:
            return json.loads(resp)
        except: pass
    return {"cv": 0.0, "time_entropy": 0.0}

def inject_seed(seed):
    send_bridge_cmd(f"SEED:{seed}")

def collect_data(duration_sec=30):
    """Monitors metrics for duration."""
    log_cv = []
    log_ent = []
    start = time.time()
    
    print(f"   ⏳ Monitoring ({duration_sec}s)...", end="", flush=True)
    last_ts = 0
    while time.time() - start < duration_sec:
        m = get_metrics()
        ts = m.get("timestamp", 0)
        if ts > last_ts or ts == 0: # Allow ts=0 if we see cv changing
            log_cv.append(m['cv'])
            log_ent.append(m['time_entropy'])
            last_ts = ts
            print(".", end="", flush=True)
        time.sleep(2)
    print(" Done.")
    
    if not log_cv: return 0, 0
    return statistics.mean(log_cv), statistics.mean(log_ent)

def validate_bridge_connection():
    """Verifies that chronos_bridge is running and miner is connected."""
    print("🔍 VALIDATING BRIDGE CONNECTION...")
    m = get_metrics()
    if m.get("voltage", 0) > 0 or m.get("freq", 0) > 0:
        print(f"   ✅ Bridge Active: Freq={m.get('freq')}MHz, Base CV={m.get('cv'):.4f}")
        return True
    print("   ❌ ERROR: Bridge not reporting telemetry. Check miner connection.")
    return False

def run_experiment():
    print("=== V04: FREQUENCY MODULATION EXPERIMENT ===\n")

    if not validate_bridge_connection():
        return

    # Frequencies to test
    frequencies = [300, 350, 400, 450, 500]
    results = []

    for f in frequencies:
        print(f"\n--- TESTING FREQUENCY: {f} MHz ---")
        set_frequency(f)
        
        # Test 1: Noise (Chaos)
        inject_seed("Cosmic Microwave Background Chaos")
        cv_noise, ent_noise = collect_data(80) # Increased for honesty
        
        # Test 2: Structure (Shakespeare)
        inject_seed("To be or not to be, that is the question.")
        cv_struct, ent_struct = collect_data(80) # Increased for honesty
        
        results.append({
            "freq": f,
            "cv_noise": cv_noise, 
            "cv_struct": cv_struct,
            "delta": cv_noise - cv_struct
        })

    # Generate Report
    filename = "docs/REPORT_FREQUENCY_MODULATION.md"
    with open(filename, "w", encoding="utf-8") as f_out:
        f_out.write("# CHIMERA V04: FREQUENCY MODULATION REPORT\n")
        f_out.write(f"**Date**: {time.strftime('%Y-%m-%d')}\n\n")
        f_out.write("## Hypothesis: Frequency Scales temporal resolution\n")
        f_out.write("Higher frequencies should reduce CV by increasing the event rate, but may also increase thermal noise.\n\n")
        f_out.write("## Results\n\n")
        f_out.write("| Frequency (MHz) | CV (Noise) | CV (Structure) | Delta | State |\n")
        f_out.write("| :--- | :--- | :--- | :--- | :--- |\n")
        
        for r in results:
            freq = r['freq']
            cv_n = r['cv_noise']
            cv_s = r['cv_struct']
            delta = r['delta']
            
            state = "Chaos"
            if cv_s < 0.6: state = "💎 Crystal"
            elif cv_s < 0.9: state = "💧 Viscous"
            
            f_out.write(f"| {freq} | {cv_n:.4f} | **{cv_s:.4f}** | {delta:.4f} | {state} |\n")

    print(f"\n✅ Report Saved: {filename}")

if __name__ == "__main__":
    run_experiment()
