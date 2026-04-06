import socket
import json
import time
import threading
import numpy as np
import binascii
import hashlib

# CONFIGURATION
BRIDGE_IP = "0.0.0.0"
STRATUM_PORT = 3333
API_PORT = 4029
TARGET_DIFFICULTY = 1
NBITS_DIFF_1 = "1d00ffff"

class HRCBridge:
    """
    Unified HRC Bridge: Precision Timing + Entropy Flooding.
    Bypasses WiFi bottleneck via Time Anchoring and nBits Hack.
    """
    def __init__(self):
        # Stratum Server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((BRIDGE_IP, STRATUM_PORT))
        self.sock.listen(5)
        
        # State Tracking
        self.arrival_times_ns = []
        self.current_seed = "INITIAL_CHIMERA_SEED"
        self.last_metrics = {
            "cv": 1.0, 
            "entropy": 0.0, 
            "sps": 0.0,
            "timestamp": time.time(),
            "last_arrival_ns": 0
        }
        self.share_count = 0
        self.start_time = time.time()
        
        print(f"🚀 HRC HIGH-FIDELITY BRIDGE ACTIVE")
        print(f"   📡 Stratum: {BRIDGE_IP}:{STRATUM_PORT}")
        print(f"   🔗 API:     {BRIDGE_IP}:{API_PORT}")
        
        # Start API Thread
        threading.Thread(target=self.run_api_server, daemon=True).start()
        # Start Telemetry Thread
        threading.Thread(target=self.telemetry_loop, daemon=True).start()

    def run_api_server(self):
        api_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        api_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        api_sock.bind(("0.0.0.0", API_PORT))
        api_sock.listen(5)
        
        while True:
            try:
                conn, _ = api_sock.accept()
                data = conn.recv(1024).decode().strip()
                
                if data == "GET_METRICS":
                    conn.send(json.dumps(self.last_metrics).encode())
                elif data.startswith("SEED:"):
                    self.current_seed = data.split(":", 1)[1]
                    print(f"\n🌱 [Bridge] Seed Updated: {self.current_seed[:30]}...")
                    conn.send(b"OK")
                elif data == "RESET":
                    self.arrival_times_ns = []
                    self.share_count = 0
                    conn.send(b"OK")
                else:
                    conn.send(b"UNKNOWN_CMD")
                conn.close()
            except Exception: pass

    def handle_client(self, conn, addr):
        print(f"⚡ ASIC LINK: {addr}")
        buffer = ""
        while True:
            try:
                data = conn.recv(4096)
                if not data: break
                
                # TIME ANCHOR: Capture arrival in nanoseconds immediately
                arrival_ns = time.time_ns()
                
                buffer += data.decode('utf-8', errors='ignore')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip(): continue
                    try:
                        self.process_stratum(json.loads(line), conn, arrival_ns)
                    except: pass
            except: break
        print(f"🔌 ASIC DISCONNECT: {addr}")

    def process_stratum(self, msg, conn, arrival_ns):
        method = msg.get('method')
        msg_id = msg.get('id')

        if method == 'mining.subscribe':
            res = [[["mining.set_difficulty", "1"], ["mining.notify", "1"]], "08000002", 4]
            self.send_json(conn, {"id": msg_id, "result": res, "error": None})

        elif method == 'mining.authorize':
            self.send_json(conn, {"id": msg_id, "result": True, "error": None})
            # Force Diff 1 immediately
            self.send_json(conn, {"id": None, "method": "mining.set_difficulty", "params": [TARGET_DIFFICULTY]})
            self.send_job(conn)

        elif method == 'mining.submit':
            # Record high-fidelity arrival
            self.arrival_times_ns.append(arrival_ns)
            self.share_count += 1
            print(".", end="", flush=True)
            
            # Send confirmation
            self.send_json(conn, {"id": msg_id, "result": True, "error": None})
            
            # Periodic job update to keep chip "sweating"
            if self.share_count % 50 == 0:
                self.send_job(conn)

    def send_job(self, conn):
        job_id = f"hrc_{int(time.time()):x}"
        # Inject seed into coinbase for physical state modulation
        coinbase = binascii.hexlify(f"{self.current_seed}-{time.time()}".encode()).decode()
        msg = {
            "params": [job_id, "0"*64, coinbase, "0000", [], "20000000", NBITS_DIFF_1, hex(int(time.time()))[2:], True],
            "id": None, "method": "mining.notify"
        }
        self.send_json(conn, msg)

    def send_json(self, conn, data):
        try:
            conn.sendall((json.dumps(data) + '\n').encode())
        except: pass

    def telemetry_loop(self):
        while True:
            time.sleep(2.0)
            if len(self.arrival_times_ns) > 5:
                # Calculate metrics from precision window
                deltas = np.diff(self.arrival_times_ns)
                if len(deltas) > 0:
                    cv = np.std(deltas) / np.mean(deltas)
                    
                    hist, _ = np.histogram(deltas, bins=10)
                    prob = hist / (np.sum(hist) + 1e-9)
                    ent = -np.sum(prob * np.log(prob + 1e-9))
                    
                    elapsed = time.time() - self.start_time
                    sps = self.share_count / elapsed if elapsed > 0 else 0
                    
                    self.last_metrics = {
                        "cv": float(cv),
                        "entropy": float(ent),
                        "sps": float(sps),
                        "timestamp": time.time(),
                        "last_arrival_ns": int(self.arrival_times_ns[-1])
                    }
                    
                    # Log to console
                    print(f"\n📊 [Bridge] Flow: {sps:.2f} sps | CV: {cv:.4f} | Ent: {ent:.4f}")

    def start(self):
        while True:
            try:
                conn, addr = self.sock.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()
            except KeyboardInterrupt:
                break
            except: pass

if __name__ == "__main__":
    bridge = HRCBridge()
    bridge.start()
