# CompliAI - Complete Rebuild Plan
## Based on OnFinance AI Standards

### Phase 1: Fix Critical UI Issues ✓
**Issues Identified:**
1. Layout height conflict (`h-screen` causing overlap)
2. Gap Analysis fading (likely z-index/opacity issues)
3. Poor spacing and contrast

**Fixes:**
- Remove fixed height constraints
- Fix z-index layering
- Improve color contrast
- Add proper padding/margins

### Phase 2: Backend Architecture Enhancement
**New Models Needed:**
1. Department (name, head, members)
2. Regulator (name, type, circulars)
3. MasterCircular (with chapters/subclauses)
4. CircularVersion (version control)
5. Evidence (with AI scoring)
6. AuditControl (audit framework)
7. ComplianceCalendar (recurring obligations)

**New Services:**
1. Multi-LLM Service (Claude/GPT/Gemini)
2. Evidence Scoring Service
3. Audit Engine Service
4. Version Control Service
5. MIS Generation Service

**New API Endpoints:**
- `/api/regulators` - CRUD
- `/api/master-circulars` - With chapters
- `/api/evidence/test` - AI scoring
- `/api/audit/run` - Audit execution
- `/api/audit/controls` - Control management
- `/api/calendar` - Compliance calendar
- `/api/departments` - Department management
- `/api/circulars/{id}/versions` - Version history
- `/api/circulars/{id}/diff` - Show differences
- `/api/chat` - NeoGPT-style chat

### Phase 3: Frontend Redesign
**New Pages:**
1. Regulators page (SEBI, RBI, NSE, BSE tabs)
2. Master Circulars page (with chapters)
3. Circular Detail page (with version control)
4. Evidence Testing page
5. Audit page (setup, run, results)
6. Compliance Calendar page
7. Departments page
8. Chat Interface (NeoGPT)

**Dashboard Redesign:**
- Donut charts for compliance status
- Department drill-down cards
- Regulator-level overview table
- Key metrics cards
- Compliance score visualization

**UI Components:**
- Version diff viewer
- Evidence upload with instant scoring
- Audit control table
- Compliance calendar grid
- Department hierarchy view
- Radial charts for audit scores

### Phase 4: AI Integration Strategy
**Use Claude Sonnet 4 for:**
- Regulatory circular analysis
- Clause interpretation
- Impact assessment
- Legal reasoning

**Use GPT-4o-mini for:**
- Task generation
- Quick summaries
- Actionable item creation

**Use Gemini 2.5 Flash for:**
- Evidence evaluation (multimodal)
- Document comparison
- PDF analysis

**Prompt Engineering:**
- Regulatory Analysis Prompt (Claude)
- Evidence Scoring Prompt (Gemini)
- Task Generation Prompt (GPT)
- Audit Control Evaluation Prompt (Claude)

### Phase 5: Testing Strategy
1. Unit tests for each service
2. Integration tests for AI workflows
3. E2E tests for complete user journeys
4. Performance tests for LLM response times
5. UI responsiveness tests

### Implementation Order:
1. Fix UI issues (30 min)
2. Backend models & DB (1 hour)
3. Multi-LLM service (1 hour)
4. Evidence & Audit services (1 hour)
5. New API endpoints (2 hours)
6. Frontend components (2 hours)
7. Dashboard redesign (1 hour)
8. New pages (2 hours)
9. Testing (1 hour)

**Total Estimated Time: 11.5 hours**

### Success Criteria:
✓ No UI overlapping or fading
✓ All OnFinance features implemented
✓ Multi-LLM integration working
✓ Evidence scoring functional
✓ Audit workflow complete
✓ Version control with diff viewer
✓ Department-wise views
✓ Compliance calendar
✓ 100% test coverage
