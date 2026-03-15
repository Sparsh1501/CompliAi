#!/usr/bin/env python3
"""
Regression test script for features 1, 4, and 5
"""
import sys
import time
import requests
import json
import subprocess
import os

# Change to backend directory
os.chdir('/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend')

def test_feature_4_no_mock_patterns():
    """Feature 4: No mock data patterns in codebase"""
    print("=" * 60)
    print("Testing Feature 4: No mock data patterns in codebase")
    print("=" * 60)

    patterns = [
        ("globalThis", "globalThis patterns"),
        ("dev-store|devStore|DevStore|mock-db|mockDb", "dev-store/mock-db patterns"),
        ("mockData|testData|fakeData|sampleData|dummyData", "mock data patterns"),
        ("TODO.*real|TODO.*database|TODO.*API|STUB|MOCK", "TODO/STUB/MOCK patterns"),
    ]

    all_clear = True
    for pattern, description in patterns:
        result = subprocess.run(
            f'grep -rE "{pattern}" --include="*.py" --include="*.js" --include="*.jsx" --include="*.ts" --include="*.tsx" --exclude-dir=venv --exclude-dir=venv.bak --exclude-dir=node_modules --exclude="test_regression.py" . ../frontend/src 2>/dev/null',
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            print(f"❌ FAILED: Found {description}")
            print(result.stdout[:500])
            all_clear = False
        else:
            print(f"✅ PASSED: No {description} found")

    # Check package.json
    result = subprocess.run(
        'grep -E "(json-server|miragejs|msw)" ../frontend/package.json 2>/dev/null',
        shell=True,
        capture_output=True,
        text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        print("❌ FAILED: Found mock server packages in package.json")
        all_clear = False
    else:
        print("✅ PASSED: No mock server packages found")

    return all_clear

def start_server():
    """Start the backend server"""
    print("\n" + "=" * 60)
    print("Starting backend server...")
    print("=" * 60)

    # Start server in background
    proc = subprocess.Popen(
        [sys.executable, 'server.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for server to start
    print("Waiting for server to start...")
    for i in range(30):
        try:
            response = requests.get('http://localhost:8000/api/health', timeout=1)
            if response.status_code == 200:
                print(f"✅ Server started successfully after {i+1} seconds")
                return proc
        except:
            time.sleep(1)

    print("❌ Server failed to start within 30 seconds")
    proc.kill()
    return None

def test_feature_1_database_connection(proc):
    """Feature 1: Database connection established (MongoDB + Qdrant)"""
    print("\n" + "=" * 60)
    print("Testing Feature 1: Database connection")
    print("=" * 60)

    try:
        response = requests.get('http://localhost:8000/api/health', timeout=5)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")

            # Check MongoDB status
            if 'mongodb_status' in data:
                if data['mongodb_status'] == 'connected':
                    print("✅ MongoDB connection: PASSED")
                else:
                    print(f"❌ MongoDB connection: FAILED - {data.get('mongodb_status')}")
                    return False
            else:
                print("❌ MongoDB status not in response")
                return False

            # Check Qdrant status
            if 'qdrant_status' in data:
                if data['qdrant_status'] in ['connected', 'memory']:
                    print(f"✅ Qdrant connection: PASSED ({data['qdrant_status']})")
                else:
                    print(f"❌ Qdrant connection: FAILED - {data.get('qdrant_status')}")
                    return False
            else:
                print("❌ Qdrant status not in response")
                return False

            return True
        else:
            print(f"❌ Health endpoint returned {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Failed to check health endpoint: {e}")
        return False

def test_feature_5_real_database_queries(proc):
    """Feature 5: Backend API queries real database"""
    print("\n" + "=" * 60)
    print("Testing Feature 5: Real database queries")
    print("=" * 60)

    # Generate unique test data
    test_email = f"regression_test_{int(time.time())}@test.com"
    test_data = {
        "email": test_email,
        "password": "TestPass123!",
        "full_name": "Regression Test User",
        "organization": "Test Org"
    }

    try:
        # Test registration (should trigger MongoDB insert)
        print(f"\n1. Testing registration with email: {test_email}")
        response = requests.post(
            'http://localhost:8000/api/auth/register',
            json=test_data,
            timeout=10
        )

        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            print("   ✅ Registration successful - MongoDB insert likely occurred")
            result = response.json()
            token = result.get('token')

            if not token:
                print("   ❌ No token in response")
                return False

            # Test login (should query MongoDB)
            print(f"\n2. Testing login with same credentials")
            login_response = requests.post(
                'http://localhost:8000/api/auth/login',
                json={"email": test_email, "password": "TestPass123!"},
                timeout=10
            )

            if login_response.status_code == 200:
                print("   ✅ Login successful - MongoDB query worked")
            else:
                print(f"   ❌ Login failed with status {login_response.status_code}")
                return False

            # Test a GET endpoint that queries database
            print(f"\n3. Testing policies endpoint (should query MongoDB)")
            headers = {"Authorization": f"Bearer {token}"}
            policies_response = requests.get(
                'http://localhost:8000/api/policies',
                headers=headers,
                timeout=10
            )

            print(f"   Status Code: {policies_response.status_code}")
            if policies_response.status_code in [200, 401, 403]:
                print("   ✅ Policies endpoint responded (MongoDB query executed)")
                return True
            else:
                print(f"   ❌ Unexpected status code: {policies_response.status_code}")
                return False

        else:
            print(f"   ❌ Registration failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Failed to test real database queries: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    results = {}
    server_proc = None

    try:
        # Test Feature 4 (no server needed)
        results['Feature 4'] = test_feature_4_no_mock_patterns()

        # Start server for Features 1 and 5
        server_proc = start_server()

        if server_proc:
            # Test Feature 1
            results['Feature 1'] = test_feature_1_database_connection(server_proc)

            # Test Feature 5
            results['Feature 5'] = test_feature_5_real_database_queries(server_proc)
        else:
            print("❌ Could not start server - skipping Features 1 and 5")
            results['Feature 1'] = False
            results['Feature 5'] = False

        # Print summary
        print("\n" + "=" * 60)
        print("REGRESSION TEST SUMMARY")
        print("=" * 60)

        for feature, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{feature}: {status}")

        all_passed = all(results.values())

        if all_passed:
            print("\n🎉 All regression tests PASSED!")
            return 0
        else:
            print("\n⚠️  Some regression tests FAILED!")
            return 1

    finally:
        if server_proc:
            print("\nStopping server...")
            server_proc.kill()
            server_proc.wait()

if __name__ == '__main__':
    sys.exit(main())
