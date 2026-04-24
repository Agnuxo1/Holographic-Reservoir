import socket
import json
import time
import threading
from collections import deque

HOST_IP = "0.0.0.0"
PORT = 3333

class BenchmarkServer:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST_IP, PORT))
        self.sock.listen(1)
        self.client_conn = None
        self.share_times = deque()
        self.start_time = None
        self.running = True

    def handle_client(self, conn, addr):
        print(f"✅ BENCHMARK: Connected to {addr}")
        self.client_conn = conn
        self.start_time = time.time()
        
        while self.running:
            try:
                data = conn.recv(1024)
                if not data: break
                
                messages = data.decode().split('\n')
                for msg in messages:
                    if not msg: continue
                    # print(f"DEBUG: {msg[:100]}...") # Log incoming
                    try:
                        self.process_message(json.loads(msg), conn)
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                print(f"❌ Connection error: {e}")
                break

    def process_message(self, msg, conn):
        msg_id = msg.get('id')
        method = msg.get('method')
        
        if method == 'mining.subscribe':
            response = {"id": msg_id, "result": [[["mining.set_difficulty", "1"], ["mining.notify", "1"]], "08000002", 4], "error": None}
            self.send_json(conn, response)
            
        elif method == 'mining.authorize':
            response = {"id": msg_id, "result": True, "error": None}
            self.send_json(conn, response)
            print("🔓 BENCHMARK STARTING: Difficulty 1")
            
            # Send initial job with diff 1
            self.set_difficulty(conn, 1)
            self.send_job(conn)

        elif method == 'mining.submit':
            self.share_times.append(time.time())
            response = {"id": msg_id, "result": True, "error": None}
            self.send_json(conn, response)
            self.send_job(conn) # Keep feeding

    def send_json(self, conn, data):
        line = json.dumps(data) + '\n'
        try:
            conn.sendall(line.encode())
        except:
            pass

    def set_difficulty(self, conn, diff):
        msg = {"id": None, "method": "mining.set_difficulty", "params": [diff]}
        self.send_json(conn, msg)

    def send_job(self, conn):
        # Dummy job
        job_id = "bench"
        coinbase = "00" * 32
        msg = {
            "params": [
                job_id,
                "00"*32,
                coinbase,
                "0000",
                [],
                "20000000",
                "1d00ffff",
                hex(int(time.time()))[2:],
                True
            ],
            "id": None,
            "method": "mining.notify"
        }
        self.send_json(conn, msg)

    def start(self):
        print(f"⏳ Waiting for Miner on query port {PORT}...")
        
        # Start server thread
        server_thread = threading.Thread(target=self._accept_loop)
        server_thread.daemon = True
        server_thread.start()

        # Monitoring loop
        # Wait up to 60s for connection
        timeout = 60 
        start_wait = time.time()
        
        while self.running:
            if self.client_conn:
                # Benchmark phase
                elapsed = time.time() - self.start_time
                if elapsed >= 30: # Wait for 30 seconds of data
                    self.report()
                    self.running = False
                    break
            else:
                current_wait = time.time() - start_wait
                if current_wait > timeout:
                     print("❌ Timeout waiting for miner connection.")
                     self.running = False
                     break
            time.sleep(0.5)
        
        try:
            if self.client_conn: self.client_conn.close()
            self.sock.close()
        except:
            pass

    def _accept_loop(self):
        try:
            while self.running:
                conn, addr = self.sock.accept()
                t = threading.Thread(target=self.handle_client, args=(conn, addr))
                t.daemon = True
                t.start()
        except:
            pass

    def report(self):
        total_shares = len(self.share_times)
        if total_shares < 2:
            print(f"⚠️ Not enough data collected ({total_shares} shares).")
            return

        duration = self.share_times[-1] - self.share_times[0]
        sps = total_shares / duration if duration > 0 else 0
        
        # Estimated Hashrate
        # 1 share at diff 1 = 2^32 hashes = 4.29 Billion hashes
        hashrate_ghs = (sps * 4.294967296) 

        print("\n" + "="*40)
        print("🚀 BENCHMARK RESULTS (30s sample)")
        print("="*40)
        print(f"Total Shares:      {total_shares}")
        print(f"Duration:          {duration:.2f} s")
        print(f"Speed:             {sps:.2f} Shares/sec")
        print(f"Est. Throughput:   {hashrate_ghs:.2f} GH/s")
        print("="*40 + "\n")

if __name__ == "__main__":
    srv = BenchmarkServer()
    srv.start()
