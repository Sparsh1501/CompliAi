"""
Re-index all Qdrant policy_clauses with proper embeddings.
The existing vectors are degenerate (all identical values from fallback).
This script regenerates real embeddings using the local SentenceTransformer model.
"""
import asyncio
import logging
import sys
import time
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "policy_clauses"
BATCH_SIZE = 100


async def reindex():
    """Re-embed all points in the policy_clauses collection."""
    # Load embedding model
    logger.info("Loading SentenceTransformer model (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    logger.info("Model loaded successfully")

    # Connect to Qdrant
    client = QdrantClient(url=QDRANT_URL)
    collection_info = client.get_collection(COLLECTION_NAME)
    total_points = collection_info.points_count
    logger.info(f"Collection '{COLLECTION_NAME}' has {total_points} points to re-index")

    if total_points == 0:
        logger.info("No points to re-index. Done.")
        return

    # Scroll through all points and re-embed
    offset = None
    processed = 0
    start_time = time.time()

    while True:
        # Scroll batch
        scroll_result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=BATCH_SIZE,
            offset=offset,
            with_payload=True,
            with_vectors=False  # Don't need old vectors
        )

        points, next_offset = scroll_result

        if not points:
            break

        # Gather texts for batch embedding
        texts = []
        point_ids = []
        payloads = []

        for point in points:
            text = point.payload.get('text', '')
            if not text:
                text = point.payload.get('original_text', '')
            if not text:
                text = 'empty'
            texts.append(text[:8000])  # Truncate like original code
            point_ids.append(point.id)
            payloads.append(point.payload)

        # Batch encode (much faster than one-by-one)
        embeddings = model.encode(texts).tolist()

        # Upsert with new embeddings
        new_points = [
            PointStruct(
                id=pid,
                vector=emb,
                payload=payload
            )
            for pid, emb, payload in zip(point_ids, embeddings, payloads)
        ]

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=new_points
        )

        processed += len(points)
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        logger.info(f"Re-indexed {processed}/{total_points} points ({rate:.0f} pts/sec)")

        if next_offset is None:
            break
        offset = next_offset

    elapsed = time.time() - start_time
    logger.info(f"Done! Re-indexed {processed} points in {elapsed:.1f}s")

    # Verify
    info = client.get_collection(COLLECTION_NAME)
    logger.info(f"Collection now has {info.indexed_vectors_count} indexed vectors, {info.points_count} points")


if __name__ == "__main__":
    asyncio.run(reindex())
