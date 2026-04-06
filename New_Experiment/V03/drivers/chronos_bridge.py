import socket
import json
import time
import threading
import numpy as np
import binascii

try:
    from scipy.stats import entropy
except ImportError:
    def entropy(pk):
        pk = np.array(pk)
        return -np.sum(pk * np.log(pk + 1e-9))

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
        self.last_metrics = {"cv": 1.0, "time_entropy": 0.0, "timestamp": 0} # Metrics Storage
        print(f"⏳ CHRONOS LISTENER OPENED on {HOST_IP}:{PORT}")
        
        # Start API Thread
        threading.Thread(target=self.api_server, daemon=True).start()

    def api_server(self):
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
                elif data.startswith("SEED:"):
                    self.current_seed = data.split(":", 1)[1]
                    print(f"\n🌱 SEED CHANGED: {self.current_seed}")
                    conn.send(b"OK")
                else:
                    conn.send(b"UNKNOWN_CMD")
                conn.close()
            except: pass

    def handle_client(self, conn, addr):
        print(f"⚡ ASIC CONNECTED: {addr}")
        buffer = ""
        while True:
            try:
                data = conn.recv(4096)
                if not data: break
                
                # TIMESTAMP DE PRECISIÓN AL RECIBIR EL PAQUETE FÍSICO
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

        # STORE FOR API
        self.last_metrics = {
            "cv": float(cv),
            "time_entropy": float(time_entropy),
            "timestamp": time.time()
        }

        print(f"📊 RITMO: CV={cv:.4f} | Entropía Temporal={time_entropy:.4f}")
        
        if cv > 1.1:
            print("🚀 DETECTADA ACTIVIDAD NO-POISSONIANA (Estructura Temporal)")

    def set_difficulty(self, conn, diff):
        self.send_json(conn, {"id": None, "method": "mining.set_difficulty", "params": [diff]})

    def send_job(self, conn):
        job_id = "chronos_job"
        coinbase = binascii.hexlify(f"{self.current_seed}-{time.time()}".encode()).decode()
        msg = {
            "params": [job_id, "0"*64, coinbase, "0000", [], "20000000", "1d00ffff", hex(int(time.time()))[2:], True],
            "id": None, "method": "mining.notify"
        }
        self.send_json(conn, msg)

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
