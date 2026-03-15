#!/usr/bin/env python3
"""Automated test for Feature 3: Data persists across server restart."""
import requests
import time
import subprocess
import os

BASE_URL = "http://localhost:8000"
TEST_EMAIL = "RESTART_TEST_12345@test.com"
TEST_PASSWORD = "TestPassword123!"

def wait_for_server(timeout=30):
    """Wait for server to be ready."""
    for i in range(timeout):
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False

def stop_server():
    """Stop the backend server."""
    print("Stopping server...")
    subprocess.run("lsof -ti :8000 | xargs kill -9 2>/dev/null || true", shell=True)
    time.sleep(5)

    # Verify it's stopped
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=1)
        print("ERROR: Server still running!")
        return False
    except:
        print("✓ Server stopped")
        return True

def start_server():
    """Start the backend server."""
    print("Starting server...")
    backend_dir = "/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend"

    # Start server in background
    cmd = f"cd {backend_dir} && source venv/bin/activate && nohup uvicorn server:app --host 0.0.0.0 --port 8000 > server.log 2>&1 & echo $! > backend.pid"
    subprocess.run(cmd, shell=True, executable='/bin/bash')

    time.sleep(3)

    # Wait for it to be ready
    if wait_for_server(30):
        print("✓ Server started and ready")
        return True
    else:
        print("ERROR: Server did not start")
        return False

def main():
    print("=" * 60)
    print("Feature 3: Data Persists Across Server Restart (Automated)")
    print("=" * 60)

    # Step 1: Ensure server is running
    print("\n[Step 1] Ensuring server is running...")
    if not wait_for_server(5):
        print("Server not running, starting it...")
        if not start_server():
            print("Failed to start server")
            return False
    print("✓ Server is running")

    # Step 2: Register/login test user
    print(f"\n[Step 2] Creating test user {TEST_EMAIL}...")
    register_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": "Restart Test User",
        "organization": "Test Org"
    }

    response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
    if response.status_code == 200:
        print("✓ User registered")
    elif "already registered" in response.text.lower():
        print("✓ User already exists")
    else:
        print(f"Registration response: {response.status_code} - {response.text}")

    # Step 3: Login to get user data
    print("\n[Step 3] Logging in BEFORE restart...")
    login_data = {"email": TEST_EMAIL, "password": TEST_PASSWORD}
    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)

    if response.status_code != 200:
        print(f"Login failed: {response.status_code} - {response.text}")
        return False

    token_before = response.json()["token"]
    headers_before = {"Authorization": f"Bearer {token_before}"}
    me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers_before)

    if me_response.status_code != 200:
        print(f"Failed to get user info: {me_response.status_code}")
        return False

    user_before = me_response.json()
    print(f"✓ User data before restart:")
    print(f"  Email: {user_before.get('email')}")
    print(f"  Name: {user_before.get('full_name')}")
    print(f"  ID: {user_before.get('id')}")

    # Step 4: STOP the server
    print("\n[Step 4] STOPPING SERVER COMPLETELY...")
    if not stop_server():
        return False

    # Step 5: RESTART the server
    print("\n[Step 5] RESTARTING SERVER...")
    if not start_server():
        return False

    # Step 6: Login again and verify data
    print("\n[Step 6] Logging in AFTER restart...")
    time.sleep(2)  # Extra wait for DB connections

    response = requests.post(f"{BASE_URL}/api/auth/login", data=login_data)

    if response.status_code != 200:
        print(f"❌ CRITICAL FAILURE - Login failed after restart!")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        print(f"\n   This indicates DATA WAS LOST - in-memory storage detected!")
        return False

    token_after = response.json()["token"]
    headers_after = {"Authorization": f"Bearer {token_after}"}
    me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers_after)

    if me_response.status_code != 200:
        print(f"Failed to get user info after restart: {me_response.status_code}")
        return False

    user_after = me_response.json()
    print(f"✓ User data after restart:")
    print(f"  Email: {user_after.get('email')}")
    print(f"  Name: {user_after.get('full_name')}")
    print(f"  ID: {user_after.get('id')}")

    # Compare
    if (user_before.get('id') == user_after.get('id') and
        user_before.get('email') == user_after.get('email') and
        user_before.get('full_name') == user_after.get('full_name')):
        print(f"\n✅ SUCCESS - Data persisted perfectly across restart!")
        return True
    else:
        print(f"\n❌ FAILED - Data mismatch!")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
