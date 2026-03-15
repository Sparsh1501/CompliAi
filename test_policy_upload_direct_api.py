#!/usr/bin/env python3
"""
Direct API test for Feature #16: Policy upload with clause extraction
This script bypasses browser file picker limitations by using requests library
"""

import requests
import json
import time
import os
from io import BytesIO

# Configuration
BASE_URL = "http://localhost:8000/api"
TEST_EMAIL = "feature16_direct_api_test@example.com"
TEST_PASSWORD = "TestPassword123!"
TEST_USER_NAME = "Feature 16 API Test User"
TEST_ORG = "API Test Org"

def create_test_pdf():
    """Create a simple test PDF with policy content"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # Add policy content
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "Know Your Customer (KYC) Policy")

    c.setFont("Helvetica", 12)
    y = 700

    policy_text = [
        "1. Customer Identification",
        "   All customers must provide valid government-issued identification.",
        "   Acceptable documents include: Passport, Driver's License, Aadhaar Card.",
        "",
        "2. Customer Due Diligence (CDD)",
        "   Enhanced due diligence required for high-risk customers.",
        "   Customer risk rating must be reviewed annually.",
        "",
        "3. Record Keeping",
        "   All KYC documents must be retained for 7 years.",
        "   Documents must be stored securely in encrypted format.",
        "",
        "4. Ongoing Monitoring",
        "   Transaction patterns must be monitored for suspicious activity.",
        "   Any unusual patterns must be reported within 24 hours.",
    ]

    for line in policy_text:
        c.drawString(100, y, line)
        y -= 20
        if y < 100:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = 750

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def register_user():
    """Register a test user"""
    print(f"\n1. Registering test user: {TEST_EMAIL}")
    response = requests.post(f"{BASE_URL}/auth/register", json={
        "full_name": TEST_USER_NAME,
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "organization": TEST_ORG
    })

    if response.status_code == 200:
        print("   ✓ User registered successfully")
        return True
    elif response.status_code == 400 and "already exists" in response.text.lower():
        print("   ✓ User already exists")
        return True
    else:
        print(f"   ✗ Registration failed: {response.status_code} - {response.text}")
        return False

def login_user():
    """Login and get JWT token"""
    print(f"\n2. Logging in as {TEST_EMAIL}")
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })

    if response.status_code == 200:
        data = response.json()
        token = data.get('token')
        print(f"   ✓ Login successful, token received")
        return token
    else:
        print(f"   ✗ Login failed: {response.status_code} - {response.text}")
        return None

def upload_policy(token):
    """Upload a policy document via API"""
    print("\n3. Creating test PDF with KYC policy content")
    pdf_content = create_test_pdf()
    print(f"   ✓ Created PDF ({len(pdf_content)} bytes)")

    print("\n4. Uploading policy via POST /api/policies/upload")

    # Prepare multipart form data
    files = {
        'file': ('test_kyc_policy_feature16.pdf', pdf_content, 'application/pdf')
    }

    policy_data = {
        'title': 'KYC Policy - Feature 16 Test',
        'policy_type': 'KYC',
        'version': '1.0',
        'department': 'Compliance'
    }

    data = {
        'policy_data': json.dumps(policy_data)
    }

    headers = {
        'Authorization': f'Bearer {token}'
    }

    response = requests.post(
        f"{BASE_URL}/policies/upload",
        files=files,
        data=data,
        headers=headers
    )

    if response.status_code == 200:
        result = response.json()
        job_id = result.get('job_id')
        print(f"   ✓ Upload started successfully")
        print(f"   Job ID: {job_id}")
        print(f"   Status: {result.get('status')}")
        return job_id
    else:
        print(f"   ✗ Upload failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

def check_upload_job(token, job_id, max_wait=30):
    """Poll upload job status until complete"""
    print(f"\n5. Monitoring upload job: {job_id}")

    headers = {
        'Authorization': f'Bearer {token}'
    }

    start_time = time.time()
    last_progress = -1

    while time.time() - start_time < max_wait:
        response = requests.get(
            f"{BASE_URL}/upload-jobs",
            headers=headers
        )

        if response.status_code != 200:
            print(f"   ✗ Failed to get job status: {response.status_code}")
            break

        jobs = response.json()
        job = next((j for j in jobs if j.get('id') == job_id), None)

        if not job:
            print(f"   ✗ Job not found")
            break

        progress = job.get('progress', 0)
        status = job.get('status', 'unknown')
        current_step = job.get('current_step', '')

        if progress != last_progress:
            print(f"   Progress: {progress}% - {status} - {current_step}")
            last_progress = progress

        if status == 'completed':
            print(f"   ✓ Upload job completed successfully!")
            clauses = job.get('clauses_extracted', 0)
            print(f"   Clauses extracted: {clauses}")
            return True
        elif status == 'failed':
            print(f"   ✗ Upload job failed: {job.get('error_message', 'Unknown error')}")
            return False

        time.sleep(1)

    print(f"   ✗ Timeout waiting for job completion")
    return False

def verify_policy_in_list(token):
    """Verify policy appears in policy list"""
    print("\n6. Verifying policy appears in list (GET /api/policies)")

    headers = {
        'Authorization': f'Bearer {token}'
    }

    response = requests.get(
        f"{BASE_URL}/policies",
        headers=headers
    )

    if response.status_code == 200:
        policies = response.json()
        matching = [p for p in policies if 'Feature 16 Test' in p.get('title', '')]

        if matching:
            policy = matching[0]
            print(f"   ✓ Policy found in list!")
            print(f"   Title: {policy.get('title')}")
            print(f"   Type: {policy.get('policy_type')}")
            print(f"   Department: {policy.get('department')}")
            print(f"   Status: {policy.get('status')}")
            return policy.get('id')
        else:
            print(f"   ✗ Policy not found in list")
            return None
    else:
        print(f"   ✗ Failed to get policies: {response.status_code}")
        return None

def verify_clause_extraction(token, policy_id):
    """Verify clause extraction by checking policy detail"""
    print(f"\n7. Verifying clause extraction (GET /api/policies/{policy_id})")

    headers = {
        'Authorization': f'Bearer {token}'
    }

    response = requests.get(
        f"{BASE_URL}/policies/{policy_id}",
        headers=headers
    )

    if response.status_code == 200:
        policy = response.json()
        clauses = policy.get('clauses', [])

        print(f"   ✓ Policy detail retrieved")
        print(f"   Total clauses: {len(clauses)}")

        if clauses:
            print(f"\n   First 3 extracted clauses:")
            for i, clause in enumerate(clauses[:3], 1):
                clause_id = clause.get('clause_id', 'N/A')
                text = clause.get('text', '')[:100]
                print(f"   {i}. {clause_id}: {text}...")
            return True
        else:
            print(f"   ✗ No clauses extracted")
            return False
    else:
        print(f"   ✗ Failed to get policy detail: {response.status_code}")
        return False

def cleanup(token, policy_id):
    """Clean up test data"""
    print(f"\n8. Cleaning up test data")

    headers = {
        'Authorization': f'Bearer {token}'
    }

    if policy_id:
        response = requests.delete(
            f"{BASE_URL}/policies/{policy_id}",
            headers=headers
        )

        if response.status_code == 200:
            print(f"   ✓ Test policy deleted")
        else:
            print(f"   ⚠ Failed to delete policy: {response.status_code}")

def main():
    """Run the complete test"""
    print("=" * 70)
    print("Feature #16: Policy Upload with Clause Extraction - Direct API Test")
    print("=" * 70)

    # Step 1: Register
    if not register_user():
        print("\n✗ Test failed: Could not register user")
        return False

    # Step 2: Login
    token = login_user()
    if not token:
        print("\n✗ Test failed: Could not login")
        return False

    # Step 3: Upload
    job_id = upload_policy(token)
    if not job_id:
        print("\n✗ Test failed: Could not start upload")
        return False

    # Step 4: Monitor job
    if not check_upload_job(token, job_id, max_wait=60):
        print("\n✗ Test failed: Upload job did not complete")
        return False

    # Step 5: Verify in list
    policy_id = verify_policy_in_list(token)
    if not policy_id:
        print("\n✗ Test failed: Policy not in list")
        return False

    # Step 6: Verify clause extraction
    if not verify_clause_extraction(token, policy_id):
        print("\n✗ Test failed: Clause extraction failed")
        return False

    # Step 7: Cleanup
    cleanup(token, policy_id)

    print("\n" + "=" * 70)
    print("✓ FEATURE #16 VERIFICATION COMPLETE - ALL TESTS PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
