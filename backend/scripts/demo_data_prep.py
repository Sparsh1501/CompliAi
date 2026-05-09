"""
One-shot demo data prep script.

This script primes the system for the four-point demo:

  1. Scrape NPCI UPI circulars (priority years: 2023, 2024, 2025) and the
     "others" bucket (where security circulars often land).
  2. Process every newly scraped (and any already-pending / failed) circular
     with the LLM clause-extraction + auto-conversion-to-Regulation pipeline.
  3. Seed the comprehensive Mobile App Security & Device Binding policy so
     gap analysis returns a realistic mix of compliant / partial / missing.
  4. Print a summary: number of circulars, processed, regulations created,
     plus a recommended demo path.

Usage (run from the backend directory)::

    python scripts/demo_data_prep.py             # dry-run plan
    python scripts/demo_data_prep.py --apply     # actually run

Tips:
  - Set ANTHROPIC_API_KEY before running --apply.
  - Set DEMO_PRODUCTS=upi,others or similar to limit scope (default: upi only).
  - Set DEMO_YEARS=2024,2025 to limit years (default: 2023,2024,2025).
  - Add --skip-scrape to use only what's already in the DB.
  - Add --skip-process to skip LLM processing.
  - Add --skip-policy-seed to skip the policy seeding step.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List

# Allow running both as `python scripts/demo_data_prep.py` from backend/ and
# as `python -m scripts.demo_data_prep`.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prime CompliAI for the four-point demo.")
    p.add_argument("--apply", action="store_true", help="Actually perform the actions (default is dry-run)")
    p.add_argument("--skip-scrape", action="store_true", help="Don't scrape; use already-stored circulars")
    p.add_argument("--skip-process", action="store_true", help="Don't run LLM processing")
    p.add_argument("--skip-policy-seed", action="store_true", help="Don't seed the demo Mobile App Security policy")
    p.add_argument(
        "--products",
        default=os.environ.get("DEMO_PRODUCTS", "upi"),
        help="Comma-separated NPCI products to scrape. Default: upi",
    )
    p.add_argument(
        "--years",
        default=os.environ.get("DEMO_YEARS", "2023,2024,2025"),
        help="Comma-separated years to scrape per product. Default: 2023,2024,2025",
    )
    p.add_argument("--limit-process", type=int, default=int(os.environ.get("DEMO_PROCESS_LIMIT", "12")),
                   help="Max number of circulars to process in this run (LLM cost guard). Default: 12")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _connect():
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "compli-ai")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    return client, db


async def _do_scrape(db, products: List[str], years: List[str]) -> dict:
    from services.npci_scraper_service import NPCIScraper
    scraper = NPCIScraper(db=db)
    await scraper.ensure_indexes()

    overall = {"products": {}, "total": 0, "new": 0, "duplicates": 0, "errors": 0}
    for product in products:
        try:
            print(f"  Scraping product={product} years={','.join(years)} ...")
            stats = await scraper.scrape_all_circulars(
                product=product,
                years=years,
                progress_callback=None,
            )
            overall["products"][product] = stats
            overall["total"] += stats.get("total", 0)
            overall["new"] += stats.get("new", 0)
            overall["duplicates"] += stats.get("duplicates", 0)
            overall["errors"] += stats.get("errors", 0)
            print(f"    Done: total={stats.get('total', 0)}, new={stats.get('new', 0)}, "
                  f"duplicates={stats.get('duplicates', 0)}, errors={stats.get('errors', 0)}")
        except Exception as e:
            print(f"    ERROR scraping {product}: {e}")
            overall["products"][product] = {"error": str(e)}
    return overall


async def _do_process(db, qdrant_client, limit: int) -> dict:
    """Run the real NPCIProcessingService on up to `limit` unprocessed circulars."""
    from services.npci_processing_service import NPCIProcessingService

    svc = NPCIProcessingService(db=db, qdrant_client=qdrant_client)
    await svc.ensure_indexes()

    cursor = db.npci_circulars.find({
        "$or": [
            {"processing_status": {"$exists": False}},
            {"processing_status": {"$nin": ["completed", "processing"]}},
        ],
    }).limit(limit)
    candidates = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        candidates.append(doc)

    print(f"  Will process up to {len(candidates)} circular(s) (limit={limit}).")

    processed = 0
    failed = 0
    for idx, doc in enumerate(candidates, start=1):
        title = (doc.get("title") or "")[:80]
        print(f"  [{idx}/{len(candidates)}] {title} ...")
        try:
            result = await svc.process_circular(doc["_id"])
            if result.get("success"):
                processed += 1
                print(f"      OK - extracted {result.get('clauses_extracted', 0)} clauses, "
                      f"regulation_id={result.get('regulation_id', 'n/a')}")
            else:
                failed += 1
                print(f"      FAILED - {result.get('error', 'unknown error')}")
        except Exception as e:
            failed += 1
            print(f"      EXCEPTION - {e}")
    return {"attempted": len(candidates), "processed": processed, "failed": failed}


async def _do_policy_seed(db) -> dict:
    """Seed the demo Mobile App Security & Device Binding policy."""
    # Re-use the standalone seeder so we keep the same content in one place.
    sys.path.insert(0, str(ROOT_DIR))
    from seed_demo_mobile_security_policy import _build_policy, POLICY_TITLE, _store_clauses_in_qdrant
    from datetime import datetime, timezone

    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")

    existing = await db.policies.find_one({"title": POLICY_TITLE})
    if existing:
        print(f"  Policy '{POLICY_TITLE}' already exists. id={existing.get('id')}")
        # Pre-seed Qdrant in case it was missed last time
        await _store_clauses_in_qdrant(existing, qdrant_url)
        return {"existed": True, "policy_id": existing.get("id")}

    policy = _build_policy(datetime.now(timezone.utc))
    await db.policies.insert_one(policy)
    print(f"  Inserted policy id={policy['id']} with {len(policy['clauses'])} clauses.")
    await _store_clauses_in_qdrant(policy, qdrant_url)
    return {"existed": False, "policy_id": policy["id"]}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(args: argparse.Namespace):
    products = [p.strip() for p in args.products.split(",") if p.strip()]
    years = [y.strip() for y in args.years.split(",") if y.strip()]

    print("=" * 78)
    print("  CompliAI - Demo Data Prep")
    print("=" * 78)
    print(f"  Mode:        {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  Products:    {products}")
    print(f"  Years:       {years}")
    print(f"  Skip scrape: {args.skip_scrape}")
    print(f"  Skip process:{args.skip_process}")
    print(f"  Skip policy: {args.skip_policy_seed}")
    print(f"  Process cap: {args.limit_process}")
    print()

    if not args.apply:
        print("Re-run with --apply to actually execute. Showing the plan:\n")
        if not args.skip_scrape:
            print(f"  1. Would scrape NPCI circulars: products={products}, years={years}")
        if not args.skip_process:
            print(f"  2. Would process up to {args.limit_process} unprocessed circulars with the LLM")
        if not args.skip_policy_seed:
            print("  3. Would insert demo Mobile App Security & Device Binding policy")
        return

    client, db = await _connect()

    # Optional: Qdrant client for embedding storage during processing
    qdrant_client = None
    try:
        from qdrant_client import QdrantClient
        qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        qdrant_client = QdrantClient(url=qdrant_url, timeout=10)
        print(f"  Qdrant connected at {qdrant_url}")
    except Exception as e:
        print(f"  Qdrant unavailable ({e}); embeddings will be skipped.")

    summary = {}

    try:
        if not args.skip_scrape:
            print("\n[Step 1] Scraping NPCI circulars...")
            summary["scrape"] = await _do_scrape(db, products, years)

        if not args.skip_process:
            print("\n[Step 2] Processing scraped circulars with LLM...")
            summary["process"] = await _do_process(db, qdrant_client, args.limit_process)

        if not args.skip_policy_seed:
            print("\n[Step 3] Seeding demo Mobile App Security policy...")
            summary["policy"] = await _do_policy_seed(db)

        # Final state snapshot
        print("\n[Final] Database state snapshot:")
        total_circulars = await db.npci_circulars.count_documents({})
        completed = await db.npci_circulars.count_documents({"processing_status": "completed"})
        failed = await db.npci_circulars.count_documents({"processing_status": "failed"})
        npci_regulations = await db.regulations.count_documents({"source": "npci_circular"})
        policies = await db.policies.count_documents({})
        print(f"  Total NPCI circulars in DB:           {total_circulars}")
        print(f"  Completed (LLM-extracted):            {completed}")
        print(f"  Failed:                               {failed}")
        print(f"  NPCI circulars promoted to regulations:{npci_regulations}")
        print(f"  Total policies in DB:                 {policies}")

        print("\nRecommended demo path:")
        print("  - Open frontend → NPCI Circulars → click any 'AI Processed' UPI circular")
        print("    related to security / device binding / fraud → scroll to 'Required Evidences for Compliance'.")
        print("  - Open Device Binding Advisor (sidebar) → review structured RASP precautions.")
        print("  - Open Gap Analysis → policy = 'Mobile App Security & Device Binding Policy v3.0 (Demo)'")
        print("    + regulation = a NPCI device-binding/UPI security circular → Run Deep Analysis.")
        print("  - Open Chat → ask 'What device binding precautions does NPCI require for UPI apps?'")

    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
