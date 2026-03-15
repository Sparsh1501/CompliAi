#!/usr/bin/env python3
"""Diagnose why Qdrant search returns 0 results."""
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import numpy as np

client = QdrantClient(host='localhost', port=6333)
model = SentenceTransformer('all-MiniLM-L6-v2')

# 1. Check a few stored vectors
scroll_result = client.scroll(
    collection_name='policy_clauses',
    limit=5,
    with_vectors=True,
    with_payload=True
)

print("=== Stored Vectors ===")
for p in scroll_result[0]:
    vec = p.vector
    if isinstance(vec, dict):
        vec = list(vec.values())[0]
    arr = np.array(vec)
    print(f"Point {p.id}: dim={len(vec)}, min={arr.min():.6f}, max={arr.max():.6f}, mean={arr.mean():.6f}, std={arr.std():.6f}")
    print(f"  First 5 values: {vec[:5]}")
    title = (p.payload.get('title') or '')[:60]
    print(f"  Title: {title}")
    text = (p.payload.get('text') or '')[:80]
    print(f"  Text: {text}")

# 2. Generate a fresh query embedding
query = 'The institution shall maintain adequate capital reserves'
embedding = model.encode(query).tolist()
emb_arr = np.array(embedding)
print(f"\n=== Query Embedding ===")
print(f"dim={len(embedding)}, min={emb_arr.min():.6f}, max={emb_arr.max():.6f}, mean={emb_arr.mean():.6f}, std={emb_arr.std():.6f}")
print(f"First 5: {embedding[:5]}")

# 3. Compute cosine similarity manually
stored_vec = np.array(scroll_result[0][0].vector if not isinstance(scroll_result[0][0].vector, dict) else list(scroll_result[0][0].vector.values())[0])
dot_product = np.dot(emb_arr, stored_vec)
norm_q = np.linalg.norm(emb_arr)
norm_s = np.linalg.norm(stored_vec)
cosine_sim = dot_product / (norm_q * norm_s) if norm_q > 0 and norm_s > 0 else 0
print(f"\nManual cosine similarity with first vector: {cosine_sim:.6f}")

# 4. Search with NO threshold
results = client.query_points(
    collection_name='policy_clauses',
    query=embedding,
    limit=5
)
points = results.points if hasattr(results, 'points') else []
print(f"\n=== Search with NO threshold: {len(points)} results ===")
for p in points[:5]:
    print(f"  Score: {p.score:.6f} | title: {(p.payload.get('title') or '')[:60]}")

# 5. Check if all vectors are identical (degenerate)
vecs = []
for p in scroll_result[0]:
    v = p.vector if not isinstance(p.vector, dict) else list(p.vector.values())[0]
    vecs.append(v[:5])
all_same = all(v == vecs[0] for v in vecs)
print(f"\n=== All 5 vectors identical? {all_same} ===")
