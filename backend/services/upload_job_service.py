"""
Upload Job Service - Manages background upload and processing jobs with WebSocket updates.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from bson import ObjectId
from fastapi import WebSocket
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid


def _sanitize_for_json(obj):
    """Recursively convert ObjectId and other non-serializable types to strings."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        logger.info(f"WebSocket connected for user {user_id}")
    
    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send a message to all connections of a specific user."""
        if user_id not in self.active_connections:
            return
        
        disconnected = set()
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(_sanitize_for_json(message))
            except Exception as e:
                logger.warning(f"Failed to send to websocket: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected sockets
        async with self._lock:
            for ws in disconnected:
                self.active_connections[user_id].discard(ws)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected users."""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)


# Global connection manager
connection_manager = ConnectionManager()


class UploadJobService:
    """Service for managing upload jobs with progress tracking."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.jobs_collection = db.upload_jobs
    
    async def create_job(
        self,
        user_id: str,
        organization: str,
        job_type: str,
        file_name: str,
        file_size: int = 0,
        metadata: Dict[str, Any] = None
    ) -> dict:
        """Create a new upload job."""
        job = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "organization": organization,
            "job_type": job_type,
            "status": "pending",
            "file_name": file_name,
            "file_size": file_size,
            "progress": 0,
            "current_step": "Initializing...",
            "total_steps": 5,
            "current_step_number": 0,
            "result_id": None,
            "result_title": None,
            "clauses_extracted": 0,
            "pages_processed": 0,
            "error_message": None,
            "error_details": None,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "completed_at": None
        }
        
        await self.jobs_collection.insert_one(job)
        
        # Notify user of new job
        await self._notify_user(user_id, {
            "type": "job_created",
            "job": self._serialize_job(job)
        })
        
        return job
    
    async def update_progress(
        self,
        job_id: str,
        progress: int,
        current_step: str,
        current_step_number: int = None,
        pages_processed: int = None,
        clauses_extracted: int = None,
        status: str = None
    ):
        """Update job progress and notify via WebSocket."""
        update_data = {
            "progress": progress,
            "current_step": current_step
        }
        
        if current_step_number is not None:
            update_data["current_step_number"] = current_step_number
        if pages_processed is not None:
            update_data["pages_processed"] = pages_processed
        if clauses_extracted is not None:
            update_data["clauses_extracted"] = clauses_extracted
        if status is not None:
            update_data["status"] = status
            if status == "processing":
                update_data["started_at"] = datetime.now(timezone.utc)
        
        result = await self.jobs_collection.find_one_and_update(
            {"id": job_id},
            {"$set": update_data},
            return_document=True
        )
        
        if result:
            await self._notify_user(result["user_id"], {
                "type": "job_progress",
                "job": self._serialize_job(result)
            })
        
        return result
    
    async def complete_job(
        self,
        job_id: str,
        result_id: str,
        result_title: str,
        clauses_extracted: int
    ):
        """Mark job as completed successfully."""
        result = await self.jobs_collection.find_one_and_update(
            {"id": job_id},
            {"$set": {
                "status": "completed",
                "progress": 100,
                "current_step": "Completed!",
                "result_id": result_id,
                "result_title": result_title,
                "clauses_extracted": clauses_extracted,
                "completed_at": datetime.now(timezone.utc)
            }},
            return_document=True
        )
        
        if result:
            await self._notify_user(result["user_id"], {
                "type": "job_completed",
                "job": self._serialize_job(result)
            })
        
        return result
    
    async def fail_job(self, job_id: str, error_message: str, error_details: str = None):
        """Mark job as failed."""
        result = await self.jobs_collection.find_one_and_update(
            {"id": job_id},
            {"$set": {
                "status": "failed",
                "current_step": "Failed",
                "error_message": error_message,
                "error_details": error_details,
                "completed_at": datetime.now(timezone.utc)
            }},
            return_document=True
        )
        
        if result:
            await self._notify_user(result["user_id"], {
                "type": "job_failed",
                "job": self._serialize_job(result)
            })
        
        return result
    
    async def get_job(self, job_id: str) -> Optional[dict]:
        """Get a job by ID."""
        job = await self.jobs_collection.find_one({"id": job_id}, {"_id": 0})
        return job
    
    async def get_user_jobs(
        self,
        user_id: str,
        limit: int = 20,
        include_completed: bool = True
    ) -> List[dict]:
        """Get all jobs for a user."""
        query = {"user_id": user_id}
        if not include_completed:
            query["status"] = {"$nin": ["completed", "failed", "cancelled"]}
        
        cursor = self.jobs_collection.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        jobs = await cursor.to_list(length=limit)
        return [self._serialize_job(job) for job in jobs]
    
    async def get_active_jobs(self, user_id: str) -> List[dict]:
        """Get active (in-progress) jobs for a user."""
        cursor = self.jobs_collection.find(
            {
                "user_id": user_id,
                "status": {"$in": ["pending", "uploading", "processing", "extracting", "analyzing"]}
            },
            {"_id": 0}
        ).sort("created_at", -1)
        
        jobs = await cursor.to_list(length=50)
        return [self._serialize_job(job) for job in jobs]
    
    async def cancel_job(self, job_id: str, user_id: str) -> bool:
        """Cancel a job (if still pending/processing)."""
        result = await self.jobs_collection.update_one(
            {
                "id": job_id,
                "user_id": user_id,
                "status": {"$in": ["pending", "uploading", "processing", "extracting"]}
            },
            {"$set": {
                "status": "cancelled",
                "current_step": "Cancelled by user",
                "completed_at": datetime.now(timezone.utc)
            }}
        )
        
        if result.modified_count > 0:
            job = await self.get_job(job_id)
            if job:
                await self._notify_user(user_id, {
                    "type": "job_cancelled",
                    "job": self._serialize_job(job)
                })
            return True
        return False
    
    async def delete_job(self, job_id: str, user_id: str) -> bool:
        """Delete a job from history."""
        result = await self.jobs_collection.delete_one({
            "id": job_id,
            "user_id": user_id
        })
        return result.deleted_count > 0
    
    async def clear_completed_jobs(self, user_id: str) -> int:
        """Clear all completed/failed jobs for a user."""
        result = await self.jobs_collection.delete_many({
            "user_id": user_id,
            "status": {"$in": ["completed", "failed", "cancelled"]}
        })
        return result.deleted_count
    
    async def _notify_user(self, user_id: str, message: dict):
        """Send notification to user via WebSocket."""
        await connection_manager.send_to_user(user_id, message)
    
    def _serialize_job(self, job: dict) -> dict:
        """Serialize job for JSON response."""
        serialized = dict(job)
        for key in ["created_at", "started_at", "completed_at"]:
            if serialized.get(key) and isinstance(serialized[key], datetime):
                serialized[key] = serialized[key].isoformat()
        return serialized
