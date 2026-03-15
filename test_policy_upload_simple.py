#!/usr/bin/env python3
"""Simple test for Feature #16: Policy document upload"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

def register_and_login():
    """Register and login, return token"""
    # Try register (ignore if exists)
    try:
        requests.post(f"{BASE_URL}/auth/register", json={
            "full_name": "Feature 16 Test",
            "email": "feature16test@test.com",
            "organization": "Test Org",
            "password": "Test123!@#"
        })
    except:
        pass

    # Login
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "feature16test@test.com",
        "password": "Test123!@#"
    })
    return r.json()['token']

def upload_policy(token):
    """Upload test PDF"""
    headers = {"Authorization": f"Bearer {token}"}

    with open('test-policy-kyc.pdf', 'rb') as f:
        files = {'file': ('test-policy-kyc.pdf', f, 'application/pdf')}
        data = {'policy_data': json.dumps({
            "title": "KYC Policy 2024",
            "policy_type": "KYC",
            "description": "Know Your Customer policy"
        })}

        r = requests.post(f"{BASE_URL}/policies/upload", headers=headers, files=files, data=data)

    print(f"Upload: {r.status_code} - {r.text}")
    return r.json()

def wait_for_job(token, job_id):
    """Wait for background job to complete"""
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(30):
        r = requests.get(f"{BASE_URL}/upload-jobs/{job_id}", headers=headers)
        job = r.json()
        status = job.get('status')

        print(f"Job status: {status} - {job.get('progress_percent', 0)}%")

        if status == 'completed':
            return job.get('entity_id')
        elif status == 'failed':
            print(f"ERROR: {job.get('error_message')}")
            return None

        time.sleep(2)

    return None

def verify_policy(token, policy_id):
    """Verify policy in list and detail"""
    headers = {"Authorization": f"Bearer {token}"}

    # Check list
    r = requests.get(f"{BASE_URL}/policies", headers=headers)
    policies = r.json()

    found = any(p.get('id') == policy_id for p in policies)
    print(f"✓ Policy in list: {found}")

    # Check detail
    r = requests.get(f"{BASE_URL}/policies/{policy_id}", headers=headers)
    policy = r.json()

    clauses = len(policy.get('clauses', []))
    print(f"✓ Policy detail loaded with {clauses} clauses")

    return found and clauses > 0

def cleanup(token, policy_id):
    """Delete test policy"""
    headers = {"Authorization": f"Bearer {token}"}
    requests.delete(f"{BASE_URL}/policies/{policy_id}", headers=headers)
    print("✓ Cleaned up")

if __name__ == "__main__":
    print("=== Feature #16 Test ===")

    token = register_and_login()
    print("✓ Logged in")

    result = upload_policy(token)
    job_id = result['job_id']
    print(f"✓ Upload started: {job_id}")

    policy_id = wait_for_job(token, job_id)
    if not policy_id:
        exit(1)

    print(f"✓ Policy created: {policy_id}")

    if verify_policy(token, policy_id):
        print("\n✓✓✓ FEATURE #16 PASSED ✓✓✓")
        cleanup(token, policy_id)
    else:
        print("\n✗ VERIFICATION FAILED")
        exit(1)
