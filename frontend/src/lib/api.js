import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_URL}/api`,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for handling errors globally
// Features #127, #128, #130 - Network and server error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Feature #127 - Network failure (no response from server)
    if (!error.response) {
      // Network error - server unreachable
      window.dispatchEvent(
        new CustomEvent('network-error', {
          detail: {
            message: 'Unable to connect to server. Please check your network connection and try again.',
          },
        })
      );
      // Add user-friendly message to error object
      error.userMessage = 'Unable to connect to server. Please check your connection.';
    } else if (error.response.status >= 500) {
      // Feature #128 - Server error (500, 502, 503, etc.)
      const serverMsg = error.response.data?.message || error.response.data?.detail || 'The server encountered an error. Please try again later.';
      window.dispatchEvent(
        new CustomEvent('server-error', {
          detail: {
            message: `Server Error: ${serverMsg}`,
          },
        })
      );
      error.userMessage = serverMsg;
    } else if (error.response.status === 401) {
      // Feature #99 - Token expired or invalid - auto logout
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      // Redirect to login page
      window.location.href = '/login';
    } else if (error.response.status === 403) {
      // Feature #98 - Forbidden access
      error.userMessage = 'You do not have permission to perform this action.';
    } else if (error.response.status === 404) {
      // Resource not found
      error.userMessage = error.response.data?.message || 'The requested resource was not found.';
    } else if (error.response.status === 413) {
      // Payload too large - file size limit exceeded
      error.userMessage = error.response.data?.detail || 'File too large. Maximum file size is 50MB.';
    } else if (error.response.status === 400) {
      // Bad request - validation errors
      error.userMessage = error.response.data?.message || error.response.data?.detail || 'Invalid request. Please check your input.';
    }

    return Promise.reject(error);
  }
);

export const policiesApi = {
  getAll: () => api.get('/policies').then(r => r.data),
  getById: (id) => api.get(`/policies/${id}`).then(r => r.data),
  update: (id, data) => api.put(`/policies/${id}`, data).then(r => r.data),
  delete: (id) => api.delete(`/policies/${id}`).then(r => r.data),
  bulkDelete: (ids) => api.delete('/policies/bulk', { data: ids }).then(r => r.data),
  submitForReview: (id) => api.post(`/policies/${id}/submit-review`).then(r => r.data),
  approve: (id, decision) => api.post(`/policies/${id}/approve`, decision).then(r => r.data),
  addClause: (policyId, clauseData) => api.post(`/policies/${policyId}/clauses`, clauseData).then(r => r.data),
  updateClause: (policyId, clauseId, data) => api.put(`/policies/${policyId}/clauses/${clauseId}`, data).then(r => r.data),
  deleteClause: (policyId, clauseId) => api.delete(`/policies/${policyId}/clauses/${clauseId}`).then(r => r.data),
  linkRegulation: (policyId, regulationId) => api.post(`/policies/${policyId}/link-regulation`, { regulation_id: regulationId }).then(r => r.data),
  unlinkRegulation: (policyId, regulationId) => api.delete(`/policies/${policyId}/link-regulation/${regulationId}`).then(r => r.data),
  getVersions: (id) => api.get(`/policies/${id}/versions`).then(r => r.data),
  compareVersions: (id, versionId) => api.get(`/policies/${id}/versions/${versionId}/diff`).then(r => r.data),
  upload: (file, data, onUploadProgress) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('policy_data', JSON.stringify(data));
    return api.post('/policies/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onUploadProgress || undefined,
      timeout: 300000, // 5 minutes for large files
    }).then(r => r.data);
  },
};

export const regulationsApi = {
  getAll: (regulator, includeNpci) => api.get('/regulations', { params: { regulator, include_npci: includeNpci || undefined } }).then(r => r.data),
  getById: (id) => api.get(`/regulations/${id}`).then(r => r.data),
  getVersions: (id) => api.get(`/regulations/${id}/versions`).then(r => r.data),
  compareVersions: (id, compareId) => api.get(`/regulations/${id}/diff/${compareId}`).then(r => r.data),
  upload: (file, data, onUploadProgress) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('regulation_data', JSON.stringify(data));
    return api.post('/regulations/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onUploadProgress || undefined,
      timeout: 300000, // 5 minutes for large files
    }).then(r => r.data);
  },
  parseFilename: (filename) => api.post('/regulations/parse-filename', { filename }).then(r => r.data),
  triggerCrawl: () => api.post('/regulations/trigger-crawl').then(r => r.data),
  getCrawlStatus: () => api.get('/regulations/crawl-status').then(r => r.data),
};

export const gapAnalysisApi = {
  run: (policyId, regulationId, analysisMode = 'deep_analysis') => api.post(`/gap-analysis/run?policy_id=${policyId}&regulation_id=${regulationId}&analysis_mode=${analysisMode}`).then(r => r.data),
  runStream: (policyId, regulationId, analysisMode = 'deep_analysis', onProgress) => {
    return new Promise((resolve, reject) => {
      const token = localStorage.getItem('token');

      // Feature #130 - Timeout handling for AI operations
      // Set a 15-minute timeout for gap analysis operations (LLM calls can be slow with many clauses)
      const TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes
      const MAX_RETRIES = 3;
      let timeoutId;
      let isResolved = false;
      let retryCount = 0;
      let lastProgress = 0;

      const cleanup = () => {
        if (timeoutId) clearTimeout(timeoutId);
        isResolved = true;
      };

      const resetTimeout = () => {
        if (timeoutId) clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
          if (!isResolved) {
            cleanup();
            const timeoutError = new Error('Gap analysis operation timed out after 15 minutes. Please try with a smaller policy or contact support.');
            timeoutError.userMessage = 'Operation timed out. This policy may be too large to analyze. Please try again or contact support.';
            reject(timeoutError);
          }
        }, TIMEOUT_MS);
      };

      resetTimeout();

      const startStream = () => {
        fetch(`${API_URL}/api/gap-analysis/run-stream?policy_id=${policyId}&regulation_id=${regulationId}&analysis_mode=${analysisMode}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'text/event-stream',
          },
        }).then(async response => {
          if (!response.ok) {
            throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
          }
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            if (isResolved) break;

            const { done, value } = await reader.read();
            if (done) {
              // Stream ended without 'done' event — might be a disconnection
              if (!isResolved) {
                // If we got significant progress, the backend might still be running.
                // The result may have been lost in transit. Check if it completed via history.
                if (lastProgress >= 80) {
                  console.warn('Stream ended near completion, attempting to fetch result from history...');
                  try {
                    // Wait a few seconds for backend to finish saving
                    await new Promise(r => setTimeout(r, 3000));
                    const history = await gapAnalysisApi.getHistory();
                    const recent = history?.[0];
                    if (recent && recent.policy_id === policyId && recent.regulation_id === regulationId) {
                      const detail = await gapAnalysisApi.getById(recent.id);
                      cleanup();
                      resolve(detail);
                      return;
                    }
                  } catch (histErr) {
                    console.warn('Failed to fetch result from history:', histErr);
                  }
                }
                // If low progress, retry the stream
                if (retryCount < MAX_RETRIES && lastProgress < 80) {
                  retryCount++;
                  console.warn(`Stream disconnected at ${lastProgress}% (retry ${retryCount}/${MAX_RETRIES})`);
                  if (onProgress) {
                    onProgress({ step: 'reconnecting', progress: lastProgress, message: `Connection lost, reconnecting (attempt ${retryCount}/${MAX_RETRIES})...`, details: {} });
                  }
                  setTimeout(startStream, 2000 * retryCount);
                  return;
                }
                // Out of retries
                cleanup();
                reject(new Error('Stream disconnected unexpectedly. The analysis may still be running — check history in a minute.'));
              }
              break;
            }

            // Reset timeout on any data received (connection is alive)
            resetTimeout();

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.step === 'done') {
                    cleanup();
                    resolve(data.result);
                    return;
                  } else if (data.error) {
                    cleanup();
                    const error = new Error(data.message);
                    error.userMessage = data.message || 'An error occurred during gap analysis.';
                    reject(error);
                    return;
                  } else if (onProgress && !isResolved) {
                    if (data.progress) lastProgress = data.progress;
                    onProgress(data);
                  }
                } catch (e) {
                  console.warn('Failed to parse SSE data:', line);
                }
              }
            }
          }
        }).catch(err => {
          if (!isResolved) {
            if (retryCount < MAX_RETRIES) {
              retryCount++;
              console.warn(`Stream fetch failed (retry ${retryCount}/${MAX_RETRIES}):`, err.message);
              if (onProgress) {
                onProgress({ step: 'reconnecting', progress: lastProgress, message: `Connection error, reconnecting (attempt ${retryCount}/${MAX_RETRIES})...`, details: {} });
              }
              setTimeout(startStream, 2000 * retryCount);
            } else {
              cleanup();
              reject(err);
            }
          }
        });
      };

      startStream();
    });
  },
  getHistory: () => api.get('/gap-analysis/history').then(r => r.data),
  getById: (id) => api.get(`/gap-analysis/${id}`).then(r => r.data),
  getSourceReference: (analysisId, gapIndex) => api.get(`/gap-analysis/${analysisId}/source-reference/${gapIndex}`).then(r => r.data),
  getAll: () => api.get('/gap-analysis/history').then(r => r.data),
  exportReport: (analysisId, format) => api.get(`/gap-analysis/${analysisId}/export`, {
    params: { format },
    responseType: 'blob'
  }).then(r => r),
  // Feature #40: Human-in-the-loop corrections
  correctGap: (analysisId, gapIndex, data) => api.post(`/gap-analysis/${analysisId}/gaps/${gapIndex}/correct`, data).then(r => r.data),
  getGapCorrections: (analysisId, gapIndex) => api.get(`/gap-analysis/${analysisId}/gaps/${gapIndex}/corrections`).then(r => r.data),
};

export const tasksApi = {
  getAll: (params) => api.get('/tasks', { params }).then(r => r.data),
  getStats: () => api.get('/tasks/stats').then(r => r.data),
  getById: (id) => api.get(`/tasks/${id}`).then(r => r.data),
  create: (data) => api.post('/tasks', data).then(r => r.data),
  update: (id, data) => api.put(`/tasks/${id}`, data).then(r => r.data),
  delete: (id) => api.delete(`/tasks/${id}`).then(r => r.data),
  updateStatus: (id, status, notes) => api.patch(`/tasks/${id}/status`, null, { params: { status, notes } }).then(r => r.data),
  assign: (id, userId) => api.post(`/tasks/${id}/assign`, { user_id: userId }).then(r => r.data),
  startTimer: (id) => api.post(`/tasks/${id}/timer/start`).then(r => r.data),
  stopTimer: (id) => api.post(`/tasks/${id}/timer/stop`).then(r => r.data),
  addEvidence: (id, evidenceId) => api.post(`/tasks/${id}/evidence`, null, { params: { evidence_id: evidenceId } }).then(r => r.data),
  submitForReview: (id, notes) => api.post(`/tasks/${id}/submit-review`, { notes }).then(r => r.data),
  approve: (id, approved, notes) => api.post(`/tasks/${id}/approve`, { approved, notes }).then(r => r.data),
  getComments: (id) => api.get(`/tasks/${id}/comments`).then(r => r.data),
  addComment: (id, content) => api.post(`/tasks/${id}/comments`, { content }).then(r => r.data),
  getTimeline: (id) => api.get(`/tasks/${id}/timeline`).then(r => r.data),
  getPendingReminders: () => api.get('/tasks/reminders/pending').then(r => r.data),
  getDependencies: (id) => api.get(`/tasks/${id}/dependencies`).then(r => r.data),
  addDependency: (id, data) => api.post(`/tasks/${id}/dependencies`, data).then(r => r.data),
  removeDependency: (id, depId) => api.delete(`/tasks/${id}/dependencies/${depId}`).then(r => r.data),
  getDependencyGraph: (id) => api.get(`/tasks/${id}/dependency-graph`).then(r => r.data),
  bulkCreate: (tasks) => api.post('/tasks/bulk-create', tasks).then(r => r.data),
  bulkAssign: (taskIds, memberId, memberName, departmentId, departmentName) =>
    api.post('/tasks/bulk-assign', { task_ids: taskIds, member_id: memberId, member_name: memberName, department_id: departmentId, department_name: departmentName }).then(r => r.data),
};

export const departmentsApi = {
  getAll: () => api.get('/departments').then(r => r.data),
  create: (data) => api.post('/departments', data).then(r => r.data),
  update: (id, data) => api.put(`/departments/${id}`, data).then(r => r.data),
  delete: (id) => api.delete(`/departments/${id}`).then(r => r.data),
  getMembers: (deptId) => api.get(`/departments/${deptId}/members`).then(r => r.data),
  getAllMembers: () => api.get('/department-members').then(r => r.data),
  addMember: (deptId, memberData) => api.post(`/departments/${deptId}/members`, memberData).then(r => r.data),
  removeMember: (deptId, memberId) => api.delete(`/departments/${deptId}/members/${memberId}`).then(r => r.data),
};

export const chartersApi = {
  getAll: () => api.get('/charters').then(r => r.data),
  getById: (id) => api.get(`/charters/${id}`).then(r => r.data),
  create: (data) => api.post('/charters', data).then(r => r.data),
  update: (id, data) => api.put(`/charters/${id}`, data).then(r => r.data),
  delete: (id) => api.delete(`/charters/${id}`).then(r => r.data),
};

// --- Organization Profile API ---
export const organizationApi = {
  getProfile: () => api.get('/organization/profile').then(r => r.data),
  updateProfile: (data) => api.put('/organization/profile', data).then(r => r.data),
  createProfile: (data) => api.post('/organization/profile', data).then(r => r.data),
  getEntityScope: () => api.get('/organization/profile/entity-scope').then(r => r.data),
  updatePersonnel: (personnel) => api.put('/organization/profile/personnel', personnel).then(r => r.data),
  updateLicense: (data) => api.put('/organization/profile/license', data).then(r => r.data),
  getLicenseTimeline: () => api.get('/organization/profile/license-timeline').then(r => r.data),
  getProfileHistory: (limit = 50) => api.get('/organization/profile/history', { params: { limit } }).then(r => r.data),
};

// --- Requirement Mapping API ---
export const requirementsApi = {
  getCatalog: () => api.get('/requirements/catalog').then(r => r.data),
  getByEntity: (entityType) => api.get(`/requirements/catalog/by-entity/${entityType}`).then(r => r.data),
  getForRegulation: (regulationId, params = {}) => api.get(`/requirements/${regulationId}`, { params }).then(r => r.data),
  getStats: (regulationId) => api.get(`/requirements/${regulationId}/stats`).then(r => r.data),
  runMapping: (regulationId, policyId, entityType = 'all') =>
    api.post('/requirements/map', null, { params: { regulation_id: regulationId, policy_id: policyId, entity_type: entityType } }).then(r => r.data),
  getMappingHistory: (params = {}) => api.get('/requirement-maps/history', { params }).then(r => r.data),
  getMappingById: (mapId) => api.get(`/requirement-maps/${mapId}`).then(r => r.data),
};

// --- Batch Upload API ---
export const batchUploadApi = {
  uploadRegulations: (files) => {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    return api.post('/regulations/batch-upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data);
  },
  uploadPolicies: (files) => {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    return api.post('/policies/batch-upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data);
  },
  getStatus: (batchId) => api.get(`/batch-uploads/${batchId}`).then(r => r.data),
  cancel: (batchId) => api.post(`/batch-uploads/${batchId}/cancel`).then(r => r.data),
  getHistory: () => api.get('/batch-uploads/history').then(r => r.data),
};

export const evidenceApi = {
  getAll: () => api.get('/evidence').then(r => r.data),
  getById: (id) => api.get(`/evidence/${id}`).then(r => r.data),
  getAuditLog: (id) => api.get(`/evidence/${id}/audit-log`).then(r => r.data),
  upload: (formData) => {
    return api.post('/evidence/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(r => r.data);
  },
  test: (id, requirement) => api.post(`/evidence/${id}/test`, { requirement }).then(r => r.data),
  validate: (id) => api.post(`/evidence/${id}/validate`).then(r => r.data),
  approve: (id, decision) => api.post(`/evidence/${id}/approve`, decision).then(r => r.data),
  override: (id, data) => api.post(`/evidence/${id}/override`, data).then(r => r.data),
};

export const checklistApi = {
  getAll: () => api.get('/checklists').then(r => r.data),
  getById: (id) => api.get(`/checklists/${id}`).then(r => r.data),
  generate: (data) => api.post('/checklists/generate', data).then(r => r.data),
  updateItem: (checklistId, itemId, data) => api.put(`/checklists/${checklistId}/items/${itemId}`, data).then(r => r.data),
  delete: (id) => api.delete(`/checklists/${id}`).then(r => r.data),
};

export const auditApi = {
  getSessions: () => api.get('/audit/sessions').then(r => r.data),
  getById: (id) => api.get(`/audit/sessions/${id}`).then(r => r.data),
  create: (data) => api.post('/audit/create', data).then(r => r.data),
  run: (id) => api.post(`/audit/${id}/run`).then(r => r.data),
  signOff: (id, data) => api.post(`/audit/${id}/sign-off`, data).then(r => r.data),
  exportReport: (id) => api.post(`/audit/${id}/export`).then(r => r.data),
  getArtefactStatus: (id) => api.get(`/audit/${id}/artefact-status`).then(r => r.data),
};

export const calendarApi = {
  getEvents: () => api.get('/calendar/events').then(r => r.data),
  createEvent: (data) => api.post('/calendar/events', data).then(r => r.data),
  updateEvent: (id, data) => api.put(`/calendar/events/${id}`, data).then(r => r.data),
  deleteEvent: (id) => api.delete(`/calendar/events/${id}`).then(r => r.data),
};

export const losLmsApi = {
  analyze: (data) => api.post('/los-lms/analyze', data).then(r => r.data),
  upload: (formData) => api.post('/los-lms/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data),
  getUploads: () => api.get('/los-lms/uploads').then(r => r.data),
  scan: (uploadId) => api.post(`/los-lms/${uploadId}/scan`).then(r => r.data),
  suggestMapping: (columns) => api.post('/los-lms/suggest-mapping', { columns }).then(r => r.data),
  saveMapping: (mappingName, fieldMappings) => api.post('/los-lms/save-mapping', { mapping_name: mappingName, field_mappings: fieldMappings }).then(r => r.data),
  getMappings: () => api.get('/los-lms/mappings').then(r => r.data),
};

export const chatApi = {
  sendMessage: (sessionId, content) => api.post('/chat', { session_id: sessionId, content }).then(r => r.data),
  getThreads: () => api.get('/chat/threads').then(r => r.data),
  getThread: (sessionId) => api.get(`/chat/threads/${sessionId}`).then(r => r.data),
  search: (q) => api.get('/chat/search', { params: { q } }).then(r => r.data),
  getInsights: () => api.get('/chat/insights').then(r => r.data),
};

export const notificationsApi = {
  getAll: () => api.get('/notifications').then(r => r.data),
  markRead: (id) => api.post(`/notifications/${id}/read`).then(r => r.data),
  markAllRead: () => api.post('/notifications/mark-all-read').then(r => r.data),
  getPreferences: () => api.get('/notifications/preferences').then(r => r.data),
  updatePreferences: (prefs) => api.put('/notifications/preferences', prefs).then(r => r.data),
  getUnreadCount: () => api.get('/notifications/unread-count').then(r => r.data),
};

export const analyticsApi = {
  getComplianceScore: () => api.get('/analytics/compliance-score').then(r => r.data),
  getSlaPerformance: () => api.get('/analytics/sla-performance').then(r => r.data),
  getGapsHeatmap: () => api.get('/analytics/gaps-heatmap').then(r => r.data),
  getEvidenceProgress: () => api.get('/analytics/evidence-progress').then(r => r.data),
  getRegulationCoverage: () => api.get('/analytics/regulation-coverage').then(r => r.data),
  exportReport: (format) => api.get('/analytics/export', {
    params: { format },
    responseType: 'blob'
  }).then(r => r),
};

export const dashboardApi = {
  getStats: () => api.get('/dashboard/stats').then(r => r.data),
};

export const uploadJobsApi = {
  getAll: (includeCompleted = true, limit = 20) =>
    api.get('/upload-jobs', { params: { include_completed: includeCompleted, limit } }).then(r => r.data),
  getActive: () => api.get('/upload-jobs/active').then(r => r.data),
  getById: (id) => api.get(`/upload-jobs/${id}`).then(r => r.data),
  cancel: (id) => api.post(`/upload-jobs/${id}/cancel`).then(r => r.data),
  delete: (id) => api.delete(`/upload-jobs/${id}`).then(r => r.data),
  clearCompleted: () => api.delete('/upload-jobs').then(r => r.data),
};

export const llmApi = {
  getStatus: () => api.get('/llm/status').then(r => r.data),
  setMode: (mode) => api.post('/llm/mode', { mode }).then(r => r.data),
  getCostSummary: () => api.get('/llm/cost-summary').then(r => r.data),
  // Feature #213: Settings-based LLM mode endpoints
  getSettingsMode: () => api.get('/settings/llm-mode').then(r => r.data),
  setSettingsMode: (mode) => api.post('/settings/llm-mode', { mode }).then(r => r.data),
};

// Feature #218: NPCI Circulars API
// Feature #220: Added schedule endpoints
export const npciApi = {
  getStats: () => api.get('/npci/stats').then(r => r.data),
  getProducts: () => api.get('/npci/products').then(r => r.data),
  getCirculars: (params) => api.get('/npci/circulars', { params }).then(r => r.data),
  getCircular: (id) => api.get(`/npci/circulars/${id}`).then(r => r.data),
  processCircular: (id) => api.post(`/npci/circulars/${id}/process`).then(r => r.data),
  getScrapeStatus: () => api.get('/npci/scrape/status').then(r => r.data),
  // Feature #220: Schedule endpoints
  getSchedule: () => api.get('/npci/schedule').then(r => r.data),
  updateSchedule: (config) => api.put('/npci/schedule', config).then(r => r.data),
  toggleSchedule: (enabled) => api.post('/npci/schedule/toggle', { enabled }).then(r => r.data),
  triggerSchedule: () => api.post('/npci/schedule/trigger').then(r => r.data),
  getScheduleStatus: () => api.get('/npci/schedule/status').then(r => r.data),
  // Convert processed circulars to full regulation records
  convertToRegulations: () => api.post('/npci/circulars/convert-to-regulations', {}, { timeout: 600000 }),
  // Demo Point #2: Required Evidences rollup per circular
  getEvidenceRollup: (id) => api.get(`/npci/circulars/${id}/evidences`).then(r => r.data),
};

// Demo Point #3: Device Binding & RASP Advisor
export const deviceBindingApi = {
  getReport: (organization = 'system', includeSummary = true) =>
    api.get('/npci/device-binding-advisor', {
      params: { organization, include_summary: includeSummary },
      timeout: 60000, // LLM summary can take a few seconds
    }).then(r => r.data),
};

// PA/PG Compliance APIs
export const complianceApi = {
  getOverview: () => api.get('/compliance/overview').then(r => r.data),
  getScore: (analysisId) => api.get(`/compliance/score/${analysisId}`).then(r => r.data),
  getTrend: () => api.get('/compliance/trend').then(r => r.data),
  getCategoryBreakdown: (analysisId) => api.get(`/compliance/category-breakdown/${analysisId}`).then(r => r.data),
  getDeadlines: () => api.get('/compliance/deadlines').then(r => r.data),
  getComprehensiveChecks: () => api.get('/compliance-checks/comprehensive').then(r => r.data),
};

export const remediationApi = {
  getList: (analysisId) => api.get(`/remediation/${analysisId}`).then(r => r.data),
  createTasks: (analysisId, maxTasks) => api.post(`/remediation/${analysisId}/create-tasks`, null, { params: { max_tasks: maxTasks } }).then(r => r.data),
};

export const policyDraftApi = {
  generate: (data) => api.post('/policy-drafts/generate', data).then(r => r.data),
  list: () => api.get('/policy-drafts').then(r => r.data),
  get: (id) => api.get(`/policy-drafts/${id}`).then(r => r.data),
  updateStatus: (id, status) => api.put(`/policy-drafts/${id}/status`, { status }).then(r => r.data),
  generateSOP: (reqId, regulationId) => api.post(`/policy-drafts/sop/${reqId}`, { regulation_id: regulationId }).then(r => r.data),
};

export const sopTemplateApi = {
  list: (params) => api.get('/sop-templates', { params }).then(r => r.data),
  get: (key) => api.get(`/sop-templates/${key}`).then(r => r.data),
  instantiate: (key, customizations) => api.post(`/sop-templates/${key}/instantiate`, customizations).then(r => r.data),
  generateCustom: (data) => api.post('/sop-templates/generate-custom', data).then(r => r.data),
};

export const approvalApi = {
  create: (data) => api.post('/approvals/create', data).then(r => r.data),
  decide: (id, decision, comments) => api.post(`/approvals/${id}/decide`, { decision, comments }).then(r => r.data),
  get: (id) => api.get(`/approvals/${id}`).then(r => r.data),
  listPending: (role) => api.get('/approvals/pending/list', { params: { role } }).then(r => r.data),
  getDocumentHistory: (docId) => api.get(`/approvals/document/${docId}/history`).then(r => r.data),
};

export const policyVersionApi = {
  create: (draftId, data) => api.post(`/policy-versions/${draftId}/create`, data).then(r => r.data),
  list: (draftId) => api.get(`/policy-versions/${draftId}`).then(r => r.data),
  get: (versionId) => api.get(`/policy-versions/detail/${versionId}`).then(r => r.data),
  compare: (a, b) => api.post('/policy-versions/compare', { version_id_a: a, version_id_b: b }).then(r => r.data),
  rollback: (draftId, versionId) => api.post(`/policy-versions/${draftId}/rollback`, { version_id: versionId }).then(r => r.data),
};

export const gapReportApi = {
  get: (analysisId) => api.get(`/gap-reports/${analysisId}`).then(r => r.data),
  generate: (analysisId) => api.post(`/gap-reports/${analysisId}/generate`).then(r => r.data),
  list: () => api.get('/gap-reports').then(r => r.data),
};

export const auditTrailApi = {
  get: (params) => api.get('/audit-trail', { params }).then(r => r.data),
  getResourceHistory: (type, id) => api.get(`/audit-trail/resource/${type}/${id}`).then(r => r.data),
  getUserActivity: (userId, limit) => api.get(`/audit-trail/user/${userId}`, { params: { limit } }).then(r => r.data),
  getSummary: (days) => api.get('/audit-trail/summary', { params: { days } }).then(r => r.data),
};

export const regulatoryFeedApi = {
  getFeed: (params) => api.get('/regulatory-feed', { params }).then(r => r.data),
  getSources: () => api.get('/regulatory-feed/sources').then(r => r.data),
  getAmendment: (id) => api.get(`/regulatory-feed/${id}`).then(r => r.data),
  create: (data) => api.post('/regulatory-feed/amendments', data).then(r => r.data),
  subscribe: (data) => api.post('/regulatory-feed/subscribe', data).then(r => r.data),
  getSubscription: () => api.get('/regulatory-feed/subscription/me').then(r => r.data),
  getImpact: (id) => api.get(`/regulatory-feed/${id}/impact`).then(r => r.data),
};

export const reportExportApi = {
  downloadDocx: (analysisId) => api.get(`/reports/${analysisId}/export/docx`, { responseType: 'blob' }),
  downloadPdf: (analysisId) => api.get(`/reports/${analysisId}/export/pdf`, { responseType: 'blob' }),
  downloadPolicyDocx: (draftId) => api.get(`/policy-drafts/${draftId}/export/docx`, { responseType: 'blob' }),
};

export const i18nApi = {
  getTranslations: (lang) => api.get(`/i18n/translations/${lang}`).then(r => r.data),
  getGlossary: (lang) => api.get(`/i18n/glossary/${lang}`).then(r => r.data),
  getLanguages: () => api.get('/i18n/languages').then(r => r.data),
  getPreference: () => api.get('/i18n/preference').then(r => r.data),
  setPreference: (lang) => api.put('/i18n/preference', { language: lang }).then(r => r.data),
};

export const securityApi = {
  getEncryptionStatus: () => api.get('/security/encryption-status').then(r => r.data),
  checkDataLocalization: () => api.get('/security/data-localization').then(r => r.data),
};

export const confluenceApi = {
  getStatus: () => api.get('/confluence/status').then(r => r.data),
  testConnection: () => api.post('/confluence/test').then(r => r.data),
  publish: (draftId, parentPageId) => api.post(`/confluence/publish/${draftId}`, { parent_page_id: parentPageId }).then(r => r.data),
  importPage: (pageId) => api.post(`/confluence/import/${pageId}`).then(r => r.data),
  listPages: (limit) => api.get('/confluence/pages', { params: { limit } }).then(r => r.data),
};

export const metricsApi = {
  getCompliance: () => api.get('/metrics/compliance').then(r => r.data),
};

export const processingApi = {
  getStats: () => api.get('/processing/stats').then(r => r.data),
  clearCache: () => api.post('/processing/clear-cache').then(r => r.data),
};

// WebSocket URL for real-time updates
export const getWebSocketUrl = () => {
  const token = localStorage.getItem('token');
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
  const wsHost = backendUrl.replace(/^https?:\/\//, '');
  return `${wsProtocol}//${wsHost}/ws/${token}`;
};

export default api;
