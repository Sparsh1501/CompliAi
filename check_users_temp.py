from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def check_users():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['compli-ai']
    users = await db.users.find({}, {"email": 1, "_id": 0}).limit(5).to_list(None)
    print("Existing users:", users)

    # Also delete feature16test@test.com if it exists to recreate it
    result = await db.users.delete_one({"email": "feature16test@test.com"})
    print(f"Deleted feature16test user: {result.deleted_count}")
    client.close()

asyncio.run(check_users())
