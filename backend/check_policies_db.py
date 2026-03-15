#!/usr/bin/env python3
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def check_policies():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['compli-ai']
    policies = db['policies']

    count = await policies.count_documents({})
    print(f"Total policies in database: {count}")

    if count > 0:
        cursor = policies.find().limit(5)
        async for policy in cursor:
            print(f"\nPolicy: {policy.get('title', 'N/A')}")
            print(f"  ID: {policy.get('_id', 'N/A')}")
            print(f"  Type: {policy.get('policy_type', 'N/A')}")
            print(f"  Status: {policy.get('status', 'N/A')}")
            print(f"  Version: {policy.get('version', 'N/A')}")
            print(f"  Clauses: {len(policy.get('clauses', []))}")

    client.close()

asyncio.run(check_policies())
