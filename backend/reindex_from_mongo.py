#!/usr/bin/env python3
"""
Wipe Qdrant policy_clauses collection and re-index from MongoDB.
Uses SentenceTransformer all-MiniLM-L6-v2 for real 384-dim embeddings.
"""
import time
import uuid
import pymongo
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "compli-ai"
COLLECTION = "policy_clauses"
VECTOR_SIZE = 384
BATCH_SIZE = 64

def main():
    # Connect
    mongo = pymongo.MongoClient(MONGO_URI)
    db = mongo[DB_NAME]
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # 1. Delete and recreate Qdrant collection
    print(f"Deleting Qdrant collection '{COLLECTION}'...")
    try:
        qdrant.delete_collection(COLLECTION)
    except Exception:
        pass  # Collection may not exist

    print(f"Creating fresh collection '{COLLECTION}' (dim={VECTOR_SIZE}, cosine)...")
    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    )

    # 2. Gather all policy clauses from MongoDB
    policies = list(db.policies.find({}, {"_id": 0}))
    print(f"\nFound {len(policies)} policies in MongoDB")

    total_clauses = 0
    all_points = []

    for policy in policies:
        policy_id = policy.get("id", "unknown")
        org = policy.get("organization", "default")
        user_id = policy.get("user_id", "unknown")
        title = (policy.get("title") or "")[:60]
        clauses = policy.get("clauses", [])

        if not clauses:
            print(f"  SKIP {policy_id[:12]}... ({title}) - no clauses")
            continue

        print(f"  Indexing {policy_id[:12]}... ({title}) - {len(clauses)} clauses, org='{org}'")

        # Build texts for batch embedding
        texts = []
        valid_clauses = []
        for clause in clauses:
            text = clause.get("text") or clause.get("original_text") or ""
            if not text.strip():
                continue
            texts.append(text)
            valid_clauses.append(clause)

        if not texts:
            print(f"    No text content, skipping")
            continue

        # Batch encode
        embeddings = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False)

        for clause, embedding in zip(valid_clauses, embeddings):
            clause_id = clause.get("clause_id", str(uuid.uuid4()))
            clause_text = clause.get("text") or clause.get("original_text") or ""

            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist(),
                payload={
                    "policy_id": policy_id,
                    "clause_id": clause_id,
                    "text": clause_text,
                    "section": clause.get("section"),
                    "page_number": clause.get("page_number"),
                    "title": clause.get("title"),
                    "requirement_type": clause.get("requirement_type", "informational"),
                    "subject_category": clause.get("subject_category", "general"),
                    "criticality": clause.get("criticality", "medium"),
                    "organization": org,
                    "user_id": user_id,
                    "tags": clause.get("tags", []),
                    "keywords": clause.get("keywords", []),
                }
            )
            all_points.append(point)
            total_clauses += 1

    # 3. Batch upsert all points
    print(f"\nUpserting {total_clauses} points to Qdrant in batches of {BATCH_SIZE}...")
    start = time.time()
    for i in range(0, len(all_points), BATCH_SIZE):
        batch = all_points[i:i + BATCH_SIZE]
        qdrant.upsert(collection_name=COLLECTION, points=batch)
        print(f"  Upserted {min(i + BATCH_SIZE, total_clauses)}/{total_clauses}")

    elapsed = time.time() - start
    print(f"\nDone! Indexed {total_clauses} clauses in {elapsed:.1f}s")

    # 4. Verify
    info = qdrant.get_collection(COLLECTION)
    print(f"\nVerification: collection has {info.points_count} points")

    # Quick search test
    test_query = "customer identity verification KYC requirements"
    test_emb = model.encode(test_query).tolist()
    results = qdrant.query_points(
        collection_name=COLLECTION, query=test_emb, limit=3, score_threshold=0.25
    )
    pts = results.points if hasattr(results, "points") else []
    print(f"\nTest search '{test_query[:40]}...' -> {len(pts)} results")
    for p in pts:
        print(f"  Score: {p.score:.4f} | policy_id: {p.payload.get('policy_id','')[:12]}... | org: {p.payload.get('organization')} | title: {(p.payload.get('title') or '')[:50]}")

    mongo.close()

if __name__ == "__main__":
    main()
