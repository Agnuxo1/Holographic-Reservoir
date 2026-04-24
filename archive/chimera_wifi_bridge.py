import asyncio
import json
import time
import binascii
import hashlib
import os
import urllib.request
import urllib.error

# Configuration
HOST = "0.0.0.0"
PORT = 3333
API_PORT = 4028
TARGET_DIFFICULTY = 128 # Hardware Floor
NBITS_DIFF_1 = "1d00ffff" 

class AxeOSController:
    """
    Neuromorphic Control Interface for AxeOS (Bitaxe/LV06).
    Uses HTTP API to read/write biological parameters (Voltage/Freq).
    """
    def __init__(self):
        self.miner_ip = None
        self.stats = {}

    def set_target_ip(self, ip):
        if self.miner_ip != ip:
            print(f"🧬 AxeOS Target Acquired: {ip}")
            self.miner_ip = ip

    async def restart_miner(self):
        if not self.miner_ip: return
        print(f"🔄 RESTARTING MINER TO APPLY CONFIG...")
        url = f"http://{self.miner_ip}/api/system/restart"
        try:
            req = urllib.request.Request(url, data=b"{}", method='POST')
            req.add_header('Content-Type', 'application/json')
            await asyncio.to_thread(urllib.request.urlopen, req)
            print("✅ Restart Command Sent")
        except Exception as e:
            print(f"❌ Restart Failed: {e}")

    async def set_frequency(self, mhz, volts):
        if not self.miner_ip: return
        print(f"💉 INJECTING PLASTICITY: {mhz} MHz / {volts} mV")
        
        url = f"http://{self.miner_ip}/api/system"
        payload = json.dumps({
            "frequency": int(mhz),
            "volts": int(volts)
        }).encode('utf-8')
        
        try:
            req = urllib.request.Request(url, data=payload, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            await asyncio.to_thread(urllib.request.urlopen, req)
            print("✅ Plasticity Accepted")
            
            # Restart to apply PLLs
            await asyncio.sleep(2.0)
            await self.restart_miner()
            
        except Exception as e:
            print(f"❌ Plasticity Rejected: {e}")

    async def poll_telemetry(self):
        if not self.miner_ip: return
        
        url = f"http://{self.miner_ip}/api/system/info"
        try:
            # Run blocking IO in thread
            response = await asyncio.to_thread(self._http_get, url)
            if response:
                data = json.loads(response)
                # Map interesting fields
                self.stats = {
                    'temp': data.get('temp', 0),
                    'volts': data.get('volts', 0),
                    'power': data.get('power', 0),
                    'freq': data.get('frequency', 0),
                    'best_diff': data.get('bestDiff', 0)
                }
                
                # --- HOMEOSTASIS LOGIC ---
                # Detecting "Coma State" (Low Freq < 300MHz)
                current_freq = self.stats.get('freq', 0)
                if current_freq > 0 and current_freq < 300:
                    print(f"⚠️ DETECTED LOW ENERGY STATE ({current_freq} MHz). BOOSTING...")
                    await self.set_frequency(400, 1200) # Safe Boost
                    
        except Exception as e:
            # print(f"⚠️ AxeOS Link Error: {e}")
            pass

    def _http_get(self, url):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return response.read()
        except:
            return None

class ChimeraDriver:
    def __init__(self):
        self.clients = set()
        self.job_counter = 0
        self.share_counter = 0
        self.start_time = time.time()
        self.axeos = AxeOSController()
        
    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        ip = addr[0]
        print(f"🔌 Connected: {addr}")
        self.clients.add(writer)
        
        # Link this connection to AxeOS Controller
        self.axeos.set_target_ip(ip)
        
        buffer = b""
        try:
            while True:
                data = await reader.read(1024)
                if not data: break
                
                buffer += data
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if not line: continue
                    try:
                        # print(f"DEBUG IN: {line}")
                        msg = json.loads(line)
                        await self.process_message(writer, msg)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"❌ Error {addr}: {e}")
        finally:
            print(f"🔌 Disconnected: {addr}")
            self.clients.discard(writer)
            writer.close()
            await writer.wait_closed()

    async def process_message(self, writer, msg):
        msg_id = msg.get('id')
        method = msg.get('method')
        
        if method == 'mining.subscribe':
            result = [[["mining.set_difficulty", "1"], ["mining.notify", "1"]], "08000002", 4]
            await self.send_res(writer, msg_id, result)

        elif method == 'mining.configure':
            # AxeOS supports version-rolling
            result = {"version-rolling": True, "version-rolling.mask": "ffffffff"}
            await self.send_res(writer, msg_id, result)
            
        elif method == 'mining.suggest_difficulty':
            await self.send_res(writer, msg_id, True)

        elif method == 'mining.authorize':
            await self.send_res(writer, msg_id, True)
            print("🔓 Worker Authorized. Setting Difficulty & Sending Job...")
            await self.send_notif(writer, "mining.set_difficulty", [TARGET_DIFFICULTY])
            await self.send_job(writer)

        elif method == 'mining.submit':
            self.share_counter += 1
            await self.send_res(writer, msg_id, True)
            # await self.send_job(writer) # Optional: Instant Re-Job

    async def send_job(self, writer):
        self.job_counter += 1
        job_id = f"{self.job_counter:x}"
        coinbase = binascii.hexlify(f"CHIMERA_{time.time()}".encode()).decode()
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
        # API for Substrate (Port 4028) - OPTIMIZED BURST PROTOCOL
        try:
            # Wait for command (e.g., "BURST:100\n")
            data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
            message = data.decode().strip()
            
            count = 1
            if message.startswith("BURST:"):
                try:
                    count = int(message.split(":")[1])
                    count = min(count, 1000) # Cap at 1000 for safety
                except:
                    count = 1
            
            response_buffer = b""
            for _ in range(count):
                if self.share_counter > 0:
                    # Use share counter + time + index to generate unique entropy
                    # We add loop index to ensure distinct hashes within the burst
                    entropy_seed = f"{self.share_counter}-{time.time()}-{_}".encode() 
                    response_buffer += hashlib.sha256(entropy_seed).digest()
                else:
                    response_buffer += os.urandom(32)
            
            writer.write(response_buffer)
            await writer.drain()
            
        except Exception as e:
            # print(f"API Error: {e}")
            pass
        finally: 
            writer.close()
            await writer.wait_closed()

    async def start_api(self):
        print(f"🔗 ENTROPY API Listening on 0.0.0.0:{API_PORT}")
        server = await asyncio.start_server(self.handle_api_client, "0.0.0.0", API_PORT)
        async with server: await server.serve_forever()

    async def telemetry_loop(self):
        print(f"📊 Telemetry Active")
        while True:
            await asyncio.sleep(5)
            # Poll AxeOS
            await self.axeos.poll_telemetry()
            
            # Substrate Stats
            elapsed = time.time() - self.start_time
            sps = self.share_counter / elapsed if elapsed > 0 else 0
            ghs = sps * 4.295 # Approx for Diff 1, but we are Diff 128, so * 128? 
            # Actually GHS = Starts * Difficulty * 2^32 / Time
            # But let's keep simple metrics
            
            # Display Hybrid Stats
            axe_stats = self.axeos.stats
            status = f"📊 STATUS: {sps:.2f} Shares/sec"
            if axe_stats:
                status += f" | 🌡️ {axe_stats.get('temp')}C | ⚡ {axe_stats.get('power')}W | 🧠 {axe_stats.get('freq')}MHz | 🔋 {axe_stats.get('volts')}mV"
            else:
                status += " | ⏳ Waiting for AxeOS Telemetry..."
                
            print(status)

    async def job_generator_loop(self):
        print(f"🌊 Chaos Injection Passive (10.0s interval)")
        while True:
            await asyncio.sleep(10.0) 
            if self.clients:
                for writer in list(self.clients):
                    try: await self.send_job(writer)
                    except: pass

    async def start(self):
        print(f"🚀 CHIMERA HYBRID DRIVER v2.0 (AxeOS Capable)")
        server = await asyncio.start_server(self.handle_client, HOST, PORT)
        
        asyncio.create_task(self.telemetry_loop())
        asyncio.create_task(self.job_generator_loop())
        asyncio.create_task(self.start_api())
        
        async with server:
            await server.serve_forever()

if __name__ == "__main__":
    driver = ChimeraDriver()
    try:
        asyncio.run(driver.start())
    except KeyboardInterrupt:
        print("🛑 Driver Stopped")