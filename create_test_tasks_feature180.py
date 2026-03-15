#!/usr/bin/env python3
"""Create test tasks for Feature #180 - Analytics team workload distribution"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# Login
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "designtest@compli.ai", "password": "Test123!"}
)
token = login_response.json()["token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Get user ID
user_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
user_id = user_response.json()["id"]

# Create tasks across different departments
tasks_to_create = [
    # Compliance Department (3 tasks)
    {"title": "KYC Policy Review", "department": "Compliance", "status": "Open", "priority": "High"},
    {"title": "AML Checklist Update", "department": "Compliance", "status": "In Progress", "priority": "Medium"},
    {"title": "RBI Guidelines Implementation", "department": "Compliance", "status": "Done", "priority": "High"},

    # Risk Department (2 tasks)
    {"title": "Risk Assessment Q1 2026", "department": "Risk", "status": "Open", "priority": "High"},
    {"title": "Operational Risk Report", "department": "Risk", "status": "In Progress", "priority": "Medium"},

    # Legal Department (2 tasks)
    {"title": "Contract Template Review", "department": "Legal", "status": "Done", "priority": "Low"},
    {"title": "Regulatory Notice Response", "department": "Legal", "status": "Open", "priority": "High"},

    # Technology Department (1 task)
    {"title": "Security Audit Preparation", "department": "Technology", "status": "In Progress", "priority": "High"},
]

created_tasks = []
for task_data in tasks_to_create:
    task_payload = {
        "title": task_data["title"],
        "description": f"Test task for workload distribution - {task_data['department']}",
        "assignee": user_id,
        "department": task_data["department"],
        "priority": task_data["priority"],
        "status": task_data["status"],
        "due_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    }

    try:
        response = requests.post(f"{BASE_URL}/api/tasks", json=task_payload, headers=headers)
        if response.status_code in [200, 201]:
            created_tasks.append(response.json())
            print(f"✓ Created: {task_data['title']} ({task_data['department']})")
        else:
            print(f"✗ Failed to create {task_data['title']}: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        print(f"✗ Error creating {task_data['title']}: {str(e)}")

print(f"\nTotal tasks created: {len(created_tasks)}")
print("\nDepartment breakdown:")
dept_count = {}
for task in tasks_to_create:
    dept = task["department"]
    dept_count[dept] = dept_count.get(dept, 0) + 1
for dept, count in sorted(dept_count.items()):
    print(f"  {dept}: {count} tasks")
