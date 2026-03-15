import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['compli-ai']
    
    print("=== LATEST UPLOAD JOBS ===")
    jobs = await db.upload_jobs.find().sort('created_at', -1).limit(3).to_list(3)
    for j in jobs:
        job_id = str(j.get("job_id", "?"))[:20]
        status = j.get("status")
        doc_type = j.get("document_type")
        progress = j.get("progress")
        error = j.get("error_message", "none")
        print(f"Job: {job_id}  Status: {status}  Type: {doc_type}  Progress: {progress}%")
        if error and error != "none":
            print(f"  Error: {error}")
        print(f"  Created: {j.get('created_at')}  Updated: {j.get('updated_at')}")
        print()
    
    print("=== LATEST POLICIES ===")
    policies = await db.policies.find().sort('created_at', -1).limit(3).to_list(3)
    for p in policies:
        clauses = p.get('clauses', [])
        title = str(p.get("title", "?"))[:50]
        status = p.get("status")
        print(f"Policy: {title}  Status: {status}  Clauses: {len(clauses)}")
        print(f"  Created: {p.get('created_at')}")
        if clauses:
            print(f"  Sample clause categories: {[c.get('subject_category','?') for c in clauses[:5]]}")
        print()
    
    client.close()

asyncio.run(check())
