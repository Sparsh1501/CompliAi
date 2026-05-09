import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { npciApi } from '../lib/api';
import { useUpload } from '../context/UploadContext';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Shield, Download, Search, RefreshCw, Loader2, FileText,
  Eye, Play, ChevronLeft, ExternalLink, CheckCircle, Clock,
  AlertCircle, Zap, Database, BarChart3, X, Timer, Settings2,
  CalendarClock, ToggleLeft, ToggleRight, Rocket, ClipboardList,
  ListChecks, FileCheck2, Smartphone, Filter, RotateCcw
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

const PRODUCTS = [
  { slug: 'all', label: 'All Products' },
  { slug: 'upi', label: 'UPI' },
  { slug: 'nach', label: 'NACH' },
  { slug: 'netc', label: 'NETC' },
  { slug: 'imps', label: 'IMPS' },
  { slug: 'nfs', label: 'NFS' },
  { slug: 'cts', label: 'CTS' },
  { slug: 'bhim-aadhaar', label: 'BHIM Aadhaar' },
  { slug: 'aeps', label: 'AePS' },
  { slug: 'e-rupi', label: 'e-RUPI' },
  { slug: 'rupay', label: 'RuPay' },
  { slug: 'e-kyc-setu-system', label: 'e-KYC Setu' },
  { slug: 'others', label: 'Others' },
];

const YEARS = ['2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016'];

export default function NPCICirculars() {
  const { setShowPanel } = useUpload();
  const navigate = useNavigate();
  // State
  const [stats, setStats] = useState({ total: 0, processed: 0, pending: 0, failed: 0, in_progress: 0, by_product: [] });
  const [circulars, setCirculars] = useState([]);
  const [totalCirculars, setTotalCirculars] = useState(0);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [yearFilter, setYearFilter] = useState('all');
  // Filter by AI processing state. Backend understands:
  //   "completed" | "pending" | "failed" | "processing" | undefined
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Detail view
  const [selectedCircular, setSelectedCircular] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Demo Point #2: Required Evidences rollup
  const [evidenceRollup, setEvidenceRollup] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  // Scrape dialog
  const [scrapeOpen, setScrapeOpen] = useState(false);
  const [scrapeProduct, setScrapeProduct] = useState('upi');
  const [scrapeYear, setScrapeYear] = useState('2025');
  const [scraping, setScraping] = useState(false);
  const [scrapeProgress, setScrapeProgress] = useState([]);

  // Process all
  const [processing, setProcessing] = useState(false);
  const [processProgress, setProcessProgress] = useState({ processed: 0, total: 0 });
  // Cancel-batch support: backend emits batch_id in the SSE start event.
  const [currentBatchId, setCurrentBatchId] = useState(null);
  const [cancelling, setCancelling] = useState(false);

  // Processing individual circular
  const [processingId, setProcessingId] = useState(null);

  // Feature #220: Schedule state
  const [scheduleConfig, setScheduleConfig] = useState(null);
  const [scheduleStatus, setScheduleStatus] = useState(null);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [triggeringSchedule, setTriggeringSchedule] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    enabled: false,
    interval_hours: 24,
    auto_process: true,
    auto_create_tasks: false,
  });

  // Load stats and circulars
  const loadStats = useCallback(async () => {
    try {
      const data = await npciApi.getStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load NPCI stats:', error);
    }
  }, []);

  const loadCirculars = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, size: pageSize };
      if (activeTab !== 'all') params.product = activeTab;
      if (yearFilter !== 'all') params.year = yearFilter;
      if (searchQuery) params.search = searchQuery;
      if (statusFilter !== 'all') params.status = statusFilter;

      const data = await npciApi.getCirculars(params);
      setCirculars(data.items || []);
      setTotalCirculars(data.total || 0);
    } catch (error) {
      console.error('Failed to load circulars:', error);
      toast.error('Failed to load circulars');
    } finally {
      setLoading(false);
    }
  }, [page, activeTab, yearFilter, searchQuery, statusFilter]);

  // Feature #220: Load schedule status
  const loadSchedule = useCallback(async () => {
    try {
      const data = await npciApi.getSchedule();
      setScheduleConfig(data.config);
      setScheduleStatus(data.status);
      setScheduleForm({
        enabled: data.config?.enabled || false,
        interval_hours: data.config?.interval_hours || 24,
        auto_process: data.config?.auto_process !== false,
        auto_create_tasks: data.config?.auto_create_tasks || false,
      });
    } catch (error) {
      console.error('Failed to load schedule:', error);
    }
  }, []);

  const handleToggleSchedule = async () => {
    try {
      const newEnabled = !scheduleForm.enabled;
      const data = await npciApi.toggleSchedule(newEnabled);
      setScheduleConfig(data.config);
      setScheduleStatus(data.status);
      setScheduleForm(prev => ({ ...prev, enabled: newEnabled }));
      toast.success(newEnabled ? 'Scheduled scraping enabled' : 'Scheduled scraping disabled');
    } catch (error) {
      toast.error('Failed to toggle schedule');
    }
  };

  const handleSaveSchedule = async () => {
    setScheduleLoading(true);
    try {
      const data = await npciApi.updateSchedule(scheduleForm);
      setScheduleConfig(data.config);
      setScheduleStatus(data.status);
      toast.success('Schedule configuration saved');
      setScheduleOpen(false);
    } catch (error) {
      toast.error('Failed to save schedule configuration');
    } finally {
      setScheduleLoading(false);
    }
  };

  const handleTriggerSchedule = async () => {
    setTriggeringSchedule(true);
    try {
      const data = await npciApi.triggerSchedule();
      toast.success(data.message || 'Scheduled scrape completed');
      loadStats();
      loadCirculars();
      loadSchedule();
    } catch (error) {
      toast.error('Failed to trigger scheduled scrape');
    } finally {
      setTriggeringSchedule(false);
    }
  };

  useEffect(() => {
    loadStats();
    loadCirculars();
    loadSchedule();
  }, [loadStats, loadCirculars, loadSchedule]);

  // On mount: if a Process-All batch is already running on the server (e.g.
  // user reloaded the page mid-run), re-attach the Cancel button so the user
  // isn't stuck waiting for it to finish silently. We don't reattach the SSE
  // stream — that connection is gone — but we let the user kill the batch.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await npciApi.getActiveProcessAllBatches();
        if (cancelled || !data?.active?.length) return;
        const batch = data.active[0];
        setProcessing(true);
        setCurrentBatchId(batch.batch_id);
        setProcessProgress({ processed: batch.processed || 0, total: batch.total || 0 });
        toast.info(
          `A Process-All batch is still running on the server (${batch.processed || 0}/${batch.total || 0}). Click Cancel to stop it.`,
          { duration: 6000 }
        );
      } catch {
        // Endpoint missing or backend down — ignore silently.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Tab change resets page
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setPage(1);
  };

  // Get product count from stats
  const getProductCount = (slug) => {
    if (slug === 'all') return stats.total;
    const prod = (stats.by_product || []).find(p => p.product === slug);
    return prod ? prod.total : 0;
  };

  // Open circular detail
  const openDetail = async (circular) => {
    setDetailLoading(true);
    setEvidenceRollup(null);
    try {
      const data = await npciApi.getCircular(circular._id);
      setSelectedCircular(data);

      // Demo Point #2: parallel-fetch the evidence rollup if circular is processed
      if (data.processing_status === 'completed') {
        setEvidenceLoading(true);
        try {
          const ev = await npciApi.getEvidenceRollup(circular._id);
          setEvidenceRollup(ev);
        } catch (e) {
          // Non-fatal: evidence rollup is a value-add view, not blocking
          console.warn('Evidence rollup fetch failed:', e);
        } finally {
          setEvidenceLoading(false);
        }
      }
    } catch (error) {
      toast.error('Failed to load circular details');
    } finally {
      setDetailLoading(false);
    }
  };

  // Process single circular (runs as background job with progress tracking)
  const handleProcessCircular = async (circularId) => {
    setProcessingId(circularId);
    try {
      const result = await npciApi.processCircular(circularId);
      setShowPanel(true);
      toast.info('Processing started! Track progress in the upload panel.', { duration: 3000 });
      // Refresh list after a delay to pick up status changes
      setTimeout(() => {
        loadCirculars();
        loadStats();
      }, 5000);
    } catch (error) {
      toast.error('Failed to process circular: ' + (error.response?.data?.detail || 'Unknown error'));
    } finally {
      setProcessingId(null);
    }
  };

  // Trigger scraping via SSE
  const handleScrape = async () => {
    setScraping(true);
    setScrapeProgress([]);

    try {
      const token = localStorage.getItem('token');
      let url = `${API_URL}/api/npci/scrape?product=${scrapeProduct}&year=${scrapeYear}`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream',
        },
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));
              setScrapeProgress(prev => [...prev, event]);

              if (event.event === 'complete') {
                toast.success(event.message || 'Scraping completed!');
                setScraping(false);
                loadCirculars();
                loadStats();
              } else if (event.event === 'error') {
                toast.error(event.message || 'Scraping failed');
                setScraping(false);
              }
            } catch (e) {
              // Skip unparseable lines
            }
          }
        }
      }
    } catch (error) {
      toast.error('Scraping failed: ' + error.message);
    } finally {
      setScraping(false);
    }
  };

  // Process circulars via SSE.
  //   scope = "all"     -> pending + previously-failed (default; the green Process All button)
  //   scope = "pending" -> only never-attempted
  //   scope = "failed"  -> only previously-failed (the red Retry-Failed button)
  const handleProcessAll = async (scope = 'all') => {
    setProcessing(true);
    setProcessProgress({ processed: 0, total: 0 });
    setCurrentBatchId(null);
    setCancelling(false);

    try {
      const token = localStorage.getItem('token');
      const url = scope && scope !== 'all'
        ? `${API_URL}/api/npci/circulars/process-all?status=${encodeURIComponent(scope)}`
        : `${API_URL}/api/npci/circulars/process-all`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream',
        },
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));

              if (event.event === 'start') {
                setProcessProgress({ processed: 0, total: event.total });
                if (event.batch_id) setCurrentBatchId(event.batch_id);
              } else if (event.event === 'progress') {
                setProcessProgress({ processed: event.processed, total: event.total });
              } else if (event.event === 'item_error') {
                // Surface failures live without spamming toasts; UI shows counts via the stats refresh below.
                setProcessProgress({ processed: event.processed, total: event.total });
              } else if (event.event === 'cancelled') {
                toast.info(event.message || 'Batch cancelled', { duration: 4000 });
                setProcessing(false);
                setCurrentBatchId(null);
                setCancelling(false);
                loadCirculars();
                loadStats();
              } else if (event.event === 'complete') {
                toast.success(event.message || 'Processing completed!');
                setProcessing(false);
                setCurrentBatchId(null);
                setCancelling(false);
                loadCirculars();
                loadStats();
              } else if (event.event === 'error') {
                toast.error(event.message || 'Processing failed');
                setProcessing(false);
                setCurrentBatchId(null);
                setCancelling(false);
              }
            } catch (e) {
              // Skip
            }
          }
        }
      }
    } catch (error) {
      toast.error('Processing failed: ' + error.message);
    } finally {
      setProcessing(false);
      setCurrentBatchId(null);
      setCancelling(false);
    }
  };

  // Request graceful cancellation of the in-flight Process-All batch.
  // The backend lets the currently-processing circular finish (so its
  // Claude call isn't wasted) and then emits an `event: cancelled` SSE
  // event which the loop above turns into final UI state.
  const handleCancelProcessAll = async () => {
    if (!processing) return;
    setCancelling(true);
    try {
      const result = await npciApi.cancelProcessAll(currentBatchId);
      const n = (result?.cancelled || []).length;
      if (n > 0) {
        toast.info('Cancelling — current circular will finish, then the batch will stop.', { duration: 4000 });
      } else {
        toast.warning('No active batch found on server. UI may be out of sync.');
        // Force-close UI so the user isn't stuck.
        setProcessing(false);
        setCurrentBatchId(null);
        setCancelling(false);
      }
    } catch (error) {
      toast.error('Cancel failed: ' + (error.response?.data?.detail || error.message));
      setCancelling(false);
    }
  };

  // Total pages
  const totalPages = Math.ceil(totalCirculars / pageSize);

  // Detail view
  if (selectedCircular) {
    return (
      <div className="space-y-6" data-testid="npci-circular-detail">
        {/* Back button */}
        <div className="flex items-center gap-3 justify-between">
          <Button variant="ghost" size="sm" onClick={() => { setSelectedCircular(null); setEvidenceRollup(null); }}>
            <ChevronLeft className="h-4 w-4 mr-1" /> Back to Circulars
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/device-binding-advisor')}
            title="Open Device Binding & RASP Advisor"
            className="text-emerald-700 border-emerald-200 hover:bg-emerald-50"
          >
            <Smartphone className="h-4 w-4 mr-1" />
            Device Binding Advisor
          </Button>
        </div>

        {/* Circular header */}
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="space-y-2 flex-1">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-emerald-700 border-emerald-300 bg-emerald-50">
                    {selectedCircular.product_label || selectedCircular.product}
                  </Badge>
                  <Badge variant="outline">{selectedCircular.year}</Badge>
                  {selectedCircular.processing_status === 'completed' ? (
                    <Badge className="bg-emerald-100 text-emerald-800">
                      <CheckCircle className="h-3 w-3 mr-1" /> AI Processed
                    </Badge>
                  ) : selectedCircular.processing_status === 'failed' ? (
                    <Badge className="bg-red-100 text-red-800" title={selectedCircular.processing_error || 'LLM extraction failed'}>
                      <AlertCircle className="h-3 w-3 mr-1" /> Failed
                    </Badge>
                  ) : selectedCircular.processing_status === 'processing' ? (
                    <Badge className="bg-blue-100 text-blue-800">
                      <Loader2 className="h-3 w-3 mr-1 animate-spin" /> Processing
                    </Badge>
                  ) : (
                    <Badge variant="secondary">
                      <Clock className="h-3 w-3 mr-1" /> Pending
                    </Badge>
                  )}
                </div>
                <CardTitle className="text-lg">{selectedCircular.title}</CardTitle>
              </div>
              <div className="flex gap-2 ml-4">
                {selectedCircular.pdf_url && (
                  <Button size="sm" variant="outline" asChild>
                    <a href={selectedCircular.pdf_url} target="_blank" rel="noopener noreferrer">
                      <Download className="h-4 w-4 mr-1" /> Download PDF
                    </a>
                  </Button>
                )}
                {selectedCircular.processing_status !== 'completed' && selectedCircular.processing_status !== 'processing' && (
                  <Button
                    size="sm"
                    onClick={() => handleProcessCircular(selectedCircular._id)}
                    disabled={processingId === selectedCircular._id}
                  >
                    {processingId === selectedCircular._id ? (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <Zap className="h-4 w-4 mr-1" />
                    )}
                    {selectedCircular.processing_status === 'failed' ? 'Retry AI Processing' : 'Process with AI'}
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
        </Card>

        {/* Demo Point #2: Required Evidences Rollup */}
        {selectedCircular.processing_status === 'completed' && (
          <Card data-testid="evidence-rollup">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <ClipboardList className="h-4 w-4 text-emerald-600" />
                    Required Evidences for Compliance
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">
                    Aggregated from extracted clauses - what an auditor would expect to see for this circular.
                  </p>
                </div>
                {evidenceLoading && <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />}
              </div>
            </CardHeader>
            <CardContent>
              {evidenceRollup ? (
                <div className="space-y-4">
                  {/* Stats strip */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
                      <div className="text-2xl font-bold text-emerald-700">
                        {evidenceRollup.evidence_items?.length || 0}
                      </div>
                      <div className="text-xs text-emerald-700">Required evidences</div>
                    </div>
                    <div className="p-3 rounded-lg bg-blue-50 border border-blue-100">
                      <div className="text-2xl font-bold text-blue-700">
                        {evidenceRollup.stats?.clauses || 0}
                      </div>
                      <div className="text-xs text-blue-700">Clauses analyzed</div>
                    </div>
                    <div className="p-3 rounded-lg bg-red-50 border border-red-100">
                      <div className="text-2xl font-bold text-red-700">
                        {evidenceRollup.stats?.impact?.high || 0}
                      </div>
                      <div className="text-xs text-red-700">High-impact</div>
                    </div>
                    <div className="p-3 rounded-lg bg-amber-50 border border-amber-100">
                      <div className="text-2xl font-bold text-amber-700">
                        {(evidenceRollup.stats?.entities?.length) || 0}
                      </div>
                      <div className="text-xs text-amber-700">Entities involved</div>
                    </div>
                  </div>

                  {/* Categories chip row */}
                  {evidenceRollup.stats?.categories && Object.keys(evidenceRollup.stats.categories).length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      <span className="text-xs text-muted-foreground self-center mr-1">Categories:</span>
                      {Object.entries(evidenceRollup.stats.categories).map(([cat, count]) => (
                        <Badge key={cat} variant="outline" className="text-xs">
                          {cat} <span className="ml-1 text-muted-foreground">·{count}</span>
                        </Badge>
                      ))}
                    </div>
                  )}

                  {/* Evidence items */}
                  {evidenceRollup.evidence_items?.length > 0 ? (
                    <div className="space-y-2">
                      {evidenceRollup.evidence_items.map((ev, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-lg border border-gray-100 bg-white hover:border-emerald-200 transition-colors"
                        >
                          <div className="flex items-start gap-3">
                            <div className="flex-shrink-0 mt-0.5">
                              <FileCheck2 className="h-4 w-4 text-emerald-600" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap mb-1">
                                <Badge
                                  variant="outline"
                                  className={
                                    ev.evidence_type === 'control' ? 'bg-blue-50 border-blue-200 text-blue-700' :
                                    ev.evidence_type === 'document' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' :
                                    ev.evidence_type === 'record' ? 'bg-violet-50 border-violet-200 text-violet-700' :
                                    ev.evidence_type === 'report' ? 'bg-amber-50 border-amber-200 text-amber-700' :
                                    ev.evidence_type === 'training' ? 'bg-pink-50 border-pink-200 text-pink-700' :
                                    'bg-gray-50 border-gray-200 text-gray-700'
                                  }
                                >
                                  {ev.evidence_type}
                                </Badge>
                                {ev.mandatory && (
                                  <Badge className="bg-red-50 text-red-700 border-red-200 text-xs" variant="outline">
                                    mandatory
                                  </Badge>
                                )}
                                <span className="text-xs text-muted-foreground">
                                  Owner: {ev.owner_function}
                                </span>
                              </div>
                              <p className="text-sm text-gray-800 mb-1">{ev.requirement}</p>
                              <p className="text-xs text-muted-foreground">
                                <span className="font-medium">Verification:</span> {ev.verification_method}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">
                      No structured evidences were extracted from this circular's clauses.
                    </p>
                  )}
                </div>
              ) : evidenceLoading ? (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin mr-2" /> Aggregating required evidences...
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  Evidence rollup unavailable. Try processing this circular with AI again.
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Extracted Clauses */}
        {selectedCircular.clauses && selectedCircular.clauses.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ListChecks className="h-4 w-4" />
                Extracted Clauses ({selectedCircular.clauses.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Accordion type="multiple" className="w-full">
                {selectedCircular.clauses.map((clause, idx) => {
                  // NPCI clauses (extracted by npci_processing_service) use `clause_text`,
                  // while the legacy regulation Clause model uses `text`. Support both.
                  const body = clause.clause_text || clause.text || clause.original_text || '';
                  const heading =
                    clause.title ||
                    (clause.clause_type ? `${clause.clause_type[0].toUpperCase()}${clause.clause_type.slice(1)}` : null) ||
                    (body ? body.split(/\s+/).slice(0, 10).join(' ') + (body.split(/\s+/).length > 10 ? '…' : '') : `Clause ${idx + 1}`);
                  return (
                    <AccordionItem key={idx} value={`clause-${idx}`}>
                      <AccordionTrigger className="text-sm">
                        <div className="flex items-center gap-2 flex-wrap text-left">
                          <Badge variant="outline" className="text-xs">{clause.clause_id || `C${idx + 1}`}</Badge>
                          <span className="line-clamp-1">{heading}</span>
                          {clause.compliance_impact && (
                            <Badge
                              variant="outline"
                              className={
                                clause.compliance_impact === 'high' ? 'text-red-700 border-red-300' :
                                clause.compliance_impact === 'medium' ? 'text-amber-700 border-amber-300' :
                                'text-green-700 border-green-300'
                              }
                            >
                              {clause.compliance_impact}
                            </Badge>
                          )}
                          {clause.category && (
                            <Badge variant="secondary" className="text-xs">{clause.category}</Badge>
                          )}
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="space-y-2">
                          {body ? (
                            <p className="text-sm text-gray-800 whitespace-pre-wrap">{body}</p>
                          ) : (
                            <p className="text-sm italic text-muted-foreground">No clause text available.</p>
                          )}
                          {clause.key_requirements && clause.key_requirements.length > 0 && (
                            <div>
                              <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide mt-2 mb-1">Key Requirements</div>
                              <ul className="space-y-0.5">
                                {clause.key_requirements.map((req, ridx) => (
                                  <li key={ridx} className="text-xs text-gray-700 flex items-start gap-1.5">
                                    <CheckCircle className="h-3 w-3 text-emerald-600 flex-shrink-0 mt-0.5" />
                                    <span>{req}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {clause.entities && clause.entities.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              <span className="text-[11px] text-muted-foreground self-center mr-1">Entities:</span>
                              {clause.entities.map((e, eidx) => (
                                <Badge key={eidx} variant="outline" className="text-[10px]">{e}</Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  );
                })}
              </Accordion>
            </CardContent>
          </Card>
        )}

        {/* Raw Text */}
        {selectedCircular.raw_text && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Raw Text</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="text-xs text-muted-foreground whitespace-pre-wrap max-h-96 overflow-y-auto bg-muted p-4 rounded-md">
                {selectedCircular.raw_text}
              </pre>
            </CardContent>
          </Card>
        )}
      </div>
    );
  }

  // Main list view
  return (
    <div className="space-y-6" data-testid="npci-circulars-page">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6 text-emerald-600" />
            NPCI Circulars
          </h1>
          <p className="text-muted-foreground mt-1">
            Browse and manage NPCI circulars across all payment products
          </p>
        </div>
        <div className="flex gap-2 items-center">
          {processing && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground" data-testid="process-all-progress-pill">
              <Loader2 className="h-3 w-3 animate-spin text-emerald-600" />
              <span>
                {processProgress.processed}/{processProgress.total || '?'}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelProcessAll}
                disabled={cancelling}
                className="text-red-700 border-red-200 hover:bg-red-50"
                title="Cancel batch — the current circular will finish first to avoid wasting Claude tokens"
                data-testid="cancel-process-all-btn"
              >
                {cancelling ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" /> Cancelling…
                  </>
                ) : (
                  <>
                    <X className="h-4 w-4 mr-1" /> Cancel
                  </>
                )}
              </Button>
            </div>
          )}
          <Button
            variant="outline"
            onClick={() => handleProcessAll('all')}
            disabled={processing || (stats.pending === 0 && (stats.failed || 0) === 0)}
            title={(stats.failed || 0) > 0 ? `Process ${stats.pending} pending + retry ${stats.failed} failed circular(s)` : `Process ${stats.pending} pending circular(s)`}
          >
            {processing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Zap className="h-4 w-4 mr-2" />
            )}
            Process All{(stats.failed || 0) > 0 ? ` (incl. ${stats.failed} failed)` : ''}
          </Button>
          <Dialog open={scrapeOpen} onOpenChange={setScrapeOpen}>
            <DialogTrigger asChild>
              <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">
                <RefreshCw className="h-4 w-4 mr-2" />
                Scrape Now
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>Scrape NPCI Circulars</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Product</Label>
                  <Select value={scrapeProduct} onValueChange={setScrapeProduct}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PRODUCTS.filter(p => p.slug !== 'all').map(p => (
                        <SelectItem key={p.slug} value={p.slug}>{p.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Year</Label>
                  <Select value={scrapeYear} onValueChange={setScrapeYear}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {YEARS.map(y => (
                        <SelectItem key={y} value={y}>{y}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {scraping && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Scraping in progress...
                    </div>
                    <div className="max-h-40 overflow-y-auto bg-muted rounded-md p-3 text-xs space-y-1">
                      {scrapeProgress.map((event, idx) => (
                        <div key={idx} className={`${event.event === 'error' ? 'text-red-500' : event.event === 'complete' ? 'text-emerald-600 font-medium' : 'text-muted-foreground'}`}>
                          {event.message || JSON.stringify(event)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <Button
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
                  onClick={handleScrape}
                  disabled={scraping}
                >
                  {scraping ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Scraping...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" /> Start Scraping
                    </>
                  )}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Circulars</p>
                <p className="text-2xl font-bold">{stats.total}</p>
              </div>
              <Database className="h-8 w-8 text-emerald-600 opacity-50" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground" title="Real LLM clause extraction succeeded">AI Processed</p>
                <p className="text-2xl font-bold text-emerald-600">{stats.processed}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-emerald-600 opacity-50" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Pending</p>
                <p className="text-2xl font-bold text-amber-600">{stats.pending}</p>
              </div>
              <Clock className="h-8 w-8 text-amber-600 opacity-50" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground" title="LLM extraction failed (no credits, Ollama down, unreadable PDF, etc.)">Failed</p>
                <p className="text-2xl font-bold text-red-600">{stats.failed || 0}</p>
                {(stats.in_progress || 0) > 0 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {stats.in_progress} in progress
                  </p>
                )}
              </div>
              <AlertCircle className="h-8 w-8 text-red-600 opacity-50" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Feature #220: Schedule Status Bar */}
      <Card className="border-dashed">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <CalendarClock className="h-5 w-5 text-blue-600" />
                <span className="font-medium text-sm">Scheduled Scraping</span>
                {scheduleForm.enabled ? (
                  <Badge className="bg-emerald-100 text-emerald-800 text-xs">
                    <CheckCircle className="h-3 w-3 mr-1" /> Active
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="text-xs">
                    <Clock className="h-3 w-3 mr-1" /> Disabled
                  </Badge>
                )}
              </div>
              {scheduleStatus?.last_run && (
                <div className="text-xs text-muted-foreground">
                  Last sync: {new Date(scheduleStatus.last_run.completed_at || scheduleStatus.last_run.started_at).toLocaleString()}
                  {scheduleStatus.last_run.new_circulars > 0 && (
                    <Badge variant="outline" className="ml-2 text-xs text-blue-700 border-blue-300">
                      +{scheduleStatus.last_run.new_circulars} new
                    </Badge>
                  )}
                </div>
              )}
              {scheduleStatus?.next_run_at && scheduleForm.enabled && (
                <div className="text-xs text-muted-foreground">
                  Next run: {new Date(scheduleStatus.next_run_at).toLocaleString()}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleTriggerSchedule}
                disabled={triggeringSchedule}
                title="Run scrape now"
              >
                {triggeringSchedule ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Rocket className="h-4 w-4" />
                )}
                <span className="ml-1.5 hidden sm:inline">Sync Now</span>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleToggleSchedule}
                title={scheduleForm.enabled ? 'Disable scheduler' : 'Enable scheduler'}
              >
                {scheduleForm.enabled ? (
                  <ToggleRight className="h-5 w-5 text-emerald-600" />
                ) : (
                  <ToggleLeft className="h-5 w-5 text-muted-foreground" />
                )}
              </Button>

              {/* Schedule Config Dialog */}
              <Dialog open={scheduleOpen} onOpenChange={setScheduleOpen}>
                <DialogTrigger asChild>
                  <Button variant="ghost" size="sm" title="Schedule settings">
                    <Settings2 className="h-4 w-4" />
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      <CalendarClock className="h-5 w-5" />
                      Schedule Configuration
                    </DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    {/* Enable/Disable Toggle */}
                    <div className="flex items-center justify-between">
                      <div>
                        <Label className="font-medium">Enable Scheduled Scraping</Label>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Automatically check for new NPCI circulars
                        </p>
                      </div>
                      <Button
                        variant={scheduleForm.enabled ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setScheduleForm(f => ({ ...f, enabled: !f.enabled }))}
                        className={scheduleForm.enabled ? 'bg-emerald-600 hover:bg-emerald-700' : ''}
                      >
                        {scheduleForm.enabled ? 'Enabled' : 'Disabled'}
                      </Button>
                    </div>

                    {/* Interval */}
                    <div className="space-y-2">
                      <Label>Check Interval</Label>
                      <Select
                        value={String(scheduleForm.interval_hours)}
                        onValueChange={(v) => setScheduleForm(f => ({ ...f, interval_hours: parseInt(v) }))}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="1">Every hour</SelectItem>
                          <SelectItem value="6">Every 6 hours</SelectItem>
                          <SelectItem value="12">Every 12 hours</SelectItem>
                          <SelectItem value="24">Daily (recommended)</SelectItem>
                          <SelectItem value="48">Every 2 days</SelectItem>
                          <SelectItem value="168">Weekly</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Auto Process */}
                    <div className="flex items-center justify-between">
                      <div>
                        <Label className="font-medium">Auto-Process New Circulars</Label>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Extract clauses from new circulars automatically
                        </p>
                      </div>
                      <Button
                        variant={scheduleForm.auto_process ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setScheduleForm(f => ({ ...f, auto_process: !f.auto_process }))}
                        className={scheduleForm.auto_process ? 'bg-blue-600 hover:bg-blue-700' : ''}
                      >
                        {scheduleForm.auto_process ? 'On' : 'Off'}
                      </Button>
                    </div>

                    {/* Auto Create Tasks */}
                    <div className="flex items-center justify-between">
                      <div>
                        <Label className="font-medium">Auto-Create Review Tasks</Label>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Create compliance review tasks for new circulars
                        </p>
                      </div>
                      <Button
                        variant={scheduleForm.auto_create_tasks ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setScheduleForm(f => ({ ...f, auto_create_tasks: !f.auto_create_tasks }))}
                        className={scheduleForm.auto_create_tasks ? 'bg-blue-600 hover:bg-blue-700' : ''}
                      >
                        {scheduleForm.auto_create_tasks ? 'On' : 'Off'}
                      </Button>
                    </div>

                    {/* Per-product tracking info */}
                    {scheduleStatus?.product_tracking && Object.keys(scheduleStatus.product_tracking).length > 0 && (
                      <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">Product Tracking</Label>
                        <div className="grid grid-cols-2 gap-1 text-xs">
                          {Object.entries(scheduleStatus.product_tracking).map(([product, info]) => (
                            <div key={product} className="flex justify-between bg-muted rounded px-2 py-1">
                              <span className="font-medium">{product.toUpperCase()}</span>
                              <span className="text-muted-foreground">
                                {info.last_scraped_at ? new Date(info.last_scraped_at).toLocaleDateString() : 'Never'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Save Button */}
                    <Button
                      className="w-full"
                      onClick={handleSaveSchedule}
                      disabled={scheduleLoading}
                    >
                      {scheduleLoading ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <CheckCircle className="h-4 w-4 mr-2" />
                      )}
                      Save Configuration
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Process All Progress */}
      {processing && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Processing circulars...</span>
                <span>{processProgress.processed}/{processProgress.total}</span>
              </div>
              <Progress value={processProgress.total > 0 ? (processProgress.processed / processProgress.total) * 100 : 0} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search, Status Filter, Year Filter, Retry-Failed (conditional) */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search circulars..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="pl-10"
          />
        </div>

        {/* AI processing status filter (Demo Point #2 helper) */}
        <Select
          value={statusFilter}
          onValueChange={(v) => { setStatusFilter(v); setPage(1); }}
        >
          <SelectTrigger
            className="w-44"
            data-testid="status-filter"
            title="Filter by AI processing status"
          >
            <Filter className="h-3.5 w-3.5 mr-1.5 text-muted-foreground" />
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="completed">
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle className="h-3.5 w-3.5 text-emerald-600" /> AI Processed
              </span>
            </SelectItem>
            <SelectItem value="pending">
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-amber-600" /> Pending
              </span>
            </SelectItem>
            <SelectItem value="failed">
              <span className="inline-flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5 text-red-600" /> Failed
              </span>
            </SelectItem>
          </SelectContent>
        </Select>

        <Select value={yearFilter} onValueChange={(v) => { setYearFilter(v); setPage(1); }}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Year" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Years</SelectItem>
            {YEARS.map(y => (
              <SelectItem key={y} value={y}>{y}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Retry-Failed-only batch action — only visible when the failed
            filter is active so it's never confused with the global Process All */}
        {statusFilter === 'failed' && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleProcessAll('failed')}
            disabled={processing || (stats.failed || 0) === 0}
            className="text-red-700 border-red-200 hover:bg-red-50"
            title={(stats.failed || 0) === 0
              ? 'No failed circulars to retry'
              : `Retry ${stats.failed} failed circular(s) only`}
            data-testid="retry-failed-btn"
          >
            {processing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RotateCcw className="h-4 w-4 mr-2" />
            )}
            Retry All Failed{stats.failed ? ` (${stats.failed})` : ''}
          </Button>
        )}

        {/* Process-Pending-only batch action — only visible when the pending
            filter is active. Skips already-failed and completed circulars
            so the user knows exactly what's about to be processed. */}
        {statusFilter === 'pending' && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleProcessAll('pending')}
            disabled={processing || (stats.pending || 0) === 0}
            className="text-emerald-700 border-emerald-200 hover:bg-emerald-50"
            title={(stats.pending || 0) === 0
              ? 'No pending circulars to process'
              : `Process ${stats.pending} pending circular(s) only`}
            data-testid="process-pending-btn"
          >
            {processing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Zap className="h-4 w-4 mr-2" />
            )}
            Process All Pending{stats.pending ? ` (${stats.pending})` : ''}
          </Button>
        )}

        <Button variant="outline" size="sm" onClick={() => { loadCirculars(); loadStats(); }}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Product Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="flex flex-wrap h-auto gap-1 bg-muted p-1">
          {PRODUCTS.map(p => (
            <TabsTrigger key={p.slug} value={p.slug} className="text-xs px-3 py-1.5 data-[state=active]:bg-emerald-600 data-[state=active]:text-white">
              {p.label}
              {getProductCount(p.slug) > 0 && (
                <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5 py-0">
                  {getProductCount(p.slug)}
                </Badge>
              )}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Table Content */}
        <div className="mt-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
            </div>
          ) : circulars.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                <Shield className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p className="text-lg font-medium">No circulars found</p>
                <p className="mt-1">Use the "Scrape Now" button to fetch NPCI circulars</p>
              </CardContent>
            </Card>
          ) : (
            <>
              <Card>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-24">ID</TableHead>
                      <TableHead>Title</TableHead>
                      <TableHead className="w-20">Product</TableHead>
                      <TableHead className="w-16">Year</TableHead>
                      <TableHead className="w-24">Status</TableHead>
                      <TableHead className="w-32">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {circulars.map((circular) => (
                      <TableRow key={circular._id} className="cursor-pointer hover:bg-muted/50">
                        <TableCell className="font-mono text-xs">
                          {circular.npci_id || '-'}
                        </TableCell>
                        <TableCell
                          className="max-w-md truncate"
                          title={circular.title}
                          onClick={() => openDetail(circular)}
                        >
                          {circular.title}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">
                            {circular.product_label || circular.product}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">{circular.year}</TableCell>
                        <TableCell>
                          {circular.processing_status === 'completed' ? (
                            <Badge className="bg-emerald-100 text-emerald-800 text-xs">
                              <CheckCircle className="h-3 w-3 mr-1" /> AI Processed
                            </Badge>
                          ) : circular.processing_status === 'failed' ? (
                            <Badge className="bg-red-100 text-red-800 text-xs" title={circular.processing_error || 'LLM extraction failed'}>
                              <AlertCircle className="h-3 w-3 mr-1" /> Failed
                            </Badge>
                          ) : circular.processing_status === 'processing' ? (
                            <Badge className="bg-blue-100 text-blue-800 text-xs">
                              <Loader2 className="h-3 w-3 mr-1 animate-spin" /> Processing
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="text-xs">
                              <Clock className="h-3 w-3 mr-1" /> Scraped
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" onClick={() => openDetail(circular)} title="View details">
                              <Eye className="h-4 w-4" />
                            </Button>
                            {circular.processing_status !== 'completed' && circular.processing_status !== 'processing' && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleProcessCircular(circular._id)}
                                disabled={processingId === circular._id}
                                title={circular.processing_status === 'failed' ? 'Retry AI processing' : 'Process with AI'}
                              >
                                {processingId === circular._id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Zap className="h-4 w-4" />
                                )}
                              </Button>
                            )}
                            {circular.pdf_url && (
                              <Button variant="ghost" size="sm" asChild title="Download PDF">
                                <a href={circular.pdf_url} target="_blank" rel="noopener noreferrer">
                                  <Download className="h-4 w-4" />
                                </a>
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, totalCirculars)} of {totalCirculars}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage(p => p - 1)}
                    >
                      Previous
                    </Button>
                    <span className="flex items-center px-3 text-sm">
                      Page {page} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => setPage(p => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </Tabs>
    </div>
  );
}
