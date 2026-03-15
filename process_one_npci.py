"""Process 1 NPCI circular using local LLM."""
import asyncio
import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ["USE_LOCAL_LLM"] = "true"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))
    os.environ["USE_LOCAL_LLM"] = "true"

    mongo_url = os.getenv('MONGODB_URL', os.getenv('MONGO_URL', 'mongodb://localhost:27017'))
    db_name = os.getenv('DB_NAME', 'compliai')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    qdrant_client = None
    try:
        from qdrant_client import QdrantClient
        qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
        qdrant_client = QdrantClient(url=qdrant_url, timeout=30)
        qdrant_client.get_collections()
        logger.info(f"Qdrant connected at {qdrant_url}")
    except Exception as e:
        logger.warning(f"Qdrant not available: {e}")

    from services.npci_processing_service import NPCIProcessingService
    from services.llm_provider import is_using_local_llm, get_llm_provider
    logger.info(f"Using local LLM: {is_using_local_llm()}")
    provider = get_llm_provider()
    logger.info(f"LLM Provider: {provider.get_provider_name()} (model: {getattr(provider, 'model', 'N/A')})")

    svc = NPCIProcessingService(db=db, qdrant_client=qdrant_client)
    await svc.ensure_indexes()

    # Get first unprocessed circular
    circ = await db.npci_circulars.find_one({
        "$or": [{"processed_at": None}, {"processed_at": {"$exists": False}}]
    })
    if not circ:
        logger.info("No unprocessed circulars found!")
        return

    circ_id = str(circ["_id"])
    title = circ.get('title', '')[:80]
    product = circ.get('product', '?')
    npci_id = circ.get('npci_id', '?')
    logger.info(f"Processing: [{product}] {title} (npci_id={npci_id})")

    result = await svc.process_circular(circ_id)

    print()
    if result.get("success"):
        logger.info(f"SUCCESS!")
        logger.info(f"  Clauses extracted: {result.get('clauses_extracted', 0)}")
        logger.info(f"  Text length: {result.get('text_length', 0)}")
        logger.info(f"  Regulation ID: {result.get('regulation_id', 'N/A')}")
        logger.info(f"  Regulation clauses: {result.get('regulation_clauses', 0)}")
        logger.info(f"  Embeddings stored: {result.get('embeddings_stored', 0)}")
    else:
        logger.error(f"FAILED: {result.get('error', 'Unknown')}")

    print("\n=== FULL RESULT ===")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
