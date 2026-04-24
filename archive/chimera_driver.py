import asyncio
import json
import time
import binascii

# Configuration
HOST = "0.0.0.0"
PORT = 3333
TARGET_DIFFICULTY = 128 # Baseline to establish flow
# Standard Diff 1 nBits
NBITS_DIFF_1 = "1d00ffff" 

class ChimeraDriver:
    def __init__(self):
        self.clients = set()
        self.job_counter = 0
        self.share_counter = 0
        self.start_time = time.time()
        self.last_report = time.time()
        
    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"🔌 Connected: {addr}")
        self.clients.add(writer)
        
        # Buffer for processing lines
        buffer = b""
        
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                
                buffer += data
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if not line: continue
                    
                    try:
                        print(f"DEBUG IN: {line}")
                        msg = json.loads(line)
                        await self.process_message(writer, msg)
                    except json.JSONDecodeError:
                        print(f"⚠️ Bad JSON: {line}")
                        
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
        params = msg.get('params', [])

        if method == 'mining.subscribe':
            # Respond with subscription details
            # Extranonce1 (hex), Extranonce2_size (int)
            result = [
                [["mining.set_difficulty", "1"], ["mining.notify", "1"]],
                "08000002", # Extranonce1
                4           # Extranonce2_size
            ]
            await self.send_res(writer, msg_id, result)

        elif method == 'mining.configure':
            # Re-enable version rolling as miner seems to prefer it
            # params: [["version-rolling"], {"version-rolling.mask": "ffffffff"}]
            result = {
                "version-rolling": True,
                "version-rolling.mask": "ffffffff" 
            }
            await self.send_res(writer, msg_id, result)
            
        elif method == 'mining.suggest_difficulty':
            # Miner wants diff 1000. Ack it.
            await self.send_res(writer, msg_id, True)

        elif method == 'mining.authorize':
            # Authorize worker
            await self.send_res(writer, msg_id, True)
            print("🔓 Worker Authorized. Setting Difficulty & Sending Job...")
            
            # 1. Set Difficulty
            await self.send_notif(writer, "mining.set_difficulty", [TARGET_DIFFICULTY])
            
            # 2. Send First Job
            await self.send_job(writer)

        elif method == 'mining.submit':
            # Receive Share
            self.share_counter += 1
            # params: worker_name, job_id, extranonce2, ntime, nonce
            # print(f"🦋 Share: {params[4]}") # Verbose off for speed
            await self.send_res(writer, msg_id, True)
            
            # Send new job occasionally or let it run? 
            # For now, let's rely on the periodic update loop.

    async def send_job(self, writer):
        self.job_counter += 1
        job_id = f"{self.job_counter:x}"
        
        # CHIMERA Payload (Merkle Root simulation)
        # We put random/time-based data in coinbase to vary the block
        coinbase = binascii.hexlify(f"CHIMERA_ENTROPY_{time.time()}".encode()).decode()
        
        params = [
            job_id,
            "0000000000000000000000000000000000000000000000000000000000000000", # PrevHash
            coinbase,   # Coinb1
            "0000",     # Coinb2 (Legacy)
            [],         # Merkle Branch
            "20000000", # Version
            NBITS_DIFF_1, # nBits (Critical for LV06 to accept work as Valid)
            hex(int(time.time()))[2:], # nTime
            True        # clean_jobs (Force switch)
        ]
        await self.send_notif(writer, "mining.notify", params)

    async def send_res(self, writer, msg_id, result):
        response = {"id": msg_id, "result": result, "error": None}
        line = json.dumps(response) + "\n"
        try:
            writer.write(line.encode())
            await writer.drain()
        except:
            pass

    async def send_notif(self, writer, method, params):
        msg = {"id": None, "method": method, "params": params}
        line = json.dumps(msg) + "\n"
        try:
            writer.write(line.encode())
            await writer.drain()
        except:
            pass

    async def telemetry_loop(self):
        print(f"📊 Telemetry Active")
        while True:
            await asyncio.sleep(5)
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                sps = self.share_counter / elapsed
                hashrate_ghs = (sps * 4.294967296) # Based on Diff 1
                
                print(f"📊 STATUS: {sps:.2f} Shares/sec | Est: {hashrate_ghs:.2f} GH/s | Total Shares: {self.share_counter}")

    async def job_generator_loop(self):
        # FLOOD MODE: Keep miner active
        print(f"🌊 Chaos Injection Active (5.0s interval - Low Diff)")
        while True:
            await asyncio.sleep(5.0) 
            if self.clients:
                for writer in list(self.clients):
                    try:
                        await self.send_job(writer)
                    except:
                        pass

    async def start(self):
        print(f"🚀 CHIMERA DRIVER v1.0 Starting on 0.0.0.0:{PORT}")
        server = await asyncio.start_server(self.handle_client, HOST, PORT)
        
        asyncio.create_task(self.telemetry_loop())
        asyncio.create_task(self.job_generator_loop())
        
        async with server:
            await server.serve_forever()

if __name__ == "__main__":
    driver = ChimeraDriver()
    try:
        asyncio.run(driver.start())
    except KeyboardInterrupt:
        print("🛑 Driver Stopped")
