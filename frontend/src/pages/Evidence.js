import React, { useEffect, useState } from 'react';
import { evidenceApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Upload, FileText, Sparkles, CheckCircle, AlertCircle, Search, ShieldCheck, Eye, RotateCcw, Hash, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { toast } from 'sonner';
import { MOCK_EVIDENCE_LIST } from '../lib/mockData';

export default function Evidence() {
  const [evidenceList, setEvidenceList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [testingId, setTestingId] = useState(null);
  const [testRequirement, setTestRequirement] = useState('');
  const [file, setFile] = useState(null);
  const [evidenceData, setEvidenceData] = useState({ title: '', description: '' });
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortColumn, setSortColumn] = useState('created_at');
  const [sortDirection, setSortDirection] = useState('desc');
  const [currentPage, setCurrentPage] = useState(1); // Pagination state
  const pageSize = 10; // Items per page
  const [detailEvidence, setDetailEvidence] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');
  const [overrideId, setOverrideId] = useState(null);
  const [validating, setValidating] = useState(null);

  useEffect(() => { loadEvidence(); }, []);

  const loadEvidence = async () => {
    try {
      const response = await evidenceApi.getAll();
      // Use mock data if API returns empty
      const list = Array.isArray(response) ? response : [];
      setEvidenceList(list.length > 0 ? list : MOCK_EVIDENCE_LIST);
    } catch (error) {
      // Fallback to mock data for demo
      setEvidenceList(MOCK_EVIDENCE_LIST);
      console.log('Using mock evidence data for demo');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) { toast.error('Please select a file'); return; }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('evidence_data', JSON.stringify(evidenceData));
      await evidenceApi.upload(formData);
      toast.success('Evidence uploaded successfully!');
      setUploadOpen(false);
      setFile(null);
      setEvidenceData({ title: '', description: '' });
      loadEvidence();
    } catch (error) {
      toast.error('Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleValidate = async (id) => {
    setValidating(id);
    try {
      const result = await evidenceApi.validate(id);
      toast.success(`Validation: ${result.explanation}`);
      loadEvidence();
    } catch (error) {
      toast.error('Validation failed');
    } finally {
      setValidating(null);
    }
  };

  const handleApprove = async (id, approved) => {
    try {
      await evidenceApi.approve(id, { approved, reason: 'Reviewed and verified' });
      toast.success(approved ? 'Evidence approved' : 'Evidence rejected');
      loadEvidence();
    } catch (error) {
      toast.error('Action failed');
    }
  };

  const handleOverride = async () => {
    if (!overrideReason.trim()) { toast.error('Please provide a reason'); return; }
    try {
      await evidenceApi.override(overrideId, { reason: overrideReason });
      toast.success('Evidence overridden to approved');
      setOverrideOpen(false);
      setOverrideReason('');
      setOverrideId(null);
      loadEvidence();
    } catch (error) {
      toast.error('Override failed');
    }
  };

  const handleTestEvidence = async (evidenceId) => {
    if (!testRequirement) { toast.error('Please enter requirement'); return; }
    try {
      const response = await evidenceApi.test(evidenceId, testRequirement);
      toast.success(`Evidence scored: ${response.compliance_score}/100`);
      setTestingId(null);
      setTestRequirement('');
      loadEvidence();
    } catch (error) {
      toast.error('Testing failed');
    }
  };

  const viewDetail = async (ev) => {
    setDetailEvidence(ev);
    setDetailOpen(true);
  };

  const getStatusBadge = (status) => {
    const map = {
      'Approved': 'bg-green-100 text-green-800',
      'auto_approved': 'bg-green-100 text-green-800',
      'human_approved': 'bg-green-100 text-green-800',
      'human_override': 'bg-blue-100 text-blue-800',
      'Pending Review': 'bg-yellow-100 text-yellow-800',
      'pending_human_review': 'bg-yellow-100 text-yellow-800',
      'Failed': 'bg-red-100 text-red-800',
      'failed': 'bg-red-100 text-red-800',
      'Rejected': 'bg-red-100 text-red-800',
      'human_rejected': 'bg-red-100 text-red-800',
    };
    return map[status] || 'bg-gray-100 text-gray-800';
  };

  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const SortIcon = ({ column }) => {
    if (sortColumn !== column) return <ArrowUpDown className="h-3 w-3 ml-1 opacity-50" />;
    return sortDirection === 'asc' ? <ArrowUp className="h-3 w-3 ml-1" /> : <ArrowDown className="h-3 w-3 ml-1" />;
  };

  const trimmedEvidenceSearch = (searchQuery || '').trim();
  const filtered = evidenceList.filter(ev => {
    const matchesSearch = !trimmedEvidenceSearch ||
      ev.title?.toLowerCase().includes(trimmedEvidenceSearch.toLowerCase()) ||
      ev.file_name?.toLowerCase().includes(trimmedEvidenceSearch.toLowerCase());
    const matchesStatus = statusFilter === 'all' ||
      ev.status === statusFilter ||
      ev.validation_status === statusFilter;
    return matchesSearch && matchesStatus;
  }).sort((a, b) => {
    let aVal = a[sortColumn] || '';
    let bVal = b[sortColumn] || '';

    // Handle date columns
    if (sortColumn === 'created_at') {
      aVal = new Date(aVal || 0).getTime();
      bVal = new Date(bVal || 0).getTime();
    }
    // Handle numeric columns (AI score)
    else if (sortColumn === 'ai_compliance_score') {
      aVal = aVal ?? -1;
      bVal = bVal ?? -1;
    }
    // Handle status column (treat as string)
    else if (sortColumn === 'validation_status' || sortColumn === 'status') {
      aVal = (a.validation_status || a.status || '').toLowerCase();
      bVal = (b.validation_status || b.status || '').toLowerCase();
    }
    // Handle string columns
    else if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase();
      bVal = (bVal || '').toLowerCase();
    }

    if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  // Pagination logic
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginatedEvidence = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // Reset to page 1 when filters or search change
  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, sortColumn, sortDirection]);

  return (
    <div className="space-y-6" data-testid="evidence-page">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center shadow-lg">
            <FileText className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold" data-testid="evidence-title">Evidence Management</h1>
            <p className="text-muted-foreground">Upload and validate compliance evidence with AI</p>
          </div>
        </div>
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogTrigger asChild>
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="upload-evidence-button">
              <Upload className="mr-2 h-4 w-4" /> Upload Evidence
            </Button>
          </DialogTrigger>
          <DialogContent data-testid="upload-evidence-dialog">
            <DialogHeader>
              <DialogTitle>Upload Evidence Document</DialogTitle>
              <DialogDescription>Upload evidence for compliance verification</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleUpload} data-testid="upload-evidence-form" className="space-y-4">
              <div>
                <Label htmlFor="evidence-title">Title</Label>
                <Input id="evidence-title" data-testid="evidence-title-input" value={evidenceData.title} onChange={(e) => setEvidenceData({ ...evidenceData, title: e.target.value })} placeholder="e.g., KYC Verification Logs" required />
              </div>
              <div>
                <Label htmlFor="evidence-description">Description</Label>
                <Textarea id="evidence-description" data-testid="evidence-description-input" value={evidenceData.description} onChange={(e) => { const val = e.target.value; if (val.length <= 10000) setEvidenceData({ ...evidenceData, description: val }); }} placeholder="Describe the evidence..." rows={3} maxLength={10000} />
                <div className="flex justify-end mt-1">
                  <span className={`text-xs ${evidenceData.description?.length > 9000 ? 'text-amber-500' : 'text-muted-foreground'}`} data-testid="evidence-description-char-count">
                    {(evidenceData.description || '').length}/10000
                  </span>
                </div>
              </div>
              <div>
                <Label htmlFor="evidence-file">File</Label>
                <Input id="evidence-file" data-testid="evidence-file-input" type="file" accept=".pdf,.docx,.xlsx,.jpg,.png,.txt" onChange={(e) => setFile(e.target.files[0])} required />
              </div>
              <Button type="submit" data-testid="submit-upload-evidence" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white" disabled={uploading}>
                {uploading ? 'Uploading...' : 'Upload Evidence'}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Search & Filter */}
      <div className="flex gap-4 items-center" data-testid="evidence-filters">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="Search evidence by name or file..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-9" data-testid="evidence-search-input" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-48" data-testid="evidence-status-filter">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="Pending">Pending</SelectItem>
            <SelectItem value="Approved">Approved</SelectItem>
            <SelectItem value="Pending Review">Pending Review</SelectItem>
            <SelectItem value="Failed">Failed</SelectItem>
            <SelectItem value="Rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64" data-testid="evidence-loading">
          <div className="text-muted-foreground">Loading evidence...</div>
        </div>
      ) : filtered.length === 0 ? (
        <Card className="flex flex-col items-center justify-center h-64" data-testid="evidence-empty">
          <CardContent className="text-center py-8">
            <FileText className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Evidence Yet</h3>
            <p className="text-muted-foreground mb-4">Upload your first evidence document</p>
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => setUploadOpen(true)}>
              <Upload className="mr-2 h-4 w-4" /> Upload Evidence
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="border rounded-lg" data-testid="evidence-table">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('title')} data-testid="sort-title">
                    Title <SortIcon column="title" />
                  </button>
                </TableHead>
                <TableHead>
                  <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('file_name')} data-testid="sort-file">
                    File <SortIcon column="file_name" />
                  </button>
                </TableHead>
                <TableHead>
                  <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('validation_status')} data-testid="sort-status">
                    Status <SortIcon column="validation_status" />
                  </button>
                </TableHead>
                <TableHead>
                  <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('ai_compliance_score')} data-testid="sort-score">
                    AI Score <SortIcon column="ai_compliance_score" />
                  </button>
                </TableHead>
                <TableHead>SHA-256 Hash</TableHead>
                <TableHead>
                  <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('created_at')} data-testid="sort-created">
                    Created <SortIcon column="created_at" />
                  </button>
                </TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedEvidence.map((ev) => (
                <TableRow key={ev.id} data-testid={`evidence-row-${ev.id}`}>
                  <TableCell className="font-medium">{ev.title}</TableCell>
                  <TableCell className="text-sm text-gray-500">{ev.file_name}</TableCell>
                  <TableCell>
                    <Badge className={getStatusBadge(ev.validation_status || ev.status || 'Pending')} data-testid={`evidence-status-${ev.id}`}>
                      {ev.validation_status || ev.status || 'Pending'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {ev.ai_compliance_score != null ? (
                      <span className={`font-medium ${ev.ai_compliance_score >= 75 ? 'text-green-600' : ev.ai_compliance_score >= 50 ? 'text-yellow-600' : 'text-red-600'}`} data-testid={`evidence-score-${ev.id}`}>
                        {ev.ai_compliance_score}/100
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {ev.sha256_hash ? (
                      <span className="font-mono text-xs text-gray-500" title={ev.sha256_hash} data-testid={`evidence-hash-${ev.id}`}>
                        <Hash className="h-3 w-3 inline mr-1" />
                        {ev.sha256_hash.substring(0, 12)}...
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-gray-500">
                    {ev.created_at ? new Date(ev.created_at).toLocaleDateString() : '—'}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => viewDetail(ev)} data-testid={`view-evidence-${ev.id}`}>
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleValidate(ev.id)} disabled={validating === ev.id} data-testid={`validate-evidence-${ev.id}`}>
                        <ShieldCheck className="h-4 w-4" />
                      </Button>
                      {(ev.validation_status === 'failed' || ev.validation_status === 'pending_human_review') && (
                        <>
                          <Button variant="ghost" size="sm" className="text-green-600" onClick={() => handleApprove(ev.id, true)} data-testid={`approve-evidence-${ev.id}`}>
                            <CheckCircle className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" className="text-blue-600" onClick={() => { setOverrideId(ev.id); setOverrideOpen(true); }} data-testid={`override-evidence-${ev.id}`}>
                            <RotateCcw className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                      {testingId === ev.id ? (
                        <div className="flex gap-1 items-center">
                          <Input placeholder="Requirement..." value={testRequirement} onChange={(e) => setTestRequirement(e.target.value)} className="w-48 h-8 text-xs" />
                          <Button size="sm" onClick={() => handleTestEvidence(ev.id)}>
                            <Sparkles className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setTestingId(null)}>✕</Button>
                        </div>
                      ) : (
                        <Button variant="ghost" size="sm" onClick={() => setTestingId(ev.id)} data-testid={`test-evidence-${ev.id}`}>
                          <Sparkles className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-4 border-t" data-testid="evidence-pagination">
              <span className="text-sm text-muted-foreground">
                Showing {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, filtered.length)} of {filtered.length}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(prev => prev - 1)}
                  data-testid="prev-page"
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(prev => prev + 1)}
                  data-testid="next-page"
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-2xl" data-testid="evidence-detail-dialog">
          <DialogHeader>
            <DialogTitle>{detailEvidence?.title}</DialogTitle>
            <DialogDescription>{detailEvidence?.description || 'No description'}</DialogDescription>
          </DialogHeader>
          {detailEvidence && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-gray-500">File:</span> {detailEvidence.file_name}</div>
                <div><span className="text-gray-500">Status:</span> <Badge className={getStatusBadge(detailEvidence.validation_status || 'Pending')}>{detailEvidence.validation_status || 'Pending'}</Badge></div>
                <div><span className="text-gray-500">AI Score:</span> {detailEvidence.ai_compliance_score ?? '—'}</div>
                <div><span className="text-gray-500">AI Confidence:</span> {detailEvidence.ai_confidence ? `${(detailEvidence.ai_confidence * 100).toFixed(0)}%` : '—'}</div>
                {detailEvidence.sha256_hash && (
                  <div className="col-span-2"><span className="text-gray-500">SHA-256:</span> <code className="text-xs break-all" data-testid="evidence-detail-hash">{detailEvidence.sha256_hash}</code></div>
                )}
              </div>
              {detailEvidence.ai_validation_notes && (
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="font-medium mb-1 flex items-center gap-1"><Sparkles className="h-4 w-4" /> AI Notes</div>
                  <p className="text-sm text-gray-600">{detailEvidence.ai_validation_notes}</p>
                </div>
              )}
              {detailEvidence.feedback_good?.length > 0 && (
                <div className="bg-green-50 p-3 rounded-md">
                  <div className="font-medium text-green-700 mb-1 flex items-center gap-1"><CheckCircle className="h-4 w-4" /> Strengths</div>
                  <ul className="text-sm text-green-600 list-disc list-inside">{detailEvidence.feedback_good.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              {detailEvidence.feedback_improvements?.length > 0 && (
                <div className="bg-amber-50 p-3 rounded-md">
                  <div className="font-medium text-amber-700 mb-1 flex items-center gap-1"><AlertCircle className="h-4 w-4" /> Improvements</div>
                  <ul className="text-sm text-amber-600 list-disc list-inside">{detailEvidence.feedback_improvements.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              {detailEvidence.audit_log?.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2" data-testid="evidence-audit-log">Audit Log</h4>
                  <div className="space-y-2">{detailEvidence.audit_log.map((entry, i) => (
                    <div key={i} className="text-sm border-l-2 border-gray-200 pl-3">
                      <div className="font-medium">{entry.action}</div>
                      <div className="text-gray-500">{entry.user_name} — {new Date(entry.timestamp).toLocaleString()}</div>
                      <div className="text-gray-600">{entry.details}</div>
                    </div>
                  ))}</div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Override Dialog */}
      <Dialog open={overrideOpen} onOpenChange={setOverrideOpen}>
        <DialogContent data-testid="override-dialog">
          <DialogHeader>
            <DialogTitle>Override AI Validation</DialogTitle>
            <DialogDescription>Provide a reason for overriding the AI validation result</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Textarea placeholder="Reason for override..." value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} data-testid="override-reason-input" rows={3} />
            <Button onClick={handleOverride} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="submit-override-button">
              Override to Approved
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
