"""
Batch Upload Service for CompliAI

Handles multi-file upload orchestration:
- Creates parent batch job + child jobs per file
- Manages concurrency (max 3 concurrent file processing)
- Aggregates progress across all files
- Supports cancel-all and cancel-individual
"""

import asyncio
import uuid
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 3
MAX_FILES_PER_BATCH = 10
MAX_TOTAL_SIZE_MB = 200


class BatchUploadService:
    """Orchestrates batch file uploads with concurrency control."""

    def __init__(self, db=None, connection_manager=None):
        self.db = db
        self.connection_manager = connection_manager
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._active_batches: Dict[str, Dict] = {}

    async def create_batch(
        self,
        files_metadata: List[Dict[str, Any]],
        upload_type: str,
        user_id: str,
        organization: str
    ) -> Dict[str, Any]:
        """
        Create a batch upload job with child jobs per file.

        Args:
            files_metadata: List of {file_name, file_size, content_type}
            upload_type: "policy" or "regulation"
            user_id: Uploading user
            organization: User's organization

        Returns:
            Batch job dict with batch_id and child job_ids
        """
        if len(files_metadata) > MAX_FILES_PER_BATCH:
            raise ValueError(f"Maximum {MAX_FILES_PER_BATCH} files per batch")

        total_size = sum(f.get("file_size", 0) for f in files_metadata)
        if total_size > MAX_TOTAL_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Total file size exceeds {MAX_TOTAL_SIZE_MB}MB limit")

        now = datetime.now(timezone.utc).isoformat()
        batch_id = str(uuid.uuid4())

        child_jobs = []
        for fm in files_metadata:
            child_id = str(uuid.uuid4())
            child_job = {
                "id": child_id,
                "batch_id": batch_id,
                "file_name": fm.get("file_name", "unknown"),
                "file_size": fm.get("file_size", 0),
                "status": "pending",
                "progress": 0,
                "current_step": "Queued",
                "result_id": None,
                "error_message": None,
                "created_at": now,
                "started_at": None,
                "completed_at": None,
            }
            child_jobs.append(child_job)

        batch_job = {
            "id": batch_id,
            "upload_type": upload_type,
            "user_id": user_id,
            "organization": organization,
            "status": "pending",
            "total_files": len(files_metadata),
            "completed_files": 0,
            "failed_files": 0,
            "progress": 0,
            "child_jobs": child_jobs,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
        }

        await self.db.batch_uploads.insert_one(batch_job)
        self._active_batches[batch_id] = {"cancelled": False}

        logger.info(f"Created batch {batch_id} with {len(child_jobs)} files")
        return {
            "batch_id": batch_id,
            "total_files": len(files_metadata),
            "job_ids": [j["id"] for j in child_jobs],
        }

    async def process_batch(
        self,
        batch_id: str,
        file_processors: List[Callable],
    ):
        """
        Process all files in a batch with concurrency control.

        Args:
            batch_id: The batch to process
            file_processors: List of async callables, one per file
        """
        now = datetime.now(timezone.utc).isoformat()
        await self.db.batch_uploads.update_one(
            {"id": batch_id},
            {"$set": {"status": "processing", "started_at": now}}
        )

        batch = await self.db.batch_uploads.find_one({"id": batch_id}, {"_id": 0})
        if not batch:
            return

        child_jobs = batch.get("child_jobs", [])

        async def process_with_semaphore(idx, processor, child_job):
            async with self._semaphore:
                if self._active_batches.get(batch_id, {}).get("cancelled"):
                    return

                child_id = child_job["id"]
                try:
                    # Update child status
                    await self._update_child_status(batch_id, child_id, "processing", 0, "Processing...")

                    # Run the file processor
                    result = await processor()

                    await self._update_child_status(
                        batch_id, child_id, "completed", 100, "Complete",
                        result_id=result.get("id") if isinstance(result, dict) else None
                    )
                except Exception as e:
                    logger.error(f"Batch file processing failed: {e}")
                    await self._update_child_status(
                        batch_id, child_id, "failed", 0, "Failed",
                        error=str(e)
                    )

                # Update batch progress
                await self._update_batch_progress(batch_id)

        tasks = []
        for idx, (processor, child_job) in enumerate(zip(file_processors, child_jobs)):
            tasks.append(process_with_semaphore(idx, processor, child_job))

        await asyncio.gather(*tasks, return_exceptions=True)

        # Finalize batch
        await self._finalize_batch(batch_id)

    async def _update_child_status(
        self,
        batch_id: str,
        child_id: str,
        status: str,
        progress: int,
        step: str,
        result_id: str = None,
        error: str = None
    ):
        """Update a child job's status."""
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "child_jobs.$[elem].status": status,
            "child_jobs.$[elem].progress": progress,
            "child_jobs.$[elem].current_step": step,
        }
        if result_id:
            update["child_jobs.$[elem].result_id"] = result_id
        if error:
            update["child_jobs.$[elem].error_message"] = error
        if status == "processing":
            update["child_jobs.$[elem].started_at"] = now
        if status in ("completed", "failed"):
            update["child_jobs.$[elem].completed_at"] = now

        await self.db.batch_uploads.update_one(
            {"id": batch_id},
            {"$set": update},
            array_filters=[{"elem.id": child_id}]
        )

        # Send WebSocket update
        if self.connection_manager:
            batch = await self.db.batch_uploads.find_one({"id": batch_id}, {"_id": 0})
            if batch:
                try:
                    await self.connection_manager.send_personal_message(
                        {
                            "type": "batch_progress",
                            "batch_id": batch_id,
                            "child_id": child_id,
                            "status": status,
                            "progress": progress,
                            "step": step,
                        },
                        batch.get("user_id", "")
                    )
                except Exception:
                    pass

    async def _update_batch_progress(self, batch_id: str):
        """Recalculate and update batch-level progress."""
        batch = await self.db.batch_uploads.find_one({"id": batch_id}, {"_id": 0})
        if not batch:
            return

        children = batch.get("child_jobs", [])
        total = len(children)
        if total == 0:
            return

        completed = len([c for c in children if c.get("status") == "completed"])
        failed = len([c for c in children if c.get("status") == "failed"])
        total_progress = sum(c.get("progress", 0) for c in children)
        avg_progress = int(total_progress / total)

        await self.db.batch_uploads.update_one(
            {"id": batch_id},
            {"$set": {
                "completed_files": completed,
                "failed_files": failed,
                "progress": avg_progress,
            }}
        )

    async def _finalize_batch(self, batch_id: str):
        """Mark batch as completed/failed."""
        batch = await self.db.batch_uploads.find_one({"id": batch_id}, {"_id": 0})
        if not batch:
            return

        children = batch.get("child_jobs", [])
        all_done = all(c.get("status") in ("completed", "failed") for c in children)
        any_failed = any(c.get("status") == "failed" for c in children)
        all_failed = all(c.get("status") == "failed" for c in children)

        now = datetime.now(timezone.utc).isoformat()
        if all_done:
            status = "failed" if all_failed else ("completed_with_errors" if any_failed else "completed")
            await self.db.batch_uploads.update_one(
                {"id": batch_id},
                {"$set": {"status": status, "completed_at": now, "progress": 100}}
            )

        self._active_batches.pop(batch_id, None)

    async def cancel_batch(self, batch_id: str) -> bool:
        """Cancel all pending files in a batch."""
        if batch_id in self._active_batches:
            self._active_batches[batch_id]["cancelled"] = True

        now = datetime.now(timezone.utc).isoformat()
        await self.db.batch_uploads.update_one(
            {"id": batch_id},
            {"$set": {"status": "cancelled", "completed_at": now}}
        )
        return True

    async def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get batch job status with all child statuses."""
        batch = await self.db.batch_uploads.find_one({"id": batch_id}, {"_id": 0})
        return batch

    async def get_batch_history(
        self,
        user_id: str,
        organization: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get batch upload history for a user."""
        cursor = self.db.batch_uploads.find(
            {"user_id": user_id, "organization": organization},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
