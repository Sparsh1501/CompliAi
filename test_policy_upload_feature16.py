#!/usr/bin/env python3
"""
Test script for Feature #16: Policy document upload
Creates a test PDF and uploads it via the API endpoint
"""
import requests
import json
import time
from pathlib import Path

# API Configuration
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api"

def create_test_pdf():
    """Create a simple test PDF file"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    pdf_path = "test-policy-feature16.pdf"
    c = canvas.Canvas(pdf_path, pagesize=letter)

    # Add content
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "Know Your Customer (KYC) Policy")

    c.setFont("Helvetica", 12)
    c.drawString(100, 720, "Effective Date: January 1, 2024")
    c.drawString(100, 700, "Organization: Test Financial Services Ltd.")

    c.setFont("Helvetica", 11)
    y_pos = 670
    clauses = [
        "1. All customers must provide valid government-issued photo identification.",
        "2. Proof of address must be submitted within 30 days of account opening.",
        "3. Enhanced due diligence is required for high-risk customers.",
        "4. Customer information must be updated annually.",
        "5. Any suspicious activity must be reported immediately to compliance.",
    ]

    for clause in clauses:
        c.drawString(100, y_pos, clause)
        y_pos -= 25

    c.save()
    return pdf_path

def register_and_login():
    """Register a test user and get auth token"""
    # Register
    register_data = {
        "full_name": "Feature 16 Test User",
        "email": "feature16test@test.com",
        "organization": "Test Org",
        "password": "Test123!@#"
    }

    try:
        response = requests.post(f"{API_URL}/auth/register", json=register_data)
        print(f"Register response: {response.status_code}")
    except Exception as e:
        print(f"Registration failed (user may exist): {e}")

    # Login
    login_data = {
        "email": "feature16test@test.com",
        "password": "Test123!@#"
    }

    response = requests.post(f"{API_URL}/auth/login", json=login_data)
    if response.status_code == 200:
        data = response.json()
        return data['token']
    else:
        raise Exception(f"Login failed: {response.status_code} - {response.text}")

def upload_policy(token, pdf_path):
    """Upload policy PDF via API"""
    headers = {
        "Authorization": f"Bearer {token}"
    }

    policy_data = {
        "title": "KYC Policy 2024",
        "policy_type": "KYC",
        "description": "Know Your Customer policy document"
    }

    with open(pdf_path, 'rb') as f:
        files = {
            'file': ('test-policy-kyc.pdf', f, 'application/pdf')
        }
        data = {
            'policy_data': json.dumps(policy_data)
        }

        response = requests.post(
            f"{API_URL}/policies/upload",
            headers=headers,
            files=files,
            data=data
        )

    print(f"Upload response: {response.status_code}")
    print(f"Response body: {response.text}")

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Upload failed: {response.status_code} - {response.text}")

def check_job_status(token, job_id):
    """Check upload job status"""
    headers = {
        "Authorization": f"Bearer {token}"
    }

    max_attempts = 30
    for i in range(max_attempts):
        response = requests.get(
            f"{API_URL}/upload-jobs/{job_id}",
            headers=headers
        )

        if response.status_code == 200:
            job = response.json()
            print(f"Job status: {job.get('status')} - Progress: {job.get('progress_percent', 0)}%")

            if job.get('status') == 'completed':
                print(f"✓ Job completed! Policy ID: {job.get('entity_id')}")
                return job.get('entity_id')
            elif job.get('status') == 'failed':
                print(f"✗ Job failed: {job.get('error_message')}")
                return None

        time.sleep(2)

    print("Timeout waiting for job completion")
    return None

def verify_policy_in_list(token, policy_id):
    """Verify policy appears in list"""
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(f"{API_URL}/policies", headers=headers)
    print(f"Get policies response: {response.status_code}")

    if response.status_code == 200:
        policies = response.json()
        print(f"Total policies: {len(policies)}")

        for policy in policies:
            if policy.get('id') == policy_id:
                print(f"✓ Found policy in list: {policy.get('title')}")
                print(f"  - Clauses extracted: {len(policy.get('clauses', []))}")
                return True

        print(f"✗ Policy {policy_id} not found in list")
        return False
    else:
        print(f"Failed to get policies: {response.text}")
        return False

def verify_policy_detail(token, policy_id):
    """Verify policy detail view with clauses"""
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(f"{API_URL}/policies/{policy_id}", headers=headers)
    print(f"Get policy detail response: {response.status_code}")

    if response.status_code == 200:
        policy = response.json()
        print(f"✓ Policy detail loaded")
        print(f"  - Title: {policy.get('title')}")
        print(f"  - Type: {policy.get('policy_type')}")
        print(f"  - Clauses: {len(policy.get('clauses', []))}")

        # Show first few clauses
        for i, clause in enumerate(policy.get('clauses', [])[:3]):
            print(f"  - Clause {i+1}: {clause.get('text')[:80]}...")

        return True
    else:
        print(f"Failed to get policy detail: {response.text}")
        return False

def cleanup(token, policy_id):
    """Clean up test data"""
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Delete policy
    response = requests.delete(f"{API_URL}/policies/{policy_id}", headers=headers)
    print(f"Cleanup: Delete policy - {response.status_code}")

if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Feature #16 Test: Policy Document Upload")
        print("=" * 60)

        # Step 1: Create test PDF
        print("\n[Step 1] Creating test PDF...")
        pdf_path = create_test_pdf()
        print(f"✓ Created: {pdf_path}")

        # Step 2: Login
        print("\n[Step 2] Logging in...")
        token = register_and_login()
        print("✓ Authenticated")

        # Step 3: Upload policy
        print("\n[Step 3] Uploading policy PDF...")
        upload_result = upload_policy(token, pdf_path)
        job_id = upload_result.get('job_id')
        print(f"✓ Upload started - Job ID: {job_id}")

        # Step 4: Wait for processing
        print("\n[Step 4] Waiting for background processing...")
        policy_id = check_job_status(token, job_id)

        if not policy_id:
            print("✗ Upload processing failed")
            exit(1)

        # Step 5: Verify in list
        print("\n[Step 5] Verifying policy appears in list...")
        if not verify_policy_in_list(token, policy_id):
            print("✗ Verification failed")
            exit(1)

        # Step 6: Verify detail view with clauses
        print("\n[Step 6] Verifying policy detail view...")
        if not verify_policy_detail(token, policy_id):
            print("✗ Verification failed")
            exit(1)

        # Cleanup
        print("\n[Cleanup] Removing test data...")
        cleanup(token, policy_id)

        print("\n" + "=" * 60)
        print("✓ Feature #16 VERIFICATION COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
