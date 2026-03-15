import requests
import concurrent.futures
import time

BASE_URL = "http://localhost:8000"

# Login
login_data = {"email": "feature192@test.com", "password": "TestPass192"}
r = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=5)
print(f"Login: {r.status_code}")
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# First, check existing tasks
r = requests.get(f"{BASE_URL}/api/tasks", headers=headers, timeout=5)
initial_tasks = r.json()
concurrent_tasks_before = [t for t in initial_tasks if "Concurrent Test Task" in t.get("title", "")]
print(f"\nExisting concurrent test tasks: {len(concurrent_tasks_before)}")

# Test: Send 5 rapid POST requests to create tasks
print("\n=== Concurrent Task Creation Test ===")
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
        start = time.time()
        r = requests.post(f"{BASE_URL}/api/tasks", json=task_data, headers=headers, timeout=5)
        elapsed = time.time() - start
        return r.status_code, i, elapsed, r.text[:100]
    except Exception as e:
        return "ERROR", i, 0, str(e)[:100]

# Execute 5 concurrent requests
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(create_task, i) for i in range(5)]
    results = [f.result() for f in futures]

print("\nResults:")
for status, i, elapsed, msg in results:
    print(f"  Task {i}: {status} ({elapsed:.3f}s) - {msg[:50]}")

# Verify exactly 5 NEW tasks created
time.sleep(1)
r = requests.get(f"{BASE_URL}/api/tasks", headers=headers, timeout=5)
all_tasks = r.json()
concurrent_tasks_after = [t for t in all_tasks if "Concurrent Test Task" in t.get("title", "")]

new_tasks_count = len(concurrent_tasks_after) - len(concurrent_tasks_before)
print(f"\nNew tasks created: {new_tasks_count} (expected: 5)")

# Check for duplicates by title
from collections import Counter
titles = [t["title"] for t in concurrent_tasks_after]
title_counts = Counter(titles)
duplicates = {title: count for title, count in title_counts.items() if count > 1}

if duplicates:
    print(f"FAIL - Duplicate titles found: {duplicates}")
else:
    print("PASS - No duplicate titles")

# Check for 500 errors
error_500_count = sum(1 for r in results if r[0] == 500)
print(f"\n500 errors: {error_500_count} (expected: 0)")
print(f"Verification: {'PASS' if error_500_count == 0 else 'FAIL'}")

# Overall result
overall_pass = (new_tasks_count == 5) and (not duplicates) and (error_500_count == 0)
print(f"\n=== OVERALL: {'PASS' if overall_pass else 'FAIL'} ===")
if overall_pass:
    print("✓ Concurrent API submissions handled gracefully")
    print("✓ No duplicate tasks created")
    print("✓ No 500 errors")
else:
    if new_tasks_count != 5:
        print(f"✗ Expected 5 new tasks, got {new_tasks_count}")
    if duplicates:
        print(f"✗ Duplicate tasks detected: {duplicates}")
    if error_500_count > 0:
        print(f"✗ {error_500_count} 500 errors occurred")
