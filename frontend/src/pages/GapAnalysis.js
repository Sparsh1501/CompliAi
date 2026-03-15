import React, { useEffect, useState, useRef, useCallback } from 'react';
import { policiesApi, regulationsApi, gapAnalysisApi, tasksApi } from '../lib/api';
import { useLatestRequest } from '../hooks/useAbortController';
import SourceReferenceViewer from '../components/SourceReferenceViewer';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import {
  Sparkles, AlertTriangle, CheckCircle, AlertCircle, Info,
  History, Play, FileText, Scale, ChevronRight, Clock,
  Target, Shield, TrendingUp, ArrowRight, Eye, XCircle,
  Loader2, FileWarning, Lightbulb, ListChecks, Brain, Cpu, Zap,
  Plus, BookOpen, Bookmark, Download, FileSpreadsheet, FileJson
} from 'lucide-react';
import { toast } from 'sonner';

const severityColors = {
  Critical: 'bg-red-100 text-red-700 border-red-200',
  High: 'bg-amber-100 text-amber-700 border-amber-200',
  Medium: 'bg-blue-100 text-blue-700 border-blue-200',
  Low: 'bg-emerald-100 text-emerald-700 border-emerald-200'
};

const gapTypeConfig = {
  missing: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-50', label: 'Missing' },
  weak: { icon: AlertCircle, color: 'text-amber-500', bg: 'bg-amber-50', label: 'Weak' },
  partial: { icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50', label: 'Partial' },
  conflicting: { icon: FileWarning, color: 'text-red-500', bg: 'bg-red-50', label: 'Conflicting' },
  compliant: { icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-50', label: 'Compliant' },
  exceeds: { icon: TrendingUp, color: 'text-blue-500', bg: 'bg-blue-50', label: 'Exceeds' },
  not_applicable: { icon: Info, color: 'text-gray-500', bg: 'bg-gray-50', label: 'N/A' },
  unknown: { icon: Info, color: 'text-gray-500', bg: 'bg-gray-50', label: 'Unknown' }
};

const getComplianceColor = (score) => {
  if (score >= 80) return 'text-emerald-600';
  if (score >= 60) return 'text-amber-500';
  if (score >= 40) return 'text-amber-500';
  return 'text-red-500';
};

const getComplianceGradient = (score) => {
  if (score >= 80) return 'from-emerald-500 to-emerald-700';
  if (score >= 60) return 'from-amber-500 to-amber-600';
  if (score >= 40) return 'from-amber-600 to-red-500';
  return 'from-red-500 to-red-700';
};

export default function GapAnalysis() {
  const [policies, setPolicies] = useState([]);
  const [regulations, setRegulations] = useState([]);
  const [selectedPolicy, setSelectedPolicy] = useState('');
  const [selectedRegulation, setSelectedRegulation] = useState('');
  const [analysisMode, setAnalysisMode] = useState('deep_analysis');
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeTab, setActiveTab] = useState('new');
  const [selectedGap, setSelectedGap] = useState(null);
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [showSourceViewer, setShowSourceViewer] = useState(false);
  const [resumingAnalysis, setResumingAnalysis] = useState(false); // true when checking for a bg-completed analysis

  // Ref for polling interval cleanup
  const pollIntervalRef = useRef(null);

  // Feature #40: Human-in-the-loop correction state
  const [correctionMode, setCorrectionMode] = useState(null); // null, 'reject', 'modify'
  const [rejectReason, setRejectReason] = useState('');
  const [modifySeverity, setModifySeverity] = useState('');
  const [modifyRemediation, setModifyRemediation] = useState('');
  const [modifyDescription, setModifyDescription] = useState('');
  const [correctionLoading, setCorrectionLoading] = useState(false);
  const [showCorrectionHistory, setShowCorrectionHistory] = useState(false);
  const [correctionHistory, setCorrectionHistory] = useState([]);
  const [correctionHistoryLoading, setCorrectionHistoryLoading] = useState(false);

  // Progress tracking state
  const [analysisProgress, setAnalysisProgress] = useState({
    progress: 0,
    step: '',
    message: '',
    details: {},
    logs: []
  });

  // Feature #193: Prevent stale API responses from overwriting fresh data
  const { getRequestId: getDataRequestId, isLatest: isLatestDataRequest } = useLatestRequest();
  const { getRequestId: getHistoryRequestId, isLatest: isLatestHistoryRequest } = useLatestRequest();
  const { getRequestId: getAnalysisRequestId, isLatest: isLatestAnalysisRequest } = useLatestRequest();
  const { getRequestId: getViewRequestId, isLatest: isLatestViewRequest } = useLatestRequest();

  const handleCreateTask = async (gap) => {
    try {
      await tasksApi.create({
        title: `Address ${gap.gap_type} gap: ${gap.regulation_clause?.title || 'Compliance Gap'}`,
        description: gap.description + (gap.suggested_fix ? '\n\nSuggested Fix: ' + gap.suggested_fix : ''),
        priority: gap.severity || 'Medium',
        department: gap.metadata?.assigned_department || null,
        source_type: 'gap_analysis',
        gap_analysis_id: result?.id || null,
        policy_id: result?.policy_id || null,
        regulation_id: result?.regulation_id || null
      });
      toast.success('Task created from gap finding!');
    } catch (error) {
      toast.error('Failed to create task: ' + (error.response?.data?.detail || error.message));
    }
  };

  // Feature #40: Human-in-the-loop correction handlers
  const handleApproveGap = async (gapIndex) => {
    setCorrectionLoading(true);
    try {
      const res = await gapAnalysisApi.correctGap(result.id, gapIndex, {
        action: 'approve'
      });
      toast.success('Gap finding approved');
      // Update local state
      const updatedGaps = [...(result.gaps || [])];
      updatedGaps[gapIndex] = res.gap;
      setResult({ ...result, gaps: updatedGaps });
    } catch (error) {
      toast.error('Failed to approve gap: ' + (error.response?.data?.detail || error.message));
    } finally {
      setCorrectionLoading(false);
    }
  };

  const handleRejectGap = async (gapIndex) => {
    if (!rejectReason.trim()) {
      toast.error('Please provide a reason for rejection');
      return;
    }
    setCorrectionLoading(true);
    try {
      const res = await gapAnalysisApi.correctGap(result.id, gapIndex, {
        action: 'reject',
        reason: rejectReason
      });
      toast.success('Gap finding rejected');
      const updatedGaps = [...(result.gaps || [])];
      updatedGaps[gapIndex] = res.gap;
      setResult({ ...result, gaps: updatedGaps });
      setCorrectionMode(null);
      setRejectReason('');
    } catch (error) {
      toast.error('Failed to reject gap: ' + (error.response?.data?.detail || error.message));
    } finally {
      setCorrectionLoading(false);
    }
  };

  const handleModifyGap = async (gapIndex) => {
    const changes = {};
    const currentGap = (result.gaps || [])[gapIndex];
    if (modifySeverity && modifySeverity !== currentGap?.severity) changes.severity = modifySeverity;
    if (modifyRemediation && modifyRemediation !== currentGap?.suggested_fix) changes.suggested_fix = modifyRemediation;
    if (modifyDescription && modifyDescription !== currentGap?.description) changes.description = modifyDescription;

    if (Object.keys(changes).length === 0) {
      toast.error('No changes made');
      return;
    }
    setCorrectionLoading(true);
    try {
      const res = await gapAnalysisApi.correctGap(result.id, gapIndex, {
        action: 'modify',
        ...changes
      });
      toast.success('Gap finding modified');
      const updatedGaps = [...(result.gaps || [])];
      updatedGaps[gapIndex] = res.gap;
      setResult({ ...result, gaps: updatedGaps });
      setCorrectionMode(null);
      setModifySeverity('');
      setModifyRemediation('');
      setModifyDescription('');
    } catch (error) {
      toast.error('Failed to modify gap: ' + (error.response?.data?.detail || error.message));
    } finally {
      setCorrectionLoading(false);
    }
  };

  const loadCorrectionHistory = async (gapIndex) => {
    setCorrectionHistoryLoading(true);
    try {
      const res = await gapAnalysisApi.getGapCorrections(result.id, gapIndex);
      setCorrectionHistory(res.corrections || []);
      setShowCorrectionHistory(true);
    } catch (error) {
      toast.error('Failed to load correction history');
      setCorrectionHistory([]);
    } finally {
      setCorrectionHistoryLoading(false);
    }
  };

  const resetCorrectionState = () => {
    setCorrectionMode(null);
    setRejectReason('');
    setModifySeverity('');
    setModifyRemediation('');
    setModifyDescription('');
    setShowCorrectionHistory(false);
    setCorrectionHistory([]);
  };

  // Save pending analysis to localStorage when analysis starts
  const savePendingAnalysis = useCallback((policyId, regulationId, mode) => {
    localStorage.setItem('pendingGapAnalysis', JSON.stringify({
      policyId,
      regulationId,
      analysisMode: mode,
      startedAt: new Date().toISOString()
    }));
  }, []);

  const clearPendingAnalysis = useCallback(() => {
    localStorage.removeItem('pendingGapAnalysis');
  }, []);

  // Check for background-completed analysis on mount
  const checkForPendingAnalysis = useCallback(async (historyList) => {
    const pending = localStorage.getItem('pendingGapAnalysis');
    if (!pending) return;

    try {
      const { policyId, regulationId, startedAt } = JSON.parse(pending);
      const startTime = new Date(startedAt).getTime();

      // Don't resume if pending analysis is older than 15 minutes (likely stale)
      if (Date.now() - startTime > 15 * 60 * 1000) {
        clearPendingAnalysis();
        return;
      }

      // Look for a matching completed result in history that was created after the analysis started
      const matchingResult = (historyList || []).find(item => {
        const matchesPolicy = item.policy_id === policyId;
        const matchesRegulation = item.regulation_id === regulationId;
        const createdAt = new Date(item.created_at).getTime();
        return matchesPolicy && matchesRegulation && createdAt >= startTime;
      });

      if (matchingResult) {
        // Analysis completed in the background — load the result
        clearPendingAnalysis();
        setResumingAnalysis(true);
        try {
          const detail = await gapAnalysisApi.getById(matchingResult.id);
          setResult(detail);
          setActiveTab('new');
          setSelectedGap(null);
          toast.success('Gap analysis completed while you were away!', {
            description: `Compliance Score: ${(detail.compliance_score || 0).toFixed(1)}%`,
            duration: 6000
          });
        } catch (err) {
          console.error('Failed to load resumed analysis:', err);
        } finally {
          setResumingAnalysis(false);
        }
      } else {
        // Analysis might still be running — start polling
        setResumingAnalysis(true);
        setAnalyzing(true);
        setAnalysisProgress({
          progress: 50,
          step: 'analyzing',
          message: 'Analysis is running in the background. Waiting for completion...',
          details: {},
          logs: [{ timestamp: new Date().toLocaleTimeString(), step: 'resume', message: 'Reconnected — waiting for background analysis to finish...' }]
        });

        // Poll every 5 seconds for up to 10 minutes
        let pollCount = 0;
        const maxPolls = 120; // 10 minutes at 5s intervals
        pollIntervalRef.current = setInterval(async () => {
          pollCount++;
          try {
            const freshHistory = await gapAnalysisApi.getHistory();
            setHistory(freshHistory || []);
            const found = (freshHistory || []).find(item => {
              const matchesPolicy = item.policy_id === policyId;
              const matchesRegulation = item.regulation_id === regulationId;
              const createdAt = new Date(item.created_at).getTime();
              return matchesPolicy && matchesRegulation && createdAt >= startTime;
            });

            if (found) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
              clearPendingAnalysis();
              try {
                const detail = await gapAnalysisApi.getById(found.id);
                setResult(detail);
                setActiveTab('new');
                setSelectedGap(null);
                toast.success('Gap analysis completed!', {
                  description: `Compliance Score: ${(detail.compliance_score || 0).toFixed(1)}%`,
                  duration: 6000
                });
              } catch (err) {
                console.error('Failed to load completed analysis:', err);
              } finally {
                setAnalyzing(false);
                setResumingAnalysis(false);
                setAnalysisProgress(prev => ({ ...prev, progress: 100, step: 'complete', message: 'Analysis complete!' }));
              }
            } else if (pollCount >= maxPolls) {
              // Stop polling after max attempts
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
              clearPendingAnalysis();
              setAnalyzing(false);
              setResumingAnalysis(false);
              toast.error('Background analysis may have failed. Please try again.');
            } else {
              // Update progress message
              setAnalysisProgress(prev => ({
                ...prev,
                progress: Math.min(90, 50 + pollCount * 0.33),
                message: `Analysis running in background... checking (${pollCount})`,
              }));
            }
          } catch (err) {
            console.error('Polling error:', err);
          }
        }, 5000);
      }
    } catch (err) {
      console.error('Error checking pending analysis:', err);
      clearPendingAnalysis();
    }
  }, [clearPendingAnalysis]);

  useEffect(() => {
    loadData();
    // Load history first, then check for pending analysis
    const initGapAnalysis = async () => {
      const historyList = await loadHistory();
      await checkForPendingAnalysis(historyList);
    };
    initGapAnalysis();

    // Cleanup polling on unmount
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, []);

  const loadData = async () => {
    const requestId = getDataRequestId();
    try {
      const [policiesRes, regulationsRes] = await Promise.all([
        policiesApi.getAll(),
        regulationsApi.getAll(undefined, true)  // Feature #219: include NPCI circulars as regulation options
      ]);
      // Feature #193: Only update state if this is still the latest request
      if (!isLatestDataRequest(requestId)) return;
      setPolicies(policiesRes);
      setRegulations(regulationsRes);
    } catch (error) {
      if (!isLatestDataRequest(requestId)) return;
      toast.error('Failed to load data');
    }
  };

  const loadHistory = async () => {
    const requestId = getHistoryRequestId();
    setLoadingHistory(true);
    try {
      const historyRes = await gapAnalysisApi.getHistory();
      // Feature #193: Only update state if this is still the latest request
      if (!isLatestHistoryRequest(requestId)) return;
      setHistory(historyRes || []);
      return historyRes || [];
    } catch (error) {
      if (!isLatestHistoryRequest(requestId)) return;
      console.error('Failed to load history:', error);
      setHistory([]);
      return [];
    } finally {
      if (isLatestHistoryRequest(requestId)) {
        setLoadingHistory(false);
      }
    }
  };

  const handleAnalyze = async () => {
    if (!selectedPolicy || !selectedRegulation) {
      toast.error('Please select both policy and regulation');
      return;
    }

    const requestId = getAnalysisRequestId();
    setAnalyzing(true);
    setResult(null);
    setSelectedGap(null);
    setAnalysisProgress({
      progress: 0,
      step: 'start',
      message: 'Starting analysis...',
      details: {},
      logs: []
    });

    // Save to localStorage so we can resume if user navigates away
    savePendingAnalysis(selectedPolicy, selectedRegulation, analysisMode);

    try {
      // Use streaming API for real-time progress
      const response = await gapAnalysisApi.runStream(
        selectedPolicy,
        selectedRegulation,
        analysisMode,
        (progressData) => {
          // Feature #193: Only update progress if this is still the latest analysis request
          if (!isLatestAnalysisRequest(requestId)) return;
          setAnalysisProgress(prev => ({
            ...progressData,
            logs: [...prev.logs, {
              timestamp: new Date().toLocaleTimeString(),
              step: progressData.step,
              message: progressData.message,
              details: progressData.details
            }].slice(-20) // Keep last 20 logs
          }));
        }
      );

      // Feature #193: Only set result if this is still the latest analysis request
      if (!isLatestAnalysisRequest(requestId)) return;
      clearPendingAnalysis();
      setResult(response);
      loadHistory();
      toast.success('Gap analysis completed successfully!', {
        description: `Compliance Score: ${response.compliance_score?.toFixed(1)}%`
      });
    } catch (error) {
      if (!isLatestAnalysisRequest(requestId)) return;
      // Don't clear pending on network errors — the backend may still be running
      if (error.message?.includes('timed out')) {
        clearPendingAnalysis();
      }
      toast.error('Analysis failed: ' + (error.message || 'Unknown error'));
    } finally {
      if (isLatestAnalysisRequest(requestId)) {
        setAnalyzing(false);
        setAnalysisProgress(prev => ({ ...prev, progress: 100, step: 'complete' }));
      }
    }
  };

  const viewHistoryItem = async (item) => {
    const requestId = getViewRequestId();
    try {
      const detail = await gapAnalysisApi.getById(item.id);
      // Feature #193: Only update state if this is still the latest view request
      if (!isLatestViewRequest(requestId)) return;
      setResult(detail);
      setActiveTab('new');
      setSelectedGap(null);
    } catch (error) {
      if (!isLatestViewRequest(requestId)) return;
      toast.error('Failed to load analysis details');
    }
  };

  const handleExport = async (format) => {
    if (!result?.id) {
      toast.error('No analysis result to export');
      return;
    }
    try {
      toast.info(`Exporting as ${format.toUpperCase()}...`);
      const response = await gapAnalysisApi.exportReport(result.id, format);
      const blob = new Blob([response.data], { type: response.headers['content-type'] });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'excel' ? 'xlsx' : format;
      a.download = `gap_analysis_${result.id.substring(0, 8)}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success(`Report exported as ${format.toUpperCase()} successfully!`);
    } catch (error) {
      toast.error('Export failed: ' + (error.message || 'Unknown error'));
    }
  };

  const handleGenerateChecklist = async () => {
    if (!result?.id) {
      toast.error('No analysis result to generate checklist from');
      return;
    }
    try {
      const { checklistApi } = await import('../lib/api');
      await checklistApi.generate({
        gap_analysis_id: result.id,
        title: `Checklist: ${result.policy_title || 'Policy'} vs ${result.regulation_title || 'Regulation'}`,
        description: `Compliance checklist generated from gap analysis on ${new Date(result.created_at).toLocaleDateString()}`
      });
      toast.success('Compliance checklist generated! View it in the Checklists page.');
    } catch (error) {
      toast.error('Failed to generate checklist: ' + (error.message || 'Unknown error'));
    }
  };

  const filteredGaps = result?.gaps?.filter(gap => {
    if (filterSeverity === 'all') return true;
    return gap.severity === filterSeverity;
  }) || [];

  return (
    <div className="space-y-6" data-testid="gap-analysis-page">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold mb-2 flex items-center gap-3 text-gradient" data-testid="gap-analysis-title">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center shadow-md">
              <Scale className="h-6 w-6 text-white" />
            </div>
            AI Gap Analysis
          </h1>
          <p className="text-muted-foreground">Compare policies against regulations to identify compliance gaps</p>
        </div>
      </div>

      {/* Banner shown when resuming a background analysis */}
      {resumingAnalysis && !result && (
        <Card className="border-2 border-blue-200 bg-blue-50/50">
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <div className="relative flex-shrink-0">
                <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-blue-900">Analysis Running in Background</h3>
                <p className="text-sm text-blue-700 mt-0.5">
                  Your gap analysis is still processing. Results will appear automatically once complete.
                </p>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                className="border-blue-300 text-blue-700 hover:bg-blue-100"
                onClick={() => {
                  if (pollIntervalRef.current) {
                    clearInterval(pollIntervalRef.current);
                    pollIntervalRef.current = null;
                  }
                  localStorage.removeItem('pendingGapAnalysis');
                  setResumingAnalysis(false);
                  setAnalyzing(false);
                  setAnalysisProgress({ progress: 0, step: '', message: '', details: {}, logs: [] });
                  toast.info('Stopped waiting for background analysis.');
                }}
              >
                Dismiss
              </Button>
            </div>
            {analysisProgress.progress > 0 && (
              <Progress value={analysisProgress.progress} className="mt-3 h-2" />
            )}
          </CardContent>
        </Card>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2 bg-gray-50 border border-gray-200">
          <TabsTrigger value="new" className="flex items-center gap-2 data-[state=active]:bg-white data-[state=active]:text-emerald-600 text-gray-500">
            <Play className="h-4 w-4" /> New Analysis
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2 data-[state=active]:bg-white data-[state=active]:text-emerald-600 text-gray-500">
            <History className="h-4 w-4" /> History ({history.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="new" className="space-y-6 mt-6">
          <Card data-testid="gap-analysis-selector" className="bg-white border-2 border-dashed border-gray-200">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-gray-900">
                <Sparkles className="h-5 w-5 text-emerald-600" />
                Run Gap Analysis
              </CardTitle>
              <CardDescription className="text-gray-500">Select a policy and regulation to analyze for compliance gaps</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <FileText className="h-4 w-4" /> Policy Document
                  </Label>
                  <Select value={selectedPolicy} onValueChange={setSelectedPolicy}>
                    <SelectTrigger data-testid="select-policy" className="h-12 bg-white border-gray-200 text-gray-900">
                      <SelectValue placeholder="Select policy to analyze" />
                    </SelectTrigger>
                    <SelectContent>
                      {policies.map((policy) => (
                        <SelectItem key={policy.id} value={policy.id}>
                          {policy.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Scale className="h-4 w-4" /> Regulation Document
                  </Label>
                  <Select value={selectedRegulation} onValueChange={setSelectedRegulation}>
                    <SelectTrigger data-testid="select-regulation" className="h-12 bg-white border-gray-200 text-gray-900">
                      <SelectValue placeholder="Select regulation (source of truth)" />
                    </SelectTrigger>
                    <SelectContent>
                      {/* Regular regulations first */}
                      {regulations.filter(r => r.source !== 'npci_scraper').map((regulation) => (
                        <SelectItem key={regulation.id} value={regulation.id}>
                          {regulation.title}
                        </SelectItem>
                      ))}
                      {/* Feature #219: NPCI circulars as regulation sources */}
                      {regulations.filter(r => r.source === 'npci_scraper').length > 0 && (
                        <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground border-t mt-1 pt-2">
                          NPCI Circulars
                        </div>
                      )}
                      {regulations.filter(r => r.source === 'npci_scraper').map((regulation) => (
                        <SelectItem key={regulation.id} value={regulation.id}>
                          <span className="flex items-center gap-2">
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">NPCI</span>
                            {regulation.title}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Analysis Mode Selector */}
              <div className="space-y-3" data-testid="analysis-mode-selector">
                <Label className="flex items-center gap-2">
                  <Brain className="h-4 w-4" /> Analysis Mode
                </Label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setAnalysisMode('quick_scan')}
                    data-testid="mode-quick-scan"
                    className={`p-4 rounded-lg border-2 text-left transition-all ${
                      analysisMode === 'quick_scan'
                        ? 'border-amber-400 bg-amber-50 shadow-sm'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Zap className={`h-5 w-5 ${analysisMode === 'quick_scan' ? 'text-amber-600' : 'text-gray-400'}`} />
                      <span className="font-semibold text-gray-900">Quick Scan</span>
                    </div>
                    <p className="text-sm text-gray-500">Fast high-level overview. Checks key regulation areas. ~1-2 min</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setAnalysisMode('deep_analysis')}
                    data-testid="mode-deep-analysis"
                    className={`p-4 rounded-lg border-2 text-left transition-all ${
                      analysisMode === 'deep_analysis'
                        ? 'border-emerald-400 bg-emerald-50 shadow-sm'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Brain className={`h-5 w-5 ${analysisMode === 'deep_analysis' ? 'text-emerald-600' : 'text-gray-400'}`} />
                      <span className="font-semibold text-gray-900">Deep Analysis</span>
                      <Badge variant="outline" className="text-xs border-emerald-300 text-emerald-600">Recommended</Badge>
                    </div>
                    <p className="text-sm text-gray-500">Thorough clause-by-clause comparison with regulatory-weighted severity scoring. ~3-8 min</p>
                  </button>
                </div>
              </div>

              <Button
                onClick={handleAnalyze}
                disabled={analyzing || !selectedPolicy || !selectedRegulation}
                className="w-full h-12 text-lg btn-shiny text-white"
                data-testid="run-analysis-button"
              >
                {analyzing ? (
                  <>
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    {analysisMode === 'deep_analysis' ? 'Deep Analysis in Progress...' : 'Quick Scanning...'}
                  </>
                ) : (
                  <>
                    {analysisMode === 'deep_analysis' ? <Brain className="mr-2 h-5 w-5" /> : <Zap className="mr-2 h-5 w-5" />}
                    {analysisMode === 'deep_analysis' ? 'Run Deep Analysis' : 'Run Quick Scan'}
                  </>
                )}
              </Button>

              {/* Progress Panel */}
              {analyzing && (
                <div className="mt-6 bg-[#1C1C1E] rounded-xl p-6 border-2 border-[#80FFF9]/30">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <Brain className="h-8 w-8 text-[#80FFF9] animate-pulse" />
                        <Zap className="h-4 w-4 text-[#FBAD41] absolute -top-1 -right-1" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-lg text-[#E6E6E9]">AI Analysis in Progress</h3>
                        <p className="text-sm text-[#808089]">{analysisProgress.message}</p>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-lg px-3 py-1 bg-[#18181A] border-[#2A2A2E] text-[#80FFF9]">
                      {analysisProgress.progress}%
                    </Badge>
                  </div>
                  
                  {/* Progress Bar */}
                  <div className="mb-4">
                    <Progress value={analysisProgress.progress} className="h-3" />
                  </div>
                  
                  {/* Step Indicators */}
                  <div className="grid grid-cols-5 gap-2 mb-4">
                    {[
                      { key: 'init', label: 'Init', icon: Cpu },
                      { key: 'prepared', label: 'Prepare', icon: FileText },
                      { key: 'analyzing', label: 'Analyze', icon: Brain },
                      { key: 'summary', label: 'Summary', icon: Lightbulb },
                      { key: 'complete', label: 'Done', icon: CheckCircle }
                    ].map(({ key, label, icon: Icon }) => {
                      const stepOrder = ['init', 'prepared', 'analyzing', 'calculating', 'summary', 'finalizing', 'complete'];
                      const currentIdx = stepOrder.indexOf(analysisProgress.step);
                      const thisIdx = stepOrder.indexOf(key);
                      const isActive = analysisProgress.step === key || (key === 'analyzing' && ['analyzing', 'calculating'].includes(analysisProgress.step));
                      const isComplete = thisIdx < currentIdx || analysisProgress.step === 'complete';
                      
                      return (
                        <div 
                          key={key}
                          className={`flex flex-col items-center p-2 rounded-lg transition-all ${
                            isActive 
                              ? 'bg-[#80FFF9]/20 border-2 border-[#80FFF9]' 
                              : isComplete
                                ? 'bg-[#34D399]/10 border border-[#34D399]/30'
                                : 'bg-[#1C1C1E] border border-[#2A2A2E]'
                          }`}
                        >
                          <Icon className={`h-5 w-5 mb-1 ${
                            isActive 
                              ? 'text-[#80FFF9] animate-pulse' 
                              : isComplete 
                                ? 'text-[#34D399]' 
                                : 'text-[#808089]'
                          }`} />
                          <span className={`text-xs font-medium ${
                            isActive ? 'text-[#80FFF9]' : isComplete ? 'text-[#34D399]' : 'text-[#808089]'
                          }`}>
                            {label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  
                  {/* Current Details */}
                  {analysisProgress.details && Object.keys(analysisProgress.details).length > 0 && (
                    <div className="bg-[#18181A] rounded-lg p-4 border border-[#2A2A2E] mb-4">
                      <h4 className="text-sm font-semibold mb-2 flex items-center gap-2 text-[#E6E6E9]">
                        <Cpu className="h-4 w-4 text-[#80FFF9]" />
                        LLM Processing Details
                      </h4>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                        {analysisProgress.details.current_clause && (
                          <div className="bg-[#80FFF9]/10 rounded p-2">
                            <span className="text-[#808089]">Clause:</span>
                            <span className="ml-1 font-medium text-[#E6E6E9]">{analysisProgress.details.current_clause}/{analysisProgress.details.total_clauses}</span>
                          </div>
                        )}
                        {analysisProgress.details.clause_title && (
                          <div className="bg-[#A78BFA]/10 rounded p-2 col-span-2">
                            <span className="text-[#808089]">Analyzing:</span>
                            <span className="ml-1 font-medium truncate text-[#E6E6E9]">{analysisProgress.details.clause_title?.substring(0, 40)}</span>
                          </div>
                        )}
                        {analysisProgress.details.llm_action && (
                          <div className="bg-[#FBAD41]/10 rounded p-2">
                            <span className="text-[#808089]">Action:</span>
                            <span className="ml-1 font-medium capitalize text-[#E6E6E9]">{analysisProgress.details.llm_action?.replace('_', ' ')}</span>
                          </div>
                        )}
                        {analysisProgress.details.compliance_score !== undefined && (
                          <div className="bg-[#34D399]/10 rounded p-2">
                            <span className="text-[#808089]">Score:</span>
                            <span className="ml-1 font-bold text-[#34D399]">{analysisProgress.details.compliance_score}%</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Activity Log */}
                  <div className="bg-slate-900 rounded-lg p-3 max-h-32 overflow-y-auto font-mono text-xs">
                    <div className="flex items-center gap-2 mb-2 text-slate-400">
                      <Target className="h-3 w-3" />
                      <span>Activity Log</span>
                    </div>
                    {analysisProgress.logs.map((log, idx) => (
                      <div key={idx} className="text-slate-300 py-0.5">
                        <span className="text-slate-500">[{log.timestamp}]</span>
                        <span className="text-indigo-400 ml-2">[{log.step}]</span>
                        <span className="ml-2">{log.message}</span>
                      </div>
                    ))}
                    {analysisProgress.logs.length === 0 && (
                      <div className="text-slate-500">Waiting for analysis to start...</div>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {result && (
            <div className="space-y-6" data-testid="gap-analysis-results">
              <Card className="overflow-hidden">
                <div className={`h-2 bg-gradient-to-r ${getComplianceGradient(result.compliance_score || 0)}`} />
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Target className="h-5 w-5" />
                      Analysis Results
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-sm">
                        <Clock className="h-3 w-3 mr-1" />
                        {new Date(result.created_at || result.enhanced_report?.analysis_timestamp || new Date()).toLocaleString()}
                      </Badge>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleGenerateChecklist}
                        className="gap-1"
                        data-testid="generate-checklist-button"
                      >
                        <ListChecks className="h-4 w-4" />
                        Checklist
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleExport('pdf')}
                        className="gap-1"
                        data-testid="export-pdf-button"
                      >
                        <Download className="h-4 w-4" />
                        PDF
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleExport('excel')}
                        className="gap-1"
                        data-testid="export-excel-button"
                      >
                        <FileSpreadsheet className="h-4 w-4" />
                        Excel
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleExport('json')}
                        className="gap-1"
                        data-testid="export-json-button"
                      >
                        <FileJson className="h-4 w-4" />
                        JSON
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                    <div className="col-span-2 md:col-span-1 bg-gray-50 rounded-xl p-4 text-center border border-gray-200">
                      <div className="text-sm text-gray-500 mb-1">Compliance Score</div>
                      <div className={`text-5xl font-bold ${getComplianceColor(result.compliance_score || 0)}`} data-testid="compliance-score">
                        {(result.compliance_score || 0).toFixed(1)}%
                      </div>
                      <Progress value={result.compliance_score || 0} className="mt-2 h-2" />
                    </div>
                    
                    <div className="bg-red-50 rounded-xl p-4 text-center border border-red-200">
                      <div className="text-sm text-red-600 mb-1">Critical</div>
                      <div className="text-3xl font-bold text-red-600" data-testid="critical-gaps">
                        {result.critical_gaps || result.enhanced_report?.critical_gaps || 0}
                      </div>
                    </div>
                    <div className="bg-amber-50 rounded-xl p-4 text-center border border-amber-200">
                      <div className="text-sm text-amber-700 mb-1">High</div>
                      <div className="text-3xl font-bold text-amber-700">
                        {result.high_gaps || result.enhanced_report?.high_gaps || 0}
                      </div>
                    </div>
                    <div className="bg-blue-50 rounded-xl p-4 text-center border border-blue-200">
                      <div className="text-sm text-blue-700 mb-1">Medium</div>
                      <div className="text-3xl font-bold text-blue-700">
                        {result.medium_gaps || result.enhanced_report?.medium_gaps || 0}
                      </div>
                    </div>
                    <div className="bg-emerald-50 rounded-xl p-4 text-center border border-emerald-200">
                      <div className="text-sm text-emerald-700 mb-1">Compliant</div>
                      <div className="text-3xl font-bold text-emerald-700">
                        {result.compliant_clauses || result.enhanced_report?.compliant_clauses || 0}
                      </div>
                    </div>
                  </div>

                  {(result.executive_summary || result.enhanced_report?.executive_summary) && (
                    <div className="bg-teal-50 rounded-xl p-6 mb-6 border border-teal-200">
                      <h3 className="font-semibold flex items-center gap-2 mb-3 text-gray-800">
                        <Lightbulb className="h-5 w-5 text-teal-600" />
                        Executive Summary
                      </h3>
                      <p className="text-sm text-gray-700 whitespace-pre-line">
                        {result.executive_summary || result.enhanced_report?.executive_summary}
                      </p>
                    </div>
                  )}

                  {(result.priority_actions?.length > 0 || result.enhanced_report?.priority_actions?.length > 0) && (
                    <div className="bg-amber-50 rounded-xl p-6 border border-amber-200">
                      <h3 className="font-semibold flex items-center gap-2 mb-3 text-gray-800">
                        <ListChecks className="h-5 w-5 text-amber-600" />
                        Priority Actions
                      </h3>
                      <ul className="space-y-2">
                        {(result.priority_actions || result.enhanced_report?.priority_actions || []).map((action, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                            <span className="bg-[#FBAD41] text-[#111113] rounded-full w-5 h-5 flex items-center justify-center flex-shrink-0 text-xs font-bold">
                              {idx + 1}
                            </span>
                            {action}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-1">
                  <Card className="h-full">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-lg">Identified Gaps</CardTitle>
                        <Badge variant="secondary">{filteredGaps.length}</Badge>
                      </div>
                      <Select value={filterSeverity} onValueChange={setFilterSeverity}>
                        <SelectTrigger className="w-full bg-white border-gray-200 text-gray-900">
                          <SelectValue placeholder="Filter by severity" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Severities</SelectItem>
                          <SelectItem value="Critical">Critical Only</SelectItem>
                          <SelectItem value="High">High Only</SelectItem>
                          <SelectItem value="Medium">Medium Only</SelectItem>
                          <SelectItem value="Low">Low Only</SelectItem>
                        </SelectContent>
                      </Select>
                    </CardHeader>
                    <CardContent className="p-0">
                      <ScrollArea className="h-[500px]">
                        <div className="space-y-1 p-4">
                          {filteredGaps.map((gap, index) => {
                            const config = gapTypeConfig[gap.gap_type] || gapTypeConfig.unknown;
                            const Icon = config.icon;
                            const isSelected = selectedGap === index;
                            
                            return (
                              <div
                                key={index}
                                onClick={() => { setSelectedGap(index); resetCorrectionState(); }}
                                className={`p-3 rounded-lg cursor-pointer transition-all border ${
                                  isSelected 
                                    ? 'border-teal-400 bg-teal-50' 
                                    : 'border-transparent hover:bg-gray-50'
                                }`}
                              >
                                <div className="flex items-center justify-between mb-1">
                                  <div className="flex items-center gap-2">
                                    <Icon className={`h-4 w-4 ${config.color}`} />
                                    <span className="font-medium text-sm">Gap #{index + 1}</span>
                                  </div>
                                  <Badge className={`text-xs ${severityColors[gap.severity] || ''}`}>
                                    {gap.severity}
                                  </Badge>
                                </div>
                                <p className="text-xs text-muted-foreground line-clamp-2">
                                  {gap.description || gap.gap_description || 'No description'}
                                </p>
                              </div>
                            );
                          })}
                          {filteredGaps.length === 0 && (
                            <div className="text-center py-8 text-muted-foreground">
                              <Info className="h-8 w-8 mx-auto mb-2 opacity-50" />
                              <p>No gaps found</p>
                            </div>
                          )}
                        </div>
                      </ScrollArea>
                    </CardContent>
                  </Card>
                </div>

                <div className="lg:col-span-2">
                  <Card className="h-full min-h-[500px]">
                    {selectedGap !== null && filteredGaps[selectedGap] ? (
                      <>
                        <CardHeader>
                          <div className="flex items-center justify-between">
                            <div>
                              <CardTitle className="flex items-center gap-2">
                                Gap #{selectedGap + 1} Details
                                <Badge className={severityColors[filteredGaps[selectedGap].severity] || ''}>
                                  {filteredGaps[selectedGap].severity}
                                </Badge>
                              </CardTitle>
                              <CardDescription className="flex items-center gap-2 mt-1">
                                {(() => {
                                  const config = gapTypeConfig[filteredGaps[selectedGap].gap_type] || gapTypeConfig.unknown;
                                  const Icon = config.icon;
                                  return (
                                    <>
                                      <Icon className={`h-4 w-4 ${config.color}`} />
                                      Type: {config.label}
                                    </>
                                  );
                                })()}
                                <span className="mx-2">•</span>
                                Confidence: {((filteredGaps[selectedGap].confidence_score || 0) * 100).toFixed(0)}%
                              </CardDescription>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setShowSourceViewer(!showSourceViewer)}
                              className={`gap-2 ${showSourceViewer ? 'bg-emerald-50 text-emerald-700 border-emerald-300' : ''}`}
                              data-testid="view-source-reference-button"
                            >
                              <BookOpen className="h-4 w-4" />
                              {showSourceViewer ? 'Hide Source' : 'View Source'}
                            </Button>
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-6">
                          <ScrollArea className="h-[400px] pr-4">
                            <div className="space-y-4">
                              <div>
                                <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                                  Gap Description
                                </h4>
                                <p className="text-sm bg-gray-50 p-3 rounded-lg text-gray-700 border border-gray-200">
                                  {filteredGaps[selectedGap].description || filteredGaps[selectedGap].gap_description || 'No description available'}
                                </p>
                              </div>

                              {filteredGaps[selectedGap].metadata?.missing_elements?.length > 0 && (
                                <div>
                                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                    <XCircle className="h-4 w-4 text-red-500" />
                                    Missing Elements
                                  </h4>
                                  <ul className="space-y-1">
                                    {filteredGaps[selectedGap].metadata.missing_elements.map((el, i) => (
                                      <li key={i} className="text-sm flex items-start gap-2 bg-red-50 p-2 rounded text-gray-700 border border-red-200">
                                        <ChevronRight className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
                                        {el}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {filteredGaps[selectedGap].metadata?.regulatory_risk && (
                                <div>
                                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                    <Shield className="h-4 w-4 text-red-500" />
                                    Regulatory Risk
                                  </h4>
                                  <p className="text-sm bg-red-50 p-3 rounded-lg text-gray-700 border border-red-200">
                                    {filteredGaps[selectedGap].metadata.regulatory_risk}
                                  </p>
                                </div>
                              )}

                              <Separator />

                              {filteredGaps[selectedGap].policy_clause && (
                                <div>
                                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                    <FileText className="h-4 w-4 text-blue-500" />
                                    Policy Clause
                                  </h4>
                                  <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
                                    <p className="text-sm font-medium text-blue-700 mb-1">
                                      {filteredGaps[selectedGap].policy_clause.title || 'Policy Clause'}
                                    </p>
                                    <p className="text-sm text-gray-700">
                                      {filteredGaps[selectedGap].policy_clause.text?.substring(0, 500) || 'No text available'}
                                      {filteredGaps[selectedGap].policy_clause.text?.length > 500 && '...'}
                                    </p>
                                  </div>
                                </div>
                              )}

                              {filteredGaps[selectedGap].regulation_clause && (
                                <div>
                                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                    <Scale className="h-4 w-4 text-purple-500" />
                                    Regulation Requirement
                                  </h4>
                                  <div className="bg-purple-50 p-3 rounded-lg border border-purple-200">
                                    <p className="text-sm font-medium text-purple-700 mb-1">
                                      {filteredGaps[selectedGap].regulation_clause.title || 'Regulation Clause'}
                                    </p>
                                    <p className="text-sm text-gray-700">
                                      {filteredGaps[selectedGap].regulation_clause.text?.substring(0, 500) || 'No text available'}
                                      {filteredGaps[selectedGap].regulation_clause.text?.length > 500 && '...'}
                                    </p>
                                  </div>
                                </div>
                              )}

                              <Separator />

                              {filteredGaps[selectedGap].suggested_fix && (
                                <div>
                                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                    <Sparkles className="h-4 w-4 text-teal-600" />
                                    AI Suggested Fix
                                  </h4>
                                  <div className="bg-teal-50 p-4 rounded-lg border border-teal-200">
                                    <p className="text-sm text-gray-700">
                                      {filteredGaps[selectedGap].suggested_fix}
                                    </p>
                                  </div>
                                </div>
                              )}

                              <Separator />

                              {/* Remediation Package */}
                              {filteredGaps[selectedGap].metadata?.draft_clause && (
                                <div data-testid="remediation-draft-clause">
                                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                    <FileText className="h-4 w-4 text-emerald-500" />
                                    Draft Clause
                                  </h4>
                                  <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 font-mono">
                                    <pre className="text-sm text-gray-700 whitespace-pre-wrap break-words">
                                      {filteredGaps[selectedGap].metadata.draft_clause}
                                    </pre>
                                  </div>
                                </div>
                              )}

                              {filteredGaps[selectedGap].metadata?.legal_citations?.length > 0 && (
                                <div data-testid="remediation-citations">
                                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                    <BookOpen className="h-4 w-4 text-purple-500" />
                                    Legal Citations
                                  </h4>
                                  <ul className="space-y-1">
                                    {filteredGaps[selectedGap].metadata.legal_citations.map((citation, i) => (
                                      <li key={i} className="text-sm flex items-start gap-2 bg-purple-50 p-2 rounded text-gray-700 border border-purple-200">
                                        <BookOpen className="h-4 w-4 text-purple-500 flex-shrink-0 mt-0.5" />
                                        {citation}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {filteredGaps[selectedGap].metadata?.similar_clauses?.length > 0 && (
                                <div data-testid="remediation-similar-clauses">
                                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                    <Bookmark className="h-4 w-4 text-blue-500" />
                                    Similar Clauses
                                  </h4>
                                  <ul className="space-y-1">
                                    {filteredGaps[selectedGap].metadata.similar_clauses.map((clause, i) => (
                                      <li key={i} className="text-sm flex items-start gap-2 bg-blue-50 p-2 rounded text-gray-700 border border-blue-200">
                                        <Bookmark className="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" />
                                        {clause}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {filteredGaps[selectedGap].metadata?.remediation_actions?.length > 0 && (
                                <div data-testid="remediation-actions">
                                  <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-gray-800">
                                    <ListChecks className="h-4 w-4 text-amber-500" />
                                    Remediation Actions
                                  </h4>
                                  <ol className="space-y-1">
                                    {filteredGaps[selectedGap].metadata.remediation_actions.map((action, i) => (
                                      <li key={i} className="text-sm flex items-start gap-2 bg-amber-50 p-2 rounded text-gray-700 border border-amber-200">
                                        <span className="bg-[#FBAD41] text-[#111113] rounded-full w-5 h-5 flex items-center justify-center flex-shrink-0 text-xs font-bold">
                                          {i + 1}
                                        </span>
                                        {action}
                                      </li>
                                    ))}
                                  </ol>
                                </div>
                              )}

                              <Separator />

                              <div className="pt-2">
                                <Button
                                  data-testid="create-task-button"
                                  onClick={() => handleCreateTask(filteredGaps[selectedGap])}
                                  className="w-full h-12 text-lg bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-700 hover:to-emerald-800 text-white"
                                >
                                  <Plus className="mr-2 h-5 w-5" />
                                  Auto-Create Task from Gap
                                </Button>
                              </div>

                              {/* Feature #40: Human-in-the-Loop Correction Section */}
                              <Separator className="my-3" />
                              <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                  <h4 className="font-semibold text-sm text-gray-700">Review & Correct</h4>
                                  {filteredGaps[selectedGap]?.review_status && (
                                    <Badge
                                      data-testid="review-status-badge"
                                      className={
                                        filteredGaps[selectedGap].review_status === 'approved'
                                          ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
                                          : filteredGaps[selectedGap].review_status === 'rejected'
                                          ? 'bg-red-100 text-red-700 border-red-300'
                                          : 'bg-blue-100 text-blue-700 border-blue-300'
                                      }
                                    >
                                      {filteredGaps[selectedGap].review_status === 'approved' ? '✓ Approved' :
                                       filteredGaps[selectedGap].review_status === 'rejected' ? '✗ Rejected' :
                                       '✎ Modified'}
                                    </Badge>
                                  )}
                                </div>

                                {/* Review status info */}
                                {filteredGaps[selectedGap]?.reviewed_by && (
                                  <p className="text-xs text-muted-foreground">
                                    Last reviewed by {filteredGaps[selectedGap].reviewed_by}
                                    {filteredGaps[selectedGap].reviewed_at && (
                                      <> on {new Date(filteredGaps[selectedGap].reviewed_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</>
                                    )}
                                  </p>
                                )}

                                {/* Action buttons row */}
                                {correctionMode === null && (
                                  <div className="flex gap-2">
                                    <Button
                                      data-testid="approve-gap-button"
                                      variant="outline"
                                      size="sm"
                                      disabled={correctionLoading}
                                      onClick={() => handleApproveGap(selectedGap)}
                                      className="flex-1 border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                                    >
                                      <CheckCircle className="mr-1 h-4 w-4" />
                                      Approve
                                    </Button>
                                    <Button
                                      data-testid="reject-gap-button"
                                      variant="outline"
                                      size="sm"
                                      disabled={correctionLoading}
                                      onClick={() => { setCorrectionMode('reject'); setRejectReason(''); }}
                                      className="flex-1 border-red-300 text-red-700 hover:bg-red-50"
                                    >
                                      <XCircle className="mr-1 h-4 w-4" />
                                      Reject
                                    </Button>
                                    <Button
                                      data-testid="modify-gap-button"
                                      variant="outline"
                                      size="sm"
                                      disabled={correctionLoading}
                                      onClick={() => {
                                        const gap = filteredGaps[selectedGap];
                                        setCorrectionMode('modify');
                                        setModifySeverity(gap?.severity || '');
                                        setModifyRemediation(gap?.suggested_fix || '');
                                        setModifyDescription(gap?.description || '');
                                      }}
                                      className="flex-1 border-blue-300 text-blue-700 hover:bg-blue-50"
                                    >
                                      <FileText className="mr-1 h-4 w-4" />
                                      Modify
                                    </Button>
                                  </div>
                                )}

                                {/* Reject form */}
                                {correctionMode === 'reject' && (
                                  <div data-testid="reject-form" className="space-y-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                                    <Label className="text-sm font-medium text-red-700">Reason for Rejection</Label>
                                    <textarea
                                      data-testid="reject-reason-input"
                                      className="w-full h-20 px-3 py-2 text-sm border border-red-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-400"
                                      placeholder="Explain why this gap finding is incorrect..."
                                      value={rejectReason}
                                      onChange={(e) => setRejectReason(e.target.value)}
                                    />
                                    <div className="flex gap-2">
                                      <Button
                                        data-testid="confirm-reject-button"
                                        size="sm"
                                        disabled={correctionLoading || !rejectReason.trim()}
                                        onClick={() => handleRejectGap(selectedGap)}
                                        className="bg-red-600 hover:bg-red-700 text-white"
                                      >
                                        {correctionLoading ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <XCircle className="mr-1 h-4 w-4" />}
                                        Confirm Rejection
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => resetCorrectionState()}
                                      >
                                        Cancel
                                      </Button>
                                    </div>
                                  </div>
                                )}

                                {/* Modify form */}
                                {correctionMode === 'modify' && (
                                  <div data-testid="modify-form" className="space-y-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                                    <div>
                                      <Label className="text-sm font-medium text-blue-700">Severity</Label>
                                      <select
                                        data-testid="modify-severity-select"
                                        className="w-full mt-1 px-3 py-2 text-sm border border-blue-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
                                        value={modifySeverity}
                                        onChange={(e) => setModifySeverity(e.target.value)}
                                      >
                                        <option value="Critical">Critical</option>
                                        <option value="High">High</option>
                                        <option value="Medium">Medium</option>
                                        <option value="Low">Low</option>
                                      </select>
                                    </div>
                                    <div>
                                      <Label className="text-sm font-medium text-blue-700">Description</Label>
                                      <textarea
                                        data-testid="modify-description-input"
                                        className="w-full mt-1 h-16 px-3 py-2 text-sm border border-blue-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400"
                                        value={modifyDescription}
                                        onChange={(e) => setModifyDescription(e.target.value)}
                                      />
                                    </div>
                                    <div>
                                      <Label className="text-sm font-medium text-blue-700">Remediation / Suggested Fix</Label>
                                      <textarea
                                        data-testid="modify-remediation-input"
                                        className="w-full mt-1 h-16 px-3 py-2 text-sm border border-blue-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400"
                                        value={modifyRemediation}
                                        onChange={(e) => setModifyRemediation(e.target.value)}
                                      />
                                    </div>
                                    <div className="flex gap-2">
                                      <Button
                                        data-testid="save-modifications-button"
                                        size="sm"
                                        disabled={correctionLoading}
                                        onClick={() => handleModifyGap(selectedGap)}
                                        className="bg-blue-600 hover:bg-blue-700 text-white"
                                      >
                                        {correctionLoading ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <CheckCircle className="mr-1 h-4 w-4" />}
                                        Save Modifications
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => resetCorrectionState()}
                                      >
                                        Cancel
                                      </Button>
                                    </div>
                                  </div>
                                )}

                                {/* Correction History toggle */}
                                <Button
                                  data-testid="view-correction-history-button"
                                  variant="ghost"
                                  size="sm"
                                  className="w-full text-muted-foreground hover:text-foreground"
                                  onClick={() => {
                                    if (showCorrectionHistory) {
                                      setShowCorrectionHistory(false);
                                    } else {
                                      loadCorrectionHistory(selectedGap);
                                    }
                                  }}
                                >
                                  <History className="mr-1 h-4 w-4" />
                                  {showCorrectionHistory ? 'Hide' : 'View'} Correction History
                                </Button>

                                {/* Correction History List */}
                                {showCorrectionHistory && (
                                  <div data-testid="correction-history" className="space-y-2">
                                    {correctionHistoryLoading ? (
                                      <div className="flex items-center justify-center py-4">
                                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                                      </div>
                                    ) : correctionHistory.length === 0 ? (
                                      <p className="text-sm text-muted-foreground text-center py-2">No corrections yet</p>
                                    ) : (
                                      correctionHistory.map((correction, idx) => (
                                        <div
                                          key={idx}
                                          data-testid={`correction-record-${idx}`}
                                          className="p-2 text-xs border rounded-md bg-gray-50 space-y-1"
                                        >
                                          <div className="flex items-center justify-between">
                                            <Badge
                                              variant="outline"
                                              className={
                                                correction.action === 'approve'
                                                  ? 'text-emerald-600 border-emerald-300'
                                                  : correction.action === 'reject'
                                                  ? 'text-red-600 border-red-300'
                                                  : 'text-blue-600 border-blue-300'
                                              }
                                            >
                                              {correction.action === 'approve' ? '✓ Approved' :
                                               correction.action === 'reject' ? '✗ Rejected' :
                                               '✎ Modified'}
                                            </Badge>
                                            <span className="text-muted-foreground">
                                              {new Date(correction.timestamp).toLocaleDateString('en-IN', {
                                                day: 'numeric', month: 'short', year: 'numeric',
                                                hour: '2-digit', minute: '2-digit'
                                              })}
                                            </span>
                                          </div>
                                          <p className="text-muted-foreground">
                                            By: {correction.user_name || correction.user_email}
                                          </p>
                                          {correction.reason && (
                                            <p className="text-red-600">Reason: {correction.reason}</p>
                                          )}
                                          {correction.changes && Object.entries(correction.changes).map(([field, change]) => (
                                            <div key={field} className="text-blue-600">
                                              <span className="font-medium">{field}:</span>{' '}
                                              <span className="line-through text-gray-400">{String(change.old).substring(0, 50)}</span>{' → '}
                                              <span>{String(change.new).substring(0, 50)}</span>
                                            </div>
                                          ))}
                                        </div>
                                      ))
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          </ScrollArea>
                        </CardContent>
                      </>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-full py-16 text-muted-foreground">
                        <Eye className="h-12 w-12 mb-4 opacity-50" />
                        <p className="text-lg font-medium">Select a gap to view details</p>
                        <p className="text-sm">Click on any gap from the list to see the full analysis</p>
                      </div>
                    )}
                  </Card>
                </div>
              </div>

              {/* Source Reference Viewer Panel */}
              {showSourceViewer && selectedGap !== null && (result?.id || result?.result_id) && (
                <div data-testid="source-reference-viewer-panel">
                  <SourceReferenceViewer
                    analysisId={result.id || result.result_id}
                    gapIndex={(() => {
                      // selectedGap is index in filteredGaps, but API expects index in original gaps array
                      const filteredGap = filteredGaps[selectedGap];
                      if (!filteredGap || filterSeverity === 'all') return selectedGap;
                      const originalIndex = result.gaps?.findIndex(g => g.id === filteredGap.id);
                      return originalIndex >= 0 ? originalIndex : selectedGap;
                    })()}
                    gap={filteredGaps[selectedGap]}
                    onClose={() => setShowSourceViewer(false)}
                  />
                </div>
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="history" className="space-y-4 mt-6" data-testid="gap-analysis-history">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                Analysis History
              </CardTitle>
              <CardDescription>View previous gap analysis results</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingHistory ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : history.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <History className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium">No previous analyses</p>
                  <p className="text-sm">Run your first gap analysis to see results here</p>
                </div>
              ) : (
                <div className="space-y-3" data-testid="history-list">
                  {history.map((item, index) => (
                    <div
                      key={item.id || index}
                      className="shiny-card flex items-center justify-between p-4 rounded-lg border transition-all cursor-pointer hover:shadow-md"
                      onClick={() => viewHistoryItem(item)}
                      data-testid={`history-item-${item.id || index}`}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className={getComplianceColor(item.compliance_score || 0)}>
                            {(item.compliance_score || 0).toFixed(1)}%
                          </Badge>
                          {item.analysis_mode && (
                            <Badge variant="outline" className={item.analysis_mode === 'deep_analysis' ? 'text-emerald-600 border-emerald-300' : 'text-amber-600 border-amber-300'}>
                              {item.analysis_mode === 'deep_analysis' ? 'Deep' : 'Quick'}
                            </Badge>
                          )}
                          <span className="text-xs text-muted-foreground">
                            <Clock className="h-3 w-3 inline mr-1" />
                            {new Date(item.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="font-medium text-sm line-clamp-1">{item.policy_title || 'Unknown Policy'}</p>
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <ArrowRight className="h-3 w-3" />
                          {item.regulation_title || 'Unknown Regulation'}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 ml-4">
                        <div className="text-center px-2">
                          <div className="text-xs text-muted-foreground">Gaps</div>
                          <div className="font-bold">{item.total_gaps || item.gaps?.length || 0}</div>
                        </div>
                        <div className="text-center px-2">
                          <div className="text-xs text-red-500">Critical</div>
                          <div className="font-bold text-red-600">{item.critical_gaps || 0}</div>
                        </div>
                        <div className="text-center px-2">
                          <div className="text-xs text-orange-500">High</div>
                          <div className="font-bold text-orange-600">{item.high_gaps || 0}</div>
                        </div>
                        <div className="text-center px-2">
                          <div className="text-xs text-yellow-500">Medium</div>
                          <div className="font-bold text-yellow-600">{item.medium_gaps || 0}</div>
                        </div>
                        <Button variant="ghost" size="sm" className="btn-silver">
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
