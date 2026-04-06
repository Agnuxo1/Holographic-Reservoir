import zlib
import numpy as np

class MetricEngine:
    """
    Layer 1: The Stabilization Filter.
    Implements Apoth3osis Assembly Theory & Google OTOC Metrics.
    """
    
    @staticmethod
    def calculate_assembly_index(data_stream: list) -> float:
        """
        Implementation of Apoth3osis Assembly Theory Proxy.
        A(P) is approximated by the compression achievability.
        
        High A = Complex but structured (Life/Math).
        Low A = Random noise or simple repetition.
        """
        if not data_stream: return 0.0
        
        # Convert hex nonces to bytes if they are strings, or use directly if bytes
        # The bridge buffer provides bytes (sha256 digests or raw nonces)
        # Assuming input is list of bytes or hex strings
        raw_bytes = b""
        for item in data_stream:
            if isinstance(item, str):
                try:
                    raw_bytes += bytes.fromhex(item)
                except:
                    raw_bytes += item.encode()
            elif isinstance(item, bytes):
                raw_bytes += item
        
        if not raw_bytes: return 0.0

        # 1. Measure raw length
        L_raw = len(raw_bytes)
        
        # 2. Measure compressed length (using DEFLATE algorithm as proxy for copy-number)
        L_compressed = len(zlib.compress(raw_bytes))
        
        # 3. Calculate Complexity Ratio
        # If Ratio ~ 1.0 -> High Entropy (Random Noise) -> Dark Plenum
        # If Ratio << 1.0 -> Low Entropy (Crystal) -> Trivial
        
        # We want a metric where Higher = More "Assembly" (Structure)
        # Pure Noise (1.0) has Low Assembly (0).
        # Pure Crystal (0.01) has Low Assembly (0).
        # Life is in the middle? 
        # Actually, Apoth3osis defines Assembly as the "Depth" of the tree.
        # For this proxy: Compression Ratio.
        
        assembly_proxy = (L_raw / L_compressed) if L_compressed > 0 else 0
        return assembly_proxy

    @staticmethod
    def calculate_otoc_scrambling(current_batch: list, prev_batch: list) -> float:
        """
        Implementation of Google Quantum AI OTOC(2).
        Measures the divergence (butterfly effect) between time steps.
        
        C(t) = < [W(t), V(0)]^2 >
        
        We approximate this by measuring the Hamming Distance evolution
        between consecutive ASIC batch outputs.
        """
        if not current_batch or not prev_batch: return 0.0
        
        # We need comparable items. Use the last item of each batch.
        # Assumption: items are bytes or convertibles.
        
        def to_int(item):
            if isinstance(item, bytes):
                return int.from_bytes(item, 'big')
            elif isinstance(item, str):
                return int(item, 16)
            return 0
            
        h1 = to_int(current_batch[-1])
        h2 = to_int(prev_batch[-1])
        
        # XOR to find differences
        xor_val = h1 ^ h2
        
        # Count bit flips (Hamming Distance)
        # Using 256-bit hashes usually
        bit_flips = bin(xor_val).count('1')
        
        # Normalize (Assuming 256-bit Hash)
        # The PLENUM bridge returns SHA256 (32 bytes = 256 bits)
        scrambling_rate = bit_flips / 256.0
        
        return scrambling_rate
