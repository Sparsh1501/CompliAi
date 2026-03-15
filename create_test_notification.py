#!/usr/bin/env python3
from pymongo import MongoClient
from datetime import datetime

def create_notification():
    client = MongoClient('mongodb://localhost:27017')
    db = client['compli-ai']

    # Find the test user
    user = db.users.find_one({"email": "feature76@test.com"})
    if not user:
        print("User not found")
        return

    # Create notification
    notification = {
        "id": f"test-notif-{int(datetime.now().timestamp() * 1000)}",
        "user_id": user['user_id'],
        "title": "Test Notification",
        "message": "This is a test notification to verify the notification panel works",
        "type": "info",
        "read": False,
        "link": "/dashboard",
        "created_at": datetime.now().isoformat()
    }

    result = db.notifications.insert_one(notification)
    print(f"Notification created: {result.inserted_id}")

    client.close()

if __name__ == "__main__":
    create_notification()
