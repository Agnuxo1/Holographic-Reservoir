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
