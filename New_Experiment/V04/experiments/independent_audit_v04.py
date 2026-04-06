import urllib.request
import json
import time
import socket

# CONFIGURATION
MINER_IP = "192.168.0.15"  
BRIDGE_API_PORT = 4029

def get_miner_ground_truth():
    url = f"http://{MINER_IP}/api/system/info"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

def get_bridge_metrics():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(("127.0.0.1", BRIDGE_API_PORT))
        s.sendall(b"GET_METRICS")
        data = s.recv(4096).decode()
        s.close()
        return json.loads(data)
    except Exception as e:
        return {"error": str(e)}

def send_command(cmd):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(("127.0.0.1", BRIDGE_API_PORT))
        s.sendall(cmd.encode())
        resp = s.recv(1024).decode()
        s.close()
        return resp
    except Exception as e:
        return f"ERROR: {e}"

def run_audit():
    print(f"🕵️ INDEPENDENT AUDIT STARTING (LIVE VERIFICATION)...")
    print("-" * 50)

    # 1. INITIAL STATE
    print("\n[STEP 1] INITIAL STATE CHECK")
    miner_start = get_miner_ground_truth()
    if "error" in miner_start:
        print(f"❌ Miner unreachable: {miner_start['error']}")
        return
    start_freq = miner_start.get("frequency", 0)
    print(f"   Current Miner Frequency: {start_freq} MHz")

    # 2. SEND COMMAND
    target_freq = 325 if start_freq != 325 else 400
    print(f"\n[STEP 2] SENDING COMMAND: SET_FREQUENCY:{target_freq}")
    resp = send_command(f"SET_FREQUENCY:{target_freq}")
    print(f"   Bridge Response: {resp}")

    # 3. WAIT FOR REBOOT & RECONNECT
    print(f"\n[STEP 3] WAITING FOR MINER REBOOT (60s)...")
    for i in range(12):
        time.sleep(5)
        print(f"   Searching for miner... ({ (i+1)*5 }s)", end="\r")
    print("\n   Checking connection...")

    # 4. FINAL VERIFICATION
    miner_final = get_miner_ground_truth()
    if "error" in miner_final:
        print(f"❌ Miner still unreachable or failed to reboot: {miner_final['error']}")
        return
    
    end_freq = miner_final.get("frequency", 0)
    print(f"\n[STEP 4] FINAL VERIFICATION")
    print(f"   Target Frequency: {target_freq} MHz")
    print(f"   Actual Frequency: {end_freq} MHz")

    print("\n[HONEST ASSESSMENT]")
    if end_freq == target_freq:
        print("✅ COMMAND VERIFIED: The hardware actually changed state.")
        print("   The implementation is now HONEST and EFFECTIVE.")
    else:
        print("🚨 AUDIT FAILURE: The hardware DID NOT change state.")
        print(f"   Reason: Firmware ignored command or implementation error.")

if __name__ == "__main__":
    run_audit()
