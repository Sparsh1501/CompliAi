#!/usr/bin/env python3
"""
Create test LOS/LMS upload data for Feature #67 testing.
This script creates a test upload with loan records that have various compliance issues.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import asyncio
import uuid

async def create_test_data():
    # Connect to MongoDB
    client = AsyncIOMotorClient('mongodb://localhost:27017/')
    db = client['compli-ai']

    # Get test user (feature67test@test.com)
    user = await db.users.find_one({"email": "feature67test@test.com"}, {"_id": 0})
    if not user:
        print("ERROR: Test user feature67test@test.com not found. Please register first.")
        return

    user_id = user['id']
    print(f"Found test user: {user['full_name']} ({user_id})")

    # Create test loan records with various compliance issues
    test_records = [
        {
            "borrower_name": "Rajesh Kumar",
            "loan_amount": "500000",
            "interest_rate": "18.5",
            "tenure_months": "36",
            "disbursement_date": "2024-01-15",
            "processing_fee": "5000",
            "insurance": "2500",
            "emi_amount": "18200",
            "annual_income": "600000",
            "credit_score": "720",
            "kyc_status": "Completed",
            "cibil_consent": "Yes",
            "sanction_letter": "Issued",
            "loan_agreement": "Signed"
        },
        {
            "borrower_name": "Priya Sharma",
            "loan_amount": "750000",
            "interest_rate": "42.0",  # EXCEEDS RBI cap of 36%
            "tenure_months": "48",
            "disbursement_date": "2024-02-10",
            "processing_fee": "20000",  # EXCEEDS 2% cap (15000 allowed)
            "insurance": "3500",
            "emi_amount": "24500",
            "annual_income": "900000",
            "credit_score": "680",
            "kyc_status": "Pending",  # NOT COMPLETED
            "cibil_consent": "No",  # NOT OBTAINED
            "sanction_letter": "Issued",
            "loan_agreement": "Signed"
        },
        {
            "borrower_name": "Amit Patel",
            "loan_amount": "300000",
            "interest_rate": "22.0",
            "tenure_months": "24",
            "disbursement_date": "2024-01-20",
            "processing_fee": "3000",
            "insurance": "1500",
            "emi_amount": "14800",
            "annual_income": "450000",
            "credit_score": "250",  # BELOW minimum 300
            "kyc_status": "Completed",
            "cibil_consent": "Yes",
            "sanction_letter": "Not Issued",  # MISSING
            "loan_agreement": "Pending"  # NOT SIGNED
        },
        {
            "borrower_name": "Sneha Gupta",
            "loan_amount": "1000000",
            "interest_rate": "16.5",
            "tenure_months": "60",
            "disbursement_date": "2024-02-05",
            "processing_fee": "10000",
            "insurance": "5000",
            "emi_amount": "24500",
            "annual_income": "1200000",
            "credit_score": "780",
            "kyc_status": "Verified",
            "cibil_consent": "Obtained",
            "sanction_letter": "Issued",
            "loan_agreement": "Signed"
        },
        {
            "borrower_name": "Vikram Singh",
            "loan_amount": "600000",
            "interest_rate": "35.5",
            "tenure_months": "42",
            "disbursement_date": "2024-01-25",
            "processing_fee": "6000",
            "insurance": "3000",
            "emi_amount": "21000",
            "annual_income": "720000",
            "credit_score": "650",
            "kyc_status": "",  # MISSING
            "cibil_consent": "",  # MISSING
            "sanction_letter": "Issued",
            "loan_agreement": "Signed"
        }
    ]

    # Create upload document
    upload_id = str(uuid.uuid4())
    upload_doc = {
        "id": upload_id,
        "upload_id": upload_id,
        "user_id": user_id,
        "filename": "test_loans_feature67.csv",
        "file_name": "test_loans_feature67.csv",
        "record_count": len(test_records),
        "total_records": len(test_records),
        "preview": test_records,
        "headers": list(test_records[0].keys()),
        "columns": list(test_records[0].keys()),
        "status": "uploaded",
        "scan_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    # Insert into database
    result = await db.los_lms_uploads.insert_one(upload_doc)
    print(f"\n✅ Created test upload: {upload_id}")
    print(f"   Filename: test_loans_feature67.csv")
    print(f"   Total records: {len(test_records)}")
    print(f"   User: {user['email']}")
    print(f"\nTest loan records:")
    for i, record in enumerate(test_records, 1):
        print(f"   {i}. {record['borrower_name']} - ₹{record['loan_amount']} @ {record['interest_rate']}% interest")

    print(f"\n📊 Expected compliance issues:")
    print(f"   - Priya Sharma: 4 exceptions (High interest 42%, High processing fee, No KYC, No CIBIL consent)")
    print(f"   - Amit Patel: 3 exceptions (Low credit score 250, No sanction letter, No loan agreement)")
    print(f"   - Vikram Singh: 2 exceptions (Missing KYC, Missing CIBIL consent)")
    print(f"   - Rajesh Kumar: 0 exceptions (Fully compliant)")
    print(f"   - Sneha Gupta: 0 exceptions (Fully compliant)")
    print(f"\n✅ Upload ID: {upload_id}")
    print(f"✅ Ready for compliance scanning via UI")

if __name__ == "__main__":
    asyncio.run(create_test_data())
