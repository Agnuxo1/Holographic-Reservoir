import networkx as nx
import numpy as np

class VeselovLayer:
    """
    Layer 2: The Holographic State.
    Maps ASIC data into a Bipartite Expander Graph.
    Ensures instant information mixing (Holography).
    """
    def __init__(self, size=256):
        self.size = size
        # Create a Bipartite Random Graph (Proven Expander)
        # Left Nodes: Input from ASIC
        # Right Nodes: Memory/State
        # p=0.1 ensures sparsity but connectivity
        self.graph = nx.bipartite.random_graph(size, size, 0.1)
        self.adj = nx.to_numpy_array(self.graph)
        
        # The state is the full adjacency size (Left + Right nodes = 2 * size)
        self.state_vector = np.zeros(len(self.adj))

    def inject_pattern(self, entropy_bytes: bytes):
        """
        Injects a raw entropy seed into the graph and propagates it.
        """
        # 1. Convert Entropy to Vector Input
        # Turn bytes into a list of integers, then normalize
        # If we have 32 bytes, we map them to the first 32 nodes?
        # Or we expand them?
        # Strategy: Use numpy to convert bytes to -1..1 values.
        
        if not entropy_bytes:
            return 0.0
            
        # Convert bytes to int generator
        vals = np.frombuffer(entropy_bytes, dtype=np.uint8)
        
        # Normalize 0..255 -> -1..1
        norm_vals = (vals / 127.5) - 1.0
        
        # 2. Create Input Vector
        input_vec = np.zeros(len(self.adj))
        
        # Inject into the first N nodes (Left partition)
        limit = min(len(norm_vals), self.size)
        input_vec[:limit] = norm_vals[:limit]
        
        # 3. Propagate through the Expander Graph (Holographic Mixing)
        # V(t+1) = tanh( Adjacency * V(t) + Input )
        # This is a Reservoir update equation
        
        # We add some decay/leakage (0.9) to prevent saturation
        new_state = np.tanh(self.adj.dot(self.state_vector) * 0.9 + input_vec)
        
        # Update State
        self.state_vector = new_state
        
        return np.mean(np.abs(self.state_vector)) # Return "System Energy/Activation"

    def get_state_snapshot(self):
        """Returns the current holographic state."""
        return self.state_vector


# ---------------------------------------------------------------------------
# Backwards-compat alias. Legacy code imports `VeselovExpander`. In v1.0 the
# canonical class is `VeselovLayer`; we keep the old name working so that
# `holographic_reservoir.core.reservoir` imports do not crash on load.
# ---------------------------------------------------------------------------
class VeselovExpander(VeselovLayer):
    """Alias of :class:`VeselovLayer` kept for backwards compatibility.

    The legacy constructor accepted ``n_input``, ``n_reservoir`` and ``degree``
    keyword arguments. We accept and ignore the extra ones, using
    ``n_reservoir`` (or ``size``) for the graph dimension.
    """

    def __init__(self, n_input=256, n_reservoir=256, degree=6, size=None, **kwargs):
        s = size if size is not None else n_reservoir
        super().__init__(size=s)
        self.n_input = n_input
        self.n_reservoir = n_reservoir
        self.degree = degree

    def propagate(self, input_layer):
        """Compatibility shim: accepts a 2D input matrix and returns the new state."""
        import numpy as _np
        arr = _np.asarray(input_layer, dtype=_np.float64)
        flat = arr.flatten()
        padded = _np.zeros(len(self.adj))
        n = min(len(flat), len(padded))
        padded[:n] = flat[:n]
        self.state_vector = _np.tanh(self.adj.dot(self.state_vector) * 0.9 + padded)
        # Map back to the expected (size, 4) shape used by reservoir.py
        out = _np.zeros((self.n_reservoir, 4), dtype=_np.float64)
        s = self.state_vector[: self.n_reservoir]
        out[: len(s), 0] = s
        return out
