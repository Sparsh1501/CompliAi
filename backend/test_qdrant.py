#!/usr/bin/env python3
"""Test Qdrant search directly to verify it works."""
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

client = QdrantClient(host='localhost', port=6333)
model = SentenceTransformer('all-MiniLM-L6-v2')

# Check collection info
info = client.get_collection('policy_clauses')
print(f"Collection has {info.points_count} points, vector size {info.config.params.vectors.size}")

# Get unique orgs
scroll_result = client.scroll(collection_name='policy_clauses', limit=100, with_payload=True)
orgs = set()
for p in scroll_result[0]:
    orgs.add(p.payload.get('organization', 'NONE'))
print(f"Unique organizations in Qdrant: {orgs}")

# Test query
query = 'The institution shall maintain adequate capital reserves in accordance with regulatory requirements'
embedding = model.encode(query).tolist()

# Search without filter
results = client.query_points(
    collection_name='policy_clauses',
    query=embedding,
    limit=5,
    score_threshold=0.5
)
points = results.points if hasattr(results, 'points') else []
print(f"\nResults without filter: {len(points)}")
for p in points[:3]:
    title = (p.payload.get('title') or '')[:60]
    print(f"  Score: {p.score:.4f} | org: {p.payload.get('organization')} | title: {title}")

# Search WITH org filter
for org_name in orgs:
    results2 = client.query_points(
        collection_name='policy_clauses',
        query=embedding,
        query_filter=Filter(must=[FieldCondition(key='organization', match=MatchValue(value=org_name))]),
        limit=5,
        score_threshold=0.5
    )
    points2 = results2.points if hasattr(results2, 'points') else []
    print(f"\nResults with org='{org_name}': {len(points2)}")
    for p in points2[:3]:
        title = (p.payload.get('title') or '')[:60]
        print(f"  Score: {p.score:.4f} | title: {title}")

print("\n=== Qdrant search is working ===")
