# Task #3: Implement Batch Document Upload for PA/PG Compliance

## Implementation Specification

---

## 1. OBJECTIVE

Add batch document upload capability to the existing upload pipeline. Users can select multiple files (PDFs, Word docs) simultaneously, each processed through the existing 7-step pipeline with per-file progress tracking. Frontend shows real-time progress for all files via WebSocket.

---

## 2. ARCHITECTURE OVERVIEW

```
┌───────────────────────────────────┐
│  Frontend: Batch Upload UI         │
│  (Drag & Drop zone, file queue)   │
└──────────────┬────────────────────┘
               │ POST /api/regulations/batch-upload
               │ (multipart: files[] + metadata[])
               ▼
┌───────────────────────────────────┐
│  Backend: Batch Upload Endpoint    │
│  server.py (NEW endpoint)          │
├───────────────────────────────────┤
│  1. Validate all files             │
│  2. Create batch job (parent)      │
│  3. Create child jobs per file     │
│  4. Queue background processing    │
│  5. Return batch_id + job_ids      │
└──────────────┬────────────────────┘
               │
               ▼
┌───────────────────────────────────┐
│  Existing Pipeline (per file)      │
│  process_regulation_upload_bg()    │
│  OR process_policy_upload_bg()     │
├───────────────────────────────────┤
│  OCR → Analysis → Clause Extract   │
│  → Enrich → Store → Embed          │
└──────────────┬────────────────────┘
               │
               ▼ WebSocket per-file progress
┌───────────────────────────────────┐
│  Frontend: Batch Progress Panel    │
│  Per-file progress bars            │
│  Overall batch progress            │
│  Cancel individual/all             │
└───────────────────────────────────┘
```

---

## 3. FILES TO CREATE

### 3.1 `backend/services/batch_upload_service.py` (NEW)

**Purpose:** Manage batch upload orchestration, progress aggregation, concurrency limits.

```python
"""
Batch Upload Service for CompliAI

Handles multi-file upload orchestration:
- Creates parent batch job + child jobs per file
- Manages concurrency (max 3 concurrent file processing)
- Aggregates progress across all files
- Supports cancel-all and cancel-individual
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timezone
import uuid


class BatchUploadService:
    """
    Orchestrates batch file uploads with concurrency control.

    Uses a semaphore to limit concurrent processing to MAX_CONCURRENT files,
    preventing API rate limits and memory exhaustion.
    """

    MAX_CONCURRENT = 3  # Max files processed simultaneously

    def __init__(self, db, upload_job_service, connection_manager):
        self.db = db
        self.upload_job_service = upload_job_service
        self.connection_manager = connection_manager

    async def create_batch(
        self,
        files: List[dict],       # [{filename, size, content_type}]
        upload_type: str,         # "regulation" | "policy" | "evidence"
        metadata: List[dict],     # Per-file metadata (title, regulatory_body, etc.)
        user_id: str,
        organization: str
    ) -> dict:
        """
        Create a batch upload with parent job + child jobs.

        Returns:
            {
                "batch_id": "uuid",
                "total_files": 5,
                "jobs": [
                    {"job_id": "uuid", "file_name": "doc1.pdf", "status": "pending"},
                    ...
                ]
            }
        """

    async def process_batch(
        self,
        batch_id: str,
        files_data: List[tuple],  # [(file_bytes, filename, metadata)]
        upload_type: str,
        user_id: str,
        organization: str
    ):
        """
        Process all files in batch with concurrency control.
        Uses asyncio.Semaphore(MAX_CONCURRENT) to limit parallel processing.

        For each file:
          1. Acquire semaphore
          2. Save file to disk
          3. Call existing process_*_upload_background()
          4. Release semaphore
          5. Update batch progress
        """

    async def get_batch_status(self, batch_id: str) -> dict:
        """
        Get aggregated status of batch:
        {
            "batch_id": "...",
            "status": "processing" | "completed" | "partial_failure" | "failed",
            "total_files": 5,
            "completed": 3,
            "failed": 1,
            "in_progress": 1,
            "overall_progress": 72,  # percentage
            "jobs": [...]
        }
        """

    async def cancel_batch(self, batch_id: str) -> dict:
        """Cancel all pending/in-progress jobs in the batch."""

    async def cancel_batch_file(self, batch_id: str, job_id: str) -> dict:
        """Cancel a single file within the batch."""

    async def _update_batch_progress(self, batch_id: str):
        """
        Recalculate batch-level progress from child jobs.
        Broadcast via WebSocket: { type: "batch_progress", batch_id, progress, ... }
        """

    async def _process_single_file(
        self,
        semaphore: asyncio.Semaphore,
        batch_id: str,
        job_id: str,
        file_data: tuple,
        upload_type: str,
        user_id: str,
        organization: str
    ):
        """
        Process a single file within the batch.
        Wraps existing process_regulation_upload_background or
        process_policy_upload_background with batch-aware progress tracking.
        """
```

---

## 4. FILES TO MODIFY

### 4.1 `backend/server.py` — New Batch Upload Endpoints

**Add 4 new endpoints:**

#### Endpoint 1: Batch Upload (Regulations)

```python
@api_router.post("/regulations/batch-upload")
async def batch_upload_regulations(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    batch_metadata: str = Form(...),  # JSON array of per-file metadata
    current_user: dict = Depends(check_not_auditor)
):
    """
    Upload multiple regulation documents at once.

    Request: multipart/form-data
      - files[]: Multiple PDF/DOCX/TXT files (max 10 per batch)
      - batch_metadata: JSON string with array of per-file metadata
        [
          {"title": "PA Master Direction", "regulatory_body": "RBI", "circular_number": "..."},
          {"title": "...", ...}
        ]

    Response:
      {
        "batch_id": "uuid",
        "total_files": 5,
        "jobs": [{"job_id": "...", "file_name": "...", "status": "pending"}],
        "message": "Batch upload started. Track progress via WebSocket."
      }

    Validation:
      - Max 10 files per batch
      - Each file max 50MB
      - Only PDF/DOCX/TXT
      - Metadata array length must match files count
    """
```

#### Endpoint 2: Batch Upload (Policies)

```python
@api_router.post("/policies/batch-upload")
async def batch_upload_policies(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    batch_metadata: str = Form(...),
    current_user: dict = Depends(check_not_auditor)
):
    """Same structure as regulation batch upload but for policies."""
```

#### Endpoint 3: Batch Status

```python
@api_router.get("/batch-uploads/{batch_id}")
async def get_batch_status(
    batch_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get real-time status of a batch upload."""
```

#### Endpoint 4: Cancel Batch

```python
@api_router.post("/batch-uploads/{batch_id}/cancel")
async def cancel_batch(
    batch_id: str,
    current_user: dict = Depends(check_not_auditor)
):
    """Cancel all pending files in a batch."""
```

**Location in server.py:** Add after existing regulation upload endpoints (~line 3530).

---

### 4.2 `backend/models.py` — New Models

```python
class BatchUploadJob(BaseModel):
    """Parent batch job tracking multiple file uploads."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    batch_type: str  # "regulation" | "policy" | "evidence"
    total_files: int
    completed_files: int = 0
    failed_files: int = 0
    status: str = "pending"  # pending, processing, completed, partial_failure, failed, cancelled
    overall_progress: float = 0.0
    child_job_ids: List[str] = []
    user_id: str
    organization: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
```

---

### 4.3 `backend/services/upload_job_service.py` — WebSocket Batch Events

**Add batch-specific WebSocket message types:**

```python
# New message types to add to notify_connected_users():
# {
#     "type": "batch_created",
#     "batch_id": "...",
#     "total_files": 5,
#     "jobs": [...]
# }
# {
#     "type": "batch_progress",
#     "batch_id": "...",
#     "overall_progress": 45,
#     "completed": 2,
#     "failed": 0,
#     "in_progress": 1,
#     "pending": 2
# }
# {
#     "type": "batch_completed",
#     "batch_id": "...",
#     "status": "completed" | "partial_failure",
#     "results": [{"job_id": "...", "status": "completed", "result_id": "..."}]
# }
```

---

### 4.4 `frontend/src/lib/api.js` — New API Methods

```javascript
// Add to regulationsApi:
regulationsApi.batchUpload = (files, metadataArray, onUploadProgress) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('batch_metadata', JSON.stringify(metadataArray));
    return api.post('/regulations/batch-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600000,  // 10 min for batch
        onUploadProgress
    });
};

// Add to policiesApi:
policiesApi.batchUpload = (files, metadataArray, onUploadProgress) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('batch_metadata', JSON.stringify(metadataArray));
    return api.post('/policies/batch-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600000,
        onUploadProgress
    });
};

// New batch API:
export const batchUploadApi = {
    getStatus: (batchId) => api.get(`/batch-uploads/${batchId}`),
    cancel: (batchId) => api.post(`/batch-uploads/${batchId}/cancel`),
};
```

---

### 4.5 `frontend/src/context/UploadContext.js` — Batch State Management

**Add batch tracking to the existing upload context:**

```javascript
// Add to UploadContext state:
const [batchJobs, setBatchJobs] = useState({});
// Structure: { batchId: { status, totalFiles, completed, failed, progress, jobs: [...] } }

// Add WebSocket handler for batch events:
// case "batch_created": ...
// case "batch_progress": ...
// case "batch_completed": ...

// Add methods:
// startBatchUpload(files, metadataArray, type)
// cancelBatch(batchId)
// getBatchProgress(batchId)
```

---

### 4.6 Frontend: Batch Upload UI Component (NEW)

**Create: `frontend/src/components/BatchUploadDialog.jsx`**

```
┌─────────────────────────────────────────────────┐
│  Batch Upload                              [X]   │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │   Drop files here or click to browse      │   │
│  │   (PDF, DOCX, TXT — max 10 files)        │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  Selected Files:                                 │
│  ┌──────────────────────────────────────────┐   │
│  │ 📄 PA_Master_Direction.pdf  [4.2 MB]  [x] │   │
│  │    Title: [PA Master Direction 2025    ]   │   │
│  │    Type:  [RBI ▼]  Circular: [____]       │   │
│  ├──────────────────────────────────────────┤   │
│  │ 📄 Merchant_KYC_Policy.pdf  [1.8 MB]  [x] │   │
│  │    Title: [Merchant KYC Policy         ]   │   │
│  │    Type:  [RBI ▼]  Circular: [____]       │   │
│  ├──────────────────────────────────────────┤   │
│  │ 📄 Settlement_SOP.docx     [0.9 MB]  [x] │   │
│  │    Title: [Settlement Operations SOP   ]   │   │
│  │    Type:  [RBI ▼]  Circular: [____]       │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  Upload Type: ○ Regulations  ○ Policies          │
│                                                  │
│           [Cancel]  [Upload All (3 files)]       │
└─────────────────────────────────────────────────┘
```

**After upload starts, shows progress:**

```
┌─────────────────────────────────────────────────┐
│  Batch Upload Progress             [Cancel All]  │
├─────────────────────────────────────────────────┤
│                                                  │
│  Overall: ████████████░░░░░░░░  62%  (2/3)      │
│                                                  │
│  ✅ PA_Master_Direction.pdf     — Completed      │
│     32 clauses extracted | 12 PA/PG requirements │
│                                                  │
│  ⏳ Merchant_KYC_Policy.pdf     — Extracting...  │
│     ████████████████░░░░  85%                    │
│                                                  │
│  ⏸ Settlement_SOP.docx          — Queued         │
│                                                  │
└─────────────────────────────────────────────────┘
```

**Props:**
```javascript
<BatchUploadDialog
    open={showBatchUpload}
    onClose={() => setShowBatchUpload(false)}
    uploadType="regulation"  // or "policy"
    onComplete={(results) => { /* refresh list */ }}
/>
```

**Key features:**
- Multi-file drag & drop
- Per-file metadata input (title, regulatory_body)
- Auto-detect title from filename (reuse `parse_regulation_filename`)
- Per-file progress bars
- Overall batch progress
- Cancel individual files
- Cancel entire batch
- Completion summary with links to created resources

---

### 4.7 `frontend/src/pages/Regulations.js` — Add "Batch Upload" Button

**Add a button next to the existing "Upload Regulation" button:**

```jsx
<Button onClick={() => setShowBatchUpload(true)} variant="outline">
    <Upload className="h-4 w-4 mr-2" />
    Batch Upload
</Button>

<BatchUploadDialog
    open={showBatchUpload}
    onClose={() => setShowBatchUpload(false)}
    uploadType="regulation"
    onComplete={() => loadRegulations()}
/>
```

### 4.8 `frontend/src/pages/Policies.js` — Same addition

---

## 5. MONGODB SCHEMA

### New Collection: `batch_uploads`

```javascript
{
    "_id": ObjectId,
    "id": "uuid",
    "batch_type": "regulation" | "policy",
    "status": "pending" | "processing" | "completed" | "partial_failure" | "failed" | "cancelled",
    "total_files": 5,
    "completed_files": 3,
    "failed_files": 1,
    "cancelled_files": 0,
    "overall_progress": 72.5,
    "child_job_ids": ["job-uuid-1", "job-uuid-2", ...],
    "results": [
        {
            "job_id": "job-uuid-1",
            "file_name": "PA_Direction.pdf",
            "status": "completed",
            "result_id": "regulation-uuid",  // Created regulation ID
            "clauses_extracted": 32,
            "processing_time_seconds": 45
        },
        {
            "job_id": "job-uuid-2",
            "file_name": "corrupted.pdf",
            "status": "failed",
            "error": "OCR extraction failed: no text detected"
        }
    ],
    "user_id": "user-uuid",
    "organization": "Default Org",
    "created_at": ISODate,
    "completed_at": ISODate
}
```

**Index:** `user_id`, `organization`, `created_at`

---

## 6. CONCURRENCY & PERFORMANCE

### Concurrency Control

```python
# In BatchUploadService.process_batch():
semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)  # 3 concurrent

tasks = []
for file_data, job_id in zip(files_data, job_ids):
    task = asyncio.create_task(
        self._process_single_file(
            semaphore, batch_id, job_id, file_data,
            upload_type, user_id, organization
        )
    )
    tasks.append(task)

# Wait for all, but don't fail the batch if one file fails
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Rate Limiting Considerations

- **Anthropic API:** Max 3 concurrent calls (semaphore handles this)
- **Qdrant writes:** No concurrency issue (writes are sequential per collection)
- **MongoDB writes:** No issue (Motor handles connection pooling)
- **Memory:** Each PDF-to-image conversion uses ~50-200MB. With 3 concurrent, max ~600MB

### Expected Performance

| Files | Est. Time | Notes |
|-------|-----------|-------|
| 1 file (100 pages) | 3-5 min | Existing pipeline |
| 3 files | 5-8 min | Parallel processing |
| 5 files | 8-12 min | 3 concurrent + 2 queued |
| 10 files | 15-25 min | Max batch size |

---

## 7. VALIDATION RULES

```python
# Batch-level validation
MAX_BATCH_SIZE = 10           # Max files per batch
MAX_TOTAL_BATCH_BYTES = 200 * 1024 * 1024  # 200MB total batch limit

# Per-file validation (same as existing)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain"
}
```

---

## 8. ERROR HANDLING

| Scenario | Behavior |
|----------|----------|
| One file fails OCR | Mark that job as failed, continue others. Batch status = "partial_failure" |
| All files fail | Batch status = "failed" |
| User cancels batch | Cancel pending jobs, let in-progress finish or cancel if possible |
| Metadata count mismatch | Return 400 before processing starts |
| Duplicate filenames | Allow (each gets unique UUID) |
| Total batch exceeds 200MB | Return 413 before processing starts |
| API rate limit hit | Exponential backoff per file, retry up to 3 times |

---

## 9. WEBSOCKET MESSAGE FLOW

```
1. User uploads 3 files
2. Backend creates batch:
   → WS: { type: "batch_created", batch_id, total_files: 3, jobs: [...] }

3. File 1 starts processing:
   → WS: { type: "job_progress", job_id: "1", progress: 10, step: "Extracting text..." }
   → WS: { type: "batch_progress", batch_id, overall_progress: 3, completed: 0 }

4. File 2 starts processing (concurrent):
   → WS: { type: "job_progress", job_id: "2", progress: 10, step: "Extracting text..." }

5. File 1 completes:
   → WS: { type: "job_completed", job_id: "1", result_id: "reg-uuid-1" }
   → WS: { type: "batch_progress", batch_id, overall_progress: 33, completed: 1 }

6. File 3 starts (was queued):
   → WS: { type: "job_progress", job_id: "3", progress: 10, step: "..." }

7. All complete:
   → WS: { type: "batch_completed", batch_id, status: "completed", results: [...] }
```

---

## 10. INTEGRATION POINTS

### With Existing Code

| Component | Integration |
|-----------|-------------|
| `process_regulation_upload_background()` (server.py:3168) | Called per-file by batch service |
| `process_policy_upload_background()` (server.py:1476) | Called per-file by batch service |
| `UploadJobService` (upload_job_service.py) | Creates child jobs, tracks per-file progress |
| `ConnectionManager` (upload_job_service.py:30) | Broadcasts batch events via WebSocket |
| `DocumentService` (document_service.py) | File saving + OCR (no changes needed) |
| `ClauseExtractionService` (clause_extraction_service.py) | Clause extraction (no changes needed) |
| `VectorService` (vector_service.py) | Embedding storage (no changes needed) |
| `UploadContext.js` | Add batch state tracking |
| `UploadProgress.js` | Extend to show batch progress panel |

### With Task #1 (PA/PG Parser)

When batch-uploading regulations, if any file is detected as a PA/PG regulation, the PA/PG enrichment pipeline (from Task #1) runs automatically as part of `process_regulation_upload_background()`.

---

## 11. TESTING CHECKLIST

- [ ] Upload 3 regulation PDFs simultaneously — all process successfully
- [ ] Upload 10 files (max batch) — verify concurrency limit of 3
- [ ] Upload 1 valid + 1 corrupted file — verify partial_failure status
- [ ] Cancel batch mid-processing — verify pending files cancelled, in-progress completes
- [ ] Verify WebSocket receives batch_created, batch_progress, batch_completed events
- [ ] Verify frontend shows per-file progress bars
- [ ] Verify overall batch progress percentage is accurate
- [ ] Upload with mismatched metadata count — verify 400 error
- [ ] Upload batch exceeding 200MB — verify 413 error
- [ ] Upload 3 files including a PA/PG regulation — verify PA/PG enrichment runs
- [ ] Verify all created regulations/policies appear in list after batch completes
