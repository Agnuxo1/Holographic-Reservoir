import asyncio
import json
import time
import binascii
import hashlib
import os
import urllib.request
import urllib.error
import struct

# Configuration
HOST = "0.0.0.0"
PORT = 3333
API_PORT = 4028

# THE DARK PLENUM SETTINGS
# We set nBits to the easiest possible difficulty (Diff 1) to allow the ASIC
# to flood us with "weak" solutions. We don't care about mining rewards.
# We care about the physical entropy of the search path.
TARGET_DIFFICULTY = 1 
NBITS_DIFF_1 = "1d00ffff" 

class AxeOSController:
    """
    Neuromorphic Control Interface for AxeOS (Bitaxe/LV06).
    Manages voltage/frequency to modulate the 'Temperature' of the Plenum.
    """
    def __init__(self):
        self.miner_ip = None
        self.stats = {}

    def set_target_ip(self, ip):
        if self.miner_ip != ip:
            print(f"🧬 [Plenum] Target Hardware Acquired: {ip}")
            self.miner_ip = ip

    async def poll_telemetry(self):
        if not self.miner_ip: return
        
        url = f"http://{self.miner_ip}/api/system/info"
        try:
            response = await asyncio.to_thread(self._http_get, url)
            if response:
                data = json.loads(response)
                self.stats = {
                    'temp': data.get('temp', 0),
                    'volts': data.get('volts', 0),
                    'power': data.get('power', 0),
                    'freq': data.get('frequency', 0),
                    'best_diff': data.get('bestDiff', 0)
                }
        except Exception as e:
            pass

    def _http_get(self, url):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return response.read()
        except:
            return None

class PlenumBridge:
    """
    Layer 0: The Dark Plenum Bridge.
    Acts as a Stratum Server that 'tricks' the ASIC into streaming maximum entropy.
    """
    def __init__(self):
        self.clients = set()
        self.job_counter = 0
        self.share_counter = 0
        self.start_time = time.time()
        self.axeos = AxeOSController()
        self.entropy_buffer = [] # Buffer for the "Dark Forms"
        
    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        ip = addr[0]
        print(f"⚡ [Plenum] ASIC Link Established: {addr}")
        self.clients.add(writer)
        self.axeos.set_target_ip(ip)
        
        buffer = b""
        try:
            while True:
                data = await reader.read(8192) # Larger buffer for high throughput
                if not data: break
                
                buffer += data
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if not line: continue
                    try:
                        msg = json.loads(line)
                        await self.process_message(writer, msg)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"❌ [Plenum] Link Error {addr}: {e}")
        finally:
            print(f"🔌 [Plenum] ASIC Disconnected: {addr}")
            self.clients.discard(writer)
            writer.close()
            await writer.wait_closed()

    async def process_message(self, writer, msg):
        msg_id = msg.get('id')
        method = msg.get('method')
        
        if method == 'mining.subscribe':
            # V3 Standard Response
            result = [[["mining.set_difficulty", "1"], ["mining.notify", "1"]], "08000002", 4]
            await self.send_res(writer, msg_id, result)

        elif method == 'mining.configure':
            # Enable version rolling for optimization
            result = {"version-rolling": True, "version-rolling.mask": "ffffffff"}
            await self.send_res(writer, msg_id, result)
            
        elif method == 'mining.suggest_difficulty':
            await self.send_res(writer, msg_id, True)

        elif method == 'mining.authorize':
            # Authorize and OPEN THE FLOODGATES
            await self.send_res(writer, msg_id, True)
            print("🔓 [Plenum] Access Authorized. Opening Entropy Valve...")
            await self.send_notif(writer, "mining.set_difficulty", [TARGET_DIFFICULTY])
            await self.send_job(writer)

        elif method == 'mining.submit':
            self.share_counter += 1
            
            # CAPTURE THE PATTERN (Layer 0 -> Layer 1)
            # params: [worker, job_id, extranonce2, ntime, nonce]
            params = msg.get('params', [])
            if len(params) >= 5:
                nonce = params[4]
                # Store specific entropy for API consumption
                # We use (Nonce + Time) hash as a high-quality entropy source
                entropy_seed = f"{nonce}-{time.time()}".encode()
                h = hashlib.sha256(entropy_seed).digest()
                self.entropy_buffer.append(h)
                
                # Keep buffer manageable
                if len(self.entropy_buffer) > 2000:
                    self.entropy_buffer = self.entropy_buffer[-1000:]
            
            await self.send_res(writer, msg_id, True)

    async def send_job(self, writer):
        self.job_counter += 1
        job_id = f"{self.job_counter:x}"
        # Semantic Seed Injection
        current_s = getattr(self, 'current_seed', f"CHIMERA_V3_PLENUM_{time.time()}")
        coinbase = binascii.hexlify(f"{current_s}".encode()).decode()
        
        # The 'nBits' field (7th param) controls the ASIC's target.
        # 1d00ffff is Diff 1. This ensures the ASIC sends EVERYTHING.
        params = [
            job_id,
            "0"*64, coinbase, "0000", [], "20000000", NBITS_DIFF_1, hex(int(time.time()))[2:], True
        ]
        await self.send_notif(writer, "mining.notify", params)

    async def send_res(self, writer, msg_id, result):
        line = json.dumps({"id": msg_id, "result": result, "error": None}) + "\n"
        try:
            writer.write(line.encode())
            await writer.drain()
        except: pass

    async def send_notif(self, writer, method, params):
        line = json.dumps({"id": None, "method": method, "params": params}) + "\n"
        try:
            writer.write(line.encode())
            await writer.drain()
        except: pass

    async def handle_api_client(self, reader, writer):
        # Layer 0 API: Consumed by Layer 1 (Metrics) and Experiments
        # Implements BURST PROTOCOL & SEED INJECTION
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
            message = data.decode().strip()
            
            # 1. SEED INJECTION
            if message.startswith("SEED:"):
                seed_text = message.split(":", 1)[1]
                print(f"🌱 [Plenum] New Semantic Seed Injected: '{seed_text[:30]}...'")
                # Update the global coinbase base
                self.current_seed = seed_text
                # Trigger immediate job update to all clients
                # (Ideally we'd do this, but for now next job loop will pick it up)
                writer.write(b"OK")
                await writer.drain()
                return

            # 2. BURST PROTOCOL
            count = 1
            if message.startswith("BURST:"):
                try:count = min(int(message.split(":")[1]), 1000)
                except: count = 1
            
            response_buffer = b""
            for _ in range(count):
                if self.entropy_buffer:
                    response_buffer += self.entropy_buffer.pop(0)
                else:
                    break # STOP. Do not send fake data.
            
            # If we have no data, we send nothing. Client socket read will timeout/wait.
            # Or we send whatever we have.
            if response_buffer:
                writer.write(response_buffer)
                await writer.drain()
            else:
                # Send explicit WAIT signal? Or just close?
                # Best to just write nothing and close. Client will see 0 bytes and retry.
                pass
            
        except Exception: pass
        finally: 
            writer.close()
            await writer.wait_closed()

    async def start_api(self):
        print(f"🔗 [Plenum] Bridge API Listening on 0.0.0.0:{API_PORT}")
        server = await asyncio.start_server(self.handle_api_client, "0.0.0.0", API_PORT)
        async with server: await server.serve_forever()

    async def telemetry_loop(self):
        print(f"📊 [Plenum] Telemetry Active")
        while True:
            await asyncio.sleep(2.0) # Fast poll for high precision
            await self.axeos.poll_telemetry()
            
            # Status Report
            elapsed = time.time() - self.start_time
            sps = self.share_counter / elapsed if elapsed > 0 else 0
            
            axe_stats = self.axeos.stats
            status = f"🌌 STATUS: {sps:.2f} Flow/sec | Buffer: {len(self.entropy_buffer)}"
            if axe_stats:
                status += f" | 🌡️ {axe_stats.get('temp')}C | ⚡ {axe_stats.get('power')}W | 🧠 {axe_stats.get('freq')}MHz"
                
            print(status)

    async def job_generator_loop(self):
        # "Tsunami Mode": Keep the ASIC overwhelmed with work
        print(f"🌊 [Plenum] Tsunami Job Generator Active")
        while True:
            await asyncio.sleep(5.0) 
            if self.clients:
                for writer in list(self.clients):
                    try: await self.send_job(writer)
                    except: pass

    async def start(self):
        print(f"🚀 CHIMERA V3: THE DARK PLENUM BRIDGE (AsyncIO + Flood)")
        print(f"    Target: 500 GH/s Flow | Strategy: nBits Hack ({NBITS_DIFF_1})")
        
        # Start Servers
        server = await asyncio.start_server(self.handle_client, HOST, PORT)
        asyncio.create_task(self.telemetry_loop())
        asyncio.create_task(self.job_generator_loop())
        asyncio.create_task(self.start_api())
        
        async with server:
            await server.serve_forever()

if __name__ == "__main__":
    bridge = PlenumBridge()
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        print("🛑 [Plenum] Collapse.")
