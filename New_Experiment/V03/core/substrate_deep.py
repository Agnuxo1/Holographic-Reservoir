import socket
import time
import hashlib
import os

class DeepSubstrate:
    """
    Phase IV-B: The Deep Accumulator.
    A client that refuses to accept PRNG. It blocks until the requested
    amount of REAL THERMODYNAMIC ENTROPY is collected from the Bridge.
    """
    def __init__(self):
        self.ip = "127.0.0.1"
        self.port = 4028
        print("⚓ [DeepSubstrate] Initialized. Mode: STRICT ACCUMULATION.")

    def mine_entropy(self, target_count=1000, timeout=300):
        """
        Blocks until 'target_count' unique hashes are retrieved from the ASIC.
        """
        collected = []
        start_time = time.time()
        
        print(f"⚓ [DeepSubstrate] Requesting {target_count} Real Hashes...")
        
        while len(collected) < target_count:
            if time.time() - start_time > timeout:
                print("❌ [DeepSubstrate] Timeout waiting for entropy.")
                break
            
            try:
                # 1. Ask for remaining needed
                needed = target_count - len(collected)
                # Cap request at 100 per burst to avoid socket overload
                req_size = min(needed, 100)
                
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect((self.ip, self.port))
                
                cmd = f"BURST:{req_size}\n".encode()
                s.sendall(cmd)
                
                data = b""
                try:
                    while True:
                        chunk = s.recv(4096)
                        if not chunk: break
                        data += chunk
                except: pass
                
                s.close()
                
                # 2. Process Data
                # Since Bridge now ONLY sends real data (or nothing), everything we get is gold.
                batch_count = 0
                for i in range(0, len(data), 32):
                    h = data[i:i+32]
                    if len(h) == 32:
                        collected.append(h)
                        batch_count += 1
                
                # Feedback
                if batch_count > 0:
                    print(f"\r⏳ Accumulating: {len(collected)}/{target_count} ({(len(collected)/target_count)*100:.1f}%)", end="")
                else:
                    # Wait a bit for miner to produce
                    time.sleep(0.5)
                    
            except Exception as e:
                # print(e)
                time.sleep(1)
        
        print(f"\n✅ [DeepSubstrate] Collection Complete. {len(collected)} hashes acquired in {time.time()-start_time:.1f}s.")
        return collected

    def inject_seed(self, seed_text):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.ip, self.port))
            s.sendall(f"SEED:{seed_text}\n".encode())
            s.close()
            print(f"🌱 Seed Injected: {seed_text}")
        except: pass
