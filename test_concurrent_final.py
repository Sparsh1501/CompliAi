import requests
import concurrent.futures
import time
import random

BASE_URL = "http://localhost:8000"

# Use a unique test run ID
test_run_id = random.randint(10000, 99999)
print(f"Test Run ID: {test_run_id}")

# Login
login_data = {"email": "feature192@test.com", "password": "TestPass192"}
r = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=5)
print(f"Login: {r.status_code}")
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Test: Send 5 rapid POST requests to create tasks
print("\n=== Feature #192: Concurrent API Submissions Test ===")
print("Testing: 5 concurrent POST requests to create tasks")

def create_task(i):
    task_data = {
        "title": f"Concurrent-{test_run_id}-Task-{i}",
        "description": f"Task created in concurrent test #{i} (run {test_run_id})",
        "status": "Pending",
        "priority": "Medium",
        "assignee": "feature192@test.com",
        "due_date": "2026-03-01"
    }
    try:
        start = time.time()
        r = requests.post(f"{BASE_URL}/api/tasks", json=task_data, headers=headers, timeout=5)
        elapsed = time.time() - start
        return r.status_code, i, elapsed
    except Exception as e:
        return "ERROR", i, 0

# Execute 5 concurrent requests
start_time = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(create_task, i) for i in range(5)]
    results = [f.result() for f in futures]
total_time = time.time() - start_time

print(f"\nAll 5 requests completed in {total_time:.3f}s")
print("\nIndividual results:")
for status, i, elapsed in results:
    print(f"  Task {i}: HTTP {status} ({elapsed:.3f}s)")

# Verify exactly 5 tasks created (no duplicates, no missing)
time.sleep(0.5)
r = requests.get(f"{BASE_URL}/api/tasks", headers=headers, timeout=5)
all_tasks = r.json()
test_tasks = [t for t in all_tasks if f"Concurrent-{test_run_id}" in t.get("title", "")]

print(f"\n=== Verification ===")
print(f"Tasks created: {len(test_tasks)} (expected: 5)")

# Check for duplicates
task_titles = [t["title"] for t in test_tasks]
unique_titles = set(task_titles)
has_duplicates = len(task_titles) != len(unique_titles)

# Check for 500 errors
error_500_count = sum(1 for r in results if r[0] == 500)
success_200_count = sum(1 for r in results if r[0] == 200)

# Print verification results
print(f"\nChecks:")
print(f"  ✓ Correct count: {len(test_tasks) == 5}")
print(f"  ✓ No duplicates: {not has_duplicates}")
print(f"  ✓ No 500 errors: {error_500_count == 0}")
print(f"  ✓ All successful: {success_200_count == 5}")

# Overall result
overall_pass = (
    len(test_tasks) == 5 and
    not has_duplicates and
    error_500_count == 0 and
    success_200_count == 5
)

print(f"\n=== RESULT: {'✓ PASS' if overall_pass else '✗ FAIL'} ===")
if overall_pass:
    print("Concurrent API submissions handled gracefully:")
    print("  - 5 rapid POST requests created exactly 5 tasks")
    print("  - No duplicate tasks")
    print("  - No 500 server errors")
    print("  - All requests returned 200 OK")
else:
    print("Issues detected:")
    if len(test_tasks) != 5:
        print(f"  ✗ Expected 5 tasks, got {len(test_tasks)}")
    if has_duplicates:
        print(f"  ✗ Duplicate tasks created")
    if error_500_count > 0:
        print(f"  ✗ {error_500_count} requests returned 500 errors")
    if success_200_count != 5:
        print(f"  ✗ Only {success_200_count}/5 requests succeeded")

exit(0 if overall_pass else 1)
