#!/usr/bin/env python3
"""
Miner Configuration Script for CHIMERA Reservoir Computing
Automatically configures LV06 miner to connect to the CHIMERA bridge
"""

import sys
import socket
import json
import urllib.request
import urllib.error
import time

class MinerConfigurator:
    def __init__(self, miner_ip="192.168.0.15", pc_ip="192.168.0.11"):
        self.miner_ip = miner_ip
        self.pc_ip = pc_ip
        self.bridge_port = 3333
        self.api_port = 80
        
    def test_miner_connectivity(self):
        """Test if miner is reachable"""
        print(f"🔌 Testing connectivity to miner at {self.miner_ip}...")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((self.miner_ip, self.api_port))
            sock.close()
            
            if result == 0:
                print(f"   ✅ Miner reachable at {self.miner_ip}")
                return True
            else:
                print(f"   ❌ Cannot reach miner at {self.miner_ip}")
                print(f"      → Check if miner is powered on")
                print(f"      → Verify IP address")
                return False
        except Exception as e:
            print(f"   ❌ Connection test failed: {e}")
            return False
    
    def get_miner_status(self):
        """Get current miner status via HTTP API"""
        print("📊 Getting miner status...")
        
        try:
            url = f"http://{self.miner_ip}/api/system/info"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                
                print(f"   🌡️  Temperature: {data.get('temp', 'N/A')}°C")
                print(f"   ⚡ Voltage: {data.get('voltage', data.get('coreVoltageActual', 'N/A'))} mV")
                print(f"   🧠 Frequency: {data.get('frequency', 'N/A')} MHz")
                print(f"   ⛏️  Hash Rate: {data.get('hashRate', 0):.2f} GH/s")
                print(f"   🔋 Power: {data.get('power', 'N/A')} W")
                
                return data
        except urllib.error.URLError as e:
            print(f"   ❌ Cannot access miner API: {e}")
            print(f"      → Check if AxeOS firmware is running")
            print(f"      → Try accessing web UI: http://{self.miner_ip}")
            return None
        except json.JSONDecodeError:
            print("   ❌ Invalid JSON response from miner")
            return None
    
    def get_current_pool_config(self):
        """Get current pool configuration"""
        print("🏊 Checking current pool configuration...")
        
        # Try different endpoints that might contain pool info
        endpoints_to_try = [
            "/api/pool",
            "/api/pools", 
            "/api/system/info",
            "/api/config"
        ]
        
        for endpoint in endpoints_to_try:
            try:
                url = f"http://{self.miner_ip}{endpoint}"
                with urllib.request.urlopen(url, timeout=3) as response:
                    data = json.loads(response.read().decode())
                    
                    # Look for pool-related information
                    pool_info = None
                    if 'poolUrl' in data:
                        pool_info = data['poolUrl']
                    elif 'pool' in data and isinstance(data['pool'], dict):
                        pool_info = data['pool'].get('url', 'Unknown')
                    elif 'pools' in data and isinstance(data['pools'], list) and len(data['pools']) > 0:
                        pool_info = data['pools'][0].get('url', 'Unknown')
                    
                    if pool_info:
                        print(f"   Current pool: {pool_info}")
                        return pool_info
            except:
                continue
        
        print("   ⚠️  Could not read current pool configuration")
        print(f"      → Check manually at: http://{self.miner_ip}")
        return None
    
    def configure_pool(self):
        """Configure miner pool to point to CHIMERA bridge"""
        print(f"⚙️  Configuring pool to point to CHIMERA bridge...")
        print(f"   Target: stratum+tcp://{self.pc_ip}:{self.bridge_port}")
        
        # Pool configuration payload
        pool_config = {
            "url": f"stratum+tcp://{self.pc_ip}:{self.bridge_port}",
            "user": "chimera",
            "password": "x"
        }
        
        # Try different configuration endpoints
        config_endpoints = [
            "/api/pool",
            "/api/pools",
            "/api/system/pool"
        ]
        
        for endpoint in config_endpoints:
            try:
                url = f"http://{self.miner_ip}{endpoint}"
                data = json.dumps(pool_config).encode('utf-8')
                
                req = urllib.request.Request(url, data=data, method='POST')
                req.add_header('Content-Type', 'application/json')
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.getcode() in [200, 201]:
                        print(f"   ✅ Pool configured successfully via {endpoint}")
                        return True
            except Exception as e:
                print(f"   ⚠️  Failed to configure via {endpoint}: {e}")
                continue
        
        print("   ❌ Automatic pool configuration failed")
        print(f"   📝 MANUAL CONFIGURATION REQUIRED:")
        print(f"      1. Open web browser: http://{self.miner_ip}")
        print(f"      2. Go to Pool Settings")
        print(f"      3. Set Pool 1 URL: stratum+tcp://{self.pc_ip}:{self.bridge_port}")
        print(f"      4. Set Worker: chimera")
        print(f"      5. Set Password: x")
        return False
    
    def verify_pool_connection(self):
        """Verify that miner is connecting to our bridge"""
        print("🔍 Verifying pool connection...")
        
        # Wait a bit for miner to connect
        print("   ⏳ Waiting 10 seconds for miner to connect to bridge...")
        time.sleep(10)
        
        # Check if we can detect the connection (bridge should show miner IP)
        # For now, just check if miner is still responding
        status = self.get_miner_status()
        if status:
            hashrate = status.get('hashRate', 0)
            if hashrate > 0:
                print(f"   ✅ Miner is hashing ({hashrate:.2f} GH/s) - likely connected to bridge")
                return True
            else:
                print(f"   ⚠️  Miner not hashing yet - may still be connecting")
                return False
        return False
    
    def run_configuration(self):
        """Run the complete configuration process"""
        print("="*60)
        print("CHIMERA MINER CONFIGURATION")
        print("="*60)
        print(f"Miner IP: {self.miner_ip}")
        print(f"PC IP: {self.pc_ip}")
        print(f"Bridge Port: {self.bridge_port}")
        print()
        
        # Step 1: Test connectivity
        if not self.test_miner_connectivity():
            print("\n❌ CONFIGURATION FAILED: Cannot reach miner")
            return False
        
        # Step 2: Get current status
        status = self.get_miner_status()
        if not status:
            print("\n❌ CONFIGURATION FAILED: Cannot access miner API")
            return False
        
        # Step 3: Check current pool
        current_pool = self.get_current_pool_config()
        
        # Step 4: Configure pool
        config_success = self.configure_pool()
        
        # Step 5: Verify connection
        if config_success:
            self.verify_pool_connection()
        
        print("\n" + "="*60)
        print("CONFIGURATION SUMMARY")
        print("="*60)
        
        if config_success:
            print("✅ Pool configuration completed")
            print("\n📋 NEXT STEPS:")
            print("1. 🌉 Start CHIMERA bridge: python chronos_bridge.py")
            print("2. 🧪 Test connection: python test_connection.py")
            print("3. 📊 Run experiment: python Empirical_Validation_Physical_Reservoir_Computing.py")
        else:
            print("⚠️  Manual configuration required")
            print(f"\n📝 MANUAL STEPS:")
            print(f"1. Open: http://{self.miner_ip}")
            print(f"2. Pool URL: stratum+tcp://{self.pc_ip}:{self.bridge_port}")
            print(f"3. Worker: chimera, Password: x")
            print("4. Save settings and restart miner")
        
        return config_success

def main():
    if len(sys.argv) > 1:
        miner_ip = sys.argv[1]
    else:
        miner_ip = "192.168.0.15"
    
    if len(sys.argv) > 2:
        pc_ip = sys.argv[2]
    else:
        pc_ip = "192.168.0.11"
    
    configurator = MinerConfigurator(miner_ip, pc_ip)
    configurator.run_configuration()

if __name__ == "__main__":
    main()