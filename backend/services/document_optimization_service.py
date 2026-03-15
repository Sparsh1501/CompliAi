"""
Document Analysis Optimization Service for CompliAI (Task #23)

Optimizes large document analysis (100+ pages) for sub-5-minute processing:
- Parallel page processing with asyncio
- Smart chunking for LLM context windows
- Caching of intermediate results
- Progress streaming via WebSocket
"""

import logging
import asyncio
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Configuration
MAX_CONCURRENT_PAGES = 5
MAX_CHUNK_SIZE = 4000  # chars per chunk for LLM
MAX_CLAUSES_PER_BATCH = 10
PAGE_CACHE_TTL = 3600  # 1 hour cache


class DocumentOptimizationService:
    """Optimizes large document processing for performance."""

    def __init__(self, db=None):
        self.db = db
        self._page_cache = {}  # In-memory cache for page processing results

    async def process_large_document(
        self,
        document_id: str,
        pages: List[Dict[str, Any]],
        process_fn,
        connection_manager=None,
        user_id: str = "",
    ) -> Dict[str, Any]:
        """
        Process a large document with parallel page processing.

        Args:
            document_id: ID of the document
            pages: List of page dicts with 'page_number' and 'text' keys
            process_fn: Async function to process each page/chunk
            connection_manager: WebSocket manager for progress updates

        Returns:
            Aggregated results from all pages
        """
        total_pages = len(pages)
        start_time = datetime.now(timezone.utc)

        # Check cache for already-processed pages
        cache_key = self._compute_document_hash(pages)
        cached = self._page_cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for document {document_id}")
            return cached

        # Smart chunking: group small pages, split large ones
        chunks = self._create_smart_chunks(pages)
        logger.info(f"Document {document_id}: {total_pages} pages -> {len(chunks)} chunks")

        # Process chunks in parallel with concurrency limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)
        results = []
        completed = 0

        async def process_chunk(chunk_idx, chunk):
            nonlocal completed
            async with semaphore:
                try:
                    result = await process_fn(chunk)
                    completed += 1

                    # Send progress update
                    if connection_manager and user_id:
                        progress = round((completed / len(chunks)) * 100)
                        try:
                            await connection_manager.send_personal_message(
                                {"type": "processing_progress", "document_id": document_id,
                                 "progress": progress, "chunk": completed, "total_chunks": len(chunks)},
                                user_id
                            )
                        except Exception:
                            pass

                    return result
                except Exception as e:
                    logger.error(f"Chunk {chunk_idx} processing failed: {e}")
                    return {"error": str(e), "chunk_idx": chunk_idx}

        tasks = [process_chunk(i, chunk) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        all_clauses = []
        errors = []
        for r in results:
            if isinstance(r, Exception):
                errors.append(str(r))
            elif isinstance(r, dict) and "error" in r:
                errors.append(r["error"])
            elif isinstance(r, dict) and "clauses" in r:
                all_clauses.extend(r["clauses"])
            elif isinstance(r, list):
                all_clauses.extend(r)

        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()

        result = {
            "document_id": document_id,
            "total_pages": total_pages,
            "total_chunks": len(chunks),
            "clauses_extracted": len(all_clauses),
            "clauses": all_clauses,
            "errors": errors[:5],  # Limit error reporting
            "processing_time_seconds": round(processing_time, 2),
            "pages_per_second": round(total_pages / max(processing_time, 0.1), 2),
        }

        # Cache the result
        self._page_cache[cache_key] = result
        # Keep cache size bounded
        if len(self._page_cache) > 50:
            oldest_key = next(iter(self._page_cache))
            del self._page_cache[oldest_key]

        return result

    def _create_smart_chunks(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create optimized chunks from pages:
        - Small pages are combined into single chunks
        - Large pages are split into multiple chunks
        """
        chunks = []
        current_chunk = {"pages": [], "text": "", "page_numbers": []}

        for page in pages:
            page_text = page.get("text", "")
            page_num = page.get("page_number", 0)

            if len(page_text) > MAX_CHUNK_SIZE:
                # Flush current chunk if non-empty
                if current_chunk["text"]:
                    chunks.append(current_chunk)
                    current_chunk = {"pages": [], "text": "", "page_numbers": []}

                # Split large page into sub-chunks
                for i in range(0, len(page_text), MAX_CHUNK_SIZE):
                    sub_text = page_text[i:i + MAX_CHUNK_SIZE]
                    chunks.append({
                        "pages": [page],
                        "text": sub_text,
                        "page_numbers": [page_num],
                        "sub_chunk": True,
                    })
            elif len(current_chunk["text"]) + len(page_text) > MAX_CHUNK_SIZE:
                # Current chunk is full, start a new one
                chunks.append(current_chunk)
                current_chunk = {"pages": [page], "text": page_text, "page_numbers": [page_num]}
            else:
                # Add to current chunk
                current_chunk["pages"].append(page)
                current_chunk["text"] += f"\n--- Page {page_num} ---\n" + page_text
                current_chunk["page_numbers"].append(page_num)

        # Don't forget the last chunk
        if current_chunk["text"]:
            chunks.append(current_chunk)

        return chunks

    def _compute_document_hash(self, pages: List[Dict[str, Any]]) -> str:
        """Compute a hash for caching based on document content."""
        content = "".join(p.get("text", "")[:100] for p in pages[:10])
        return hashlib.md5(content.encode()).hexdigest()

    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get document processing performance statistics."""
        if not self.db:
            return {"cache_size": len(self._page_cache)}

        # Get recent processing stats from upload jobs
        pipeline = [
            {"$match": {"status": "completed", "document_type": {"$exists": True}}},
            {"$sort": {"completed_at": -1}},
            {"$limit": 100},
            {"$group": {
                "_id": None,
                "avg_processing_time": {"$avg": "$processing_time_seconds"},
                "total_documents": {"$sum": 1},
                "total_pages": {"$sum": "$total_pages"},
            }}
        ]

        try:
            results = await self.db.upload_jobs.aggregate(pipeline).to_list(length=1)
            stats = results[0] if results else {}
        except Exception:
            stats = {}

        return {
            "cache_size": len(self._page_cache),
            "max_concurrent_pages": MAX_CONCURRENT_PAGES,
            "max_chunk_size": MAX_CHUNK_SIZE,
            "avg_processing_time": round(stats.get("avg_processing_time", 0), 2),
            "total_documents_processed": stats.get("total_documents", 0),
            "total_pages_processed": stats.get("total_pages", 0),
        }

    def clear_cache(self):
        """Clear the processing cache."""
        self._page_cache.clear()
        return {"status": "cache_cleared"}
