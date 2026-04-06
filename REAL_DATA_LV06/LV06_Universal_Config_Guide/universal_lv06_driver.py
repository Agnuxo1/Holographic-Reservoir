"""
Lucky Miner LV06 Universal Driver SDK v1.0
Hardware Support: Bitmain BM1387 (AxeOS Firmware) or BM1366
Purpose: High-performance Neuromorphic Reservoir Computing Control
"""

import socket
import json
import time
import struct
import requests
import threading
from typing import Optional, List, Dict, Any, Callable

class LV06Config:
    """Manages HTTP API interactions for device configuration."""
    def __init__(self, ip: str):
        self.ip = ip
        self.base_url = f"http://{ip}/api"

    def set_frequency(self, mhz: int) -> bool:
        """Sets the ASIC frequency and reboots if necessary."""
        try:
            r = requests.patch(f"{self.base_url}/system", json={"frequency": mhz}, timeout=5)
            return r.status_code == 200
        except Exception as e:
            print(f"[LV06] Config Error: {e}")
            return False

    def reboot(self):
        """Triggers a hardware reboot."""
        try:
            requests.post(f"{self.base_url}/reboot", timeout=2)
            return True
        except:
            return False

class LV06StratumServer(threading.Thread):
    """
    High-fidelity Stratum Server for state injection and harvesting.
    Optimized for low-latency neuromorphic feedback.
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 3333):
        super().__init__()
        self.host = host
        self.port = port
        self.running = True
        self.connection_active = False
        self.client_conn = None
        self.current_shares = []
        self.job_counter = 0
        
        # Stratum Constants
        self.extranonce1 = "08000002"
        self.extranonce2_size = 4

    def run(self):
        """Main server loop."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(1)
        sock.settimeout(1.0)
        
        print(f"[Stratum] Listening on {self.host}:{self.port}")
        
        while self.running:
            try:
                conn, addr = sock.accept()
                self._handle_client(conn)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running: print(f"[Stratum] Socket Error: {e}")

    def _handle_client(self, conn):
        self.client_conn = conn
        self.connection_active = True
        buffer = ""
        while self.running:
            try:
                data = conn.recv(8192).decode('utf-8', errors='ignore')
                if not data: break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    self._process_line(conn, line)
            except:
                break
        self.connection_active = False
        self.client_conn = None

    def _process_line(self, conn, line):
        try:
            msg = json.loads(line)
        except: return
        
        mid = msg.get('id')
        method = msg.get('method')
        
        if method == 'mining.subscribe':
            res = [[["mining.set_difficulty", "s1"], ["mining.notify", "s2"]], self.extranonce1, self.extranonce2_size]
            self._send(conn, {"id": mid, "result": res, "error": None})
        elif method == 'mining.authorize':
            self._send(conn, {"id": mid, "result": True, "error": None})
        elif method == 'mining.submit':
            # Capture share with high-precision timestamp
            arrival = time.perf_counter()
            self._send(conn, {"id": mid, "result": True, "error": None})
            self.current_shares.append({"time": arrival, "msg": msg})
        elif method == 'mining.configure':
            self._send(conn, {"id": mid, "result": {"version-rolling.mask": "ffffffff"}, "error": None})

    def _send(self, conn, data):
        try:
            line = json.dumps(data) + "\n"
            conn.sendall(line.encode())
        except: pass

    def set_difficulty(self, diff: float):
        """Updates the difficulty target for the miner."""
        if self.client_conn:
            self._send(self.client_conn, {"id": None, "method": "mining.set_difficulty", "params": [diff]})

    def inject_input(self, value: float, clean_jobs: bool = True):
        """
        Injects a normalized value into the ASIC via the Coinbase script.
        Uses OP_PUSH format for hardware validation.
        """
        if not self.client_conn: return False
        
        self.job_counter += 1
        u_hex = struct.pack('>f', value).hex()
        
        # Professional Coinbase Structure: [Version][InCnt][Prev][Idx][ScriptLen][Data]
        header = "01000000" + "01" + "00" * 32 + "ffffffff" + "10" 
        # Encapsulated Input (OP_PUSH4 + 4 bytes + OP_PUSH10 + Padding)
        coinb1 = header + "04" + u_hex + "0a" + "00"*10
        coinb2 = "ffffffff" + "01" + "00f2052a01000000" + "00"*8
        ntime = hex(int(time.time()))[2:].zfill(8)
        
        params = [str(self.job_counter), "0"*64, coinb1, coinb2, [], "20000000", "1f00ffff", ntime, clean_jobs]
        self._send(self.client_conn, {"id": None, "method": "mining.notify", "params": params})
        return True

    def harvest_state(self):
        """Returns and clears all shares captured since last call."""
        batch = list(self.current_shares)
        self.current_shares = []
        return batch

    def stop(self):
        self.running = False
        if self.client_conn: self.client_conn.close()

if __name__ == "__main__":
    # Self-test / Example usage
    print("LV06 Driver SDK initialized.")
