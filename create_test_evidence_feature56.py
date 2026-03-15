#!/usr/bin/env python3
"""
Create test evidence for Feature #56 - Evidence lifecycle workflow
Tests different validation statuses and lifecycle states
"""
from pymongo import MongoClient
from datetime import datetime, timezone
import uuid

def create_test_evidence():
    # Connect to MongoDB
    client = MongoClient('mongodb://localhost:27017')
    db = client['compliai']

    # Get the test user
    user = db.users.find_one({"email": "evidencetest@example.com"})
    if not user:
        print("❌ Test user not found. Please register first.")
        return

    user_id = user['user_id']
    org = user['organization']
    full_name = user['full_name']

    print(f"✓ Found user: {full_name} ({user_id})")

    # Clear existing test evidence for this user
    result = db.evidence.delete_many({"user_id": user_id})
    print(f"✓ Cleared {result.deleted_count} existing evidence records")

    # Test evidence scenarios for lifecycle workflow
    test_evidence = [
        {
            "id": str(uuid.uuid4()),
            "title": "Test Evidence - High Confidence Auto-Approved",
            "description": "Evidence that should auto-approve with high confidence",
            "file_url": "https://example.com/evidence/high-confidence.pdf",
            "file_name": "high-confidence.pdf",
            "file_type": "pdf",
            "file_size": 125000,
            "sha256_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6",
            "ocr_text": "Customer Due Diligence completed on 2024-01-15 by John Doe",
            "extracted_fields": {
                "dates": ["2024-01-15"],
                "names": ["John Doe"],
                "amounts": [],
                "signatures_present": True
            },
            "validation_status": "uploaded",  # Initial status before validation
            "ai_compliance_score": None,
            "ai_confidence": None,
            "ai_validation_notes": None,
            "ai_explanation": None,
            "audit_log": [
                {
                    "action": "uploaded",
                    "user_id": user_id,
                    "user_name": full_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": "Evidence uploaded"
                }
            ],
            "user_id": user_id,
            "organization": org,
            "uploaded_by_name": full_name,
            "created_at": datetime.now(timezone.utc),
            "tags": []
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Test Evidence - Medium Confidence Pending Review",
            "description": "Evidence with uncertain AI validation requiring human review",
            "file_url": "https://example.com/evidence/medium-confidence.pdf",
            "file_name": "medium-confidence.pdf",
            "file_type": "pdf",
            "file_size": 98000,
            "sha256_hash": "b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7",
            "ocr_text": "Document partially complete, missing some signatures",
            "extracted_fields": {
                "dates": ["2024-02-01"],
                "names": ["Jane Smith"],
                "amounts": ["5000"],
                "signatures_present": False
            },
            "validation_status": "uploaded",
            "ai_compliance_score": None,
            "ai_confidence": None,
            "ai_validation_notes": None,
            "ai_explanation": None,
            "audit_log": [
                {
                    "action": "uploaded",
                    "user_id": user_id,
                    "user_name": full_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": "Evidence uploaded"
                }
            ],
            "user_id": user_id,
            "organization": org,
            "uploaded_by_name": full_name,
            "created_at": datetime.now(timezone.utc),
            "tags": []
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Test Evidence - Low Confidence Failed",
            "description": "Evidence that AI marks as failed (for override testing)",
            "file_url": "https://example.com/evidence/low-confidence.pdf",
            "file_name": "low-confidence.pdf",
            "file_type": "pdf",
            "file_size": 45000,
            "sha256_hash": "c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8",
            "ocr_text": "Incomplete document, missing critical information",
            "extracted_fields": {
                "dates": [],
                "names": [],
                "amounts": [],
                "signatures_present": False
            },
            "validation_status": "uploaded",
            "ai_compliance_score": None,
            "ai_confidence": None,
            "ai_validation_notes": None,
            "ai_explanation": None,
            "audit_log": [
                {
                    "action": "uploaded",
                    "user_id": user_id,
                    "user_name": full_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": "Evidence uploaded"
                }
            ],
            "user_id": user_id,
            "organization": org,
            "uploaded_by_name": full_name,
            "created_at": datetime.now(timezone.utc),
            "tags": []
        }
    ]

    # Insert test evidence
    result = db.evidence.insert_many(test_evidence)
    print(f"✓ Created {len(result.inserted_ids)} test evidence records")

    # Print evidence IDs for reference
    for i, evidence in enumerate(test_evidence):
        print(f"  {i+1}. {evidence['title']}")
        print(f"     ID: {evidence['id']}")
        print(f"     Status: {evidence['validation_status']}")

    print("\n✅ Test evidence created successfully!")
    print("\nNext steps for Feature #56 testing:")
    print("1. Navigate to /evidence page in browser")
    print("2. Click on first evidence to trigger AI validation")
    print("3. Verify high confidence → auto_approved status")
    print("4. Click on second evidence to trigger validation")
    print("5. Verify medium confidence → pending_human_review status")
    print("6. Approve the pending evidence manually")
    print("7. Click on third evidence (failed)")
    print("8. Test human override functionality")
    print("9. Verify all lifecycle transitions are tracked in audit_log")

    client.close()

if __name__ == "__main__":
    create_test_evidence()
