"""
Script to batch process all NPCI circulars and auto-convert them to regulations.
Runs directly against MongoDB, using the NPCIProcessingService pipeline.
"""
import asyncio
import os
import sys
import logging

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('anthropic').setLevel(logging.WARNING)


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv

    # Load env from backend
    load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

    mongo_url = os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
    db_name = os.getenv('DB_NAME', 'compliai')

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Initialize Qdrant client
    qdrant_client = None
    try:
        from qdrant_client import QdrantClient
        qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
        qdrant_client = QdrantClient(url=qdrant_url, timeout=30)
        qdrant_client.get_collections()
        logger.info(f"Connected to Qdrant at {qdrant_url}")
    except Exception as e:
        logger.warning(f"Qdrant not available: {e}")

    from services.npci_processing_service import NPCIProcessingService
    processing_service = NPCIProcessingService(db=db, qdrant_client=qdrant_client)
    await processing_service.ensure_indexes()

    # Count unprocessed
    total_unprocessed = await db.npci_circulars.count_documents({
        "$or": [
            {"processed_at": None},
            {"processed_at": {"$exists": False}},
        ]
    })

    total_all = await db.npci_circulars.count_documents({})
    already_processed = total_all - total_unprocessed

    logger.info(f"=== NPCI Circular Processing ===")
    logger.info(f"Total circulars: {total_all}")
    logger.info(f"Already processed: {already_processed}")
    logger.info(f"To process: {total_unprocessed}")
    logger.info(f"================================")

    if total_unprocessed == 0:
        logger.info("Nothing to process!")
        return

    # Get all unprocessed circular IDs
    cursor = db.npci_circulars.find(
        {
            "$or": [
                {"processed_at": None},
                {"processed_at": {"$exists": False}},
            ]
        },
        {"_id": 1, "title": 1, "npci_id": 1, "product": 1}
    )

    circulars = []
    async for doc in cursor:
        circulars.append(doc)

    processed_count = 0
    failed_count = 0
    regulation_count = 0

    for idx, circ in enumerate(circulars):
        circ_id = str(circ["_id"])
        title = circ.get("title", "Unknown")[:70]
        product = circ.get("product", "?")
        npci_id = circ.get("npci_id", "?")

        logger.info(f"[{idx+1}/{total_unprocessed}] Processing: [{product}] {title} (npci_id={npci_id})")

        try:
            result = await processing_service.process_circular(circ_id)

            if result.get("success"):
                processed_count += 1
                clauses = result.get("clauses_extracted", 0)
                reg_id = result.get("regulation_id", "N/A")
                if reg_id and reg_id != "N/A":
                    regulation_count += 1
                logger.info(f"  -> OK: {clauses} clauses, regulation_id={reg_id}")
            else:
                failed_count += 1
                logger.error(f"  -> FAILED: {result.get('error', 'Unknown error')}")

        except Exception as e:
            failed_count += 1
            logger.error(f"  -> EXCEPTION: {e}")

        # Rate limiting to avoid overwhelming LLM API
        await asyncio.sleep(0.5)

        # Progress report every 25
        if (idx + 1) % 25 == 0:
            logger.info(f"--- Progress: {idx+1}/{total_unprocessed} | OK: {processed_count} | Failed: {failed_count} | Regulations: {regulation_count} ---")

    logger.info(f"")
    logger.info(f"=== PROCESSING COMPLETE ===")
    logger.info(f"Total processed: {processed_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Regulations created: {regulation_count}")
    logger.info(f"===========================")


if __name__ == "__main__":
    asyncio.run(main())
