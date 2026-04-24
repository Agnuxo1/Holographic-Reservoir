import socket
import time
import json
import urllib.request
import statistics
import threading

# Config
DRIVER_IP = "127.0.0.1"
DRIVER_PORT = 4028
MINER_IP = "192.168.0.15" # Hardcoded from discovery
SAMPLES = 1000

class Benchmark:
    def __init__(self):
        self.latencies = []
        self.power_readings = []
        self.temp_readings = []
        self.running = True
        
    def poll_telemetry(self):
        while self.running:
            try:
                url = f"http://{MINER_IP}/api/system/info"
                with urllib.request.urlopen(url, timeout=2) as response:
                    data = json.loads(response.read())
                    self.power_readings.append(data.get('power', 0))
                    self.temp_readings.append(data.get('temp', 0))
            except:
                pass
            time.sleep(1)

    def measure_entropy(self):
        print(f"⚡ Starting Entropy Benchmark ({SAMPLES} samples)...")
        start_total = time.time()
        
        for i in range(SAMPLES):
            t0 = time.time()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2.0)
                    s.connect((DRIVER_IP, DRIVER_PORT))
                    data = s.recv(32)
                    if len(data) != 32:
                        print(f"⚠️ Partial data: {len(data)}")
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                
            t1 = time.time()
            self.latencies.append((t1 - t0) * 1000) # ms
            
            if i % 100 == 0:
                print(f"   Progress: {i}/{SAMPLES}")

        total_time = time.time() - start_total
        print(f"✅ Completed in {total_time:.2f}s")

    def report(self):
        avg_lat = statistics.mean(self.latencies)
        min_lat = min(self.latencies)
        max_lat = max(self.latencies)
        jitter = statistics.stdev(self.latencies)
        
        avg_pwr = statistics.mean(self.power_readings) if self.power_readings else 0
        avg_tmp = statistics.mean(self.temp_readings) if self.temp_readings else 0
        
        print("\n" + "="*40)
        print("🇨🇱 CHIMERA SYSTEM BENCHMARK RESULTS")
        print("="*40)
        print(f"🔢 Samples:       {SAMPLES}")
        print(f"⏱️ Latency (Avg): {avg_lat:.2f} ms")
        print(f"🚀 Latency (Min): {min_lat:.2f} ms")
        print(f"🐢 Latency (Max): {max_lat:.2f} ms")
        print(f"〰️ Jitter:        {jitter:.2f} ms")
        print("-" * 20)
        print(f"⚡ Avg Power:     {avg_pwr:.2f} W")
        print(f"🌡️ Avg Temp:      {avg_tmp:.2f} C")
        print("="*40)

if __name__ == "__main__":
    bench = Benchmark()
    
    # Start telemetry poller in background
    t = threading.Thread(target=bench.poll_telemetry)
    t.start()
    
    try:
        bench.measure_entropy()
    finally:
        bench.running = False
        t.join()
        
    bench.report()
