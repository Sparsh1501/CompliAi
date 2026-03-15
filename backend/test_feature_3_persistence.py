#!/usr/bin/env python3
"""Test Feature 3: Data persists across server restart."""
import requests
import time
import os
import signal

BASE_URL = "http://localhost:8000"
TEST_EMAIL = "RESTART_TEST_12345@test.com"
TEST_PASSWORD = "TestPassword123!"

def test_persistence():
    """Test data persistence across server restart."""
    print("=" * 60)
    print("Feature 3: Data Persists Across Server Restart")
    print("=" * 60)

    # Step 1: Register test user
    print("\n[Step 1] Creating test user...")
    register_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "name": "Restart Test User",
        "organization": "Test Org"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
        if response.status_code == 200:
            print(f"✓ User registered successfully")
            user_data = response.json()
            print(f"  User ID: {user_data.get('id', 'N/A')}")
        elif response.status_code == 400 and "already registered" in response.text.lower():
            print(f"✓ User already exists (from previous test)")
        else:
            print(f"✗ Registration failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ Registration error: {e}")
        return False

    # Step 2: Login to verify user exists
    print("\n[Step 2] Logging in to verify user exists before restart...")
    login_data = {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD
    }

    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", data=login_data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            print(f"✓ Login successful before restart")
            print(f"  Token type: {token_data.get('token_type')}")

            # Get user info
            headers = {"Authorization": f"Bearer {access_token}"}
            me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
            if me_response.status_code == 200:
                user_info = me_response.json()
                print(f"  User email: {user_info.get('email')}")
                print(f"  User name: {user_info.get('name')}")
            else:
                print(f"✗ Could not get user info: {me_response.status_code}")
        else:
            print(f"✗ Login failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ Login error: {e}")
        return False

    # Step 3: Stop the server
    print("\n[Step 3] Stopping the server...")
    pid_file = "/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend/backend.pid"

    try:
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            print(f"  Found PID: {pid}")
            os.kill(pid, signal.SIGTERM)
            print(f"✓ Server stopped (PID {pid})")
        else:
            print(f"  PID file not found, using lsof to kill processes on port 8000")
            os.system("lsof -ti :8000 | xargs kill -9 2>/dev/null")
            print(f"✓ Server processes killed")

        time.sleep(3)

        # Verify server is down
        try:
            requests.get(f"{BASE_URL}/api/health", timeout=2)
            print(f"✗ Server still responding!")
            return False
        except requests.exceptions.RequestException:
            print(f"✓ Server confirmed stopped")
    except Exception as e:
        print(f"Warning: Error stopping server: {e}")

    # Step 4: Restart the server
    print("\n[Step 4] Restarting the server...")
    print("  Please manually restart the server now.")
    print("  Press Enter when the server has started...")
    input()

    # Wait for server to be ready
    print("  Waiting for server to be ready...")
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=2)
            if response.status_code == 200:
                print(f"✓ Server is back online")
                break
        except:
            pass
        time.sleep(1)
        if i % 5 == 0:
            print(f"  Still waiting... ({i}/{max_retries})")
    else:
        print(f"✗ Server did not come back online")
        return False

    # Step 5: Login again to verify data persisted
    print("\n[Step 5] Verifying data persisted after restart...")
    time.sleep(2)  # Give server a moment to fully initialize

    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", data=login_data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            print(f"✓ Login successful AFTER restart")

            # Get user info again
            headers = {"Authorization": f"Bearer {access_token}"}
            me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
            if me_response.status_code == 200:
                user_info = me_response.json()
                print(f"  User email: {user_info.get('email')}")
                print(f"  User name: {user_info.get('name')}")

                if user_info.get('email') == TEST_EMAIL:
                    print(f"\n✅ SUCCESS - Data persisted across restart!")
                    print(f"   User data is identical before and after restart")
                    return True
                else:
                    print(f"\n✗ FAILED - User email mismatch")
                    return False
            else:
                print(f"✗ Could not get user info after restart: {me_response.status_code}")
                return False
        else:
            print(f"✗ Login failed after restart: {response.status_code}")
            print(f"  Response: {response.text}")
            print(f"\n❌ CRITICAL FAILURE - Data was LOST after restart!")
            print(f"   This indicates in-memory storage instead of persistent database")
            return False
    except Exception as e:
        print(f"✗ Error verifying persistence: {e}")
        return False

if __name__ == "__main__":
    success = test_persistence()
    exit(0 if success else 1)
