import struct
import math
import numpy as np

class ChimeraLayer:
    """
    Implements the NeuroCHIMERA / Veselov architecture neural mapping.
    
    Concept:
    The raw energetic output of the S9 (Hashes) is decoded into a 4D Vector Space (RGBa).
    This space represents the 'Qualia' or 'Subconscious State' of the system.
    """
    
    def __init__(self):
        self.hns_memory = [] # Rolling buffer of recent vectors
        self.memory_capacity = 50
        
        # Synaptic Plasticity (STDP)
        # Maps a Context ID (Seed) to a Weight (Importance)
        self.synaptic_weights = {} 
        self.global_plasticity_rate = 0.1
        
        # System States
        self.entropy = 0.0
        self.free_energy = 0.0
        self.coherence = 0.0

    def decode_hns(self, hash_bytes):
        """
        Decodes a single 32-byte hash into a CHIMERA Vector (R, G, B, A).
        Uses modulo arithmetic to map chaos to [0, 1].
        """
        if len(hash_bytes) != 32:
            return None
            
        # Unpack 4 unsigned 64-bit integers (Big Endian)
        chunks = struct.unpack(">4Q", hash_bytes)
        
        norm = 1000000.0
        
        # R (Red - Activation)
        r = (chunks[0] % norm) / norm
        
        # G (Green - Direction/Vector) 
        g = (chunks[1] % norm) / norm
        
        # B (Blue - Weight/Plasticity)
        # In STDP, this channel controls "How much we learn" from this spike.
        b = (chunks[2] % norm) / norm
        
        # A (Alpha - Time/Phase)
        a = (chunks[3] % norm) / norm
        
        return {"r": r, "g": g, "b": b, "a": a}

    def process_spikes(self, raw_hashes, context_key=None):
        """
        Integrates a batch of raw hashes (Spikes) into the Neural State.
        :param context_key: Optional identifier for the "Thought" (Seed) to enable Hebbian learning.
        """
        # Decode all
        vectors = []
        for h in raw_hashes:
            v = self.decode_hns(h)
            if v: vectors.append(v)
            
        # Add to memory (FIFO)
        self.hns_memory.extend(vectors)
        if len(self.hns_memory) > self.memory_capacity:
            self.hns_memory = self.hns_memory[-self.memory_capacity:]
            
        # STDP Update (Learning)
        if context_key is not None and vectors:
            self._apply_stdp(context_key, vectors)
            
        # Re-calculate Global Metrics
        self._update_metrics(context_key)
        
        return len(vectors)

    def _apply_stdp(self, context_key, vectors):
        """
        Spike-Timing-Dependent Plasticity Rule.
        Delta W = LearningRate * Plasticity(B) * (Coherence(A) - Decay)
        """
        # 1. Average Plasticity of this batch (Blue Channel)
        avg_plasticity = sum(v["b"] for v in vectors) / len(vectors)
        
        # 2. Average Phase/Coherence (Alpha Channel)
        # High Alpha = "Resonant" -> Potentiation (Learn)
        # Low Alpha = "Noise" -> Depression (Forget/Habituate)
        avg_phase = sum(v["a"] for v in vectors) / len(vectors)
        
        # 3. Calculate Weight Delta
        # Threshold at 0.5: Above = Strengthen, Below = Weaken
        delta = (avg_phase - 0.5) * avg_plasticity * self.global_plasticity_rate
        
        # 4. Apply
        current_weight = self.synaptic_weights.get(context_key, 1.0)
        new_weight = current_weight + delta
        
        # Clamp weight between 0.1 and 5.0
        new_weight = max(0.1, min(5.0, new_weight))
        self.synaptic_weights[context_key] = new_weight

    def _update_metrics(self, active_context_key=None):
        """
        Calculates Thermodynamics of the Neural Reservoir.
        """
        if not self.hns_memory:
            self.entropy = 0.0
            self.free_energy = 0.0
            self.coherence = 1.0
            return

        # 1. Free Energy (Approximation using R channel sum)
        # Weighted by Synaptic Weight if context is known
        weight = 1.0
        if active_context_key:
            weight = self.synaptic_weights.get(active_context_key, 1.0)
            
        total_activation = sum(v["r"] for v in self.hns_memory) * weight
        self.free_energy = total_activation
        
        # 2. Shannon Entropy of the Activation Distribution
        if total_activation > 0:
            probs = [(v["r"] * weight)/total_activation for v in self.hns_memory]
            # Clip sum of probs to 1.0 just in case floating point errors
            prob_sum = sum(probs)
            if prob_sum > 0:
                probs = [p/prob_sum for p in probs]
                self.entropy = -sum(p * math.log(p + 1e-9) for p in probs)
            else:
                self.entropy = 0
        else:
            self.entropy = 0
            
        # 3. Coherence (Phase Synchronization)
        phases = [v["a"] for v in self.hns_memory]
        if len(phases) > 1:
            variance = np.var(phases)
            self.coherence = 1.0 / (1.0 + variance * 10) 
        else:
            self.coherence = 1.0

    def get_state_summary(self):
        """
        Returns a dictionary suitable for LLM Context or Analysis.
        """
        return {
            "energy": self.free_energy,
            "entropy": self.entropy,
            "coherence": self.coherence,
            "memory_depth": len(self.hns_memory),
            "synaptic_count": len(self.synaptic_weights)
        }

    def get_state_summary(self):
        """
        Returns a dictionary suitable for LLM Context or Analysis.
        """
        return {
            "energy": self.free_energy,
            "entropy": self.entropy,
            "coherence": self.coherence,
            "memory_depth": len(self.hns_memory),
            "synaptic_count": len(self.synaptic_weights)
        }

    def save_memory(self, filepath="brain_weights.json"):
        import json
        try:
            with open(filepath, 'w') as f:
                json.dump(self.synaptic_weights, f)
            print(f"[Neural] Memory saved ({len(self.synaptic_weights)} synapses).")
        except Exception as e:
            print(f"[Neural] Save failed: {e}")

    def load_memory(self, filepath="brain_weights.json"):
        import json
        import os
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    # JSON keys are strings, convert back to int for seeds
                    data = json.load(f)
                    self.synaptic_weights = {int(k): float(v) for k, v in data.items()}
                print(f"[Neural] Memory loaded ({len(self.synaptic_weights)} synapses).")
            except Exception as e:
                print(f"[Neural] Load failed: {e}")
