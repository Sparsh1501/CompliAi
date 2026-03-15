#!/usr/bin/env python3
"""Create test policy in MongoDB for Feature #16"""
import sys
sys.path.insert(0, './backend')

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import asyncio

async def create_test_policy():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['compli-ai']

    # Find user
    user = await db.users.find_one({'email': 'feature16test@test.com'})
    if not user:
        print('ERROR: Test user not found')
        return

    user_id = user['id']
    organization = user['organization']
    print(f"Found user: {user['full_name']} ({organization})")

    # Create policy
    policy_id = f"policy_{int(datetime.now().timestamp() * 1000)}"
    timestamp = datetime.now().isoformat()

    policy = {
        'id': policy_id,
        'title': 'KYC Policy 2024 - Feature 16 Test',
        'policy_type': 'KYC',
        'description': 'Know Your Customer policy document - test upload',
        'version': '1.0',
        'department': 'Compliance',
        'organization': organization,
        'created_by': user_id,
        'status': 'active',
        'file_name': 'test-policy-kyc.pdf',
        'file_size': 3907,
        'file_path': '/tmp/uploads/test-policy-kyc.pdf',
        'upload_date': timestamp,
        'last_modified': timestamp,
        'clauses': [
            {
                'id': f"clause_{int(datetime.now().timestamp() * 1000)}_1",
                'policy_id': policy_id,
                'text': 'All customers must provide valid government-issued photo identification before account opening.',
                'section': 'Customer Identification',
                'clause_number': '1',
                'category': 'identity_verification',
                'keywords': ['identification', 'photo ID', 'government-issued'],
                'created_at': timestamp
            },
            {
                'id': f"clause_{int(datetime.now().timestamp() * 1000)}_2",
                'policy_id': policy_id,
                'text': 'Proof of address must be submitted within 30 days of account opening through utility bills or bank statements.',
                'section': 'Address Verification',
                'clause_number': '2',
                'category': 'address_verification',
                'keywords': ['address', 'utility bills', 'bank statements'],
                'created_at': timestamp
            },
            {
                'id': f"clause_{int(datetime.now().timestamp() * 1000)}_3",
                'policy_id': policy_id,
                'text': 'Enhanced due diligence is required for high-risk customers including PEPs and those from high-risk jurisdictions.',
                'section': 'Enhanced Due Diligence',
                'clause_number': '3',
                'category': 'risk_assessment',
                'keywords': ['enhanced due diligence', 'PEPs', 'high-risk'],
                'created_at': timestamp
            },
            {
                'id': f"clause_{int(datetime.now().timestamp() * 1000)}_4",
                'policy_id': policy_id,
                'text': 'Customer information must be updated and reverified annually to maintain current records.',
                'section': 'Annual Updates',
                'clause_number': '4',
                'category': 'record_maintenance',
                'keywords': ['annual update', 'reverification', 'current records'],
                'created_at': timestamp
            },
            {
                'id': f"clause_{int(datetime.now().timestamp() * 1000)}_5",
                'policy_id': policy_id,
                'text': 'Any suspicious activity must be reported immediately to the compliance officer within 24 hours of detection.',
                'section': 'Suspicious Activity Reporting',
                'clause_number': '5',
                'category': 'reporting',
                'keywords': ['suspicious activity', 'compliance officer', '24 hours'],
                'created_at': timestamp
            }
        ],
        'metadata': {
            'total_clauses': 5,
            'extraction_method': 'AI-powered (test data)',
            'processing_status': 'completed'
        }
    }

    await db.policies.insert_one(policy)
    print(f"Created policy: {policy_id}")
    print(f"  - Title: {policy['title']}")
    print(f"  - Type: {policy['policy_type']}")
    print(f"  - Clauses: {len(policy['clauses'])}")

    # Create upload job
    job_id = f"job_{int(datetime.now().timestamp() * 1000)}"
    job = {
        'id': job_id,
        'user_id': user_id,
        'organization': organization,
        'job_type': 'policy',
        'file_name': 'test-policy-kyc.pdf',
        'file_size': 3907,
        'status': 'completed',
        'progress_percent': 100,
        'entity_id': policy_id,
        'entity_type': 'policy',
        'started_at': timestamp,
        'completed_at': timestamp,
        'metadata': {
            'title': policy['title'],
            'policy_type': policy['policy_type'],
            'clauses_extracted': 5
        }
    }

    await db.upload_jobs.insert_one(job)
    print(f"Created upload job: {job_id}")
    print(f"\n✓ SUCCESS: Policy ID = {policy_id}")

    client.close()

if __name__ == '__main__':
    asyncio.run(create_test_policy())
