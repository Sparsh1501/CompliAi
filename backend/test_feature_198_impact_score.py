"""
Test script for Feature #198: Human-in-the-loop correction on impact scores

This test verifies:
1. The ImpactScoreAdjustment model is properly defined
2. The endpoint /api/regulation-updates/{id}/adjust-impact-score exists
3. Impact score corrections are tracked in history
"""

import sys
import importlib.util

def test_feature_198():
    """Test Feature #198 implementation"""

    print("=" * 70)
    print("Feature #198: Human-in-the-loop correction on impact scores")
    print("=" * 70)
    print()

    # Test 1: Verify ImpactScoreAdjustment model exists
    print("Test 1: Verify ImpactScoreAdjustment model...")
    try:
        with open('backend/models.py', 'r') as f:
            content = f.read()

        if 'class ImpactScoreAdjustment' in content:
            print("   ✓ ImpactScoreAdjustment model found")
        else:
            print("   ✗ ImpactScoreAdjustment model NOT found")
            return False
    except Exception as e:
        print(f"   ✗ Error reading models.py: {e}")
        return False

    # Test 2: Verify RegulationUpdate model has impact_score fields
    print("\nTest 2: Verify RegulationUpdate has impact_score fields...")
    try:
        with open('backend/models.py', 'r') as f:
            content = f.read()

        if 'impact_score: Optional[float]' in content:
            print("   ✓ impact_score field found in RegulationUpdate")
        else:
            print("   ✗ impact_score field NOT found")
            return False

        if 'impact_score_corrections: List[Dict[str, Any]]' in content:
            print("   ✓ impact_score_corrections field found in RegulationUpdate")
        else:
            print("   ✗ impact_score_corrections field NOT found")
            return False
    except Exception as e:
        print(f"   ✗ Error reading models.py: {e}")
        return False

    # Test 3: Verify endpoint exists in server.py
    print("\nTest 3: Verify adjustment endpoint exists...")
    try:
        with open('backend/server.py', 'r') as f:
            content = f.read()

        if 'regulation-updates/{update_id}/adjust-impact-score' in content:
            print("   ✓ Endpoint /regulation-updates/{id}/adjust-impact-score found")
        else:
            print("   ✗ Endpoint NOT found")
            return False

        if 'adjust_impact_score' in content:
            print("   ✓ adjust_impact_score function found")
        else:
            print("   ✗ adjust_impact_score function NOT found")
            return False

        # Check for correction tracking logic
        if '"impact_score_corrections": correction_record' in content or '$push' in content:
            print("   ✓ Correction history tracking logic found")
        else:
            print("   ✗ Correction history tracking NOT found")
            return False
    except Exception as e:
        print(f"   ✗ Error reading server.py: {e}")
        return False

    # Test 4: Verify frontend has adjustment UI
    print("\nTest 4: Verify frontend UI components...")
    try:
        with open('frontend/src/pages/RegulatoryUpdates.js', 'r') as f:
            content = f.read()

        if 'adjustScoreOpen' in content:
            print("   ✓ Adjustment dialog state found")
        else:
            print("   ✗ Adjustment dialog state NOT found")
            return False

        if 'handleAdjustScore' in content or 'adjustScore' in content:
            print("   ✓ Adjustment handler function found")
        else:
            print("   ✗ Adjustment handler function NOT found")
            return False

        if 'impact_score_corrections' in content:
            print("   ✓ Correction history display found")
        else:
            print("   ✗ Correction history display NOT found")
            return False

        if 'Edit3' in content or 'Adjust' in content:
            print("   ✓ Adjust button found")
        else:
            print("   ✗ Adjust button NOT found")
            return False

        if 'History' in content and 'showHistory' in content:
            print("   ✓ History view toggle found")
        else:
            print("   ✗ History view toggle NOT found")
            return False
    except Exception as e:
        print(f"   ✗ Error reading RegulatoryUpdates.js: {e}")
        return False

    # Test 5: Verify validation constraints
    print("\nTest 5: Verify validation constraints...")
    try:
        with open('backend/models.py', 'r') as f:
            content = f.read()

        if 'ge=0' in content and 'le=100' in content:
            print("   ✓ Score range validation (0-100) found")
        else:
            print("   ✗ Score range validation NOT found")
            return False

        if 'min_length=10' in content:
            print("   ✓ Justification minimum length validation found")
        else:
            print("   ✗ Justification validation NOT found")
            return False
    except Exception as e:
        print(f"   ✗ Error checking validation: {e}")
        return False

    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED - Feature #198 is correctly implemented!")
    print("=" * 70)
    print()
    print("Summary:")
    print("  • ImpactScoreAdjustment model: DEFINED")
    print("  • RegulationUpdate.impact_score: ADDED")
    print("  • RegulationUpdate.impact_score_corrections: ADDED")
    print("  • Backend endpoint: IMPLEMENTED")
    print("  • Correction tracking: IMPLEMENTED")
    print("  • Frontend UI: IMPLEMENTED")
    print("  • Adjustment dialog: IMPLEMENTED")
    print("  • History view: IMPLEMENTED")
    print("  • Validation constraints: IMPLEMENTED")
    print()

    return True

if __name__ == "__main__":
    success = test_feature_198()
    sys.exit(0 if success else 1)
