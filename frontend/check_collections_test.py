from pymongo import MongoClient
import sys

try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client['compli-ai']
    
    collections = db.list_collection_names()
    print(f"Found {len(collections)} collections:")
    for col in sorted(collections):
        print(f"  - {col}")
    
    # Check required collections
    required = [
        'users', 'policies', 'policy_versions', 'approval_workflows',
        'regulations', 'regulation_updates', 'clauses', 'gap_analyses',
        'tasks', 'task_dependencies', 'escalation_rules', 'evidence',
        'evidence_audit_log', 'evidence_templates', 'departments',
        'department_members', 'audit_sessions', 'calendar_events',
        'chat_threads', 'chat_messages', 'los_lms_data', 'los_lms_mappings',
        'los_lms_exceptions', 'notification_preferences', 'notifications'
    ]
    
    missing = [col for col in required if col not in collections]
    if missing:
        print(f"\nMISSING collections: {missing}")
        sys.exit(1)
    else:
        print(f"\n✓ All {len(required)} required collections exist")
    
    # Check indexes on key collections
    print("\nChecking indexes:")
    users_indexes = list(db.users.list_indexes())
    print(f"  users: {len(users_indexes)} indexes")
    for idx in users_indexes:
        print(f"    - {idx['name']}: {idx.get('key', {})}")
    
    policies_indexes = list(db.policies.list_indexes())
    print(f"  policies: {len(policies_indexes)} indexes")
    
    tasks_indexes = list(db.tasks.list_indexes())
    print(f"  tasks: {len(tasks_indexes)} indexes")
    
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
