# REGRESSION REPORT - Infrastructure Features 2 & 3

**Date**: 2026-02-07
**Tester**: Testing Agent
**Features Affected**: #2 (Database schema/collections), #3 (Data persistence)

## SUMMARY

Critical regression found in MongoDB integration. The backend server cannot write data to MongoDB due to missing authentication credentials in the connection string.

## FAILED FEATURES

### Feature #2: Database schema/collections applied correctly
- **Status**: ❌ FAILING
- **Expected**: MongoDB database "compli-ai" exists with 25+ collections
- **Actual**: Database "compli-ai" does NOT exist in MongoDB

### Feature #3: Data persists across server restart
- **Status**: ❌ FAILING (Cannot verify - prerequisite failed)
- **Expected**: User data persists after server restart
- **Actual**: Cannot test because database doesn't exist

## ROOT CAUSE

**Authentication Mismatch:**

1. **Docker Compose Configuration** (`docker-compose.yml`):
   - MongoDB configured with authentication:
     ```yaml
     MONGO_INITDB_ROOT_USERNAME: admin
     MONGO_INITDB_ROOT_PASSWORD: compliai123
     ```

2. **Backend Configuration** (`.env` - BEFORE FIX):
   - Connection string missing credentials:
     ```
     MONGO_URL=mongodb://localhost:27017
     ```

3. **Result**:
   - Health endpoint passes (admin ping doesn't require auth for connection test)
   - Application appears functional
   - But writes to database FAIL SILENTLY
   - No collections are created
   - User registration appears to work but data is NOT saved

## EVIDENCE

1. **Health Endpoint** (`GET /api/health`):
   ```json
   {
     "status": "healthy",
     "mongodb_status": "connected",  ← Misleading! Ping works but writes don't
     "mongodb_version": "6.0.20",
     "qdrant_status": "connected"
   }
   ```

2. **Mongo Express UI**:
   - Only shows default databases: admin, config, local
   - "compli-ai" database NOT found
   - Screenshot: `mongo-express-databases.png`

3. **User Registration Test**:
   - Registered user: `RESTART_TEST_12345@test.com`
   - Registration appeared successful (no error)
   - But checking MongoDB: **NO users collection exists**
   - Data was NOT persisted

4. **Qdrant Status**:
   - ✓ Qdrant collections exist: `policy_clauses`, `regulation_clauses`
   - Qdrant works because it has no authentication configured

## FIX APPLIED

Updated `/backend/.env`:

```diff
- MONGO_URL=mongodb://localhost:27017
+ MONGO_URL=mongodb://admin:compliai123@localhost:27017
```

## VERIFICATION REQUIRED

**After server restart**, verify:

1. Check health endpoint still reports connected
2. Navigate to Mongo Express: http://localhost:8081 (admin/admin123)
3. Verify "compli-ai" database now exists
4. Register a new test user
5. Verify user appears in MongoDB `users` collection
6. Restart server
7. Verify user still exists (persistence test)

## IMPACT ASSESSMENT

**Severity**: 🔴 CRITICAL

- All user registrations since deployment have FAILED silently
- No data is being persisted to MongoDB
- Application appears functional but is non-functional for data storage
- Qdrant (vector database) is working, but MongoDB (primary database) is not

## RECOMMENDED ACTIONS

1. ✅ **DONE**: Fixed `.env` configuration
2. 🔄 **TODO**: Restart backend server to apply fix
3. 🔄 **TODO**: Re-run Feature #2 verification
4. 🔄 **TODO**: Re-run Feature #3 verification
5. 🔄 **TODO**: Check for any existing users and determine if data recovery is needed

## FILES MODIFIED

- `/backend/.env` - Added MongoDB credentials to MONGO_URL
- `/backend/test_mongodb_auth.py` - Created diagnostic script
- `REGRESSION_REPORT.md` - This file

---

**Next Steps**: Restart the server and re-test Features #2 and #3.
