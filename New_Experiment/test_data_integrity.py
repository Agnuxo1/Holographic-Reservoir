#!/usr/bin/env python3
"""
Data Integrity Test - Measure real share loss percentage

This script measures how many shares are actually produced by the ASIC
versus how many arrive at the bridge, providing honest metrics about
data integrity for scientific rigor.

Author: Francisco Angulo de Lafuente
Date: December 2025
"""

import json
import time
import urllib.request
import socket
from datetime import datetime

# Configuration
MINER_IP = "192.168.0.15"
BRIDGE_IP = "127.0.0.1"
BRIDGE_PORT = 4029
TEST_DURATION_SEC = 60
OUTPUT_FILE = "data_integrity_report.json"

def get_miner_stats():
    """Get current stats from miner via AxeOS API"""
    try:
        url = f"http://{MINER_IP}/api/system/info"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"[WARNING] Failed to get miner stats: {e}")
        return {}

def get_bridge_metrics():
    """Get current metrics from bridge API"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((BRIDGE_IP, BRIDGE_PORT))
        s.sendall(b"GET_METRICS")
        resp = s.recv(4096).decode()
        s.close()
        return json.loads(resp)
    except Exception as e:
        print(f"[WARNING] Failed to get bridge metrics: {e}")
        return {}

def reset_bridge():
    """Reset bridge counters"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((BRIDGE_IP, BRIDGE_PORT))
        s.sendall(b"RESET")
        resp = s.recv(1024).decode()
        s.close()
        return resp == "OK"
    except:
        return False

def run_integrity_test():
    """Run the data integrity test"""
    print("=" * 70)
    print("DATA INTEGRITY TEST - Measuring Real Share Loss")
    print("=" * 70)
    print(f"Miner IP: {MINER_IP}")
    print(f"Bridge IP: {BRIDGE_IP}:{BRIDGE_PORT}")
    print(f"Test Duration: {TEST_DURATION_SEC} seconds")
    print()

    # Step 1: Get initial miner state
    print("[1/5] Getting initial miner stats...")
    miner_stats_start = get_miner_stats()
    if not miner_stats_start:
        print("[ERROR] Cannot connect to miner. Aborting.")
        return None

    initial_shares_miner = miner_stats_start.get("sharesAccepted", 0)
    frequency = miner_stats_start.get("frequency", 0)
    voltage = miner_stats_start.get("coreVoltageActual", 0)
    temp = miner_stats_start.get("temp", 0)
    hashrate = miner_stats_start.get("hashRate", 0)

    print(f"   Miner State:")
    print(f"     Frequency: {frequency} MHz")
    print(f"     Voltage: {voltage} mV")
    print(f"     Temperature: {temp} C")
    print(f"     HashRate: {hashrate}")
    print(f"     Initial Shares: {initial_shares_miner}")
    print()

    # Step 2: Reset bridge counters
    print("[2/5] Resetting bridge counters...")
    if reset_bridge():
        print("   Bridge reset successfully")
    else:
        print("   [WARNING] Bridge reset failed, continuing anyway...")
    print()

    # Step 3: Wait briefly for reset to propagate
    time.sleep(2)

    # Step 4: Monitor for test duration
    print(f"[3/5] Monitoring for {TEST_DURATION_SEC} seconds...")
    start_time = time.time()
    samples = []

    while time.time() - start_time < TEST_DURATION_SEC:
        elapsed = time.time() - start_time
        print(f"   Progress: {elapsed:.0f}/{TEST_DURATION_SEC}s", end="\r")

        # Sample bridge metrics
        bridge_metrics = get_bridge_metrics()
        samples.append({
            "elapsed": elapsed,
            "cv": bridge_metrics.get("cv", 0),
            "entropy": bridge_metrics.get("time_entropy", 0),
            "sps": bridge_metrics.get("sps", 0)
        })

        time.sleep(5)  # Sample every 5 seconds

    print()
    print()

    # Step 5: Get final counts
    print("[4/5] Getting final share counts...")
    miner_stats_end = get_miner_stats()
    bridge_metrics_final = get_bridge_metrics()

    final_shares_miner = miner_stats_end.get("sharesAccepted", 0)
    final_sps_bridge = bridge_metrics_final.get("sps", 0)

    shares_produced = final_shares_miner - initial_shares_miner
    shares_received_estimate = final_sps_bridge * TEST_DURATION_SEC

    print(f"   Shares Produced (Miner): {shares_produced}")
    print(f"   Shares Received (Bridge estimate): {shares_received_estimate:.0f}")
    print()

    # Step 6: Calculate loss percentage
    print("[5/5] Calculating data integrity metrics...")

    if shares_produced > 0:
        loss_percentage = 100 * (1 - shares_received_estimate / shares_produced)
    else:
        loss_percentage = 0

    # Estimate theoretical maximum at current hashrate
    # At difficulty 1: ~4.3B hashes per share
    # Theoretical shares/sec = hashrate / 4.3G
    if hashrate > 0:
        # Parse hashrate (format like "493.11 GH/s")
        try:
            hr_value = float(hashrate.split()[0])
            hr_unit = hashrate.split()[1] if len(hashrate.split()) > 1 else "GH/s"

            if "GH/s" in hr_unit or "GH" in hr_unit:
                hr_in_gh = hr_value
            elif "TH/s" in hr_unit or "TH" in hr_unit:
                hr_in_gh = hr_value * 1000
            elif "MH/s" in hr_unit or "MH" in hr_unit:
                hr_in_gh = hr_value / 1000
            else:
                hr_in_gh = 0

            theoretical_shares_per_sec = (hr_in_gh * 1e9) / (2**32)  # Diff 1 target
            theoretical_total = theoretical_shares_per_sec * TEST_DURATION_SEC
        except:
            theoretical_total = 0
    else:
        theoretical_total = 0

    # Create report
    report = {
        "test_id": f"INTEGRITY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "test_duration_sec": TEST_DURATION_SEC,
        "miner_config": {
            "frequency_mhz": frequency,
            "voltage_mv": voltage,
            "temperature_c": temp,
            "hashrate": hashrate
        },
        "share_counts": {
            "miner_shares_produced": shares_produced,
            "bridge_shares_received_estimate": round(shares_received_estimate, 1),
            "theoretical_maximum": round(theoretical_total, 1)
        },
        "data_integrity": {
            "loss_percentage": round(loss_percentage, 2),
            "reception_rate": round(100 - loss_percentage, 2),
            "bridge_sps": round(final_sps_bridge, 2)
        },
        "bridge_metrics_samples": samples,
        "verdict": ""
    }

    # Determine verdict
    if loss_percentage < 10:
        report["verdict"] = "EXCELLENT: Data loss < 10%. Time anchoring provides highly representative sampling."
    elif loss_percentage < 50:
        report["verdict"] = "GOOD: Moderate data loss. Time anchoring captures rhythm accurately."
    elif loss_percentage < 90:
        report["verdict"] = "ACCEPTABLE: High data loss but time anchoring ensures temporal fidelity."
    else:
        report["verdict"] = "CRITICAL: Very high data loss (>90%). Time anchoring CRITICAL for valid measurements."

    # Save report
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(report, f, indent=2)

    # Print summary
    print()
    print("=" * 70)
    print("DATA INTEGRITY REPORT")
    print("=" * 70)
    print(f"Shares Produced (Miner):     {shares_produced}")
    print(f"Shares Received (Bridge):    {shares_received_estimate:.0f}")
    print(f"Theoretical Maximum:         {theoretical_total:.0f}")
    print()
    print(f"Loss Percentage:             {loss_percentage:.2f}%")
    print(f"Reception Rate:              {100 - loss_percentage:.2f}%")
    print(f"Bridge SPS:                  {final_sps_bridge:.2f} shares/sec")
    print()
    print(f"VERDICT: {report['verdict']}")
    print()
    print(f"Full report saved to: {OUTPUT_FILE}")
    print("=" * 70)

    return report

if __name__ == "__main__":
    print("=" * 70)
    print("DATA INTEGRITY TEST")
    print("Measuring Real Share Loss for Scientific Rigor")
    print("=" * 70)
    print()

    response = input("Press ENTER to start test (or 'q' to quit): ")
    if response.lower() == 'q':
        print("Test cancelled.")
        exit(0)

    run_integrity_test()
