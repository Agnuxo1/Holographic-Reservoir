import socket
import time
import os

def inject_seed(seed):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 4029))
        s.sendall(f"SEED:{seed}".encode())
        s.close()
        print(f"💉 Injected Seed: '{seed}'")
    except Exception as e:
        print(f"❌ Error injecting seed: {e}")

def run_modulation_experiment():
    print("--- EXPERIMENT 3: CHRONODYNAMIC MODULATION ---")
    print("Objective: Control the Coefficient of Variation (CV) via Semantic Seeds.")
    
    # 1. BASELINE (The Void)
    print("\n[PHASE 1] BASELINE: The Void")
    inject_seed("VOID_SILENCE_NOTHING")
    print("Monitoring Bridge Output... (Wait 60s)")
    time.sleep(60)
    
    # 2. CALM (Order)
    print("\n[PHASE 2] CALM: Order & Harmony")
    inject_seed("ORDER_HARMONY_CRYSTAL_STRUCTURE_CALM_PEACE_FLOW")
    print("Monitoring Bridge Output... (Wait 60s)")
    time.sleep(60)
    
    # 3. PANIC (Chaos)
    print("\n[PHASE 3] PANIC: Chaos & Entropy")
    inject_seed("CHAOS_PANIC_FIRE_EMERGENCY_ALARM_SCREAM_RUN")
    print("Monitoring Bridge Output... (Wait 60s)")
    time.sleep(60)
    
    print("\n--- EXPERIMENT COMPLETE ---")
    print("Check Bridge Terminal for CV Changes.")

if __name__ == "__main__":
    run_modulation_experiment()
