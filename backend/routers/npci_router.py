"""
NPCI Circular Scraping API Router
Feature #217: API endpoints for NPCI circular management.
Feature #220: Scheduled scraping with new circular detection.

Endpoints:
- POST /api/npci/scrape - Trigger scraping for a specific product and year (or all)
- GET /api/npci/scrape/status - Get current scraping job status
- GET /api/npci/circulars - List all scraped circulars with pagination, search, filter
- GET /api/npci/circulars/{id} - Get single circular with extracted clauses
- POST /api/npci/circulars/{id}/process - Trigger LLM clause extraction for a circular
- POST /api/npci/circulars/process-all - Batch process all unprocessed circulars
- GET /api/npci/products - List all available NPCI products with circular counts
- GET /api/npci/stats - Get scraping statistics
- GET /api/npci/schedule - Get schedule configuration and status
- PUT /api/npci/schedule - Update schedule configuration
- POST /api/npci/schedule/toggle - Enable/disable scheduled scraping
- POST /api/npci/schedule/trigger - Manually trigger scheduled scrape
- GET /api/npci/schedule/status - Get scheduler runtime status
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

npci_router = APIRouter(prefix="/npci", tags=["NPCI Circulars"])

# Track scraping job status in-memory (per-process)
_scrape_jobs = {}

# Track in-flight Process-All batches so the UI can cancel them mid-run.
# Key: batch_id (uuid str). Value: dict with keys
#   - cancel_requested (bool)
#   - started_at (iso str)
#   - total (int)
#   - processed (int)  - updated by the batch loop
#   - failed (int)     - updated by the batch loop
#   - cancelled_at (iso str | None)
# Single-process only; for multi-worker deployments swap for Redis or Mongo.
_active_process_all_batches: Dict[str, Dict[str, Any]] = {}


def _register_batch(batch_id: str, total: int) -> None:
    _active_process_all_batches[batch_id] = {
        "batch_id": batch_id,
        "cancel_requested": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "processed": 0,
        "failed": 0,
        "cancelled_at": None,
    }


def _unregister_batch(batch_id: str) -> None:
    _active_process_all_batches.pop(batch_id, None)


def _is_batch_cancelled(batch_id: str) -> bool:
    return bool(_active_process_all_batches.get(batch_id, {}).get("cancel_requested"))


def _get_server_module():
    """Get the server module (handles __main__ vs server module name)."""
    import sys
    # When run as 'python server.py', the module is __main__
    main = sys.modules.get('__main__')
    if main and hasattr(main, 'npci_scraper'):
        return main
    # When run as 'uvicorn server:app', the module is 'server'
    import server
    return server


def _get_dependencies():
    """Get server dependencies (npci_scraper, db, get_current_user) from server module."""
    srv = _get_server_module()
    return srv.npci_scraper, srv.db, srv.get_current_user


# -------------------------------------------------------------------
# POST /api/npci/scrape - Trigger scraping with SSE progress streaming
# -------------------------------------------------------------------
@npci_router.post("/scrape")
async def trigger_scrape(
    product: Optional[str] = Query(None, description="NPCI product to scrape (or omit for all)"),
    year: Optional[str] = Query(None, description="Year to scrape (e.g., 2025)"),
    years: Optional[str] = Query(None, description="Comma-separated years (e.g., 2024,2025)"),
):
    """
    Trigger NPCI circular scraping with SSE progress streaming.
    Returns a Server-Sent Events stream with progress updates.
    """
    npci_scraper, db, get_current_user = _get_dependencies()
    from services.npci_scraper_service import NPCI_PRODUCTS

    async def generate_events():
        job_id = f"scrape_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        _scrape_jobs[job_id] = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "product": product or "all",
            "year": year,
            "progress": [],
        }

        try:
            yield f"data: {json.dumps({'event': 'start', 'job_id': job_id, 'message': 'Scraping started...'})}\n\n"

            async def progress_callback(message):
                _scrape_jobs[job_id]["progress"].append(message)
                # Non-blocking: don't await here, just format the event

            # Parse years list
            year_list = None
            if years:
                year_list = [y.strip() for y in years.split(",") if y.strip()]
            elif year:
                year_list = [year]

            if product:
                # Scrape specific product
                if product not in NPCI_PRODUCTS:
                    yield f"data: {json.dumps({'event': 'error', 'message': f'Unknown product: {product}. Valid: {NPCI_PRODUCTS}'})}\n\n"
                    return

                yield f"data: {json.dumps({'event': 'progress', 'message': f'Scraping {product}...'})}\n\n"

                stats = await npci_scraper.scrape_all_circulars(
                    product=product,
                    years=year_list,
                    progress_callback=progress_callback,
                )

                yield f"data: {json.dumps({'event': 'product_complete', 'product': product, 'stats': stats})}\n\n"
            else:
                # Scrape all products
                yield f"data: {json.dumps({'event': 'progress', 'message': 'Scraping all NPCI products...'})}\n\n"

                overall_stats = {"products": {}, "total": 0, "new": 0, "duplicates": 0, "errors": 0}

                for prod in NPCI_PRODUCTS:
                    yield f"data: {json.dumps({'event': 'progress', 'message': f'Scraping {prod}...'})}\n\n"

                    try:
                        prod_stats = await npci_scraper.scrape_all_circulars(
                            product=prod,
                            years=year_list,
                            progress_callback=progress_callback,
                        )
                        overall_stats["products"][prod] = prod_stats
                        overall_stats["total"] += prod_stats.get("total", 0)
                        overall_stats["new"] += prod_stats.get("new", 0)
                        overall_stats["duplicates"] += prod_stats.get("duplicates", 0)
                        overall_stats["errors"] += prod_stats.get("errors", 0)

                        yield f"data: {json.dumps({'event': 'product_complete', 'product': prod, 'stats': prod_stats})}\n\n"
                    except Exception as e:
                        logger.error(f"Error scraping {prod}: {e}")
                        yield f"data: {json.dumps({'event': 'product_error', 'product': prod, 'error': str(e)})}\n\n"

                stats = overall_stats

            _scrape_jobs[job_id]["status"] = "completed"
            _scrape_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            _scrape_jobs[job_id]["result"] = stats

            yield f"data: {json.dumps({'event': 'complete', 'job_id': job_id, 'stats': stats, 'message': 'Scraping completed successfully'})}\n\n"

        except Exception as e:
            logger.error(f"Error during scraping: {e}", exc_info=True)
            _scrape_jobs[job_id]["status"] = "failed"
            _scrape_jobs[job_id]["error"] = str(e)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# -------------------------------------------------------------------
# GET /api/npci/scrape/status - Get current scraping job status
# -------------------------------------------------------------------
@npci_router.get("/scrape/status")
async def get_scrape_status():
    """Get status of recent scraping jobs."""
    # Return last 10 jobs
    sorted_jobs = sorted(
        _scrape_jobs.items(),
        key=lambda x: x[1].get("started_at", ""),
        reverse=True,
    )[:10]

    return {
        "jobs": [
            {"job_id": jid, **jdata}
            for jid, jdata in sorted_jobs
        ],
        "active_count": sum(1 for _, j in _scrape_jobs.items() if j.get("status") == "running"),
    }


# -------------------------------------------------------------------
# GET /api/npci/circulars - List circulars with pagination and filters
# -------------------------------------------------------------------
@npci_router.get("/circulars")
async def list_circulars(
    product: Optional[str] = Query(None, description="Filter by product"),
    year: Optional[str] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in title"),
    processed: Optional[bool] = Query(None, description="Legacy: equivalent to status=completed"),
    status: Optional[str] = Query(
        None,
        description="Filter by processing status: 'completed', 'pending', 'failed', 'processing' (or omit for all)",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """List all scraped NPCI circulars with pagination, search, and filters."""
    npci_scraper, db, get_current_user = _get_dependencies()

    result = await npci_scraper.list_circulars(
        product=product,
        year=year,
        search=search,
        processed_only=processed if processed else False,
        status=status,
        page=page,
        size=size,
    )

    return result


# -------------------------------------------------------------------
# GET /api/npci/circulars/{circular_id} - Get single circular
# -------------------------------------------------------------------
@npci_router.get("/circulars/{circular_id}")
async def get_circular(circular_id: str):
    """Get a single circular with its extracted clauses."""
    npci_scraper, db, get_current_user = _get_dependencies()

    circular = await npci_scraper.get_circular_by_id(circular_id)
    if not circular:
        raise HTTPException(status_code=404, detail="Circular not found")

    return circular


# -------------------------------------------------------------------
# POST /api/npci/circulars/{circular_id}/process - LLM clause extraction
# Feature #216: Enhanced processing with NPCIProcessingService
# Now uses background job + upload_job_service for progress tracking
# -------------------------------------------------------------------
@npci_router.post("/circulars/{circular_id}/process")
async def process_circular(
    circular_id: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Re-process even if already completed"),
):
    """
    Trigger LLM clause extraction for a specific circular.
    Runs as a background job with real-time progress tracking via upload_job_service,
    matching the regulation upload pipeline experience.

    By default, refuses to re-process circulars that are already `completed`
    or currently `processing` (prevents wasted Claude credits and duplicate
    regulation rows from impatient repeated clicks). Pass `?force=true` to
    deliberately re-run a completed circular.
    """
    npci_scraper, db, get_current_user = _get_dependencies()
    srv = _get_server_module()

    circular = await npci_scraper.get_circular_by_id(circular_id)
    if not circular:
        raise HTTPException(status_code=404, detail="Circular not found")

    current_status = circular.get("processing_status")
    if current_status == "processing":
        return {
            "success": False,
            "message": "Already processing — wait for it to finish before retrying.",
            "circular_id": circular_id,
            "status": current_status,
        }
    if current_status == "completed" and not force:
        return {
            "success": False,
            "message": "Already processed. Pass force=true to re-process.",
            "circular_id": circular_id,
            "status": current_status,
            "clause_count": circular.get("clause_count", 0),
        }

    try:
        upload_job_service = srv.upload_job_service

        # Mark the circular as processing immediately so a second click can't
        # race past the status check above before the background task starts.
        from bson import ObjectId
        await npci_scraper.collection.update_one(
            {"_id": ObjectId(circular_id)},
            {"$set": {"processing_status": "processing"}, "$unset": {"processing_error": ""}},
        )

        # Create a tracking job (same as regulation upload)
        job = await upload_job_service.create_job(
            user_id="system",
            organization="system",
            job_type="regulation",
            file_name=circular.get("title", f"NPCI Circular {circular_id}"),
            file_size=0,
            metadata={
                "source": "npci_circular",
                "circular_id": circular_id,
                "product": circular.get("product", ""),
                "npci_id": circular.get("npci_id", ""),
            }
        )

        # Run processing in background
        background_tasks.add_task(
            _process_npci_circular_background,
            job['id'],
            circular_id,
        )

        return {
            "success": True,
            "message": "Processing started",
            "job_id": job['id'],
            "circular_id": circular_id,
            "status": "processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting NPCI circular processing {circular_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


async def _process_npci_circular_background(job_id: str, circular_id: str):
    """Background task that processes an NPCI circular with upload_job_service progress updates."""
    srv = _get_server_module()
    upload_job_service = srv.upload_job_service

    try:
        # Step 1: Starting
        await upload_job_service.update_progress(
            job_id, 10, "Downloading NPCI circular PDF...", 1, status="uploading"
        )

        processing_service = _get_processing_service()

        # Get circular details
        from bson import ObjectId
        circular = await processing_service.circulars_collection.find_one(
            {"_id": ObjectId(circular_id)}
        )
        if not circular:
            await upload_job_service.fail_job(job_id, "Circular not found", "NotFoundError")
            return

        # Step 2: Download PDF
        if not circular.get("pdf_downloaded") and circular.get("pdf_url"):
            pdf_path = await processing_service._download_pdf(
                circular["pdf_url"], circular.get("npci_id")
            )
            if pdf_path:
                circular["local_pdf_path"] = pdf_path
                circular["pdf_downloaded"] = True
                await processing_service.circulars_collection.update_one(
                    {"_id": ObjectId(circular_id)},
                    {"$set": {"pdf_downloaded": True, "local_pdf_path": pdf_path}}
                )

        await upload_job_service.update_progress(
            job_id, 20, "Extracting text from PDF...", 2, status="processing"
        )

        # Step 3: Extract text
        raw_text = ""
        if circular.get("local_pdf_path"):
            from services.npci_processing_service import extract_text_with_vision_fallback
            raw_text = await extract_text_with_vision_fallback(
                circular["local_pdf_path"], db=processing_service.db
            )
        if not raw_text:
            raw_text = circular.get("title", "No text available")

        await upload_job_service.update_progress(
            job_id, 30, f"Extracted {len(raw_text)} characters. AI analyzing impact...", 3, status="analyzing"
        )

        # Step 4: Parse title + NPCI-specific clause extraction
        from services.npci_processing_service import parse_circular_title
        title_info = parse_circular_title(circular.get("title", ""))

        # NPCI-specific clause extraction
        npci_clauses = await processing_service._extract_clauses_with_llm(
            raw_text, circular.get("title", ""),
            circular.get("product", ""), circular.get("year", "")
        )

        # Store NPCI-specific clauses
        await processing_service._store_clauses(npci_clauses, circular_id, circular)

        await upload_job_service.update_progress(
            job_id, 45, f"Extracted {len(npci_clauses)} NPCI clauses. Running full regulation analysis...", 4, status="extracting"
        )

        # Step 5: Convert to regulation (full pipeline like regulation upload)
        # This runs ClauseExtractionService + LLM impact analysis + saves to regulations collection
        await upload_job_service.update_progress(
            job_id, 50, "AI extracting regulatory clauses...", 4, status="extracting"
        )

        reg_result = await processing_service._convert_circular_to_regulation(
            circular=circular,
            circular_id=circular_id,
            raw_text=raw_text,
            title_info=title_info,
        )

        await upload_job_service.update_progress(
            job_id, 85, "Saving to database...", 6
        )

        # Step 6: Update circular status (and clear any stale error from a
        # previous failed run so the UI doesn't keep showing "Failed" hints
        # next to a successfully-completed circular).
        await processing_service.circulars_collection.update_one(
            {"_id": ObjectId(circular_id)},
            {
                "$set": {
                    "raw_text": raw_text,
                    "clauses": npci_clauses,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "processing_status": "completed",
                    "parsed_title": title_info,
                    "clause_count": len(npci_clauses),
                },
                "$unset": {"processing_error": ""},
            },
        )

        # Complete the job
        regulation_id = reg_result.get("regulation_id", circular_id)
        reg_clauses_count = reg_result.get("clauses_count", len(npci_clauses))

        await upload_job_service.complete_job(
            job_id=job_id,
            result_id=regulation_id,
            result_title=circular.get("title", f"NPCI Circular {circular_id}"),
            clauses_extracted=reg_clauses_count
        )

        logger.info(f"[NPCI PROCESS] Completed job {job_id}: circular {circular_id} → regulation {regulation_id}")

    except Exception as e:
        logger.error(f"[NPCI PROCESS] Failed job {job_id}: {str(e)}", exc_info=True)
        await upload_job_service.fail_job(job_id, str(e), str(e.__class__.__name__))
        # Also mark the circular row as failed so stats stay honest
        # (do NOT set processed_at — only success sets that).
        try:
            from bson import ObjectId
            processing_service = _get_processing_service()
            await processing_service.circulars_collection.update_one(
                {"_id": ObjectId(circular_id)},
                {"$set": {
                    "processing_status": "failed",
                    "processing_error": str(e)[:500],
                }}
            )
        except Exception as inner:
            logger.error(f"[NPCI PROCESS] Could not update circular {circular_id} as failed: {inner}")


# -------------------------------------------------------------------
# POST /api/npci/circulars/process-all - Batch process with SSE
#
# IMPORTANT: This now uses the REAL NPCIProcessingService pipeline
# (PDF text extraction + LLM clause extraction + Qdrant embeddings +
# auto-conversion to Regulation). A circular is only marked
# `processing_status="completed"` (and `processed_at=now`) when LLM
# extraction actually succeeds; failures are recorded as
# `processing_status="failed"` so stats stay honest. The previous
# placeholder logic that hard-coded a single fake clause and flipped
# `processed_at` without ever calling an LLM was removed because it
# made the "Processed" count meaningless.
# -------------------------------------------------------------------
def _build_batch_query(scope: str) -> Dict[str, Any]:
    """Build the MongoDB query for a Process-All batch.

    Scopes:
        "all"     — pending + failed (everything that isn't completed/processing)
        "pending" — only never-attempted-or-marked-pending
        "failed"  — only previously-failed (Retry-Failed button)
    """
    s = (scope or "all").strip().lower()
    if s == "failed":
        return {"processing_status": "failed"}
    if s == "pending":
        return {
            "$or": [
                {"processing_status": {"$exists": False}},
                {"processing_status": {"$nin": ["completed", "failed", "processing"]}},
            ]
        }
    # default: everything that needs processing (pending + failed)
    return {
        "$or": [
            {"processing_status": {"$exists": False}},
            {"processing_status": {"$nin": ["completed", "processing"]}},
        ]
    }


@npci_router.post("/circulars/process-all")
async def process_all_circulars(
    request: Request,
    status: Optional[str] = Query(
        None,
        description="Scope: 'all' (default — pending+failed), 'pending', or 'failed' (retry-failed-only)",
    ),
):
    """
    Batch process circulars matching ``status`` (default: pending + failed)
    with SSE progress streaming. Uses the real NPCIProcessingService pipeline.

    The first SSE event (``event: start``) includes a ``batch_id`` UUID. Pass
    that ``batch_id`` to ``POST /api/npci/circulars/process-all/cancel`` to
    gracefully halt the batch between iterations (the in-flight circular
    finishes its LLM call so we don't waste tokens on a half-extracted
    clause set).

    The endpoint also stops automatically if the SSE client disconnects, so
    closing the browser tab is enough to halt processing.
    """
    npci_scraper, db, get_current_user = _get_dependencies()
    processing_service = _get_processing_service()

    batch_id = uuid.uuid4().hex
    scope = (status or "all").strip().lower()
    if scope not in ("all", "pending", "failed"):
        scope = "all"

    async def generate_events():
        try:
            cursor = db.npci_circulars.find(_build_batch_query(scope))
            unprocessed = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                unprocessed.append(doc)

            total = len(unprocessed)
            _register_batch(batch_id, total)
            scope_label = {
                "failed": f"Retrying {total} previously-failed circular(s)...",
                "pending": f"Processing {total} pending circular(s)...",
                "all": f"Processing {total} circulars with AI...",
            }.get(scope, f"Processing {total} circulars with AI...")
            yield f"data: {json.dumps({'event': 'start', 'batch_id': batch_id, 'scope': scope, 'total': total, 'message': scope_label})}\n\n"

            processed = 0
            failed = 0

            for doc in unprocessed:
                # Cancel-checks BEFORE pulling the next circular, so an
                # in-flight LLM call always finishes (avoids partial state +
                # wasted Claude tokens), but the next one is skipped.
                if _is_batch_cancelled(batch_id):
                    logger.info(f"[NPCI BATCH] Cancel requested for batch {batch_id}; stopping after {processed + failed}/{total}.")
                    break
                if await request.is_disconnected():
                    logger.info(f"[NPCI BATCH] Client disconnected for batch {batch_id}; stopping after {processed + failed}/{total}.")
                    break

                circular_id = doc["_id"]
                try:
                    result = await processing_service.process_circular(circular_id)

                    if result.get("success"):
                        processed += 1
                        msg = (
                            f"Processed {processed}/{total} - "
                            f"{result.get('clauses_extracted', 0)} clauses extracted"
                        )
                        yield f"data: {json.dumps({'event': 'progress', 'batch_id': batch_id, 'processed': processed, 'failed': failed, 'total': total, 'current': doc.get('title', '')[:100], 'message': msg})}\n\n"
                    else:
                        failed += 1
                        err = result.get("error", "Unknown error")
                        logger.warning(f"Failed to process circular {circular_id}: {err}")
                        yield f"data: {json.dumps({'event': 'item_error', 'batch_id': batch_id, 'circular_id': circular_id, 'error': err, 'processed': processed, 'failed': failed, 'total': total})}\n\n"

                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing circular {circular_id}: {e}", exc_info=True)
                    yield f"data: {json.dumps({'event': 'item_error', 'batch_id': batch_id, 'circular_id': circular_id, 'error': str(e), 'processed': processed, 'failed': failed, 'total': total})}\n\n"

                # Update tracker for any clients polling /process-all/active.
                state = _active_process_all_batches.get(batch_id)
                if state is not None:
                    state["processed"] = processed
                    state["failed"] = failed

                # Small delay to be nice to the LLM provider / rate limits
                await asyncio.sleep(0.3)

            cancelled = _is_batch_cancelled(batch_id)
            remaining = total - processed - failed
            if cancelled:
                msg = (
                    f"Cancelled by user: {processed} succeeded, {failed} failed, "
                    f"{remaining} skipped of {total} total."
                )
                yield f"data: {json.dumps({'event': 'cancelled', 'batch_id': batch_id, 'processed': processed, 'failed': failed, 'remaining': remaining, 'total': total, 'message': msg})}\n\n"
            else:
                msg = (
                    f"Batch processing complete: {processed} succeeded with real AI extraction, "
                    f"{failed} failed (likely LLM unavailable or PDF unreadable)"
                )
                yield f"data: {json.dumps({'event': 'complete', 'batch_id': batch_id, 'processed': processed, 'failed': failed, 'total': total, 'message': msg})}\n\n"

        except Exception as e:
            logger.error(f"Batch processing error: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'batch_id': batch_id, 'message': str(e)})}\n\n"
        finally:
            _unregister_batch(batch_id)

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# -------------------------------------------------------------------
# POST /api/npci/circulars/process-all/cancel - Cancel a running batch
# GET  /api/npci/circulars/process-all/active - List in-flight batches
# -------------------------------------------------------------------
@npci_router.get("/circulars/process-all/active")
async def list_active_process_all_batches():
    """List currently-running Process-All batches (one entry per batch_id).

    Useful for the frontend to render a "cancel" button when reloading the
    page mid-batch (since the SSE stream is connection-bound).
    """
    return {
        "active": list(_active_process_all_batches.values()),
        "count": len(_active_process_all_batches),
    }


@npci_router.post("/circulars/process-all/cancel")
async def cancel_process_all_batch(
    batch_id: Optional[str] = Query(None, description="Batch id to cancel; omit to cancel ALL active batches"),
):
    """Request graceful cancellation of a running Process-All batch.

    The currently-in-flight circular finishes (so its LLM call isn't wasted),
    then the loop exits and emits an `event: cancelled` SSE event.
    """
    if not _active_process_all_batches:
        return {"cancelled": [], "message": "No active Process-All batches."}

    targets = [batch_id] if batch_id else list(_active_process_all_batches.keys())
    cancelled = []
    for bid in targets:
        state = _active_process_all_batches.get(bid)
        if state is None:
            continue
        state["cancel_requested"] = True
        state["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        cancelled.append(bid)

    if not cancelled and batch_id:
        raise HTTPException(status_code=404, detail=f"No active batch with id={batch_id}")

    return {
        "cancelled": cancelled,
        "message": f"Cancellation requested for {len(cancelled)} batch(es). Currently-running circular will finish first.",
    }


# -------------------------------------------------------------------
# GET /api/npci/products - List products with circular counts
# -------------------------------------------------------------------
@npci_router.get("/products")
async def list_products():
    """List all NPCI products with their circular counts."""
    npci_scraper, db, get_current_user = _get_dependencies()
    from services.npci_scraper_service import NPCI_PRODUCTS, NPCI_PRODUCT_LABELS

    stats = await npci_scraper.get_product_stats()

    return {
        "products": stats,
        "all_products": [
            {"slug": p, "label": NPCI_PRODUCT_LABELS.get(p, p)}
            for p in NPCI_PRODUCTS
        ],
    }


# -------------------------------------------------------------------
# GET /api/npci/stats - Overall scraping statistics
# -------------------------------------------------------------------
@npci_router.get("/stats")
async def get_stats():
    """Get overall NPCI scraping statistics."""
    npci_scraper, db, get_current_user = _get_dependencies()

    stats = await npci_scraper.get_overall_stats()
    return stats


# ===================================================================
# Feature #220: Scheduled NPCI Circular Scraping Endpoints
# ===================================================================

def _get_scheduler():
    """Get the NPCI scheduler service instance from server module."""
    srv = _get_server_module()
    return srv.npci_scheduler


def _get_processing_service():
    """Get the NPCI processing service instance from server module."""
    srv = _get_server_module()
    return srv.npci_processing_service


def _get_device_binding_advisor():
    """Get the Device Binding Advisor service instance from server module."""
    srv = _get_server_module()
    return getattr(srv, "device_binding_advisor", None)


# ===================================================================
# Demo Helper #1: Required Evidences Rollup (Point #2 of demo)
# ===================================================================

@npci_router.get("/circulars/{circular_id}/evidences")
async def get_circular_evidence_rollup(circular_id: str):
    """
    Aggregate every "what evidence is required" data point for a single
    NPCI circular into one structured payload. Powers the demo's
    "Required Evidences" view on the circular detail page.
    """
    advisor = _get_device_binding_advisor()
    if advisor is None:
        raise HTTPException(status_code=503, detail="Device binding advisor not initialized")

    result = await advisor.aggregate_evidences_for_circular(circular_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ===================================================================
# Demo Helper #2: Device Binding & RASP Advisor (Point #3 of demo)
# ===================================================================

@npci_router.get("/device-binding-advisor")
async def get_device_binding_advisor_report(
    organization: str = Query("system", description="Organization scope for coverage data"),
    include_summary: bool = Query(True, description="Whether to LLM-generate an executive summary"),
):
    """
    Return a structured device-binding & RASP precaution advisor.
    Combines NPCI's curated requirements with extracted clauses from
    scraped circulars and (when available) live coverage data from
    the most recent gap analysis.
    """
    advisor = _get_device_binding_advisor()
    if advisor is None:
        raise HTTPException(status_code=503, detail="Device binding advisor not initialized")

    report = await advisor.get_advisor_report(
        organization=organization,
        include_summary=include_summary,
    )
    return report


# -------------------------------------------------------------------
# GET /api/npci/schedule - Get schedule configuration
# -------------------------------------------------------------------
@npci_router.get("/schedule")
async def get_schedule_config():
    """Get the current NPCI scraping schedule configuration."""
    scheduler = _get_scheduler()
    config = await scheduler.get_schedule_config()
    status = await scheduler.get_schedule_status()
    return {
        "config": config,
        "status": status,
    }


# -------------------------------------------------------------------
# PUT /api/npci/schedule - Update schedule configuration
# -------------------------------------------------------------------
@npci_router.put("/schedule")
async def update_schedule_config(body: dict):
    """
    Update the NPCI scraping schedule configuration.

    Body fields:
    - enabled (bool): Enable/disable scheduled scraping
    - interval_hours (int): Hours between scrapes (1-168)
    - auto_process (bool): Auto-process new circulars with LLM
    - auto_create_tasks (bool): Auto-create review tasks for new circulars
    - products (list[str]): Products to scrape (empty = all)
    """
    scheduler = _get_scheduler()
    config = await scheduler.update_config(body)
    status = await scheduler.get_schedule_status()
    return {
        "config": config,
        "status": status,
        "message": "Schedule configuration updated",
    }


# -------------------------------------------------------------------
# POST /api/npci/schedule/toggle - Toggle scheduler on/off
# -------------------------------------------------------------------
@npci_router.post("/schedule/toggle")
async def toggle_schedule(body: dict):
    """
    Enable or disable the NPCI scheduled scraper.

    Body: { "enabled": true/false }
    """
    enabled = body.get("enabled", False)
    scheduler = _get_scheduler()
    config = await scheduler.toggle(enabled)
    status = await scheduler.get_schedule_status()
    return {
        "config": config,
        "status": status,
        "message": f"NPCI scheduler {'enabled' if enabled else 'disabled'}",
    }


# -------------------------------------------------------------------
# POST /api/npci/schedule/trigger - Manual trigger
# -------------------------------------------------------------------
@npci_router.post("/schedule/trigger")
async def trigger_scheduled_scrape():
    """
    Manually trigger an immediate scheduled scrape run.
    Runs the same logic as the automated scheduler.
    """
    scheduler = _get_scheduler()
    result = await scheduler.trigger_now()
    return {
        "success": True,
        "result": result,
        "message": f"Scheduled scrape completed: {result.get('new_circulars', 0)} new circulars found",
    }


# -------------------------------------------------------------------
# GET /api/npci/schedule/status - Get scheduler runtime status
# -------------------------------------------------------------------
@npci_router.get("/schedule/status")
async def get_schedule_status():
    """Get the current scheduler runtime status."""
    scheduler = _get_scheduler()
    status = await scheduler.get_schedule_status()
    return status


# ===================================================================
# Feature #216: NPCI Clause Analysis Endpoints
# ===================================================================

# -------------------------------------------------------------------
# GET /api/npci/clauses/stats - Clause extraction statistics
# -------------------------------------------------------------------
@npci_router.get("/clauses/stats")
async def get_clause_stats():
    """Get statistics about extracted NPCI circular clauses."""
    processing_service = _get_processing_service()
    stats = await processing_service.get_clause_stats()
    return stats


# -------------------------------------------------------------------
# GET /api/npci/circulars/{circular_id}/clauses - Get clauses for a circular
# -------------------------------------------------------------------
@npci_router.get("/circulars/{circular_id}/clauses")
async def get_circular_clauses(circular_id: str):
    """Get all extracted clauses for a specific circular."""
    processing_service = _get_processing_service()
    clauses = await processing_service.get_clauses_for_circular(circular_id)
    return {"circular_id": circular_id, "clauses": clauses, "count": len(clauses)}


# -------------------------------------------------------------------
# POST /api/npci/circulars/batch-process - Batch process with NPCIProcessingService
# -------------------------------------------------------------------
@npci_router.post("/circulars/batch-process")
async def batch_process_circulars():
    """
    Batch process all unprocessed circulars using NPCIProcessingService.
    Uses the full pipeline: PDF extraction + LLM clause analysis + Qdrant embeddings.
    Returns SSE stream with progress.
    """
    processing_service = _get_processing_service()

    async def generate_events():
        try:
            yield f"data: {json.dumps({'event': 'start', 'message': 'Starting enhanced batch processing...'})}\n\n"

            async def progress_callback(message):
                pass  # Progress tracked via result

            result = await processing_service.batch_process_all(progress_callback=progress_callback)

            msg = f"Batch processing complete: {result.get('processed', 0)} processed, {result.get('failed', 0)} failed"
            yield f"data: {json.dumps({'event': 'complete', 'result': result, 'message': msg})}\n\n"

        except Exception as e:
            logger.error(f"Batch processing error: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# -------------------------------------------------------------------
# POST /api/npci/circulars/convert-to-regulations - Convert already-processed
# circulars to regulation records (backfill for pre-auto-conversion circulars)
# -------------------------------------------------------------------
@npci_router.post("/circulars/convert-to-regulations")
async def convert_circulars_to_regulations():
    """
    Convert all already-processed NPCI circulars to regulation records.
    This is a backfill endpoint for circulars that were processed
    before the auto-conversion feature was added.
    Returns SSE progress stream.
    """
    npci_scraper, db, get_current_user = _get_dependencies()
    processing_service = _get_processing_service()

    async def generate_events():
        try:
            # Find real-LLM-completed circulars that don't have a regulation record yet
            processed_cursor = db.npci_circulars.find({
                "processing_status": "completed",
            })
            circulars = []
            async for doc in processed_cursor:
                npci_id = str(doc.get("npci_id", ""))
                # Check if regulation already exists
                existing_reg = await db.regulations.find_one({
                    "source": "npci_circular",
                    "source_circular_id": npci_id,
                })
                if not existing_reg:
                    doc["_id"] = str(doc["_id"])
                    circulars.append(doc)

            total = len(circulars)
            yield f"data: {json.dumps({'event': 'start', 'total': total, 'message': f'Converting {total} circulars to regulations...'})}\n\n"

            converted = 0
            errors = 0

            for doc in circulars:
                try:
                    raw_text = doc.get("raw_text", doc.get("title", ""))
                    from services.npci_processing_service import parse_circular_title
                    title_info = parse_circular_title(doc.get("title", ""))

                    result = await processing_service._convert_circular_to_regulation(
                        circular=doc,
                        circular_id=doc["_id"],
                        raw_text=raw_text,
                        title_info=title_info,
                    )
                    converted += 1
                    yield f"data: {json.dumps({'event': 'progress', 'converted': converted, 'total': total, 'current': doc.get('title', '')[:80], 'regulation_id': result.get('regulation_id')})}\n\n"
                except Exception as e:
                    errors += 1
                    logger.error(f"Failed to convert circular {doc.get('npci_id')}: {e}")
                    yield f"data: {json.dumps({'event': 'item_error', 'npci_id': doc.get('npci_id'), 'error': str(e)})}\n\n"

                await asyncio.sleep(0.5)  # Rate limiting for LLM calls

            yield f"data: {json.dumps({'event': 'complete', 'converted': converted, 'errors': errors, 'total': total, 'message': f'Conversion complete: {converted} converted, {errors} errors'})}\n\n"

        except Exception as e:
            logger.error(f"Conversion to regulation error: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
