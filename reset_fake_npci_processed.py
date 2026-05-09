"""
One-shot data migration: reset NPCI circulars that were marked "processed"
by legacy placeholder code paths (the old POST /api/npci/circulars/process-all
and scheduler _auto_process_circulars).

A circular is considered fake-processed if:
- processed_at is set, AND
- processing_status is NOT "completed" (i.e. real LLM extraction never finished)

For every such circular this script:
- Clears processed_at, processing_status, processing_error
- Clears raw_text (was just the title)
- Clears clauses (was a single hard-coded placeholder)
- Clears clause_count and parsed_title

Run:
    python reset_fake_npci_processed.py            # dry run (default)
    python reset_fake_npci_processed.py --apply    # actually update
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))


async def main(apply: bool):
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

    mongo_url = os.getenv('MONGO_URL') or os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
    db_name = os.getenv('DB_NAME', 'compli-ai')

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    coll = db.npci_circulars

    fake_filter = {
        "processed_at": {"$ne": None, "$exists": True},
        "processing_status": {"$ne": "completed"},
    }

    total = await coll.count_documents({})
    real_completed = await coll.count_documents({"processing_status": "completed"})
    fake = await coll.count_documents(fake_filter)

    print(f"=== NPCI Circular Cleanup (db={db_name}) ===")
    print(f"Total circulars:                 {total}")
    print(f"Real completed (processing_status=completed): {real_completed}")
    print(f"Fake-processed (to reset):       {fake}")
    print()

    if fake == 0:
        print("Nothing to do. Database is already clean.")
        return

    print("Sample of 5 to be reset:")
    cursor = coll.find(fake_filter).limit(5)
    async for doc in cursor:
        title = (doc.get("title") or "")[:80]
        print(f"  - npci_id={doc.get('npci_id')}  product={doc.get('product')}  title={title}")
    print()

    if not apply:
        print("DRY RUN. Re-run with --apply to actually reset these rows.")
        return

    result = await coll.update_many(
        fake_filter,
        {
            "$unset": {
                "processed_at": "",
                "processing_status": "",
                "processing_error": "",
                "raw_text": "",
                "clauses": "",
                "clause_count": "",
                "parsed_title": "",
            }
        }
    )
    print(f"Updated {result.modified_count} circulars (matched {result.matched_count}).")

    # Verify
    remaining_fake = await coll.count_documents(fake_filter)
    new_total = await coll.count_documents({})
    new_real_completed = await coll.count_documents({"processing_status": "completed"})
    new_pending = new_total - new_real_completed - await coll.count_documents({"processing_status": "failed"})
    print(f"\nAfter cleanup:")
    print(f"  Total: {new_total}")
    print(f"  Real completed: {new_real_completed}")
    print(f"  Pending (will show as 'Pending' in UI): {new_pending}")
    print(f"  Remaining fake: {remaining_fake}")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry run)")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
