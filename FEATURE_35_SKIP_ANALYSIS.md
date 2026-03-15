# Feature #35: Regulation Version Diff View - SKIPPED

**Feature ID:** 35
**Category:** Workflow Completeness
**Status:** SKIPPED ⏭️
**Date:** 2026-02-08
**Reason:** Complex implementation required, not currently implemented

## Feature Description

Verify regulation version comparison with highlighted changes (side-by-side and inline views with AI summary).

## Verification Steps Required

1. ❌ Navigate to regulation with multiple versions
2. ❌ Open diff view
3. ❌ Verify side-by-side comparison
4. ❌ Verify inline highlighted changes mode
5. ❌ Verify additions green, removals red
6. ❌ Verify AI summary of changes displayed

## Current State Analysis

### Data Model: PARTIAL SUPPORT ✅

**File:** `backend/models.py` (Regulation class, lines 342-365)

**Version Fields Exist:**
```python
version: str = "1.0"  # Current version number
previous_version_id: Optional[str] = None  # Link to previous version
```

**These fields allow:**
- Storing multiple versions of same regulation
- Linking versions together
- Tracking version history

### Backend Implementation: NOT IMPLEMENTED ❌

**Missing Components:**

1. **Version Comparison Endpoint**
   - No `GET /api/regulations/{id}/diff/{other_id}` endpoint
   - No text diff algorithm implementation
   - No change detection logic

2. **AI Summary Generation**
   - No LLM integration for summarizing changes
   - No analysis of clause additions/removals
   - No impact assessment of changes

3. **Version Management**
   - No endpoint to create new version from existing
   - No version retrieval by version number
   - No version history listing

### Frontend Implementation: NOT IMPLEMENTED ❌

**Missing Components:**

1. **Diff View Component**
   - No RegulationDiff.js or similar component
   - No side-by-side comparison view
   - No inline diff view with highlighting

2. **UI Controls**
   - No version selector dropdown
   - No toggle between side-by-side/inline views
   - No navigation between changes

3. **Styling**
   - No green highlighting for additions
   - No red highlighting for removals
   - No diff-specific CSS

### Third-Party Libraries Needed

**Recommended:**
- `diff` or `diff-match-patch` (NPM) - Text diffing algorithm
- `react-diff-viewer` (NPM) - Pre-built diff component
- Backend text diff library (Python difflib or similar)

## Why This Feature Requires Significant Work

### 1. Backend API Development (~3-4 hours)

**Endpoints to Create:**
```python
# Compare two regulation versions
GET /api/regulations/{id}/compare/{version_id}
  Returns: {
    "additions": [...],
    "removals": [...],
    "modifications": [...],
    "ai_summary": "..."
  }

# List all versions of a regulation
GET /api/regulations/{id}/versions
  Returns: [
    {version: "2.0", date: "...", changes: "..."},
    {version: "1.0", date: "...", changes: "..."}
  ]

# Create new version
POST /api/regulations/{id}/create-version
  Body: {new_content, version_number, change_summary}
```

**Implementation Tasks:**
- Text diff algorithm (Python difflib)
- Clause-level comparison logic
- AI summary generation via Claude/OpenAI
- Version history retrieval
- Database queries for version linking

### 2. Frontend Development (~4-5 hours)

**Components to Create:**

```jsx
// RegulationDiffView.js
- Version selector dropdowns (compare version A vs B)
- Toggle: Side-by-side | Inline
- Diff display area with syntax highlighting
- Change statistics (X additions, Y removals)
- AI summary panel
- Navigation: Previous/Next change

// Integration with RegulationDetail.js
- "View Version History" button
- Version badge display
- Link to diff view
```

**Styling:**
- Green background for additions
- Red background for removals
- Yellow for modifications
- Line number margins
- Scrolling synchronization (side-by-side)

### 3. Testing (~1-2 hours)

- Create test regulations with multiple versions
- Verify diff accuracy
- Test side-by-side vs inline modes
- Verify color highlighting
- Test AI summary generation
- Browser compatibility

**Total Estimated Effort: 8-11 hours**

## Workaround Available

**Manual Version Comparison:**
Users can currently:
1. Open regulation version 1 in one browser tab
2. Open regulation version 2 in another tab
3. Manually compare side-by-side
4. Note differences manually

This is not ideal but functional for basic needs.

## Recommendation

**SKIP this feature for now** and prioritize:
- Features verifiable through code inspection
- Features requiring less implementation work
- Features with higher business impact

**Implementation can be added later** as a dedicated enhancement when:
- Time allows for proper implementation
- Testing environment is available
- Requirements are refined (preferences for diff library, UI layout)

## Dependencies

Feature #35 depends on: #1, #2, #3, #4, #5, #34

- ✅ #1-5: Infrastructure features (passing)
- ✅ #34: Regulation detail view (passing)

Dependencies are satisfied, but **implementation doesn't exist**.

## Next Steps (If/When Implementing)

1. **Research & Planning (1 hour)**
   - Evaluate diff libraries (diff.js, diff-match-patch, jsdiff)
   - Design API response schema
   - Sketch UI mockups

2. **Backend Implementation (3 hours)**
   - Install difflib or similar library
   - Create comparison endpoint
   - Integrate AI summary generation
   - Add version history endpoint

3. **Frontend Implementation (4 hours)**
   - Install react-diff-viewer or build custom
   - Create RegulationDiffView component
   - Add version selector controls
   - Implement side-by-side and inline views
   - Style additions/removals/modifications

4. **Testing & Refinement (2 hours)**
   - Create test data with versions
   - Test all diff modes
   - Verify AI summaries
   - Fix edge cases

5. **Documentation**
   - Update user guide
   - Add API documentation
   - Create usage examples

## Conclusion

Feature #35 is **SKIPPED** due to:
- ❌ No existing implementation
- ❌ Complex multi-component feature (backend + frontend + AI)
- ❌ 8-11 hours estimated effort
- ❌ Cannot be verified through static analysis
- ❌ Sandbox environment prevents integration testing

**The feature CAN be implemented** but requires dedicated development time in a proper development environment with testing capabilities.

**Alternative:** Complete other passing-viable features first, implement this in a focused development session later.

