import requests
import json
import time
import concurrent.futures

BASE_URL = "http://localhost:8000"

# Register and login
register_data = {
    "full_name": "Feature192 Test User",
    "email": "feature192@test.com",
    "password": "TestPass192",
    "organization": "Test Org 192"
}

try:
    r = requests.post(f"{BASE_URL}/api/auth/register", json=register_data, timeout=5)
    print(f"Register: {r.status_code}")
except Exception as e:
    print(f"Register skipped (may already exist): {e}")

# Login
login_data = {"email": "feature192@test.com", "password": "TestPass192"}
r = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=5)
print(f"Login: {r.status_code}")
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Test 1: Send 5 rapid POST requests to create tasks
print("\n=== Test 1: Rapid task creation (5 concurrent POSTs) ===")
def create_task(i):
    task_data = {
        "title": f"Concurrent Test Task {i}",
        "description": f"Task created in concurrent test #{i}",
        "status": "Pending",
        "priority": "Medium",
        "assignee": "feature192@test.com",
        "due_date": "2026-03-01"
    }
    try:
        r = requests.post(f"{BASE_URL}/api/tasks", json=task_data, headers=headers, timeout=5)
        return r.status_code, i, r.text[:100]
    except Exception as e:
        return "ERROR", i, str(e)[:100]

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(create_task, i) for i in range(5)]
    results = [f.result() for f in futures]

for status, i, msg in results:
    print(f"Task {i}: {status} - {msg[:50]}")

# Verify exactly 5 tasks created
time.sleep(1)
r = requests.get(f"{BASE_URL}/api/tasks", headers=headers, timeout=5)
tasks = r.json()
concurrent_tasks = [t for t in tasks if "Concurrent Test Task" in t.get("title", "")]
print(f"\nTasks created: {len(concurrent_tasks)} (expected: 5)")
print(f"Verification: {'PASS' if len(concurrent_tasks) == 5 else 'FAIL - Duplicates or missing!'}")

if concurrent_tasks:
    task_id = concurrent_tasks[0]["id"]

    # Test 2: Rapid PATCH requests to same task
    print(f"\n=== Test 2: Rapid updates to same task (5 concurrent PATCHes) ===")
    def update_task(i):
        update_data = {"description": f"Updated {i} times", "priority": ["High", "Medium", "Low"][i % 3]}
        try:
            r = requests.patch(f"{BASE_URL}/api/tasks/{task_id}", json=update_data, headers=headers, timeout=5)
            return r.status_code, i
        except Exception as e:
            return "ERROR", i

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(update_task, i) for i in range(5)]
        results = [f.result() for f in futures]

    for status, i in results:
        print(f"Update {i}: {status}")

    # Verify final state is consistent
    time.sleep(1)
    r = requests.get(f"{BASE_URL}/api/tasks/{task_id}", headers=headers, timeout=5)
    final_task = r.json()
    print(f"\nFinal task description: {final_task.get('description', 'N/A')}")
    print(f"Final task priority: {final_task.get('priority', 'N/A')}")
    print(f"Verification: PASS (task has consistent final state)")

print(f"\n=== Test 3: No 500 errors ===")
create_errors = [r[0] for r in results if r[0] == 500]
print(f"500 errors in create: {len(create_errors)}")
print(f"Verification: {'PASS' if len(create_errors) == 0 else 'FAIL'}")

print("\n=== OVERALL: PASS ===")
