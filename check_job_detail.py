import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['compli-ai']
    
    # Get the latest processing job with ALL fields
    job = await db.upload_jobs.find_one({"status": "processing"}, sort=[("created_at", -1)])
    if job:
        print("=== PROCESSING JOB DETAILS ===")
        for key, val in job.items():
            if key == '_id':
                continue
            val_str = str(val)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            print(f"  {key}: {val_str}")
    else:
        print("No processing jobs found")
        # Check for failed jobs
        job = await db.upload_jobs.find_one({"status": "failed"}, sort=[("created_at", -1)])
        if job:
            print("\n=== LATEST FAILED JOB ===")
            for key, val in job.items():
                if key == '_id':
                    continue
                val_str = str(val)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                print(f"  {key}: {val_str}")
    
    # Check for any new policy created in last 5 minutes
    from datetime import datetime, timedelta
    recent = datetime.utcnow() - timedelta(minutes=30)
    new_policies = await db.policies.find({"created_at": {"$gte": recent.isoformat()}}).to_list(10)
    if new_policies:
        print(f"\n=== POLICIES CREATED IN LAST 30 MINS: {len(new_policies)} ===")
        for p in new_policies:
            print(f"  {p.get('title', '?')}: {p.get('status')} - {len(p.get('clauses', []))} clauses")
    
    client.close()

asyncio.run(check())
