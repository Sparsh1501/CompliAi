#!/usr/bin/env python3
"""
Feature Database Investigation Script

Purpose: Identify why the orchestrator keeps assigning the same 3 blocked features
         and determine if there are other testable features available.

Usage: python investigate_features.py
"""

import sqlite3
import json
from collections import defaultdict

# Known sandbox-incompatible features
SANDBOX_BLOCKED = {1, 2, 3, 16, 32, 36, 56, 57, 58, 59, 63, 80, 109, 143, 144, 145}

def main():
    print("=" * 80)
    print("FEATURE DATABASE INVESTIGATION")
    print("=" * 80)
    print()

    # Connect to feature database
    # (Adjust path if database is in a different location)
    db_path = ".autoforge/features.db"

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ ERROR: Could not connect to database: {e}")
        print(f"   Looking for: {db_path}")
        return

    # Get all features
    cursor.execute("SELECT * FROM features ORDER BY priority")
    all_features = cursor.fetchall()

    print(f"Total Features: {len(all_features)}")
    print()

    # Analyze features
    passing = []
    failing = []
    in_progress = []

    for feature in all_features:
        if feature['passes']:
            passing.append(feature)
        elif feature['in_progress']:
            in_progress.append(feature)
        else:
            failing.append(feature)

    print(f"✅ Passing: {len(passing)}")
    print(f"⏳ In Progress: {len(in_progress)}")
    print(f"❌ Not Passing: {len(failing)}")
    print()

    # Analyze non-passing features
    print("=" * 80)
    print("NON-PASSING FEATURES ANALYSIS")
    print("=" * 80)
    print()

    # Group by category
    by_category = defaultdict(list)
    for feature in failing:
        by_category[feature['category']].append(feature)

    # Check dependencies
    def get_dependencies(feature):
        """Parse dependencies JSON string"""
        try:
            deps = json.loads(feature['dependencies'])
            return deps if deps else []
        except:
            return []

    def has_blocked_dependency(feature, visited=None):
        """Recursively check if feature depends on blocked features"""
        if visited is None:
            visited = set()

        if feature['id'] in visited:
            return False  # Circular dependency, stop
        visited.add(feature['id'])

        deps = get_dependencies(feature)
        for dep_id in deps:
            if dep_id in SANDBOX_BLOCKED:
                return True

            # Get dependent feature
            cursor.execute("SELECT * FROM features WHERE id = ?", (dep_id,))
            dep_feature = cursor.fetchone()
            if dep_feature and not dep_feature['passes']:
                # Check if this dependency is also blocked
                if has_blocked_dependency(dep_feature, visited):
                    return True

        return False

    # Categorize non-passing features
    sandbox_blocked_direct = []
    sandbox_blocked_dependency = []
    potentially_testable = []

    for feature in failing:
        if feature['id'] in SANDBOX_BLOCKED:
            sandbox_blocked_direct.append(feature)
        elif has_blocked_dependency(feature):
            sandbox_blocked_dependency.append(feature)
        else:
            potentially_testable.append(feature)

    print(f"📋 Non-Passing Features Breakdown:")
    print(f"   - Direct sandbox blocks: {len(sandbox_blocked_direct)}")
    print(f"   - Blocked by dependencies: {len(sandbox_blocked_dependency)}")
    print(f"   - Potentially testable: {len(potentially_testable)}")
    print()

    # Show potentially testable features
    if potentially_testable:
        print("=" * 80)
        print("🎯 POTENTIALLY TESTABLE FEATURES (No blocked dependencies)")
        print("=" * 80)
        print()

        for feature in sorted(potentially_testable, key=lambda f: f['priority'])[:20]:
            deps = get_dependencies(feature)
            print(f"Feature #{feature['id']} (Priority {feature['priority']})")
            print(f"  Category: {feature['category']}")
            print(f"  Name: {feature['name']}")
            print(f"  Dependencies: {deps}")
            print()
    else:
        print("=" * 80)
        print("⚠️  NO TESTABLE FEATURES FOUND")
        print("=" * 80)
        print()
        print("All remaining features depend on sandbox-blocked features.")
        print("This explains why the orchestrator keeps assigning #16, #36, #80.")
        print()
        print("RECOMMENDATION: Switch to local development environment.")
        print("Sandbox work is COMPLETE at 72%.")
        print()

    # Show dependency chains for blocked features
    print("=" * 80)
    print("🔗 DEPENDENCY CHAINS (Why features are blocked)")
    print("=" * 80)
    print()

    def get_blocking_chain(feature, depth=0, max_depth=5):
        """Show why a feature is blocked"""
        if depth > max_depth:
            return "  " * depth + "[max depth reached]"

        deps = get_dependencies(feature)
        if not deps:
            return ""

        result = []
        for dep_id in deps:
            if dep_id in SANDBOX_BLOCKED:
                result.append("  " * depth + f"→ Feature #{dep_id} [SANDBOX BLOCKED]")
            else:
                cursor.execute("SELECT * FROM features WHERE id = ?", (dep_id,))
                dep_feature = cursor.fetchone()
                if dep_feature and not dep_feature['passes']:
                    result.append("  " * depth + f"→ Feature #{dep_id} (not passing)")
                    chain = get_blocking_chain(dep_feature, depth + 1, max_depth)
                    if chain:
                        result.append(chain)

        return "\n".join(result)

    # Show chains for some blocked-by-dependency features
    for feature in sandbox_blocked_dependency[:5]:
        print(f"Feature #{feature['id']}: {feature['name']}")
        print(f"  Category: {feature['category']}")
        print(f"  Priority: {feature['priority']}")
        print(f"  Blocked because:")
        print(get_blocking_chain(feature))
        print()

    # Priority analysis
    print("=" * 80)
    print("📊 PRIORITY QUEUE ANALYSIS")
    print("=" * 80)
    print()

    print("Lowest priority non-passing features:")
    for feature in sorted(failing, key=lambda f: f['priority'])[:10]:
        blocked = "BLOCKED" if feature['id'] in SANDBOX_BLOCKED else ""
        deps = get_dependencies(feature)
        has_blocked = has_blocked_dependency(feature)
        status = "BLOCKED BY DEPS" if has_blocked else "TESTABLE?"
        print(f"  #{feature['id']:3d} (Priority {feature['priority']:3d}) - {status:15s} - {feature['name'][:50]}")

    print()

    # Summary
    print("=" * 80)
    print("🎯 CONCLUSION")
    print("=" * 80)
    print()

    if len(potentially_testable) > 0:
        print(f"✅ Found {len(potentially_testable)} potentially testable features!")
        print()
        print("RECOMMENDATION: Fix orchestrator to assign these features instead of #16, #36, #80.")
        print()
        print("The orchestrator should:")
        print("1. Filter out features #16, #32, #36, #56-59, #63, #80, #109, #143-145")
        print("2. Assign features from the potentially_testable list")
        print("3. Check if dependencies are PASSING before assigning")
    else:
        print("❌ No testable features remaining in sandbox.")
        print()
        print("ALL remaining features depend on file upload functionality.")
        print()
        print("RECOMMENDATION: Stop sandbox sessions, switch to local environment.")
        print()
        print("To complete the remaining 56 features (28%):")
        print("1. Set up local development environment")
        print("2. Run Docker with MongoDB and Qdrant")
        print("3. Test file upload features (#16, #32)")
        print("4. This will unblock all dependent features")
        print("5. Complete final 28% of features")

    print()
    print("=" * 80)

    conn.close()

if __name__ == "__main__":
    main()
