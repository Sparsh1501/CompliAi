import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def fix():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['compli-ai']
    
    result = await db.upload_jobs.update_many(
        {"status": "processing"},
        {"$set": {"status": "failed", "error_message": "OCR timed out - batch size too large"}}
    )
    print(f"Marked {result.modified_count} stuck jobs as failed")
    client.close()

asyncio.run(fix())
