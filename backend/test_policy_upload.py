#!/usr/bin/env python3
import requests
import json

# Login to get token
login_response = requests.post(
    'http://localhost:8000/api/auth/login',
    json={
        'email': 'feature16_test_feb8@example.com',
        'password': 'TestPass123!'
    }
)
print(f"Login status: {login_response.status_code}")
token = login_response.json()['access_token']
print(f"Got token: {token[:50]}...")

# Upload policy
files = {'file': open('/tmp/claude/test_kyc_policy.pdf', 'rb')}
data = {
    'title': 'Test KYC Policy',
    'policy_type': 'KYC',
    'version': '1.0',
    'department': 'Compliance'
}
headers = {'Authorization': f'Bearer {token}'}

upload_response = requests.post(
    'http://localhost:8000/api/policies/upload',
    headers=headers,
    files=files,
    data=data
)

print(f"\nUpload status: {upload_response.status_code}")
print(f"Response: {json.dumps(upload_response.json(), indent=2)}")

# Check if policy appears in list
list_response = requests.get(
    'http://localhost:8000/api/policies',
    headers=headers
)
print(f"\nPolicy list status: {list_response.status_code}")
policies = list_response.json()
print(f"Total policies: {len(policies)}")
if policies:
    print(f"First policy: {policies[0].get('title', 'N/A')}")
