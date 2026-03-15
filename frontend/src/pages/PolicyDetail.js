import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { policiesApi, regulationsApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import ClauseViewer from '../components/ClauseViewer';
import { 
  ArrowLeft, 
  FileText, 
  Calendar, 
  Building, 
  Download,
  Edit,
  Trash2,
  Share2,
  Clock,
  CheckCircle,
  AlertTriangle,
  Plus,
  Save,
  X,
  Link2,
  Shield,
  Send,
  ThumbsUp,
  ThumbsDown,
  History,
  GitCompare,
  Search,
  Unlink,
  Info
} from 'lucide-react';
import { toast } from 'sonner';

const statusConfig = {
  draft: { color: 'bg-amber-100 text-amber-700', label: 'Draft' },
  active: { color: 'bg-emerald-100 text-emerald-700', label: 'Active' },
  archived: { color: 'bg-gray-100 text-gray-500', label: 'Archived' },
  review: { color: 'bg-blue-100 text-blue-700', label: 'Under Review' },
  approved: { color: 'bg-green-100 text-green-700', label: 'Approved' },
  rejected: { color: 'bg-red-100 text-red-700', label: 'Rejected' },
};

export default function PolicyDetail() {
  const { policyId } = useParams();
  const navigate = useNavigate();
  const [policy, setPolicy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('clauses');

  // Metadata editing
  const [editingMeta, setEditingMeta] = useState(false);
  const [metaForm, setMetaForm] = useState({});
  const [savingMeta, setSavingMeta] = useState(false);

  // Clause CRUD
  const [addClauseOpen, setAddClauseOpen] = useState(false);
  const [editClauseOpen, setEditClauseOpen] = useState(false);
  const [deleteClauseOpen, setDeleteClauseOpen] = useState(false);
  const [selectedClause, setSelectedClause] = useState(null);
  const [clauseForm, setClauseForm] = useState({ text: '', section: '', page_number: '' });
  const [savingClause, setSavingClause] = useState(false);

  // Delete policy
  const [deletePolicyOpen, setDeletePolicyOpen] = useState(false);
  const [deletingPolicy, setDeletingPolicy] = useState(false);

  // Approval
  const [approvalAction, setApprovalAction] = useState(null); // 'approve' | 'reject'
  const [approvalReason, setApprovalReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Linked regulations
  const [regulations, setRegulations] = useState([]);
  const [linkRegulationOpen, setLinkRegulationOpen] = useState(false);
  const [regSearchQuery, setRegSearchQuery] = useState('');
  const [linkingRegId, setLinkingRegId] = useState(null);
  const [unlinkingRegId, setUnlinkingRegId] = useState(null);

  // Version history (Feature #23)
  const [versions, setVersions] = useState([]);
  const [loadingVersions, setLoadingVersions] = useState(false);

  // Diff view (Feature #24)
  const [selectedVersionForDiff, setSelectedVersionForDiff] = useState(null);
  const [diffData, setDiffData] = useState(null);
  const [loadingDiff, setLoadingDiff] = useState(false);
  const [diffViewMode, setDiffViewMode] = useState('side-by-side'); // 'side-by-side' | 'inline'

  // Feature #193: Prevent stale API responses from overwriting fresh data
  const policyRequestIdRef = useRef(0);

  useEffect(() => {
    loadPolicy();
  }, [policyId]);

  const loadPolicy = useCallback(async () => {
    const requestId = ++policyRequestIdRef.current;
    try {
      const response = await policiesApi.getById(policyId);
      // Feature #193: Only update state if this is still the latest request
      if (requestId !== policyRequestIdRef.current) return;
      setPolicy(response);
    } catch (error) {
      if (requestId !== policyRequestIdRef.current) return;
      toast.error('Failed to load policy');
      navigate('/policies');
    } finally {
      if (requestId === policyRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [policyId, navigate]);

  const loadRegulations = async () => {
    try {
      const regs = await regulationsApi.getAll();
      setRegulations(regs);
    } catch(e) { /* ignore */ }
  };

  // Link regulation to policy
  const handleLinkRegulation = async (regulationId) => {
    setLinkingRegId(regulationId);
    try {
      const result = await policiesApi.linkRegulation(policyId, regulationId);
      setPolicy(prev => ({ ...prev, linked_regulations: result.linked_regulations }));
      toast.success('Regulation linked successfully');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to link regulation');
    } finally {
      setLinkingRegId(null);
    }
  };

  // Unlink regulation from policy
  const handleUnlinkRegulation = async (regulationId) => {
    setUnlinkingRegId(regulationId);
    try {
      const result = await policiesApi.unlinkRegulation(policyId, regulationId);
      setPolicy(prev => ({ ...prev, linked_regulations: result.linked_regulations }));
      toast.success('Regulation unlinked');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to unlink regulation');
    } finally {
      setUnlinkingRegId(null);
    }
  };

  // Feature #23: Load version history
  const loadVersions = async () => {
    setLoadingVersions(true);
    try {
      const data = await policiesApi.getVersions(policyId);
      setVersions(data.versions || []);
    } catch (e) {
      console.error('Failed to load versions:', e);
    } finally {
      setLoadingVersions(false);
    }
  };

  // Feature #24: Load diff between version and current
  const loadDiff = async (versionId) => {
    setLoadingDiff(true);
    setSelectedVersionForDiff(versionId);
    try {
      const data = await policiesApi.compareVersions(policyId, versionId);
      setDiffData(data);
    } catch (e) {
      toast.error('Failed to load diff');
      console.error('Failed to load diff:', e);
    } finally {
      setLoadingDiff(false);
    }
  };

  const closeDiff = () => {
    setSelectedVersionForDiff(null);
    setDiffData(null);
  };

  useEffect(() => {
    if (activeTab === 'linked-regulations') {
      loadRegulations();
    }
    if (activeTab === 'versions') {
      loadVersions();
    }
  }, [activeTab]);

  // --- Metadata ---
  const startEditMeta = () => {
    setMetaForm({
      title: policy.title || '',
      department: policy.department || '',
      owner: policy.owner || '',
      effective_date: policy.effective_date || '',
      review_date: policy.review_date || '',
    });
    setEditingMeta(true);
  };

  const [dateValidationErrors, setDateValidationErrors] = useState({});

  // Validate dates in policy metadata form
  const validatePolicyDates = (form) => {
    const errors = {};
    if (form.effective_date && form.review_date) {
      const effectiveDate = new Date(form.effective_date);
      const reviewDate = new Date(form.review_date);
      if (reviewDate <= effectiveDate) {
        errors.review_date = 'Review date must be after the effective date';
      }
    }
    setDateValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleEffectiveDateChange = (e) => {
    const newForm = { ...metaForm, effective_date: e.target.value };
    setMetaForm(newForm);
    validatePolicyDates(newForm);
  };

  const handleReviewDateChange = (e) => {
    const newForm = { ...metaForm, review_date: e.target.value };
    setMetaForm(newForm);
    validatePolicyDates(newForm);
  };

  const saveMeta = async () => {
    // Validate dates before saving
    if (!validatePolicyDates(metaForm)) {
      toast.error('Please fix date validation errors before saving');
      return;
    }
    setSavingMeta(true);
    try {
      await policiesApi.update(policyId, metaForm);
      toast.success('Policy metadata updated');
      setEditingMeta(false);
      setDateValidationErrors({});
      await loadPolicy();
    } catch (error) {
      toast.error('Failed to update metadata');
    } finally {
      setSavingMeta(false);
    }
  };

  // --- Clause CRUD ---
  const openAddClause = () => {
    setClauseForm({ text: '', section: '', page_number: '' });
    setAddClauseOpen(true);
  };

  const handleAddClause = async () => {
    if (!clauseForm.text.trim()) { toast.error('Clause text is required'); return; }
    setSavingClause(true);
    try {
      await policiesApi.addClause(policyId, {
        text: clauseForm.text,
        section: clauseForm.section || undefined,
        page_number: clauseForm.page_number ? parseInt(clauseForm.page_number) : undefined,
      });
      toast.success('Clause added');
      setAddClauseOpen(false);
      await loadPolicy();
    } catch (error) {
      toast.error('Failed to add clause');
    } finally {
      setSavingClause(false);
    }
  };

  const openEditClause = (clause) => {
    setSelectedClause(clause);
    setClauseForm({
      text: clause.text || clause.clause_text || '',
      section: clause.section || '',
      page_number: clause.page_number || '',
    });
    setEditClauseOpen(true);
  };

  const handleEditClause = async () => {
    if (!clauseForm.text.trim()) { toast.error('Clause text is required'); return; }
    setSavingClause(true);
    try {
      const clauseId = selectedClause.clause_id || selectedClause.id;
      await policiesApi.updateClause(policyId, clauseId, {
        text: clauseForm.text,
        section: clauseForm.section || undefined,
        page_number: clauseForm.page_number ? parseInt(clauseForm.page_number) : undefined,
      });
      toast.success('Clause updated');
      setEditClauseOpen(false);
      setSelectedClause(null);
      await loadPolicy();
    } catch (error) {
      toast.error('Failed to update clause');
    } finally {
      setSavingClause(false);
    }
  };

  const openDeleteClause = (clause) => {
    setSelectedClause(clause);
    setDeleteClauseOpen(true);
  };

  const handleDeleteClause = async () => {
    setSavingClause(true);
    try {
      const clauseId = selectedClause.clause_id || selectedClause.id;
      await policiesApi.deleteClause(policyId, clauseId);
      toast.success('Clause deleted');
      setDeleteClauseOpen(false);
      setSelectedClause(null);
      await loadPolicy();
    } catch (error) {
      toast.error('Failed to delete clause');
    } finally {
      setSavingClause(false);
    }
  };

  // --- Policy Delete ---
  const handleDeletePolicy = async () => {
    setDeletingPolicy(true);
    try {
      await policiesApi.delete(policyId);
      toast.success('Policy deleted');
      navigate('/policies');
    } catch (error) {
      toast.error('Failed to delete policy');
    } finally {
      setDeletingPolicy(false);
    }
  };

  // --- Approval Workflow ---
  const handleSubmitForReview = async () => {
    setSubmitting(true);
    try {
      await policiesApi.submitForReview(policyId);
      toast.success('Policy submitted for review');
      await loadPolicy();
    } catch (error) {
      toast.error('Failed to submit for review: ' + (error.response?.data?.detail || ''));
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprovalDecision = async () => {
    setSubmitting(true);
    try {
      await policiesApi.approve(policyId, {
        decision: approvalAction,
        reason: approvalReason || undefined,
      });
      toast.success(approvalAction === 'approve' ? 'Policy approved' : 'Policy rejected');
      setApprovalAction(null);
      setApprovalReason('');
      await loadPolicy();
    } catch (error) {
      toast.error('Failed: ' + (error.response?.data?.detail || ''));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="policy-detail-loading">
        <div className="text-muted-foreground">Loading policy...</div>
      </div>
    );
  }

  if (!policy) {
    return (
      <div className="flex flex-col items-center justify-center h-64" data-testid="policy-not-found">
        <AlertTriangle className="w-12 h-12 text-yellow-500 mb-4" />
        <h3 className="text-lg font-semibold mb-2">Policy Not Found</h3>
        <Button onClick={() => navigate('/policies')}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Policies
        </Button>
      </div>
    );
  }

  const status = statusConfig[policy.status?.toLowerCase()] || statusConfig.draft;
  const clauses = policy.clauses || [];
  const approvalHistory = policy.approval_history || [];

  const clauseStats = {
    total: clauses.length,
    mandatory: clauses.filter(c => c.requirement_type === 'mandatory').length,
    highPriority: clauses.filter(c => c.criticality === 'high').length,
    categories: [...new Set(clauses.map(c => c.subject_category).filter(Boolean))].length
  };

  // Find linked regulations (by policy_type match or explicit links)
  const linkedRegulations = regulations.filter(r =>
    (policy.linked_regulations || []).includes(r.id) ||
    r.regulatory_body === (policy.policy_type === 'KYC' ? 'RBI' : undefined)
  );

  return (
    <div className="space-y-6" data-testid="policy-detail-page">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="policy-breadcrumb">
        <button onClick={() => navigate('/policies')} className="hover:text-foreground">Policies</button>
        <span>&gt;</span>
        <span className="text-foreground font-medium">{policy.title}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between" data-testid="policy-header">
        <div className="flex items-start gap-4">
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => navigate('/policies')}
            className="hover:bg-gray-100"
            data-testid="back-button"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center shadow-lg">
                <FileText className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-3xl font-bold text-gradient" data-testid="policy-title">{policy.title}</h1>
            </div>
            <div className="flex items-center gap-3 text-muted-foreground" data-testid="policy-meta-bar">
              <Badge className={status.color} data-testid="policy-status">{status.label}</Badge>
              <span>•</span>
              <span data-testid="policy-type">{policy.policy_type?.replace(/_/g, ' ')}</span>
              <span>•</span>
              <span data-testid="policy-version">v{policy.version}</span>
              {policy.department && (
                <>
                  <span>•</span>
                  <span className="flex items-center gap-1" data-testid="policy-department">
                    <Building className="w-4 h-4" />
                    {policy.department}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
        
        <div className="flex gap-2" data-testid="policy-actions">
          {(policy.status || 'draft').toLowerCase() === 'draft' && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleSubmitForReview}
              disabled={submitting}
              className="btn-silver"
              data-testid="submit-for-review-button"
            >
              <Send className="w-4 h-4 mr-2" /> Submit for Review
            </Button>
          )}
          <Button variant="outline" size="sm" className="btn-silver" data-testid="download-button">
            <Download className="w-4 h-4 mr-2" /> Download
          </Button>
          <Button variant="outline" size="sm" className="btn-shiny text-white" onClick={startEditMeta} data-testid="edit-policy-button">
            <Edit className="w-4 h-4 mr-2" /> Edit
          </Button>
          <Button variant="outline" size="sm" className="text-red-600 hover:bg-red-50" onClick={() => setDeletePolicyOpen(true)} data-testid="delete-policy-button">
            <Trash2 className="w-4 h-4 mr-2" /> Delete
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="policy-stats">
        <Card className="stats-card">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold" data-testid="total-clauses">{clauseStats.total}</div>
                <div className="text-sm text-muted-foreground">Total Clauses</div>
              </div>
              <FileText className="w-8 h-8 text-muted-foreground/30" />
            </div>
          </CardContent>
        </Card>
        <Card className="stats-card">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-red-500">{clauseStats.mandatory}</div>
                <div className="text-sm text-muted-foreground">Mandatory</div>
              </div>
              <AlertTriangle className="w-8 h-8 text-red-500/30" />
            </div>
          </CardContent>
        </Card>
        <Card className="stats-card">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-amber-500">{clauseStats.highPriority}</div>
                <div className="text-sm text-muted-foreground">High Priority</div>
              </div>
              <AlertTriangle className="w-8 h-8 text-amber-500/30" />
            </div>
          </CardContent>
        </Card>
        <Card className="stats-card">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-blue-500">{clauseStats.categories}</div>
                <div className="text-sm text-muted-foreground">Categories</div>
              </div>
              <Building className="w-8 h-8 text-blue-500/30" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Executive Summary */}
      {policy.summary && (
        <Card className="shiny-card border-emerald-200">
          <CardContent className="pt-4">
            <div className="flex gap-3">
              <Info className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">
                  Executive Summary
                </h3>
                <p className="text-gray-700">
                  {policy.summary}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Impact Cards */}
      {(policy.impact_organization || policy.impact_technical || policy.impact_operational) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {policy.impact_organization && (
            <Card className="shiny-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Building className="w-4 h-4" />
                  Organization Impact
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {policy.impact_organization}
                </p>
              </CardContent>
            </Card>
          )}
          
          {policy.impact_technical && (
            <Card className="shiny-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Technical Impact
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {policy.impact_technical}
                </p>
              </CardContent>
            </Card>
          )}
          
          {policy.impact_operational && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  Operational Impact
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {policy.impact_operational}
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Key Areas */}
      {policy.key_areas && policy.key_areas.length > 0 && (
        <Card>
          <CardContent className="pt-4">
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-600" />
              Key Compliance Areas
            </h3>
            <div className="flex flex-wrap gap-2">
              {policy.key_areas.map((area, idx) => (
                <Badge key={idx} variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                  {area}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full" data-testid="policy-tabs">
        <TabsList className="bg-muted/50">
          <TabsTrigger value="clauses" data-testid="clauses-tab" className="data-[state=active]:bg-white data-[state=active]:text-emerald-600 data-[state=active]:shadow-sm">
            Clauses ({clauses.length})
          </TabsTrigger>
          <TabsTrigger value="overview" data-testid="overview-tab" className="data-[state=active]:bg-white data-[state=active]:text-emerald-600 data-[state=active]:shadow-sm">
            Overview
          </TabsTrigger>
          <TabsTrigger value="versions" data-testid="versions-tab" className="data-[state=active]:bg-white data-[state=active]:text-emerald-600 data-[state=active]:shadow-sm">
            Versions
          </TabsTrigger>
          <TabsTrigger value="approval" data-testid="approval-tab" className="data-[state=active]:bg-white data-[state=active]:text-emerald-600 data-[state=active]:shadow-sm">
            Approval
          </TabsTrigger>
          <TabsTrigger value="linked-regulations" data-testid="linked-regulations-tab" className="data-[state=active]:bg-white data-[state=active]:text-emerald-600 data-[state=active]:shadow-sm">
            Linked Regulations
          </TabsTrigger>
        </TabsList>
        
        {/* Clauses Tab */}
        <TabsContent value="clauses" className="mt-6" data-testid="clauses-tab-content">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">Policy Clauses</h2>
            <Button onClick={openAddClause} data-testid="add-clause-button" size="sm">
              <Plus className="w-4 h-4 mr-2" /> Add Clause
            </Button>
          </div>
          <ClauseViewer
            clauses={clauses}
            documentType="policy"
            title={policy?.title || ''}
            onEditClause={openEditClause}
            onDeleteClause={openDeleteClause}
          />
        </TabsContent>
        
        {/* Overview Tab */}
        <TabsContent value="overview" className="mt-6" data-testid="overview-tab-content">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Policy Information</CardTitle>
              {!editingMeta && (
                <Button variant="outline" size="sm" onClick={startEditMeta} data-testid="edit-metadata-button">
                  <Edit className="w-4 h-4 mr-2" /> Edit
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              {editingMeta ? (
                <div className="space-y-4" data-testid="metadata-edit-form">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Title</Label>
                      <Input value={metaForm.title} onChange={(e) => setMetaForm({...metaForm, title: e.target.value})} data-testid="meta-title-input" />
                    </div>
                    <div className="space-y-2">
                      <Label>Owner</Label>
                      <Input value={metaForm.owner} onChange={(e) => setMetaForm({...metaForm, owner: e.target.value})} placeholder="e.g., compliance_head" data-testid="meta-owner-input" />
                    </div>
                    <div className="space-y-2">
                      <Label>Department</Label>
                      <Input value={metaForm.department} onChange={(e) => setMetaForm({...metaForm, department: e.target.value})} data-testid="meta-department-input" />
                    </div>
                    <div className="space-y-2">
                      <Label>Effective Date</Label>
                      <Input
                        type="date"
                        value={metaForm.effective_date}
                        onChange={handleEffectiveDateChange}
                        max={metaForm.review_date || undefined}
                        data-testid="meta-effective-date-input"
                      />
                      {dateValidationErrors.effective_date && (
                        <p className="text-xs text-red-500 mt-1" data-testid="effective-date-error">
                          {dateValidationErrors.effective_date}
                        </p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label>Review Date</Label>
                      <Input
                        type="date"
                        value={metaForm.review_date}
                        onChange={handleReviewDateChange}
                        min={metaForm.effective_date || undefined}
                        data-testid="meta-review-date-input"
                      />
                      {dateValidationErrors.review_date && (
                        <p className="text-xs text-red-500 mt-1" data-testid="review-date-error">
                          {dateValidationErrors.review_date}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={saveMeta} disabled={savingMeta || Object.keys(dateValidationErrors).length > 0} data-testid="save-metadata-button">
                      <Save className="w-4 h-4 mr-2" /> {savingMeta ? 'Saving...' : 'Save'}
                    </Button>
                    <Button variant="outline" onClick={() => { setEditingMeta(false); setDateValidationErrors({}); }} data-testid="cancel-metadata-button">
                      <X className="w-4 h-4 mr-2" /> Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4" data-testid="metadata-display">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Title</label>
                    <p className="mt-1" data-testid="meta-title">{policy.title}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Type</label>
                    <p className="mt-1">{policy.policy_type?.replace(/_/g, ' ')}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Version</label>
                    <p className="mt-1">{policy.version}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Status</label>
                    <p className="mt-1"><Badge className={status.color}>{status.label}</Badge></p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Owner</label>
                    <p className="mt-1" data-testid="meta-owner">{policy.owner || 'Not specified'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Department</label>
                    <p className="mt-1" data-testid="meta-department">{policy.department || 'Not specified'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Effective Date</label>
                    <p className="mt-1" data-testid="meta-effective-date">{policy.effective_date || 'Not set'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Review Date</label>
                    <p className="mt-1" data-testid="meta-review-date">{policy.review_date || 'Not set'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">File</label>
                    <p className="mt-1">{policy.file_name || 'Not available'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Created</label>
                    <p className="mt-1">{policy.created_at ? new Date(policy.created_at).toLocaleDateString() : 'Unknown'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Last Updated</label>
                    <p className="mt-1">{policy.updated_at ? new Date(policy.updated_at).toLocaleDateString() : 'Unknown'}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Versions Tab - Feature #23 & #24 */}
        <TabsContent value="versions" className="mt-6" data-testid="versions-tab-content">
          {/* Diff View Panel */}
          {diffData && (
            <Card className="mb-6 border-2 border-blue-200" data-testid="diff-view-panel">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <GitCompare className="w-5 h-5 text-blue-600" /> Diff: Version {diffData.version_number} vs Current
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Button
                      variant={diffViewMode === 'side-by-side' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setDiffViewMode('side-by-side')}
                      data-testid="diff-mode-side-by-side"
                    >
                      Side by Side
                    </Button>
                    <Button
                      variant={diffViewMode === 'inline' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setDiffViewMode('inline')}
                      data-testid="diff-mode-inline"
                    >
                      Inline
                    </Button>
                    <Button variant="ghost" size="sm" onClick={closeDiff} data-testid="close-diff">
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                <CardDescription data-testid="diff-summary">{diffData.changes_summary}</CardDescription>
              </CardHeader>
              <CardContent>
                {/* Stats bar */}
                <div className="flex gap-4 mb-4 text-sm" data-testid="diff-stats">
                  <span className="text-green-600 font-medium" data-testid="diff-additions-count">+{diffData.stats?.additions_count || 0} added</span>
                  <span className="text-red-600 font-medium" data-testid="diff-deletions-count">-{diffData.stats?.deletions_count || 0} removed</span>
                  <span className="text-amber-600 font-medium" data-testid="diff-modifications-count">~{diffData.stats?.modifications_count || 0} modified</span>
                  <span className="text-gray-500">{diffData.stats?.unchanged_count || 0} unchanged</span>
                </div>

                {/* Metadata changes */}
                {diffData.metadata_changes && diffData.metadata_changes.length > 0 && (
                  <div className="mb-4 p-3 bg-blue-50 rounded-lg" data-testid="metadata-changes">
                    <h4 className="text-sm font-medium mb-2">Metadata Changes</h4>
                    {diffData.metadata_changes.map((change, idx) => (
                      <div key={idx} className="text-sm">
                        <span className="font-medium">{change.field}:</span>{' '}
                        <span className="text-red-600 line-through">{change.old_value || 'none'}</span>{' → '}
                        <span className="text-green-600">{change.new_value || 'none'}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Clause diff */}
                {diffViewMode === 'side-by-side' ? (
                  <div className="grid grid-cols-2 gap-4" data-testid="diff-side-by-side">
                    <div>
                      <h4 className="text-sm font-medium mb-2 text-gray-500">Version {diffData.version_number} (Previous)</h4>
                      {diffData.deletions?.map((d, idx) => (
                        <div key={`del-${idx}`} className="p-2 mb-2 bg-red-50 border border-red-200 rounded text-sm" data-testid={`diff-deletion-${idx}`}>
                          <Badge className="bg-red-100 text-red-700 text-xs mb-1">Removed</Badge>
                          <p className="text-red-700">{d.text}</p>
                          {d.section && <span className="text-xs text-red-400">Section: {d.section}</span>}
                        </div>
                      ))}
                      {diffData.modifications?.map((m, idx) => (
                        <div key={`mod-old-${idx}`} className="p-2 mb-2 bg-amber-50 border border-amber-200 rounded text-sm" data-testid={`diff-mod-old-${idx}`}>
                          <Badge className="bg-amber-100 text-amber-700 text-xs mb-1">Modified</Badge>
                          <p className="text-red-600">{m.old_text}</p>
                          {m.section && <span className="text-xs text-amber-400">Section: {m.section}</span>}
                        </div>
                      ))}
                    </div>
                    <div>
                      <h4 className="text-sm font-medium mb-2 text-gray-500">Current Version</h4>
                      {diffData.additions?.map((a, idx) => (
                        <div key={`add-${idx}`} className="p-2 mb-2 bg-green-50 border border-green-200 rounded text-sm" data-testid={`diff-addition-${idx}`}>
                          <Badge className="bg-green-100 text-green-700 text-xs mb-1">Added</Badge>
                          <p className="text-green-700">{a.text}</p>
                          {a.section && <span className="text-xs text-green-400">Section: {a.section}</span>}
                        </div>
                      ))}
                      {diffData.modifications?.map((m, idx) => (
                        <div key={`mod-new-${idx}`} className="p-2 mb-2 bg-green-50 border border-green-200 rounded text-sm" data-testid={`diff-mod-new-${idx}`}>
                          <Badge className="bg-amber-100 text-amber-700 text-xs mb-1">Modified</Badge>
                          <p className="text-green-600">{m.new_text}</p>
                          {m.section && <span className="text-xs text-green-400">Section: {m.section}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2" data-testid="diff-inline">
                    {diffData.additions?.map((a, idx) => (
                      <div key={`add-${idx}`} className="p-2 bg-green-50 border-l-4 border-green-500 rounded text-sm" data-testid={`diff-inline-addition-${idx}`}>
                        <span className="text-green-700 font-mono">+ </span>
                        <span className="text-green-700">{a.text}</span>
                      </div>
                    ))}
                    {diffData.deletions?.map((d, idx) => (
                      <div key={`del-${idx}`} className="p-2 bg-red-50 border-l-4 border-red-500 rounded text-sm" data-testid={`diff-inline-deletion-${idx}`}>
                        <span className="text-red-700 font-mono">- </span>
                        <span className="text-red-700">{d.text}</span>
                      </div>
                    ))}
                    {diffData.modifications?.map((m, idx) => (
                      <div key={`mod-${idx}`} className="space-y-1" data-testid={`diff-inline-mod-${idx}`}>
                        <div className="p-2 bg-red-50 border-l-4 border-red-500 rounded text-sm">
                          <span className="text-red-700 font-mono">- </span>
                          <span className="text-red-700 line-through">{m.old_text}</span>
                        </div>
                        <div className="p-2 bg-green-50 border-l-4 border-green-500 rounded text-sm">
                          <span className="text-green-700 font-mono">+ </span>
                          <span className="text-green-700">{m.new_text}</span>
                        </div>
                      </div>
                    ))}
                    {diffData.unchanged?.map((u, idx) => (
                      <div key={`unch-${idx}`} className="p-2 bg-gray-50 rounded text-sm text-gray-500" data-testid={`diff-inline-unchanged-${idx}`}>
                        <span className="font-mono">  </span>
                        {u.text}
                      </div>
                    ))}
                  </div>
                )}

                {(!diffData.additions?.length && !diffData.deletions?.length && !diffData.modifications?.length && !diffData.metadata_changes?.length) && (
                  <p className="text-sm text-muted-foreground text-center py-4">No differences found between these versions.</p>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="w-5 h-5" /> Version History
              </CardTitle>
              <CardDescription>Track changes and updates to this policy</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingVersions ? (
                <div className="text-center py-4 text-muted-foreground">Loading versions...</div>
              ) : (
                <div className="space-y-4" data-testid="version-history-list">
                  {versions.length > 0 ? (
                    versions.slice().reverse().map((v, idx) => (
                      <div key={v.id || idx} className={`flex items-start gap-4 p-3 border rounded-lg ${v.is_current ? 'border-green-300 bg-green-50/30' : ''}`} data-testid={`version-entry-${v.version_number || idx}`}>
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                          v.is_current ? 'bg-green-100' :
                          v.change_type === 'clause_added' ? 'bg-blue-100' :
                          v.change_type === 'clause_edited' ? 'bg-amber-100' :
                          v.change_type === 'clause_deleted' ? 'bg-red-100' :
                          'bg-blue-100'
                        }`}>
                          {v.is_current ? <CheckCircle className="w-4 h-4 text-green-600" /> :
                           v.change_type === 'clause_deleted' ? <Trash2 className="w-4 h-4 text-red-600" /> :
                           v.change_type === 'clause_edited' ? <Edit className="w-4 h-4 text-amber-600" /> :
                           <GitCompare className="w-4 h-4 text-blue-600" />}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <p className="font-medium" data-testid={`version-number-${v.version_number || idx}`}>
                                Version {v.version_number}{v.is_current ? ' (Current)' : ''}
                              </p>
                              {v.clauses_count !== undefined && (
                                <Badge variant="outline" className="text-xs">{v.clauses_count} clauses</Badge>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground" data-testid={`version-date-${v.version_number || idx}`}>
                                {v.created_at ? new Date(v.created_at).toLocaleString() : ''}
                              </span>
                              {!v.is_current && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => loadDiff(v.id)}
                                  disabled={loadingDiff && selectedVersionForDiff === v.id}
                                  data-testid={`compare-version-${v.version_number || idx}`}
                                >
                                  <GitCompare className="w-3 h-3 mr-1" />
                                  {loadingDiff && selectedVersionForDiff === v.id ? 'Loading...' : 'Compare'}
                                </Button>
                              )}
                            </div>
                          </div>
                          <p className="text-sm text-muted-foreground" data-testid={`version-summary-${v.version_number || idx}`}>
                            {v.changes_summary || (v.is_current ? `${clauses.length} clauses` : 'Version update')}
                          </p>
                          {v.created_by && <span className="text-xs text-muted-foreground">by {v.created_by}</span>}
                        </div>
                      </div>
                    ))
                  ) : (
                    <>
                      <div className="flex items-start gap-4 p-3 border rounded-lg border-green-300 bg-green-50/30" data-testid="version-entry-current">
                        <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                          <CheckCircle className="w-4 h-4 text-green-600" />
                        </div>
                        <div>
                          <p className="font-medium">v{policy.version} (Current)</p>
                          <p className="text-sm text-muted-foreground">
                            Policy uploaded — {clauses.length} clauses extracted automatically
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {policy.created_at ? new Date(policy.created_at).toLocaleString() : 'Unknown'}
                          </p>
                        </div>
                      </div>
                      {(policy.audit_trail || []).map((entry, idx) => (
                        <div key={idx} className="flex items-start gap-4 p-3 border rounded-lg" data-testid={`audit-entry-${idx}`}>
                          <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
                            <Edit className="w-4 h-4 text-amber-600" />
                          </div>
                          <div>
                            <p className="font-medium">{entry.action}</p>
                            {entry.field && (
                              <p className="text-sm text-muted-foreground">
                                Field "{entry.field}": {entry.old_value ? `"${String(entry.old_value).substring(0, 60)}..." → ` : ''}"
                                {String(entry.new_value || '').substring(0, 60)}..."
                              </p>
                            )}
                            <p className="text-xs text-muted-foreground mt-1">
                              {entry.user && `by ${entry.user} • `}
                              {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : ''}
                            </p>
                          </div>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Approval Tab */}
        <TabsContent value="approval" className="mt-6" data-testid="approval-tab-content">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5" /> Approval Workflow
              </CardTitle>
              <CardDescription>Current status: <Badge className={status.color}>{status.label}</Badge></CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Actions */}
              <div className="flex gap-3" data-testid="approval-actions">
                {(policy.status || 'draft').toLowerCase() === 'draft' && (
                  <Button onClick={handleSubmitForReview} disabled={submitting} data-testid="approval-submit-review">
                    <Send className="w-4 h-4 mr-2" /> Submit for Review
                  </Button>
                )}
                {(policy.status || '').toLowerCase() === 'review' && (
                  <>
                    <Button onClick={() => setApprovalAction('approve')} className="bg-green-600 hover:bg-green-700" data-testid="approve-button">
                      <ThumbsUp className="w-4 h-4 mr-2" /> Approve
                    </Button>
                    <Button variant="destructive" onClick={() => setApprovalAction('reject')} data-testid="reject-button">
                      <ThumbsDown className="w-4 h-4 mr-2" /> Reject
                    </Button>
                  </>
                )}
              </div>

              {/* Approval history */}
              <div data-testid="approval-history">
                <h3 className="font-medium mb-3">Approval History</h3>
                {approvalHistory.length > 0 ? (
                  <div className="space-y-3">
                    {approvalHistory.map((entry, idx) => (
                      <div key={idx} className="flex items-start gap-3 p-3 border rounded-lg" data-testid={`approval-entry-${idx}`}>
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                          entry.decision === 'approve' ? 'bg-green-100' : entry.decision === 'reject' ? 'bg-red-100' : 'bg-blue-100'
                        }`}>
                          {entry.decision === 'approve' ? <ThumbsUp className="w-4 h-4 text-green-600" /> :
                           entry.decision === 'reject' ? <ThumbsDown className="w-4 h-4 text-red-600" /> :
                           <Send className="w-4 h-4 text-blue-600" />}
                        </div>
                        <div>
                          <p className="font-medium capitalize">{entry.decision || entry.action || 'Submitted'}</p>
                          {entry.reason && <p className="text-sm text-muted-foreground">{entry.reason}</p>}
                          <p className="text-xs text-muted-foreground mt-1">
                            {entry.user && `by ${entry.user} • `}
                            {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : ''}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground" data-testid="no-approval-history">No approval actions yet</p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Linked Regulations Tab */}
        <TabsContent value="linked-regulations" className="mt-6" data-testid="linked-regulations-tab-content">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Link2 className="w-5 h-5" /> Linked Regulations
                </CardTitle>
                <CardDescription>Regulations mapped to this policy</CardDescription>
              </div>
              <Button size="sm" onClick={() => { loadRegulations(); setLinkRegulationOpen(true); }} data-testid="link-regulation-btn">
                <Plus className="w-4 h-4 mr-1" /> Link Regulation
              </Button>
            </CardHeader>
            <CardContent>
              {linkedRegulations.length > 0 ? (
                <div className="space-y-3" data-testid="linked-regulations-list">
                  {linkedRegulations.map(reg => (
                    <div key={reg.id} className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50" data-testid={`linked-reg-${reg.id}`}>
                      <div className="flex items-center gap-3 cursor-pointer flex-1" onClick={() => navigate(`/regulations/${reg.id}`)}>
                        <Shield className="w-5 h-5 text-emerald-600" />
                        <div>
                          <p className="font-medium">{reg.title}</p>
                          <p className="text-xs text-muted-foreground">{reg.regulatory_body} {reg.circular_number && `• ${reg.circular_number}`}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{reg.clauses?.length || 0} clauses</Badge>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-red-600"
                          onClick={(e) => { e.stopPropagation(); handleUnlinkRegulation(reg.id); }}
                          disabled={unlinkingRegId === reg.id}
                          data-testid={`unlink-reg-${reg.id}`}
                          title="Unlink regulation"
                        >
                          <Unlink className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8" data-testid="no-linked-regulations">
                  <Shield className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
                  <p className="text-muted-foreground">No regulations linked to this policy yet.</p>
                  <p className="text-sm text-muted-foreground mt-1">Click "Link Regulation" to manually link, or run a gap analysis to auto-link.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Add Clause Dialog */}
      <Dialog open={addClauseOpen} onOpenChange={setAddClauseOpen}>
        <DialogContent data-testid="add-clause-dialog">
          <DialogHeader>
            <DialogTitle>Add New Clause</DialogTitle>
            <DialogDescription>Add a clause to this policy manually</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Clause Text *</Label>
              <Textarea
                value={clauseForm.text}
                onChange={(e) => setClauseForm({...clauseForm, text: e.target.value})}
                placeholder="Enter the clause text..."
                rows={4}
                data-testid="clause-text-input"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Section</Label>
                <Input
                  value={clauseForm.section}
                  onChange={(e) => setClauseForm({...clauseForm, section: e.target.value})}
                  placeholder="e.g., 4.1"
                  data-testid="clause-section-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Page Number</Label>
                <Input
                  type="number"
                  value={clauseForm.page_number}
                  onChange={(e) => setClauseForm({...clauseForm, page_number: e.target.value})}
                  placeholder="e.g., 5"
                  data-testid="clause-page-input"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setAddClauseOpen(false)} data-testid="cancel-add-clause">Cancel</Button>
              <Button onClick={handleAddClause} disabled={savingClause} data-testid="submit-add-clause">
                {savingClause ? 'Adding...' : 'Add Clause'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Clause Dialog */}
      <Dialog open={editClauseOpen} onOpenChange={setEditClauseOpen}>
        <DialogContent data-testid="edit-clause-dialog">
          <DialogHeader>
            <DialogTitle>Edit Clause</DialogTitle>
            <DialogDescription>Modify the clause text and metadata</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Clause Text *</Label>
              <Textarea
                value={clauseForm.text}
                onChange={(e) => setClauseForm({...clauseForm, text: e.target.value})}
                rows={4}
                data-testid="edit-clause-text-input"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Section</Label>
                <Input
                  value={clauseForm.section}
                  onChange={(e) => setClauseForm({...clauseForm, section: e.target.value})}
                  data-testid="edit-clause-section-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Page Number</Label>
                <Input
                  type="number"
                  value={clauseForm.page_number}
                  onChange={(e) => setClauseForm({...clauseForm, page_number: e.target.value})}
                  data-testid="edit-clause-page-input"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEditClauseOpen(false)} data-testid="cancel-edit-clause">Cancel</Button>
              <Button onClick={handleEditClause} disabled={savingClause} data-testid="save-edit-clause">
                {savingClause ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Clause Confirmation */}
      <AlertDialog open={deleteClauseOpen} onOpenChange={setDeleteClauseOpen}>
        <AlertDialogContent data-testid="delete-clause-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Clause?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. The clause will be permanently removed from this policy.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-clause">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteClause} className="bg-red-600 hover:bg-red-700" disabled={savingClause} data-testid="confirm-delete-clause">
              {savingClause ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Policy Confirmation */}
      <AlertDialog open={deletePolicyOpen} onOpenChange={setDeletePolicyOpen}>
        <AlertDialogContent data-testid="delete-policy-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Policy?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete "{policy.title}" and all its associated clauses. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-policy">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeletePolicy} className="bg-red-600 hover:bg-red-700" disabled={deletingPolicy} data-testid="confirm-delete-policy">
              {deletingPolicy ? 'Deleting...' : 'Delete Policy'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Link Regulation Dialog */}
      <Dialog open={linkRegulationOpen} onOpenChange={setLinkRegulationOpen}>
        <DialogContent className="max-w-lg" data-testid="link-regulation-dialog">
          <DialogHeader>
            <DialogTitle>Link Regulation</DialogTitle>
            <DialogDescription>Search and select a regulation to link to this policy</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search regulations..."
                value={regSearchQuery}
                onChange={(e) => setRegSearchQuery(e.target.value)}
                className="pl-9"
                data-testid="reg-search-input"
              />
            </div>
            <div className="max-h-[300px] overflow-y-auto space-y-2" data-testid="reg-search-results">
              {regulations
                .filter(r => {
                  // Filter out already-linked regulations
                  const linked = policy.linked_regulations || [];
                  if (linked.includes(r.id)) return false;
                  // Apply search filter
                  if (!regSearchQuery) return true;
                  const q = regSearchQuery.toLowerCase();
                  return (
                    r.title?.toLowerCase().includes(q) ||
                    r.regulatory_body?.toLowerCase().includes(q) ||
                    r.circular_number?.toLowerCase().includes(q)
                  );
                })
                .map(reg => (
                  <div
                    key={reg.id}
                    className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50"
                    data-testid={`search-reg-${reg.id}`}
                  >
                    <div className="flex items-center gap-3 flex-1">
                      <Shield className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="font-medium text-sm truncate">{reg.title}</p>
                        <p className="text-xs text-muted-foreground">
                          {reg.regulatory_body} {reg.circular_number && `• ${reg.circular_number}`}
                        </p>
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleLinkRegulation(reg.id)}
                      disabled={linkingRegId === reg.id}
                      data-testid={`link-reg-btn-${reg.id}`}
                    >
                      {linkingRegId === reg.id ? 'Linking...' : 'Link'}
                    </Button>
                  </div>
                ))
              }
              {regulations.filter(r => {
                const linked = policy.linked_regulations || [];
                if (linked.includes(r.id)) return false;
                if (!regSearchQuery) return true;
                const q = regSearchQuery.toLowerCase();
                return r.title?.toLowerCase().includes(q) || r.regulatory_body?.toLowerCase().includes(q) || r.circular_number?.toLowerCase().includes(q);
              }).length === 0 && (
                <div className="text-center py-6 text-muted-foreground" data-testid="no-reg-results">
                  <p className="text-sm">No unlinked regulations found{regSearchQuery && ` matching "${regSearchQuery}"`}.</p>
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Approval Decision Dialog */}
      <Dialog open={!!approvalAction} onOpenChange={() => setApprovalAction(null)}>
        <DialogContent data-testid="approval-decision-dialog">
          <DialogHeader>
            <DialogTitle>{approvalAction === 'approve' ? 'Approve Policy' : 'Reject Policy'}</DialogTitle>
            <DialogDescription>
              {approvalAction === 'approve'
                ? 'This will advance the policy to Approved status.'
                : 'This will return the policy to Draft status.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Reason (optional)</Label>
              <Textarea
                value={approvalReason}
                onChange={(e) => setApprovalReason(e.target.value)}
                placeholder={approvalAction === 'reject' ? 'Please provide a reason for rejection...' : 'Add a note (optional)'}
                rows={3}
                data-testid="approval-reason-input"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setApprovalAction(null)}>Cancel</Button>
              <Button
                onClick={handleApprovalDecision}
                disabled={submitting}
                className={approvalAction === 'approve' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}
                data-testid="confirm-approval-decision"
              >
                {submitting ? 'Processing...' : approvalAction === 'approve' ? 'Approve' : 'Reject'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
