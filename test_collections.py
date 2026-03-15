import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_collections():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["compli-ai"]

    collections = await db.list_collection_names()
    print("=== MongoDB Collections ===")
    for coll in sorted(collections):
        print(f"  - {coll}")
    print(f"\nTotal: {len(collections)} collections")

    # Check required collections from spec
    required = [
        "users", "policies", "policy_versions", "approval_workflows",
        "regulations", "regulation_updates", "clauses", "gap_analyses",
        "tasks", "task_dependencies", "escalation_rules",
        "evidence", "evidence_audit_log", "evidence_templates",
        "departments", "department_members", "audit_sessions",
        "calendar_events", "chat_threads", "chat_messages",
        "los_lms_data", "los_lms_mappings", "los_lms_exceptions",
        "notification_preferences", "notifications"
    ]

    print("\n=== Required Collections Check ===")
    missing = []
    for req in required:
        if req in collections:
            print(f"  ✓ {req}")
        else:
            print(f"  ✗ {req} - MISSING")
            missing.append(req)

    if missing:
        print(f"\n⚠️  {len(missing)} collections missing: {missing}")
    else:
        print("\n✓ All required collections exist!")

asyncio.run(check_collections())
