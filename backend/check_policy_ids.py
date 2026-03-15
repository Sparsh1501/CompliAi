#!/usr/bin/env python3
"""Check policy_ids in Qdrant and in the policy being analyzed."""
from qdrant_client import QdrantClient
import pymongo

# Check Qdrant policy_ids
client = QdrantClient(host='localhost', port=6333)
scroll_result = client.scroll(collection_name='policy_clauses', limit=100, with_payload=True)
policy_ids = set()
for p in scroll_result[0]:
    pid = p.payload.get('policy_id', 'NONE')
    policy_ids.add(pid)

print(f"Unique policy_ids in Qdrant ({len(policy_ids)}):")
for pid in sorted(policy_ids):
    # Count how many clauses per policy
    count = sum(1 for p in scroll_result[0] if p.payload.get('policy_id') == pid)
    print(f"  {pid}: ~{count}+ clauses (from first 100)")

# Check MongoDB policies
mongo = pymongo.MongoClient('mongodb://localhost:27017')
db = mongo['compli-ai']
policies = list(db.policies.find({}, {'id': 1, 'title': 1, 'user_id': 1, '_id': 0}))
print(f"\nPolicies in MongoDB ({len(policies)}):")
for p in policies[:10]:
    print(f"  id={p.get('id')}, title={p.get('title', '')[:50]}")
