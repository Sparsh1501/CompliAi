from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["compli-ai"]

collections = sorted(db.list_collection_names())
print("=== MongoDB Collections ===")
for coll in collections:
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

# Check indexes on key collections
print("\n=== Index Check ===")
try:
    user_indexes = list(db.users.list_indexes())
    print(f"Users collection indexes: {len(user_indexes)}")
    for idx in user_indexes:
        print(f"  - {idx['name']}: {idx.get('key', {})}")

    policy_indexes = list(db.policies.list_indexes())
    print(f"\nPolicies collection indexes: {len(policy_indexes)}")
    for idx in policy_indexes:
        print(f"  - {idx['name']}: {idx.get('key', {})}")

    task_indexes = list(db.tasks.list_indexes())
    print(f"\nTasks collection indexes: {len(task_indexes)}")
    for idx in task_indexes:
        print(f"  - {idx['name']}: {idx.get('key', {})}")
except Exception as e:
    print(f"Error checking indexes: {e}")
