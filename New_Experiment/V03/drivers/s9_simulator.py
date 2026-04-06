import hashlib
import struct
import time
import binascii

class S9_Miner:
    """
    Simulates the specific behavior of the BM1387 chip (Antminer S9).
    It performs the Double SHA-256 (SHA256d) function on a standard 80-byte Bitcoin header format.
    
    In CHIMERA, the 'Merkle Root' field (bytes 36-68) is used to inject the "Neuro-Seed".
    """
    
    def __init__(self, simulation_difficulty_bits=16):
        """
        :param simulation_difficulty_bits: Number of zero bits required at start of hash.
                                           16 bits = ~65k hashes per "spike". good for Python speed.
                                           20 bits = ~1M hashes.
        """
        self.difficulty_bits = simulation_difficulty_bits
        self._update_target()
        
        # Approximate S9 chip stats for scaling measurements (not used for logic, just metadata)
        self.real_chip_freq = 600e6 # 600 MHz
        
        print(f"[S9 Simulator] Initialized. Difficulty: {self.difficulty_bits} bits")

    def _update_target(self):
        """Recalculates target based on bits."""
        self.target_prefix_zeros = self.difficulty_bits // 8
        self.extra_bits = self.difficulty_bits % 8

    def set_difficulty(self, bits):
        """
        Dynamically adjusts the "Consciousness Threshold".
        """
        # Clamp to reasonable simulation limits (e.g. 8 to 24 bits)
        # 8 bits = super easy (full noise)
        # 24 bits = very hard (deep focus/sleep)
        bits = max(8, min(24, int(bits)))
        
        if bits != self.difficulty_bits:
            self.difficulty_bits = bits
            self._update_target()
            return True
        return False

    def sha256d(self, data):
        """Double SHA-256 hash."""
        return hashlib.sha256(hashlib.sha256(data).digest()).digest()

    def check_difficulty(self, hash_bytes):
        """
        Checks if the hash meets the difficulty target.
        This mimics the hardware comparator.
        """
        # 1. Full byte checks
        for i in range(self.target_prefix_zeros):
            if hash_bytes[i] != 0:
                return False
        
        # 2. Remaining bit check
        if self.extra_bits > 0:
            # We need the next byte to be smaller than 2^(8 - extra_bits)
            limit = 1 << (8 - self.extra_bits)
            if hash_bytes[self.target_prefix_zeros] >= limit:
                return False
                
        return True

    def construct_header(self, seed_int):
        """
        Constructs a valid 80-byte Bitcoin Block Header with the Neuro-Seed.
        Format:
        - Version (4 bytes)
        - Prev Block (32 bytes)
        - Merkle Root (32 bytes) <-- SEED GOES HERE
        - Time (4 bytes)
        - Bits (4 bytes)
        - Nonce (4 bytes)
        """
        version = struct.pack("<I", 2) # Version 2
        prev_block = b'\x00' * 32
        
        # Neuro-Seed Injection into Merkle Root
        # We fill the 32 bytes with the seed repeated or padded
        seed_bytes = struct.pack("<I", seed_int)
        merkle_root = (seed_bytes * 8)[:32] 
        
        timestamp = struct.pack("<I", int(time.time()))
        bits = struct.pack("<I", 0x1d00ffff) # Standard Diff
        # Nonce is processed in the loop
        
        return version + prev_block + merkle_root + timestamp + bits

    def mine(self, seed_int, timeout_ms=500):
        """
        The Main "Chip" Loop.
        Iterates nonces to find hashes matching the target.
        
        :return: List of valid 'spikes' (hashes) found.
        """
        base_header = self.construct_header(seed_int)
        
        found_spikes = []
        hashes_computed = 0
        start_time = time.time()
        
        # Simulate the nonce range of a chip (0 to 2^32)
        # In Python we just loop until timeout
        nonce = 0
        
        while True:
            # Check timeout
            elapsed = (time.time() - start_time) * 1000
            if elapsed > timeout_ms:
                break
                
            # Pack nonce (4 bytes, Little Endian)
            nonce_bytes = struct.pack("<I", nonce)
            
            # Combine header + nonce
            # Note: In real valid block hashing, nonce is at end (offset 76)
            full_header = base_header + nonce_bytes
            
            # Hash
            h_out = self.sha256d(full_header)
            hashes_computed += 1
            
            # Filter (Comparator)
            if self.check_difficulty(h_out):
                # Reverse for standard display (LE vs BE confusion in mining)
                # But for CHIMERA signal, raw bytes is fine.
                found_spikes.append(h_out)
            
            nonce += 1
            
            # Python optimization: Check time less frequently
            if nonce % 1000 == 0:
                elapsed = (time.time() - start_time) * 1000
                if elapsed > timeout_ms:
                    break

        return found_spikes, hashes_computed
