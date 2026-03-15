import requests
import json

# Login to get token
login_data = {
    "email": "test@test.com",
    "password": "test123"
}

# Try to login or register
try:
    response = requests.post("http://localhost:8000/api/auth/login", json=login_data)
    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✓ Logged in successfully")
    else:
        # Register if login fails
        reg_data = {
            "email": "test@test.com",
            "password": "test123",
            "name": "Test User",
            "organization": "Test Org"
        }
        response = requests.post("http://localhost:8000/api/auth/register", json=reg_data)
        token = response.json()["access_token"]
        print(f"✓ Registered new user")
except Exception as e:
    print(f"✗ Error with auth: {e}")
    exit(1)

# Test the regulatory updates endpoint
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("http://localhost:8000/api/regulation-updates", headers=headers)
print(f"\n✓ GET /api/regulation-updates - Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
