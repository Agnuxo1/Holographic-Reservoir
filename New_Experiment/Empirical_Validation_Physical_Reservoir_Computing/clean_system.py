#!/usr/bin/env python3
"""
System Cleanup Script for CHIMERA Reservoir Computing
Kills all Python processes and prepares the system for fresh experiment
"""

import os
import sys
import subprocess
import time

def kill_python_processes():
    """Kill all Python processes to ensure clean state"""
    print("🧹 CLEANING SYSTEM: Killing all Python processes...")
    
    try:
        # Windows method
        if os.name == 'nt':
            result = subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("   ✅ Python processes terminated successfully")
            else:
                print("   ℹ️  No Python processes found or already clean")
        else:
            # Linux/Mac method
            result = subprocess.run(['pkill', '-f', 'python'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("   ✅ Python processes terminated successfully")
            else:
                print("   ℹ️  No Python processes found or already clean")
    except Exception as e:
        print(f"   ⚠️  Error killing processes: {e}")
    
    # Also kill specific CHIMERA-related processes
    processes_to_kill = [
        'chronos_bridge',
        'plenum_bridge', 
        'Empirical_Validation',
        'configure_lv06'
    ]
    
    for process in processes_to_kill:
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/IM', f'{process}.exe'], 
                             capture_output=True, text=True)
            else:
                subprocess.run(['pkill', '-f', process], 
                             capture_output=True, text=True)
        except:
            pass
    
    print("   ✅ System cleanup complete")
    return True

def check_network_config():
    """Verify network configuration"""
    print("\n🌐 CHECKING NETWORK CONFIGURATION...")
    
    # Expected IPs
    expected_pc_ip = "192.168.0.11"
    expected_miner_ip = "192.168.0.15"
    
    print(f"   Expected PC IP: {expected_pc_ip}")
    print(f"   Expected Miner IP: {expected_miner_ip}")
    
    # Check current IP (basic check)
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"   Current host IP: {local_ip}")
        
        if local_ip == expected_pc_ip:
            print("   ✅ PC IP matches expected configuration")
        else:
            print(f"   ⚠️  PC IP mismatch. Expected {expected_pc_ip}, got {local_ip}")
            
    except Exception as e:
        print(f"   ⚠️  Could not determine local IP: {e}")
    
    return True

def test_miner_connectivity():
    """Test basic connectivity to miner"""
    print("\n🔌 TESTING MINER CONNECTIVITY...")
    
    miner_ip = "192.168.0.15"
    
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        
        # Test HTTP port
        result = sock.connect_ex((miner_ip, 80))
        if result == 0:
            print(f"   ✅ Miner reachable at {miner_ip}:80")
        else:
            print(f"   ❌ Cannot reach miner at {miner_ip}:80")
            print(f"      → Check if miner is powered on")
            print(f"      → Verify IP address: {miner_ip}")
            
        sock.close()
        
    except Exception as e:
        print(f"   ❌ Connectivity test failed: {e}")
        return False
    
    return True

def display_next_steps():
    """Display what to do next"""
    print("\n" + "="*60)
    print("SYSTEM CLEANUP COMPLETE")
    print("="*60)
    print("\n📋 NEXT STEPS:")
    print("1. 🔄 RESTART THE MINER (power cycle LV06)")
    print("2. ⚙️  Configure miner pool: stratum+tcp://192.168.0.11:3333")
    print("3. 🌉 Start bridge: python chronos_bridge.py")
    print("4. 🧪 Test connection: python test_connection.py 192.168.0.15")
    print("5. 📊 Run experiment: python Empirical_Validation_Physical_Reservoir_Computing.py")
    
    print("\n💡 CRITICAL: The 'Time Anchor' pattern will prevent WiFi bottleneck")
    print("   - Bridge accumulates timestamps locally")
    print("   - Experiment polls every 2 seconds (not constantly)")
    print("   - Batch fetching minimizes WiFi traffic")
    print("   - This prevents the 99% share loss problem")

def main():
    print("="*60)
    print("CHIMERA RESERVOIR COMPUTING - SYSTEM CLEANUP")
    print("="*60)
    
    # Step 1: Kill processes
    kill_python_processes()
    time.sleep(1)
    
    # Step 2: Check network
    check_network_config()
    
    # Step 3: Test miner connectivity
    test_miner_connectivity()
    
    # Step 4: Show next steps
    display_next_steps()

if __name__ == "__main__":
    main()