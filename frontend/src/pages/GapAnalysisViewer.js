import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import {
  Shield, CheckCircle, AlertTriangle, AlertCircle, XCircle, TrendingUp,
  FileText, ArrowLeft, Download, Loader2, Eye, ChevronDown, ChevronUp,
  BookOpen, Target, Lightbulb, Scale, Info
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../lib/api';

const gapTypeConfig = {
  missing: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-50 border-red-200', label: 'Missing' },
  weak: { icon: AlertCircle, color: 'text-amber-500', bg: 'bg-amber-50 border-amber-200', label: 'Weak' },
  partial: { icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50 border-amber-200', label: 'Partial' },
  conflicting: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-50 border-red-200', label: 'Conflicting' },
  compliant: { icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-50 border-emerald-200', label: 'Compliant' },
  exceeds: { icon: TrendingUp, color: 'text-blue-500', bg: 'bg-blue-50 border-blue-200', label: 'Exceeds' },
};

const severityColors = {
  Critical: 'bg-red-100 text-red-700',
  High: 'bg-amber-100 text-amber-700',
  Medium: 'bg-blue-100 text-blue-700',
  Low: 'bg-emerald-100 text-emerald-700',
};

function DiffView({ regulationText, policyText }) {
  if (!regulationText && !policyText) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
      <div className="rounded-lg border p-3 bg-red-50/50">
        <div className="flex items-center gap-1 mb-2">
          <BookOpen className="h-3.5 w-3.5 text-red-500" />
          <span className="text-xs font-semibold text-red-700">Regulation Requirement</span>
        </div>
        <p className="text-xs leading-relaxed text-gray-700 whitespace-pre-wrap">
          {regulationText || 'No regulation text available'}
        </p>
      </div>
      <div className="rounded-lg border p-3 bg-emerald-50/50">
        <div className="flex items-center gap-1 mb-2">
          <FileText className="h-3.5 w-3.5 text-emerald-500" />
          <span className="text-xs font-semibold text-emerald-700">Policy Coverage</span>
        </div>
        <p className="text-xs leading-relaxed text-gray-700 whitespace-pre-wrap">
          {policyText || 'No matching policy text found'}
        </p>
      </div>
    </div>
  );
}

function FindingCard({ finding, index }) {
  const [expanded, setExpanded] = useState(false);
  const gapConfig = gapTypeConfig[finding.gap_type] || gapTypeConfig.missing;
  const GapIcon = gapConfig.icon;

  return (
    <Card className={`border ${gapConfig.bg}`}>
      <div
        className="p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3 flex-1">
            <div className="mt-0.5">
              <GapIcon className={`h-5 w-5 ${gapConfig.color}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-mono text-muted-foreground">#{finding.finding_number}</span>
                <Badge className={severityColors[finding.severity] || ''} variant="outline">
                  {finding.severity}
                </Badge>
                <Badge variant="outline">{gapConfig.label}</Badge>
              </div>
              <p className="text-sm mt-1 font-medium">{finding.description?.slice(0, 200)}</p>
              {finding.rbi_citation && (
                <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <Scale className="h-3 w-3" />
                  {finding.rbi_citation}
                </p>
              )}
            </div>
          </div>
          <Button variant="ghost" size="sm" className="ml-2">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>

        {expanded && (
          <div className="mt-4 space-y-3 border-t pt-3">
            <DiffView
              regulationText={finding.regulation_text}
              policyText={finding.policy_text}
            />

            {finding.suggested_fix && (
              <div className="rounded-lg border p-3 bg-blue-50/50">
                <div className="flex items-center gap-1 mb-1">
                  <Lightbulb className="h-3.5 w-3.5 text-blue-500" />
                  <span className="text-xs font-semibold text-blue-700">Recommended Action</span>
                </div>
                <p className="text-xs text-gray-700">{finding.suggested_fix}</p>
              </div>
            )}

            {finding.missing_elements?.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-red-600">Missing Elements:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {finding.missing_elements.map((el, i) => (
                    <Badge key={i} variant="outline" className="text-xs bg-red-50">
                      {el}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {finding.evidence_map?.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-gray-600">Evidence Assessment:</span>
                <div className="space-y-1 mt-1">
                  {finding.evidence_map.map((ev, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      {ev.status === 'present' ? (
                        <CheckCircle className="h-3 w-3 text-emerald-500" />
                      ) : ev.status === 'partial' ? (
                        <AlertCircle className="h-3 w-3 text-amber-500" />
                      ) : (
                        <XCircle className="h-3 w-3 text-red-500" />
                      )}
                      <span>{ev.indicator}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-4 text-xs text-muted-foreground pt-1">
              <span>Category: {finding.subject_category}</span>
              <span>Department: {finding.assigned_department}</span>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

export default function GapAnalysisViewer() {
  const { analysisId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState(null);
  const [filter, setFilter] = useState('all');

  const fetchReport = useCallback(async () => {
    if (!analysisId) return;
    setLoading(true);
    try {
      const res = await api.get(`/api/gap-reports/${analysisId}`);
      setReport(res.data);
    } catch (err) {
      toast.error('Failed to load gap analysis report');
    } finally {
      setLoading(false);
    }
  }, [analysisId]);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="p-6 text-center text-muted-foreground">
        Report not found. <Button variant="link" onClick={() => navigate(-1)}>Go back</Button>
      </div>
    );
  }

  const summary = report.executive_summary || {};
  const findings = report.findings || [];

  const filteredFindings = filter === 'all'
    ? findings
    : findings.filter(f => f.gap_type === filter);

  const typeCounts = {};
  findings.forEach(f => {
    typeCounts[f.gap_type] = (typeCounts[f.gap_type] || 0) + 1;
  });

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <div className="flex-1">
          <h1 className="text-xl font-bold">Gap Analysis Report</h1>
          <p className="text-sm text-muted-foreground">
            {report.policy_title} vs {report.regulation_title}
          </p>
        </div>
      </div>

      {/* Executive Summary */}
      <Card className="bg-gradient-to-r from-slate-50 to-white">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Target className="h-4 w-4" /> Executive Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-primary">{summary.compliance_percentage}%</div>
              <p className="text-xs text-muted-foreground">Compliance</p>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{summary.total_requirements_assessed}</div>
              <p className="text-xs text-muted-foreground">Total Assessed</p>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-emerald-600">{summary.compliant_count}</div>
              <p className="text-xs text-muted-foreground">Compliant</p>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{summary.critical_gaps}</div>
              <p className="text-xs text-muted-foreground">Critical Gaps</p>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-amber-600">{summary.high_severity_gaps}</div>
              <p className="text-xs text-muted-foreground">High Severity</p>
            </div>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">{summary.narrative}</p>
        </CardContent>
      </Card>

      {/* Filter Bar */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={filter === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('all')}
        >
          All ({findings.length})
        </Button>
        {Object.entries(typeCounts).map(([type, count]) => {
          const config = gapTypeConfig[type] || {};
          return (
            <Button
              key={type}
              variant={filter === type ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilter(type)}
            >
              {config.label || type} ({count})
            </Button>
          );
        })}
      </div>

      {/* Findings */}
      <div className="space-y-3">
        {filteredFindings.map((finding, idx) => (
          <FindingCard key={idx} finding={finding} index={idx} />
        ))}
        {filteredFindings.length === 0 && (
          <div className="text-center text-muted-foreground py-8">
            No findings match this filter.
          </div>
        )}
      </div>

      {/* Citation Index */}
      {report.citation_index && Object.keys(report.citation_index).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Scale className="h-4 w-4" /> RBI Citation Index
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(report.citation_index).map(([citation, findingNums]) => (
                <div key={citation} className="flex items-center justify-between py-1 border-b last:border-0">
                  <span className="text-sm font-medium">{citation}</span>
                  <div className="flex gap-1">
                    {findingNums.map(n => (
                      <Badge key={n} variant="outline" className="text-xs">#{n}</Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
