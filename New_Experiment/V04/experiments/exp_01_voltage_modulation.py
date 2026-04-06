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

def set_voltage(mV):
    """Sets the ASIC voltage via Bridge."""
    print(f"   💊 Dosing Voltage: {mV}mV...")
    send_bridge_cmd(f"SET_VOLTAGE:{mV}")
    print("   ⏳ Waiting 60s for Miner Reboot/Stabilization...")
    time.sleep(60) # Wait for power adjustment and potential service restart

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
        if ts > last_ts:
            log_cv.append(m['cv'])
            log_ent.append(m['time_entropy'])
            last_ts = ts
            print(".", end="", flush=True)
        time.sleep(1)
    print(" Done.")
    
    if not log_cv: return 0, 0
    return statistics.mean(log_cv), statistics.mean(log_ent)

def validate_bridge_connection():
    """Verifies that chronos_bridge is running and miner is connected."""
    print("🔍 VALIDATING BRIDGE CONNECTION...")

    # Step 1: Check if API is reachable
    try:
        m = get_metrics()
        # Relax check: If we have telemetry (voltage/temp), the bridge is alive even if CV isn't calculated yet
        has_telemetry = m.get("voltage", 0) > 0 or m.get("temp", 0) > 0
        if m.get("timestamp", 0) > 0 or has_telemetry:
            ts = m.get("timestamp", "N/A (Waiting for sync)")
            print(f"   ✅ Bridge Active: CV={m['cv']:.4f}, Last Update={ts}")
            if has_telemetry:
                print(f"      [Telemetría Detectada: {m['voltage']}mV, {m['temp']}°C]")
            return True
        else:
            print("   ❌ ERROR: Bridge API returns zero data")
            print("   📋 Troubleshooting:")
            print("      1. Is chronos_bridge.py running? (python V04/drivers/chronos_bridge.py)")
            print("      2. Is the LV06 connected to port 3333?")
            print("      3. Check miner config: Pool URL = <this_pc_ip>:3333")
            return False

    except Exception as e:
        print(f"   ❌ ERROR: Cannot reach Bridge API: {e}")
        print("   📋 Solution: Run 'python V04/drivers/chronos_bridge.py' first")
        return False

def run_experiment():
    print("=== V04: VOLTAGE MODULATION EXPERIMENT ===\n")

    # Validate connection before starting
    if not validate_bridge_connection():
        print("\n❌ EXPERIMENT ABORTED: Bridge not ready")
        return

    print("\n✅ VALIDATION PASSED - Starting Experiment\n")

    # 1. Baseline (Probed - 990mV)
    # 2. Sedation 1 (950mV)
    # 3. Sedation 2 (900mV)
    # 4. Deep Coma (850mV)

    voltages = [990, 950, 900, 850]
    results = []

    # Ensure standard frequency first
    # Note: Frequency is set by the bridge on connect (400MHz).

    for v in voltages:
        print(f"\n--- TESTING VOLTAGE: {v}mV ---")
        set_voltage(v)
        
        # Test 1: Noise (Control)
        inject_seed("Chaos and Entropy")
        cv_noise, ent_noise = collect_data(25)
        
        # Test 2: Structure (Target)
        inject_seed("Structure and Order (Shakespeare)")
        cv_struct, ent_struct = collect_data(25)
        
        results.append({
            "voltage": v,
            "cv_noise": cv_noise, 
            "cv_struct": cv_struct,
            "delta": cv_noise - cv_struct
        })

    # Generate Report
    filename = "docs/REPORT_VOLTAGE_MODULATION.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# CHIMERA V04: VOLTAGE MODULATION REPORT\n")
        f.write("**Date**: " + time.strftime('%Y-%m-%d') + "\n\n")
        f.write("## Hypothesis: Sedation Induces Order\n")
        f.write("Lowering voltage should reduce thermal noise, allowing semantic seeds to lock the 'Crystal State' (Low CV).\n\n")
        f.write("## Results\n\n")
        f.write("| Voltage (mV) | CV (Noise) | CV (Structure) | Delta (Sensitivity) | State |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        
        print("\nSUMMARY TABLE:")
        print(f"{'Volt':<6} | {'CV Noise':<10} | {'CV Struct':<10} | {'Delta':<10}")
        
        for r in results:
            v = r['voltage']
            cv_n = r['cv_noise']
            cv_s = r['cv_struct']
            delta = r['delta']
            
            state = "Chaos"
            if cv_s < 0.5: state = "💎 Crystal (Locked)"
            elif cv_s < 0.8: state = "💧 Viscous"
            
            row = f"| {v} | {cv_n:.4f} | **{cv_s:.4f}** | {delta:.4f} | {state} |"
            f.write(row + "\n")
            print(f"{v:<6} | {cv_n:.4f}     | {cv_s:.4f}     | {delta:.4f}")
            
    print(f"\n✅ Report Saved: {filename}")

if __name__ == "__main__":
    run_experiment()
