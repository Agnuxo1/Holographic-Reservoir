import urllib.request
import urllib.error
import urllib.parse
import socket
import json
import time
import threading
import numpy as np
import binascii
import hashlib

# Import entropy function with fallback
try:
    from scipy.stats import entropy
except ImportError:
    def entropy(pk):
        pk = np.array(pk)
        pk = pk[pk > 0]  # Remove zeros to avoid log(0)
        return -np.sum(pk * np.log(pk))

# CONFIGURACIÓN
HOST_IP = "0.0.0.0"
PORT = 3333
DIFFICULTY = 1  # Mantener válvula abierta

class ChronosBridge:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST_IP, PORT))
        self.sock.listen(5)
        self.arrival_times = []
        self.current_seed = "CHRONOS_BASELINE"
        self.pending_voltage = None
        self.pending_frequency = None # NEW: Track pending frequency changes
        # Expanded Metrics
        self.last_metrics = {
            "cv": 1.0, "time_entropy": 0.0, "timestamp": 0,
            "voltage": 0, "power": 0, "temp": 0, "freq": 0, "hashrate": 0
        }
        self.miner_ip = None # Store for HTTP Control
        self.extranonce1 = "08000002"
        self.current_job_ctx = {}
        self.recent_hashes = []
        self.hash_lock = threading.Lock()
        print(f"⏳ CHRONOS LISTENER OPENED on {HOST_IP}:{PORT}")

        # Start Threads
        threading.Thread(target=self.api_server, daemon=True).start()
        threading.Thread(target=self.telemetry_loop, daemon=True).start()

    def telemetry_loop(self):
        print("📊 TELEMETRY ENGINE STARTED")
        while True:
            time.sleep(3)
            if not self.miner_ip: continue
            
            try:
                url = f"http://{self.miner_ip}/api/system/info"
                with urllib.request.urlopen(url, timeout=2) as response:
                    data = json.loads(response.read().decode())
                    
                    # Update Metrics
                    v = data.get('coreVoltageActual', 0)
                    if v == 0: v = data.get('coreVoltage', 0) # Fallback
                    
                    self.last_metrics["voltage"] = v
                    self.last_metrics["power"] = data.get('power', 0)
                    self.last_metrics["temp"] = data.get('temp', 0)
                    self.last_metrics["freq"] = data.get('frequency', 0)
                    self.last_metrics["hashrate"] = data.get('hashRate', 0)
                    
                    # PRINT STATUS LINE
                    print(f"   📊 [{self.miner_ip}] "
                          f"🌡️ {self.last_metrics['temp']}°C | "
                          f"⚡ {self.last_metrics['power']}W | "
                          f"🔋 {self.last_metrics['voltage']}mV | "
                          f"🧠 {self.last_metrics['freq']}MHz | "
                          f"⛏️ {self.last_metrics['hashrate']} GH/s"
                          )
            except Exception as e:
                # print(f"   ⚠️ Telemetry Error: {e}") 
                pass

    def set_hardware_params(self, freq=None, vol=None):
        # HARDWARE MODULATION via HTTP (AxeOS/LuckyMiner)
        if not self.miner_ip:
            print("⚠️ DISCARDING COMMAND: No Miner IP known yet.")
            return

        try:
            # Current stats as baseline
            payload = {
                "frequency": self.last_metrics.get("freq", 400),
                "volts": self.last_metrics.get("voltage", 1000)
            }
            
            if freq: payload["frequency"] = int(freq)
            if vol: payload["volts"] = int(vol)
            
            url = f"http://{self.miner_ip}/api/system"
            print(f"💊 HTTP PATCH {url} -> {payload}")
            
            js_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=js_data, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=5) as response:
                print(f"   ✅ HARDWARE CONFIG UPDATED: {response.getcode()}")
            
            # TRIGGER RESTART (Required for Frequency/Voltage PLLs)
            print("   🔄 RESTARTING MINER TO APPLY CHANGES...")
            restart_url = f"http://{self.miner_ip}/api/system/restart"
            req_restart = urllib.request.Request(restart_url, data=b"{}", method='POST')
            req_restart.add_header('Content-Type', 'application/json')
            try:
                urllib.request.urlopen(req_restart, timeout=5)
            except: pass 
                
        except Exception as e:
            print(f"   ❌ HTTP ERROR: {e}")

    def api_server(self):
        # ... (Legacy API code)
        api_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        api_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        api_sock.bind(("0.0.0.0", 4029))
        api_sock.listen(5)
        print("🔗 API LISTENING on 4029")
        
        while True:
            try:
                conn, _ = api_sock.accept()
                data = conn.recv(1024).decode().strip()
                
                if data == "GET_METRICS":
                    conn.send(json.dumps(self.last_metrics).encode())
                elif data == "GET_RECENT_HASHES":
                    with self.hash_lock:
                        # Send as hex strings
                        hex_hashes = [binascii.hexlify(h).decode() for h in self.recent_hashes]
                        conn.send(json.dumps(hex_hashes).encode())
                        self.recent_hashes = [] # Clear after fetch (Packet mode)
                elif data.startswith("SEED:"):
                    self.current_seed = data.split(":", 1)[1]
                    print(f"\n🌱 SEED CHANGED: {self.current_seed}")
                    conn.send(b"OK")
                elif data.startswith("SET_VOLTAGE:"):
                    vol = int(data.split(":")[1])
                    self.pending_voltage = vol
                    conn.send(b"OK")
                elif data.startswith("SET_FREQUENCY:"):
                    freq = int(data.split(":")[1])
                    self.pending_frequency = freq
                    print(f"🧠 PENDING FREQUENCY CHANGE: {freq} MHz")
                    conn.send(b"OK")
                else:
                    conn.send(b"UNKNOWN_CMD")
                conn.close()
            except: pass

    def handle_client(self, conn, addr):
        self.miner_ip = addr[0]
        print(f"⚡ ASIC CONNECTED: {self.miner_ip}")

        buffer = ""
        # Note: self.pending_voltage is now initialized in __init__

        while True:
            # CHECK FOR PENDING HARDWARE DOSING
            if self.pending_voltage is not None:
                self.set_hardware_params(vol=self.pending_voltage)
                self.pending_voltage = None
            
            if self.pending_frequency is not None:
                self.set_hardware_params(freq=self.pending_frequency)
                self.pending_frequency = None
            
            # Non-blocking receive
            try:
                conn.setblocking(0)
                try:
                    data = conn.recv(4096)
                    if not data: break
                except BlockingIOError:
                    time.sleep(0.01)
                    continue
                except: break
                
                conn.setblocking(1)
                
                arrival_ns = time.time_ns() 
                
                buffer += data.decode('utf-8', errors='ignore')
                while '\n' in buffer:
                    msg_str, buffer = buffer.split('\n', 1)
                    if not msg_str.strip(): continue
                    try:
                        self.process_message(json.loads(msg_str), conn, arrival_ns)
                    except: pass
            except: break

    def process_message(self, msg, conn, timestamp):
        method = msg.get('method')
        msg_id = msg.get('id')

        if method == 'mining.subscribe':
            resp = {"id": msg_id, "result": [[["mining.set_difficulty", "1"], ["mining.notify", "1"]], "08000002", 4], "error": None}
            self.send_json(conn, resp)

        elif method == 'mining.authorize':
            resp = {"id": msg_id, "result": True, "error": None}
            self.send_json(conn, resp)
            self.set_difficulty(conn, DIFFICULTY)
            self.set_frequency(conn, 400) # WAKE UP CALL
            self.send_job(conn)

        elif method == 'mining.submit':
            # Reconstruction for "Honest" Data
            params = msg.get('params', [])
            if len(params) >= 5:
                en2 = params[2]
                ntime = params[3]
                nonce = params[4]
                h = self.calculate_hash(en2, ntime, nonce)
                if h:
                    with self.hash_lock:
                        self.recent_hashes.append(h)
                        if len(self.recent_hashes) > 100: # Limit buffer
                            self.recent_hashes.pop(0)

            # GUARDAR SOLO EL TIEMPO
            self.arrival_times.append(timestamp)
            print(".", end="", flush=True) # Feedback visual
            
            # Análisis en tiempo real (Ventana de 10 eventos)
            if len(self.arrival_times) > 10:
                print("") # Nueva linea
                self.analyze_rhythm()
                self.arrival_times = [] # Reset ventana

            resp = {"id": msg_id, "result": True, "error": None}
            self.send_json(conn, resp)

    def analyze_rhythm(self):
        # Calcular Deltas (Tiempo entre 'spikes')
        times = np.array(self.arrival_times)
        deltas = np.diff(times) # Nanosegundos entre hits
        
        # 1. Burstiness (Coeficiente de Variación)
        # Si CV > 1, el minero está "pensando a ráfagas" (Estructura)
        # Si CV ~ 1, es proceso de Poisson (Aleatorio puro)
        mean_delta = np.mean(deltas)
        std_delta = np.std(deltas)
        cv = std_delta / mean_delta if mean_delta > 0 else 0
        
        # 2. Entropía Temporal
        # Histograma de tiempos de espera
        hist, _ = np.histogram(deltas, bins=10)
        prob = hist / np.sum(hist)
        time_entropy = entropy(prob)

        # UPDATE METRICS (Merge with telemetry)
        self.last_metrics.update({
            "cv": float(cv),
            "time_entropy": float(time_entropy),
            "timestamp": time.time()
        })

        print(f"📊 RITMO: CV={cv:.4f} | Entropía Temporal={time_entropy:.4f}")
        
        if cv > 1.1:
            print("🚀 DETECTADA ACTIVIDAD NO-POISSONIANA (Estructura Temporal)")

    def set_difficulty(self, conn, diff):
        self.send_json(conn, {"id": None, "method": "mining.set_difficulty", "params": [diff]})

    def send_job(self, conn):
        job_id = "chronos_job"
        coinbase = binascii.hexlify(f"{self.current_seed}-{time.time()}".encode()).decode()
        
        # Store for hash reconstruction
        self.current_job_ctx = {
            "version": "20000000",
            "prevhash": "0" * 64,
            "coinb1": coinbase,
            "coinb2": "0000",
            "nbits": "1d00ffff",
        }

        msg = {
            "params": [
                job_id, 
                self.current_job_ctx["prevhash"], 
                self.current_job_ctx["coinb1"], 
                self.current_job_ctx["coinb2"], 
                [], 
                self.current_job_ctx["version"], 
                self.current_job_ctx["nbits"], 
                hex(int(time.time()))[2:], 
                True
            ],
            "id": None, "method": "mining.notify"
        }
        self.send_json(conn, msg)

    def calculate_hash(self, en2_hex, ntime_hex, nonce_hex):
        try:
            if not self.current_job_ctx: return None
            
            # 1. Coinbase Transaction hash (Merkle Root if branch is empty)
            coinbase_hex = self.current_job_ctx["coinb1"] + self.extranonce1 + en2_hex + self.current_job_ctx["coinb2"]
            coinbase_bin = binascii.unhexlify(coinbase_hex)
            merkle_root = hashlib.sha256(hashlib.sha256(coinbase_bin).digest()).digest()

            # 2. Block Header (80 bytes)
            # Reversing components as per Bitcoin Stratum V1 spec
            header = (
                binascii.unhexlify(self.current_job_ctx["version"])[::-1] +
                binascii.unhexlify(self.current_job_ctx["prevhash"])[::-1] +
                merkle_root +
                binascii.unhexlify(ntime_hex)[::-1] +
                binascii.unhexlify(self.current_job_ctx["nbits"])[::-1] +
                binascii.unhexlify(nonce_hex)[::-1]
            )
            
            # 3. Double SHA256
            final_hash = hashlib.sha256(hashlib.sha256(header).digest()).digest()
            return final_hash[::-1] # Standard LE display
        except Exception as e:
            # print(f"DEBUG HASH ERROR: {e}")
            return None

    def send_json(self, conn, data):
        conn.sendall((json.dumps(data) + '\n').encode())

    def start(self):
        while True:
            conn, addr = self.sock.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def set_frequency(self, conn, freq):
        # Universal Driver Wake Up Packet
        # Sends a frequency command to force the chip out of sleep
        print(f"⚡ SENDING WAKE-UP SIGNAL: {freq}MHz")
        self.send_json(conn, {"id": None, "method": "mining.set_frequency", "params": [str(freq)]})

if __name__ == "__main__":
    bridge = ChronosBridge()
    bridge.start()
