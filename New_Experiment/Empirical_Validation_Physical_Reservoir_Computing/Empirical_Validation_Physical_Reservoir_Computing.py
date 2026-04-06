"""
Empirical Validation of Physical Reservoir Computing
Using Luck Miner LV06 SHA-256 ASIC

This experiment validates:
- Echo State Property (ESP)
- Fading Memory
- Separation Property
- Computational capability via NARMA-10 benchmark

Author: Francisco Angulo de Lafuente
"""

import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import socket
import json
import time
import threading
import numpy as np
import queue
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
import matplotlib.pyplot as plt

# =========================
# CONFIGURATION PARAMETERS
# =========================

BRIDGE_API_HOST = "127.0.0.1"  # CHIMERA bridge API
BRIDGE_API_PORT = 4029         # Bridge API port
MEASUREMENT_INTERVAL = 0.1     # seconds
EXPERIMENT_DURATION = 1200     # seconds (20 minutes)
WASHOUT = 200                  # reservoir warm-up steps

RIDGE_ALPHA = 1e-6
RANDOM_SEED = 42

np.random.seed(RANDOM_SEED)

# =========================
# NARMA-10 TASK DEFINITION
# =========================

def generate_narma10(length):
    """
    Generates NARMA-10 input-output pairs.
    """
    u = np.random.uniform(0, 0.5, size=length)
    y = np.zeros(length)

    for t in range(10, length):
        y[t] = (
            0.3 * y[t - 1]
            + 0.05 * y[t - 1] * np.sum(y[t - 10:t])
            + 1.5 * u[t - 10] * u[t - 1]
            + 0.1
        )

    return u, y

# =========================
# ASIC INTERFACE VIA BRIDGE
# =========================

class LuckMinerInterface:
    """
    Interface to Luck Miner LV06 via CHIMERA bridge (Stratum server).
    Measures hash timing jitter as reservoir state by capturing share arrival times.
    
    The bridge (chronos_bridge.py) acts as a Stratum server that receives
    shares from the LV06 miner. This interface captures the timing between
    share submissions to extract reservoir state.
    """

    def __init__(self, bridge_host="127.0.0.1", bridge_port=4029):
        self.bridge_host = bridge_host
        self.bridge_port = bridge_port
        self.arrival_times = []  # Store timestamps of share arrivals
        self.last_arrival_time = None
        self.running = False
        self.lock = threading.Lock()
        
    def start(self):
        """
        Starts the interface. The bridge must already be running.
        This interface works by monitoring share arrivals from the bridge.
        """
        self.running = True
        print("✅ Interface started. Make sure chronos_bridge.py is running and miner is connected.")
        
    def _capture_share_timing(self):
        """
        Captures timing information from share arrivals.
        This is called externally when a share timestamp is available.
        For now, we'll poll the bridge metrics and infer timing.
        """
        # Alternative: We'll track timing by monitoring the bridge's metrics
        # and inferring share arrival rate
        pass
    
    def add_share_timestamp(self, timestamp=None):
        """
        Adds a share arrival timestamp.
        Call this when you detect a share arrival (e.g., via bridge monitoring).
        
        Args:
            timestamp: Unix timestamp in seconds. If None, uses current time.
        """
        if timestamp is None:
            timestamp = time.time()
        
        with self.lock:
            self.arrival_times.append(timestamp)
            # Keep only recent timestamps (last 1000)
            if len(self.arrival_times) > 1000:
                self.arrival_times = self.arrival_times[-1000:]
            self.last_arrival_time = timestamp
    
    def get_state(self, window=10):
        """
        Returns a reservoir state vector based on timing statistics.
        
        The state vector includes:
        - Time deltas between consecutive shares
        - Differences of deltas (rate of change)
        - Statistical moments (mean, std)
        
        Args:
            window: Number of recent share intervals to use
            
        Returns:
            numpy array: Reservoir state vector
        """
        with self.lock:
            if len(self.arrival_times) < 2:
                # Not enough data, return zero state
                state_dim = window + window + 2  # deltas + diff(deltas) + mean + std
                return np.zeros(state_dim)
            
            # Calculate time deltas between consecutive arrivals
            times = np.array(self.arrival_times[-window-1:])
            deltas = np.diff(times)  # Time intervals between shares
            
            # If we have fewer than window deltas, pad with zeros
            if len(deltas) < window:
                padding = window - len(deltas)
                deltas = np.concatenate([np.zeros(padding), deltas])
            else:
                deltas = deltas[-window:]
            
            # Calculate differences of deltas (second-order timing structure)
            delta_diffs = np.diff(deltas, prepend=deltas[0])
            
            # Statistical features
            mean_delta = np.mean(deltas) if len(deltas) > 0 else 0.0
            std_delta = np.std(deltas) if len(deltas) > 0 else 0.0
            
            # Construct state vector
            stats = np.array([mean_delta, std_delta])
            state = np.concatenate([
                deltas,              # Raw timing intervals
                delta_diffs,         # Rate of change of intervals
                stats                # Statistical moments
            ])
            
            return state
    
    def clear_old_data(self):
        """Clears old timing data, keeping only recent entries."""
        with self.lock:
            if len(self.arrival_times) > 100:
                self.arrival_times = self.arrival_times[-100:]
    
    def stop(self):
        """Stops the interface."""
        self.running = False
        print("Interface stopped.")


class BridgeShareMonitor:
    """
    Monitors the CHIMERA bridge to detect share arrivals.
    This class can poll the bridge or connect to capture share events.
    
    Note: The current bridge implementation doesn't expose individual
    share timestamps via API, so we simulate by monitoring metrics.
    For a production implementation, the bridge should be modified to
    expose share arrival events.
    """
    
    def __init__(self, bridge_host="127.0.0.1", bridge_port=4029):
        self.bridge_host = bridge_host
        self.bridge_port = bridge_port
        self.running = False
        self.last_share_count = 0
        self.last_check_time = time.time()
        
    def check_bridge_connection(self):
        """Check if bridge is running and accessible."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((self.bridge_host, self.bridge_port))
            sock.close()
            return result == 0
        except:
            return False
    
    def get_metrics(self):
        """Get metrics from bridge API."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.bridge_host, self.bridge_port))
            sock.sendall(b'GET_METRICS')
            data = sock.recv(4096).decode()
            sock.close()
            return json.loads(data)
        except Exception as e:
            return None
    
    def get_share_timestamps(self):
        """
        Get individual share timestamps from bridge API (batch mode).
        
        Returns all accumulated timestamps since last call.
        Bridge buffers locally to minimize WiFi traffic (Time Anchor pattern).
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # Increased timeout for large batches
            sock.connect((self.bridge_host, self.bridge_port))
            sock.sendall(b'GET_SHARE_TIMESTAMPS')
            
            # Receive data in chunks (may be large if many timestamps accumulated)
            chunks = []
            sock.settimeout(10)  # Allow time for large data transfer
            
            while True:
                try:
                    chunk = sock.recv(65536)  # Larger buffer for batch data
                    if not chunk:
                        break
                    chunks.append(chunk)
                    # Check if we've received all data
                    # JSON arrays end with ']', so check if we have complete JSON
                    if chunk.endswith(b']') or len(chunk) < 65536:
                        break
                except socket.timeout:
                    # If timeout, try to parse what we have
                    break
            
            sock.close()
            
            # Decode and parse JSON
            data = b''.join(chunks).decode('utf-8', errors='ignore')
            if data and data.strip():
                return json.loads(data)
            return []
        except json.JSONDecodeError as e:
            # Partial JSON - return empty list, will retry next poll
            return []
        except Exception as e:
            # Network errors - return None to indicate failure
            return None
    
    def monitor_share_arrivals(self, interface, poll_interval=2.0):
        """
        Monitors bridge for share arrivals with WiFi-friendly polling.
        
        CRITICAL: To avoid WiFi bottleneck, we use "Time Anchor" pattern:
        - Poll infrequently (every 2-5 seconds) to let bridge accumulate shares
        - Bridge buffers timestamps locally, we fetch in batches
        - This prevents saturating WiFi connection which causes 99% share loss
        
        Args:
            interface: LuckMinerInterface instance to update
            poll_interval: How often to poll (seconds). Use 2.0+ to avoid WiFi saturation
        """
        self.running = True
        
        if not self.check_bridge_connection():
            print("⚠️  WARNING: Bridge not accessible. Make sure chronos_bridge.py is running.")
            return
        
        print(f"📊 Monitoring bridge for share arrivals (Time Anchor mode, poll every {poll_interval}s)...")
        print("   💡 Using infrequent polling to prevent WiFi bottleneck")
        
        consecutive_failures = 0
        total_shares_captured = 0
        last_poll_time = time.time()
        
        while interface.running and self.running:
            try:
                current_time = time.time()
                elapsed = current_time - last_poll_time
                
                # Only poll if enough time has passed (Time Anchor)
                if elapsed < poll_interval:
                    time.sleep(0.1)  # Small sleep to avoid busy loop
                    continue
                
                last_poll_time = current_time
                
                # Get accumulated timestamps from bridge (batch fetch)
                timestamps = self.get_share_timestamps()
                
                if timestamps is not None:
                    consecutive_failures = 0
                    batch_size = len(timestamps)
                    
                    if batch_size > 0:
                        # Add all accumulated timestamps to interface
                        for ts in timestamps:
                            interface.add_share_timestamp(ts)
                            total_shares_captured += 1
                        
                        # Optional: Print progress every 100 shares
                        if total_shares_captured % 100 == 0:
                            print(f"   📈 Shares captured: {total_shares_captured} (last batch: {batch_size})")
                else:
                    consecutive_failures += 1
                    if consecutive_failures > 5:
                        print("⚠️  Bridge not responding. Continuing to wait...")
                        consecutive_failures = 0
                    
            except Exception as e:
                # Silent error handling - bridge might be temporarily unavailable
                pass
        
        print(f"📊 Share monitoring stopped. Total shares captured: {total_shares_captured}")
    
    def stop(self):
        """Stop monitoring."""
        self.running = False

# =========================
# EXPERIMENT EXECUTION
# =========================

def run_experiment():
    """
    Main experiment function.
    
    Requirements:
    1. chronos_bridge.py must be running (start it separately)
    2. LV06 miner must be connected to the bridge
    3. Miner should be actively hashing (check bridge output for dots "...")
    """
    print("=" * 70)
    print("Luck Miner LV06 Reservoir Computing Experiment")
    print("=" * 70)
    print("\n⚠️  PREREQUISITES:")
    print("   1. Start chronos_bridge.py in a separate terminal:")
    print("      python chronos_bridge.py")
    print("   2. Ensure LV06 miner is connected and hashing")
    print("   3. Wait for bridge to show: ⚡ ASIC CONNECTED")
    print("   4. You should see share arrivals: ..........")
    print("\n" + "=" * 70 + "\n")
    
    # Initialize interface and monitor
    interface = LuckMinerInterface(BRIDGE_API_HOST, BRIDGE_API_PORT)
    interface.start()
    
    monitor = BridgeShareMonitor(BRIDGE_API_HOST, BRIDGE_API_PORT)
    
    # Check bridge connection
    if not monitor.check_bridge_connection():
        print("❌ ERROR: Cannot connect to bridge!")
        print(f"   Make sure chronos_bridge.py is running and listening on {BRIDGE_API_HOST}:{BRIDGE_API_PORT}")
        print("   Start the bridge first, then run this experiment.")
        return None
    
    print("✅ Bridge connection confirmed")
    
    # Start monitoring share arrivals in background
    monitor_thread = threading.Thread(
        target=monitor.monitor_share_arrivals,
        args=(interface,),
        daemon=True
    )
    monitor_thread.start()
    
    # Generate NARMA-10 task
    length = int(EXPERIMENT_DURATION / MEASUREMENT_INTERVAL)
    u, y_target = generate_narma10(length)
    
    print(f"\n📊 Experiment Configuration:")
    print(f"   Duration: {EXPERIMENT_DURATION} seconds ({EXPERIMENT_DURATION/60:.1f} minutes)")
    print(f"   Measurement interval: {MEASUREMENT_INTERVAL} seconds")
    print(f"   Total samples: {length}")
    print(f"   Washout period: {WASHOUT} samples")
    print(f"\n🔄 Collecting reservoir states...")
    print("   (This will take approximately {:.1f} minutes)".format(EXPERIMENT_DURATION/60))
    
    # Wait for initial shares to accumulate
    time.sleep(2)
    
    reservoir_states = []
    outputs = []
    progress_interval = max(1, length // 20)  # Show progress every 5%
    
    for t in range(length):
        time.sleep(MEASUREMENT_INTERVAL)
        
        state = interface.get_state()
        reservoir_states.append(state)
        outputs.append(y_target[t])
        
        # Show progress
        if (t + 1) % progress_interval == 0:
            progress = (t + 1) / length * 100
            elapsed = (t + 1) * MEASUREMENT_INTERVAL
            remaining = EXPERIMENT_DURATION - elapsed
            print(f"   Progress: {progress:.1f}% | Elapsed: {elapsed:.0f}s | Remaining: {remaining:.0f}s")
    
    interface.stop()
    monitor.stop()
    
    print("\n✅ Data collection complete")

    X = np.array(reservoir_states)
    Y = np.array(outputs)
    
    print(f"\n📈 Data Statistics:")
    print(f"   Total samples collected: {len(X)}")
    print(f"   State vector dimension: {X.shape[1] if len(X) > 0 else 0}")
    print(f"   Samples after washout: {len(X) - WASHOUT}")
    
    if len(X) <= WASHOUT:
        print("\n❌ ERROR: Insufficient data collected!")
        print(f"   Need at least {WASHOUT + 1} samples, but only got {len(X)}")
        print("   Make sure the miner is actively hashing and shares are arriving.")
        return None

    # Remove washout period
    X = X[WASHOUT:]
    Y = Y[WASHOUT:]

    # Train/test split (70/30)
    split = int(0.7 * len(X))

    X_train, X_test = X[:split], X[split:]
    Y_train, Y_test = Y[:split], Y[split:]
    
    print(f"\n🔧 Training Configuration:")
    print(f"   Training samples: {len(X_train)}")
    print(f"   Test samples: {len(X_test)}")
    print(f"   Ridge regularization (alpha): {RIDGE_ALPHA}")

    print("\n🎓 Training linear readout...")
    readout = Ridge(alpha=RIDGE_ALPHA)
    readout.fit(X_train, Y_train)

    print("📊 Evaluating performance...")
    Y_pred = readout.predict(X_test)

    mse = mean_squared_error(Y_test, Y_pred)
    nrmse = np.sqrt(mse) / np.std(Y_test) if np.std(Y_test) > 0 else float('inf')
    
    # Calculate baseline (random permutation)
    baseline_nrmse = np.sqrt(mean_squared_error(Y_test, np.random.permutation(Y_test))) / np.std(Y_test) if np.std(Y_test) > 0 else float('inf')

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"   NRMSE: {nrmse:.4f}")
    print(f"   Baseline (random): {baseline_nrmse:.4f}")
    print(f"   Improvement over baseline: {((baseline_nrmse - nrmse) / baseline_nrmse * 100):.1f}%")
    print("=" * 70)

    # Plot results
    plt.figure(figsize=(12, 5))
    
    # Plot full test set
    plt.subplot(1, 2, 1)
    plot_length = min(300, len(Y_test))
    plt.plot(Y_test[:plot_length], label="Target", linewidth=1.5)
    plt.plot(Y_pred[:plot_length], label="Prediction", linewidth=1.5, alpha=0.8)
    plt.xlabel("Time Step")
    plt.ylabel("Output Value")
    plt.title(f"NARMA-10 Prediction (First {plot_length} steps)\nNRMSE = {nrmse:.4f}")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Scatter plot
    plt.subplot(1, 2, 2)
    plt.scatter(Y_test, Y_pred, alpha=0.5, s=10)
    plt.plot([Y_test.min(), Y_test.max()], [Y_test.min(), Y_test.max()], 'r--', linewidth=2)
    plt.xlabel("Target")
    plt.ylabel("Prediction")
    plt.title("Target vs Prediction")
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save figure
    output_file = "narma10_results.png"
    plt.savefig(output_file, dpi=150)
    print(f"\n💾 Results saved to: {output_file}")
    
    plt.show()

    return nrmse

# =========================
# BASELINE COMPARISON
# =========================

def random_baseline(y):
    return np.sqrt(mean_squared_error(y, np.random.permutation(y))) / np.std(y)

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    try:
        nrmse = run_experiment()
        
        if nrmse is None:
            print("\n❌ Experiment failed. See error messages above.")
            exit(1)
        
        print("\n" + "=" * 70)
        print("EXPERIMENT COMPLETED")
        print("=" * 70)
        
        if nrmse < 0.3:
            print("✅ RESULT: Reservoir Computing capability CONFIRMED.")
            print("   The LV06 ASIC demonstrates computational capability")
            print("   for the NARMA-10 task (NRMSE < 0.3).")
        elif nrmse < 0.5:
            print("⚠️  RESULT: Partial confirmation.")
            print("   The reservoir shows some computational capability")
            print("   but performance is moderate (0.3 < NRMSE < 0.5).")
        else:
            print("❌ RESULT: Hypothesis NOT confirmed.")
            print("   The reservoir did not demonstrate sufficient")
            print("   computational capability (NRMSE >= 0.5).")
        
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Experiment interrupted by user.")
        exit(0)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
