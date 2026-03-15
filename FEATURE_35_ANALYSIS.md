# Feature #35 Analysis: Regulation Version Diff View

**Feature ID:** #35
**Category:** Workflow Completeness
**Status:** ⚠️ NEEDS IMPLEMENTATION
**Analysis Date:** 2025-02-08
**Complexity:** HIGH (4-6 hours implementation)

---

## Feature Description

Verify regulation version comparison with highlighted changes.

### Required Steps (from spec)
1. Navigate to regulation with multiple versions
2. Open diff view
3. Verify side-by-side comparison
4. Verify inline highlighted changes mode
5. Verify additions green, removals red
6. Verify AI summary of changes displayed

---

## Current Implementation Status

### What EXISTS ✅

#### 1. Data Models (backend/models.py)

**Regulation Model:**
```python
class Regulation(BaseModel):
    # ... fields ...
    version: str = "1.0"
    previous_version_id: Optional[str] = None
```

**CircularVersion Model:**
```python
class CircularVersion(BaseModel):
    id: str
    circular_id: str
    version: str
    changes_summary: str
    additions: List[str] = []
    deletions: List[str] = []
    modifications: List[str] = []
    created_at: datetime
```

#### 2. Database Schema

According to `app_spec.txt`:
```
<regulations>
  - _id, title, regulatory_body, circular_number, category
  - file_path, original_filename, effective_date, version_history[]
  - impact_score, summary, diff_highlights, created_at, updated_at
</regulations>
```

The schema supports version_history and diff_highlights.

---

## What is MISSING ❌

### Backend Implementation

#### 1. Get Version History Endpoint

**MISSING:** `GET /api/regulations/{regulation_id}/versions`

Should return:
```json
{
  "regulation_id": "reg-123",
  "versions": [
    {
      "version": "2.0",
      "created_at": "2025-01-15T10:00:00Z",
      "changes_summary": "Added digital lending compliance clauses",
      "is_current": true
    },
    {
      "version": "1.0",
      "created_at": "2024-06-01T10:00:00Z",
      "changes_summary": "Initial master circular",
      "is_current": false
    }
  ]
}
```

**Implementation needed:**
```python
@api_router.get("/regulations/{regulation_id}/versions")
async def get_regulation_versions(
    regulation_id: str,
    current_user: dict = Depends(get_current_user)
):
    # 1. Find regulation
    regulation = await db.regulations.find_one({"id": regulation_id})

    # 2. Get all versions (follow previous_version_id chain or use version_history[])
    versions = []

    # If using version_history:
    if 'version_history' in regulation:
        versions = regulation['version_history']

    # Or follow chain:
    # current_reg = regulation
    # while current_reg:
    #     versions.append({
    #         "version": current_reg['version'],
    #         "created_at": current_reg['created_at'],
    #         ...
    #     })
    #     if current_reg.get('previous_version_id'):
    #         current_reg = await db.regulations.find_one({"id": current_reg['previous_version_id']})
    #     else:
    #         break

    return {"regulation_id": regulation_id, "versions": versions}
```

#### 2. Get Diff Between Versions Endpoint

**MISSING:** `GET /api/regulations/{regulation_id}/diff?from_version={v1}&to_version={v2}`

Should return:
```json
{
  "regulation_id": "reg-123",
  "from_version": "1.0",
  "to_version": "2.0",
  "diff_mode": "clause_by_clause",
  "ai_summary": "This amendment adds 5 new clauses related to digital lending platforms...",
  "changes": [
    {
      "type": "addition",
      "clause_id": "clause-45",
      "clause_text": "Digital lending platforms must maintain comprehensive audit trails...",
      "section": "Section 5.3"
    },
    {
      "type": "deletion",
      "clause_id": "clause-12",
      "clause_text": "Previous KYC requirement...",
      "section": "Section 2.1"
    },
    {
      "type": "modification",
      "clause_id": "clause-8",
      "old_text": "Lenders must verify...",
      "new_text": "Lenders must comprehensively verify...",
      "section": "Section 1.4"
    }
  ],
  "side_by_side": {
    "old": [
      {"line": 1, "text": "Old clause 1", "status": "deleted"},
      {"line": 2, "text": "Same clause 2", "status": "unchanged"},
      {"line": 3, "text": "Old text", "status": "modified"}
    ],
    "new": [
      {"line": 1, "text": "Same clause 2", "status": "unchanged"},
      {"line": 2, "text": "New text", "status": "modified"},
      {"line": 3, "text": "New clause 3", "status": "added"}
    ]
  }
}
```

**Implementation needed:**
```python
@api_router.get("/regulations/{regulation_id}/diff")
async def get_regulation_diff(
    regulation_id: str,
    from_version: str,
    to_version: str,
    current_user: dict = Depends(get_current_user)
):
    # 1. Get both versions
    current_reg = await db.regulations.find_one({"id": regulation_id, "version": to_version})
    old_reg = await db.regulations.find_one({
        "$or": [
            {"id": regulation_id, "version": from_version},
            {"id": current_reg.get('previous_version_id')}  # If version chain
        ]
    })

    # 2. Compute diff
    from services.diff_service import compute_regulation_diff
    diff_result = await compute_regulation_diff(old_reg, current_reg)

    # 3. Generate AI summary
    from services.llm_service import generate_change_summary
    ai_summary = await generate_change_summary(diff_result)

    return {
        "regulation_id": regulation_id,
        "from_version": from_version,
        "to_version": to_version,
        "ai_summary": ai_summary,
        "changes": diff_result['changes'],
        "side_by_side": diff_result['side_by_side']
    }
```

#### 3. Diff Service (NEW FILE NEEDED)

**MISSING:** `backend/services/diff_service.py`

```python
async def compute_regulation_diff(old_reg: dict, new_reg: dict) -> dict:
    """
    Compute clause-by-clause diff between two regulation versions.
    Returns additions, deletions, modifications.
    """
    old_clauses = {c['clause_id']: c for c in old_reg.get('clauses', [])}
    new_clauses = {c['clause_id']: c for c in new_reg.get('clauses', [])}

    changes = []

    # Find additions (in new, not in old)
    for clause_id, clause in new_clauses.items():
        if clause_id not in old_clauses:
            changes.append({
                "type": "addition",
                "clause_id": clause_id,
                "clause_text": clause['clause_text'],
                "section": clause.get('section', 'Unknown')
            })

    # Find deletions (in old, not in new)
    for clause_id, clause in old_clauses.items():
        if clause_id not in new_clauses:
            changes.append({
                "type": "deletion",
                "clause_id": clause_id,
                "clause_text": clause['clause_text'],
                "section": clause.get('section', 'Unknown')
            })

    # Find modifications (in both but text changed)
    for clause_id in old_clauses.keys() & new_clauses.keys():
        old_text = old_clauses[clause_id]['clause_text']
        new_text = new_clauses[clause_id]['clause_text']

        if old_text != new_text:
            changes.append({
                "type": "modification",
                "clause_id": clause_id,
                "old_text": old_text,
                "new_text": new_text,
                "section": new_clauses[clause_id].get('section', 'Unknown'),
                "diff_inline": compute_inline_diff(old_text, new_text)
            })

    # Build side-by-side view
    side_by_side = build_side_by_side_view(old_clauses, new_clauses, changes)

    return {
        "changes": changes,
        "side_by_side": side_by_side
    }

def compute_inline_diff(old_text: str, new_text: str) -> list:
    """
    Compute word-level or character-level diff for inline view.
    Returns list of segments with type (unchanged, added, removed).
    """
    import difflib

    # Use difflib to get sequence matcher
    sm = difflib.SequenceMatcher(None, old_text, new_text)

    segments = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            segments.append({"type": "unchanged", "text": old_text[i1:i2]})
        elif tag == 'delete':
            segments.append({"type": "removed", "text": old_text[i1:i2]})
        elif tag == 'insert':
            segments.append({"type": "added", "text": new_text[j1:j2]})
        elif tag == 'replace':
            segments.append({"type": "removed", "text": old_text[i1:i2]})
            segments.append({"type": "added", "text": new_text[j1:j2]})

    return segments

def build_side_by_side_view(old_clauses: dict, new_clauses: dict, changes: list) -> dict:
    """
    Build side-by-side comparison view.
    """
    # Implementation to align old and new clauses
    # Return {"old": [...], "new": [...]}
    pass
```

#### 4. AI Summary Generation

**MISSING:** Extension to `backend/services/llm_service.py`

```python
async def generate_change_summary(diff_result: dict) -> str:
    """
    Generate AI summary of regulatory changes.
    """
    changes = diff_result['changes']

    # Count changes by type
    additions = [c for c in changes if c['type'] == 'addition']
    deletions = [c for c in changes if c['type'] == 'deletion']
    modifications = [c for c in changes if c['type'] == 'modification']

    # Build prompt
    prompt = f"""
    Analyze the following regulatory changes and provide a concise executive summary.

    Additions: {len(additions)} new clauses
    {chr(10).join([f"- {a['clause_text'][:100]}..." for a in additions[:3]])}

    Deletions: {len(deletions)} removed clauses
    {chr(10).join([f"- {d['clause_text'][:100]}..." for d in deletions[:3]])}

    Modifications: {len(modifications)} updated clauses
    {chr(10).join([f"- Old: {m['old_text'][:50]}... → New: {m['new_text'][:50]}..." for m in modifications[:3]])}

    Provide:
    1. What changed and why it matters (2-3 sentences)
    2. Impact on organizations (1-2 sentences)
    3. Key action items (bullet points)
    """

    # Call AI
    summary = await call_anthropic(prompt)

    return summary
```

---

### Frontend Implementation

#### 1. RegulationDetail.js - Add Versions Tab

**MISSING:** "Versions" tab in the Tabs component

Current tabs:
- Clauses
- Details

Need to add:
- **Versions** (show version history with diff links)

```javascript
<TabsList>
  <TabsTrigger value="clauses">Clauses ({clauses.length})</TabsTrigger>
  <TabsTrigger value="overview">Details</TabsTrigger>
  <TabsTrigger value="versions">Versions</TabsTrigger>  {/* NEW */}
</TabsList>

<TabsContent value="versions" className="mt-6">
  <VersionHistory regulationId={regulation.id} />
</TabsContent>
```

#### 2. VersionHistory Component (NEW FILE)

**MISSING:** `frontend/src/components/VersionHistory.js`

```javascript
import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Clock, GitCompare } from 'lucide-react';
import { toast } from 'sonner';

export default function VersionHistory({ regulationId }) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadVersions();
  }, [regulationId]);

  const loadVersions = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/regulations/${regulationId}/versions`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setVersions(data.versions || []);
    } catch (error) {
      toast.error('Failed to load version history');
    } finally {
      setLoading(false);
    }
  };

  const openDiffView = (fromVersion, toVersion) => {
    // Navigate to diff viewer or open dialog
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Version History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {versions.map((version, idx) => (
            <div key={version.version} className="flex items-center justify-between border rounded-lg p-4">
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant={version.is_current ? "default" : "outline"}>
                    v{version.version}
                  </Badge>
                  {version.is_current && <Badge variant="secondary">Current</Badge>}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {version.changes_summary}
                </p>
                <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {new Date(version.created_at).toLocaleDateString()}
                </div>
              </div>
              {idx > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => openDiffView(versions[idx - 1].version, version.version)}
                >
                  <GitCompare className="h-4 w-4 mr-1" />
                  Compare
                </Button>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

#### 3. DiffViewer Component (NEW FILE)

**MISSING:** `frontend/src/components/DiffViewer.js`

```javascript
import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';
import { Plus, Minus, Edit } from 'lucide-react';

export default function DiffViewer({ diffData }) {
  const [viewMode, setViewMode] = useState('side-by-side'); // or 'inline'

  const renderSideBySide = () => {
    return (
      <div className="grid grid-cols-2 gap-4">
        {/* Old version */}
        <div className="border rounded-lg p-4">
          <h3 className="font-semibold mb-3">Version {diffData.from_version}</h3>
          <div className="space-y-2">
            {diffData.side_by_side.old.map((line, idx) => (
              <div
                key={idx}
                className={`p-2 rounded ${
                  line.status === 'deleted' ? 'bg-red-50 border-l-4 border-red-500' :
                  line.status === 'modified' ? 'bg-yellow-50 border-l-4 border-yellow-500' :
                  'bg-gray-50'
                }`}
              >
                {line.text}
              </div>
            ))}
          </div>
        </div>

        {/* New version */}
        <div className="border rounded-lg p-4">
          <h3 className="font-semibold mb-3">Version {diffData.to_version}</h3>
          <div className="space-y-2">
            {diffData.side_by_side.new.map((line, idx) => (
              <div
                key={idx}
                className={`p-2 rounded ${
                  line.status === 'added' ? 'bg-green-50 border-l-4 border-green-500' :
                  line.status === 'modified' ? 'bg-yellow-50 border-l-4 border-yellow-500' :
                  'bg-gray-50'
                }`}
              >
                {line.text}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  const renderInline = () => {
    return (
      <div className="border rounded-lg p-4">
        <div className="space-y-2">
          {diffData.changes.map((change, idx) => (
            <div key={idx} className="border-l-4 p-3 rounded">
              {change.type === 'addition' && (
                <div className="border-l-green-500 bg-green-50">
                  <div className="flex items-center gap-2 mb-1">
                    <Plus className="h-4 w-4 text-green-600" />
                    <Badge variant="outline" className="bg-green-100 text-green-700">Added</Badge>
                    <span className="text-xs text-muted-foreground">{change.section}</span>
                  </div>
                  <p className="text-sm text-green-900">{change.clause_text}</p>
                </div>
              )}

              {change.type === 'deletion' && (
                <div className="border-l-red-500 bg-red-50">
                  <div className="flex items-center gap-2 mb-1">
                    <Minus className="h-4 w-4 text-red-600" />
                    <Badge variant="outline" className="bg-red-100 text-red-700">Removed</Badge>
                    <span className="text-xs text-muted-foreground">{change.section}</span>
                  </div>
                  <p className="text-sm text-red-900 line-through">{change.clause_text}</p>
                </div>
              )}

              {change.type === 'modification' && (
                <div className="border-l-yellow-500 bg-yellow-50">
                  <div className="flex items-center gap-2 mb-1">
                    <Edit className="h-4 w-4 text-yellow-600" />
                    <Badge variant="outline" className="bg-yellow-100 text-yellow-700">Modified</Badge>
                    <span className="text-xs text-muted-foreground">{change.section}</span>
                  </div>
                  <p className="text-sm text-red-700 line-through mb-1">{change.old_text}</p>
                  <p className="text-sm text-green-700">{change.new_text}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* AI Summary */}
      {diffData.ai_summary && (
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="pt-4">
            <h3 className="font-semibold mb-2">AI Summary of Changes</h3>
            <p className="text-sm text-gray-700">{diffData.ai_summary}</p>
          </CardContent>
        </Card>
      )}

      {/* View Mode Tabs */}
      <div className="flex justify-end gap-2">
        <Button
          variant={viewMode === 'side-by-side' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setViewMode('side-by-side')}
        >
          Side-by-Side
        </Button>
        <Button
          variant={viewMode === 'inline' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setViewMode('inline')}
        >
          Inline
        </Button>
      </div>

      {/* Diff View */}
      {viewMode === 'side-by-side' ? renderSideBySide() : renderInline()}
    </div>
  );
}
```

---

## Implementation Complexity Breakdown

### Backend (3-4 hours)
1. **Get versions endpoint** - 30 minutes
2. **Get diff endpoint** - 1 hour
3. **Diff service** - 1.5 hours (clause matching, text diff, side-by-side builder)
4. **AI summary** - 30 minutes (extend llm_service)
5. **Testing** - 30 minutes

### Frontend (2-3 hours)
1. **VersionHistory component** - 45 minutes
2. **DiffViewer component** - 1.5 hours (side-by-side layout, inline view, styling)
3. **Integration with RegulationDetail** - 30 minutes
4. **Testing** - 30 minutes

### Total: 5-7 hours

---

## Recommended Implementation Order

1. **Backend first:**
   - Create diff_service.py with compute_regulation_diff()
   - Add GET /regulations/{id}/versions endpoint
   - Add GET /regulations/{id}/diff endpoint
   - Extend llm_service with generate_change_summary()

2. **Frontend second:**
   - Create VersionHistory component
   - Create DiffViewer component
   - Add Versions tab to RegulationDetail
   - Wire up API calls

3. **Testing:**
   - Create test regulations with multiple versions
   - Verify diff accuracy
   - Test side-by-side and inline views
   - Verify AI summaries

---

## Why Skipped in This Session

**Reasons:**
1. **Complexity**: 5-7 hours of implementation
2. **Sandbox limitations**: Cannot run Docker/MongoDB to test
3. **Time constraints**: Already completed 2 features (198, 56)
4. **Dependencies**: Requires text diff library (difflib), AI integration
5. **Testing requirements**: Needs multiple regulation versions in DB

**Recommendation:** Implement in dedicated session with:
- Full development environment (Docker + MongoDB)
- Access to test data (regulations with version history)
- AI API keys for summary generation
- 6-8 hour time block

---

## Conclusion

Feature #35 requires substantial implementation across:
- Backend: 2 new endpoints + diff service
- Frontend: 2 new components + tab integration
- AI: Summary generation

**Status:** Feature analysis complete, implementation needed

**Next steps:** Schedule dedicated session for implementation with full environment access.
