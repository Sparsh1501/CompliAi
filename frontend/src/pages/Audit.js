import React, { useEffect, useState } from 'react';
import { auditApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import { Shield, Plus, Play, CheckCircle, Clock, FileText, Download, PenLine, Eye, Search, AlertTriangle, XCircle, Info } from 'lucide-react';
import { toast } from 'sonner';

/* ─── RAG colour helpers ─── */
const RAG_CONFIG = {
  green: {
    dot: 'bg-green-500',
    badge: 'bg-green-100 text-green-800 border-green-200',
    label: 'Complete/Approved',
    icon: CheckCircle,
    description: 'All required artefacts uploaded and approved. Control is fully compliant.',
  },
  amber: {
    dot: 'bg-amber-500',
    badge: 'bg-amber-100 text-amber-800 border-amber-200',
    label: 'Pending/Partial',
    icon: AlertTriangle,
    description: 'Some artefacts uploaded but pending review, or partial compliance identified.',
  },
  red: {
    dot: 'bg-red-500',
    badge: 'bg-red-100 text-red-800 border-red-200',
    label: 'Missing/Failed',
    icon: XCircle,
    description: 'Required artefacts missing or control found non-compliant. Immediate action needed.',
  },
};

const getRAGFromScore = (score) => {
  if (score >= 75) return 'green';
  if (score >= 50) return 'amber';
  return 'red';
};

/* ─── RAG Badge component ─── */
function RAGBadge({ status, showLabel = true, size = 'md', tooltipText }) {
  const cfg = RAG_CONFIG[status] || RAG_CONFIG.red;
  const Icon = cfg.icon;
  const dotSize = size === 'sm' ? 'w-2.5 h-2.5' : 'w-3 h-3';
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm';

  const badge = (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border ${cfg.badge} ${textSize} font-medium`}
      data-testid={`rag-badge-${status}`}
    >
      <span className={`${dotSize} rounded-full ${cfg.dot} inline-block shrink-0`} />
      {showLabel && <span>{cfg.label}</span>}
    </span>
  );

  if (tooltipText) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>{badge}</TooltipTrigger>
          <TooltipContent side="top" className="max-w-xs text-xs">
            <p>{tooltipText}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return badge;
}

/* ─── RAG Legend component ─── */
function RAGLegend({ summary }) {
  return (
    <div className="bg-gray-50 border rounded-lg p-4 mb-4" data-testid="rag-legend">
      <div className="flex items-center gap-2 mb-3">
        <Info className="h-4 w-4 text-gray-500" />
        <h5 className="text-sm font-semibold text-gray-700">Artefact Status Legend</h5>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {Object.entries(RAG_CONFIG).map(([key, cfg]) => {
          const Icon = cfg.icon;
          const count = summary ? summary[key] : null;
          return (
            <div
              key={key}
              className="flex items-start gap-2 p-2 rounded-md bg-white border"
              data-testid={`rag-legend-${key}`}
            >
              <span className={`w-4 h-4 rounded-full ${cfg.dot} mt-0.5 shrink-0`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1">
                  <Icon className={`h-3.5 w-3.5 ${key === 'green' ? 'text-green-600' : key === 'amber' ? 'text-amber-600' : 'text-red-600'}`} />
                  <span className="text-sm font-medium">{cfg.label}</span>
                  {count != null && (
                    <span className={`text-xs font-bold ml-auto ${key === 'green' ? 'text-green-700' : key === 'amber' ? 'text-amber-700' : 'text-red-700'}`}>
                      {count}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-0.5 leading-tight">{cfg.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Main Audit page ─── */
export default function Audit() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [running, setRunning] = useState(null);
  const [detailSession, setDetailSession] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [artefactData, setArtefactData] = useState(null);
  const [artefactLoading, setArtefactLoading] = useState(false);
  const [signOffOpen, setSignOffOpen] = useState(false);
  const [signOffNotes, setSignOffNotes] = useState('');
  const [signOffId, setSignOffId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [auditData, setAuditData] = useState({ audit_type: 'external', scope: '' });

  useEffect(() => { loadSessions(); }, []);

  const loadSessions = async () => {
    try {
      const response = await auditApi.getSessions();
      setSessions(response);
    } catch (error) {
      toast.error('Failed to load audit sessions');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await auditApi.create(auditData);
      toast.success('Audit session created!');
      setCreateOpen(false);
      setAuditData({ audit_type: 'external', scope: '' });
      loadSessions();
    } catch (error) {
      toast.error('Failed to create audit');
    } finally {
      setCreating(false);
    }
  };

  const handleRunAudit = async (auditId) => {
    setRunning(auditId);
    try {
      const response = await auditApi.run(auditId);
      toast.success(`Audit completed! Score: ${response.overall_score}/100`);
      loadSessions();
    } catch (error) {
      toast.error('Audit execution failed');
    } finally {
      setRunning(null);
    }
  };

  const handleViewDetail = async (session) => {
    try {
      const detail = await auditApi.getById(session.id);
      setDetailSession(detail);
      setDetailOpen(true);
      // Load artefact status data with RAG indicators
      loadArtefactStatus(session.id);
    } catch {
      setDetailSession(session);
      setDetailOpen(true);
    }
  };

  const loadArtefactStatus = async (auditId) => {
    setArtefactLoading(true);
    setArtefactData(null);
    try {
      const data = await auditApi.getArtefactStatus(auditId);
      setArtefactData(data);
    } catch {
      // Fallback: artefact status not available (audit may not be run yet)
      setArtefactData(null);
    } finally {
      setArtefactLoading(false);
    }
  };

  const handleSignOff = async () => {
    try {
      await auditApi.signOff(signOffId, { notes: signOffNotes });
      toast.success('Audit signed off successfully');
      setSignOffOpen(false);
      setSignOffNotes('');
      setSignOffId(null);
      loadSessions();
    } catch (error) {
      toast.error('Sign-off failed');
    }
  };

  const handleExport = async (auditId) => {
    try {
      const response = await auditApi.exportReport(auditId);
      toast.success('Audit report generated');
      const blob = new Blob([JSON.stringify(response.report, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit-report-${auditId}.json`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error('Export failed');
    }
  };

  const getStatusColor = (status) => {
    const map = {
      'Completed': 'bg-green-100 text-green-800',
      'Signed Off': 'bg-blue-100 text-blue-800',
      'In Progress': 'bg-yellow-100 text-yellow-800',
      'Created': 'bg-gray-100 text-gray-800',
    };
    return map[status] || 'bg-gray-100 text-gray-800';
  };

  const trimmedAuditSearch = (searchQuery || '').trim();
  const filtered = sessions.filter(s =>
    !trimmedAuditSearch || s.scope?.toLowerCase().includes(trimmedAuditSearch.toLowerCase()) || s.audit_type?.toLowerCase().includes(trimmedAuditSearch.toLowerCase())
  );

  /* Helper to get RAG status from a control in the session list */
  const getControlRAG = (ctrl) => {
    if (ctrl.rag_status) return ctrl.rag_status;
    const score = ctrl.compliance_score ?? ctrl.score;
    if (score == null) return 'red';
    return getRAGFromScore(score);
  };

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center shadow-lg">
            <Shield className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold" data-testid="audit-title">Audit Management</h1>
            <p className="text-muted-foreground">AI-powered compliance audits</p>
          </div>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="create-audit-button">
              <Plus className="mr-2 h-4 w-4" /> Create Audit
            </Button>
          </DialogTrigger>
          <DialogContent data-testid="create-audit-dialog">
            <DialogHeader>
              <DialogTitle>Create Audit Session</DialogTitle>
              <DialogDescription>Setup a new compliance audit</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreate} data-testid="create-audit-form" className="space-y-4">
              <div>
                <Label>Audit Type</Label>
                <Select value={auditData.audit_type} onValueChange={(v) => setAuditData({ ...auditData, audit_type: v })}>
                  <SelectTrigger data-testid="audit-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="external">External Audit</SelectItem>
                    <SelectItem value="internal">Internal Audit</SelectItem>
                    <SelectItem value="regulatory">Regulatory Audit</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Scope</Label>
                <Input value={auditData.scope} onChange={(e) => setAuditData({ ...auditData, scope: e.target.value })} placeholder="e.g., RBI Compliance Audit 2025" required data-testid="audit-scope-input" />
              </div>
              <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white" disabled={creating} data-testid="submit-create-audit">
                {creating ? 'Creating...' : 'Create Audit Session'}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Search */}
      <div className="relative" data-testid="audit-search">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input placeholder="Search audits..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-9" data-testid="audit-search-input" />
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64" data-testid="audit-loading">
          <div className="text-muted-foreground">Loading audits...</div>
        </div>
      ) : filtered.length === 0 ? (
        <Card className="flex flex-col items-center justify-center h-64" data-testid="audit-empty">
          <CardContent className="text-center py-8">
            <Shield className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Audits Yet</h3>
            <p className="text-muted-foreground mb-4">Create your first audit session</p>
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" /> Create Audit
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="border rounded-lg" data-testid="audit-table">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Controls</TableHead>
                <TableHead>RAG</TableHead>
                <TableHead>Sign-off</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((session) => {
                const ragStatus = session.overall_score != null ? getRAGFromScore(session.overall_score) : null;
                return (
                  <TableRow key={session.id} data-testid={`audit-row-${session.id}`}>
                    <TableCell className="font-medium capitalize">{session.audit_type}</TableCell>
                    <TableCell>{session.scope}</TableCell>
                    <TableCell>
                      <Badge className={getStatusColor(session.status)} data-testid={`audit-status-${session.id}`}>{session.status}</Badge>
                    </TableCell>
                    <TableCell>
                      {session.overall_score != null ? (
                        <span className={`font-bold ${session.overall_score >= 75 ? 'text-green-600' : session.overall_score >= 50 ? 'text-yellow-600' : 'text-red-600'}`} data-testid={`audit-score-${session.id}`}>
                          {session.overall_score}%
                        </span>
                      ) : '\u2014'}
                    </TableCell>
                    <TableCell>{session.controls?.length || 0}</TableCell>
                    <TableCell>
                      {ragStatus ? (
                        <RAGBadge
                          status={ragStatus}
                          showLabel={false}
                          size="sm"
                          tooltipText={RAG_CONFIG[ragStatus]?.description}
                        />
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border bg-gray-100 text-gray-500 text-xs font-medium">
                          <span className="w-2.5 h-2.5 rounded-full bg-gray-300 inline-block" />
                          N/A
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      {session.signed_off ? (
                        <Badge className="bg-blue-100 text-blue-800" data-testid={`audit-signoff-${session.id}`}>
                          <CheckCircle className="h-3 w-3 mr-1" /> Signed
                        </Badge>
                      ) : '\u2014'}
                    </TableCell>
                    <TableCell className="text-sm text-gray-500">
                      {session.created_at ? new Date(session.created_at).toLocaleDateString() : '\u2014'}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm" onClick={() => handleViewDetail(session)} data-testid={`view-audit-${session.id}`}>
                          <Eye className="h-4 w-4" />
                        </Button>
                        {session.status !== 'Completed' && session.status !== 'Signed Off' && (
                          <Button variant="ghost" size="sm" onClick={() => handleRunAudit(session.id)} disabled={running === session.id} data-testid={`run-audit-${session.id}`}>
                            {running === session.id ? <Clock className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                          </Button>
                        )}
                        {session.status === 'Completed' && !session.signed_off && (
                          <Button variant="ghost" size="sm" onClick={() => { setSignOffId(session.id); setSignOffOpen(true); }} data-testid={`signoff-audit-${session.id}`}>
                            <PenLine className="h-4 w-4" />
                          </Button>
                        )}
                        {(session.status === 'Completed' || session.status === 'Signed Off') && (
                          <Button variant="ghost" size="sm" onClick={() => handleExport(session.id)} data-testid={`export-audit-${session.id}`}>
                            <Download className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={(open) => { setDetailOpen(open); if (!open) { setArtefactData(null); } }}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto" data-testid="audit-detail-dialog">
          <DialogHeader>
            <DialogTitle className="capitalize">{detailSession?.audit_type} Audit</DialogTitle>
            <DialogDescription>{detailSession?.scope}</DialogDescription>
          </DialogHeader>
          {detailSession && (
            <div className="space-y-4">
              {/* Summary cards */}
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold" data-testid="audit-detail-score">{detailSession.overall_score ?? '\u2014'}%</div>
                  <div className="text-sm text-gray-500">Overall Score</div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold">{detailSession.controls?.length || 0}</div>
                  <div className="text-sm text-gray-500">Controls</div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <Badge className={getStatusColor(detailSession.status)}>{detailSession.status}</Badge>
                  <div className="text-sm text-gray-500 mt-1">Status</div>
                </div>
              </div>

              {/* RAG Summary Bar (from artefact-status endpoint) */}
              {artefactData?.summary && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg" data-testid="rag-summary-bar">
                  <span className="text-sm font-medium text-gray-600">RAG Summary:</span>
                  <div className="flex items-center gap-2">
                    <RAGBadge status="green" showLabel={true} size="sm" />
                    <span className="text-sm font-bold text-green-700">{artefactData.summary.green}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <RAGBadge status="amber" showLabel={true} size="sm" />
                    <span className="text-sm font-bold text-amber-700">{artefactData.summary.amber}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <RAGBadge status="red" showLabel={true} size="sm" />
                    <span className="text-sm font-bold text-red-700">{artefactData.summary.red}</span>
                  </div>
                </div>
              )}

              {/* Artefact Status Matrix – from artefact-status endpoint */}
              {artefactData && artefactData.controls?.length > 0 && (
                <div data-testid="artefact-status-matrix">
                  <h4 className="font-medium mb-2">Artefact Status (Red / Amber / Green)</h4>

                  {/* Legend */}
                  <RAGLegend summary={artefactData.summary} />

                  <div className="border rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-gray-50">
                          <TableHead>Control</TableHead>
                          <TableHead>Category</TableHead>
                          <TableHead>RAG Status</TableHead>
                          <TableHead>Score</TableHead>
                          <TableHead>Evidence</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {artefactData.controls.map((ctrl, i) => (
                          <TableRow key={ctrl.control_id || i} data-testid={`artefact-row-${ctrl.rag_status}`}>
                            <TableCell className="text-sm font-medium">{ctrl.control_name || `Control ${i+1}`}</TableCell>
                            <TableCell className="text-sm text-gray-600">{ctrl.category || '\u2014'}</TableCell>
                            <TableCell>
                              <RAGBadge
                                status={ctrl.rag_status}
                                showLabel={true}
                                tooltipText={RAG_CONFIG[ctrl.rag_status]?.description}
                              />
                            </TableCell>
                            <TableCell>
                              {ctrl.compliance_score != null ? (
                                <span className={`text-sm font-semibold ${ctrl.compliance_score >= 75 ? 'text-green-600' : ctrl.compliance_score >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                                  {Math.round(ctrl.compliance_score)}%
                                </span>
                              ) : '\u2014'}
                            </TableCell>
                            <TableCell>
                              <div className="text-xs space-y-0.5">
                                <div className="flex items-center gap-1">
                                  <span className="text-gray-500">Required:</span>
                                  <span className="font-medium">{ctrl.total_required}</span>
                                </div>
                                <div className="flex items-center gap-1">
                                  <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                                  <span className="text-gray-500">Approved:</span>
                                  <span className="font-medium text-green-700">{ctrl.approved_count}</span>
                                </div>
                                {ctrl.pending_count > 0 && (
                                  <div className="flex items-center gap-1">
                                    <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
                                    <span className="text-gray-500">Pending:</span>
                                    <span className="font-medium text-amber-700">{ctrl.pending_count}</span>
                                  </div>
                                )}
                                {ctrl.rejected_count > 0 && (
                                  <div className="flex items-center gap-1">
                                    <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
                                    <span className="text-gray-500">Rejected:</span>
                                    <span className="font-medium text-red-700">{ctrl.rejected_count}</span>
                                  </div>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {/* Fallback: show controls from session data if artefact endpoint not available */}
              {!artefactData && !artefactLoading && detailSession.controls?.length > 0 && (
                <div data-testid="artefact-status-matrix">
                  <h4 className="font-medium mb-2">Control Artefact Status</h4>

                  {/* Legend */}
                  <RAGLegend />

                  <div className="border rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-gray-50">
                          <TableHead>Control</TableHead>
                          <TableHead>Category</TableHead>
                          <TableHead>RAG Status</TableHead>
                          <TableHead>Evidence</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailSession.controls.map((ctrl, i) => {
                          const rag = getControlRAG(ctrl);
                          return (
                            <TableRow key={i} data-testid={`artefact-row-${rag}`}>
                              <TableCell className="text-sm font-medium">{ctrl.name || ctrl.control_name || ctrl.title || `Control ${i+1}`}</TableCell>
                              <TableCell className="text-sm text-gray-600">{ctrl.category || '\u2014'}</TableCell>
                              <TableCell>
                                <RAGBadge
                                  status={rag}
                                  showLabel={true}
                                  tooltipText={RAG_CONFIG[rag]?.description}
                                />
                              </TableCell>
                              <TableCell>{ctrl.evidence_count || 0} items</TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {artefactLoading && (
                <div className="text-center py-4 text-gray-500 text-sm" data-testid="artefact-loading">
                  Loading artefact status...
                </div>
              )}

              {/* Sign-off info */}
              {detailSession.signed_off && (
                <div className="bg-blue-50 p-4 rounded-md" data-testid="audit-signoff-info">
                  <div className="flex items-center gap-2 font-medium text-blue-700 mb-1">
                    <CheckCircle className="h-4 w-4" /> Signed Off
                  </div>
                  <div className="text-sm text-blue-600">By: {detailSession.signed_off_by}</div>
                  <div className="text-sm text-blue-600">At: {detailSession.signed_off_at ? new Date(detailSession.signed_off_at).toLocaleString() : '\u2014'}</div>
                  {detailSession.sign_off_notes && <div className="text-sm mt-1">{detailSession.sign_off_notes}</div>}
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Sign-off Dialog */}
      <Dialog open={signOffOpen} onOpenChange={setSignOffOpen}>
        <DialogContent data-testid="signoff-dialog">
          <DialogHeader>
            <DialogTitle>Compliance Sign-Off</DialogTitle>
            <DialogDescription>Complete sign-off for this audit session</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Textarea placeholder="Sign-off notes..." value={signOffNotes} onChange={(e) => setSignOffNotes(e.target.value)} data-testid="signoff-notes-input" rows={3} />
            <Button onClick={handleSignOff} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="submit-signoff">
              <CheckCircle className="mr-2 h-4 w-4" /> Complete Sign-Off
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
