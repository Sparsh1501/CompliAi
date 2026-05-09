import React, { useEffect, useState, useMemo } from 'react';
import { deviceBindingApi } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';
import {
  Shield, Smartphone, Lock, AlertTriangle, CheckCircle, XCircle, HelpCircle,
  Loader2, RefreshCw, ExternalLink, Sparkles, Activity, FileText,
  ShieldAlert, ShieldCheck, ChevronRight, BookOpen,
} from 'lucide-react';
import { toast } from 'sonner';

const COVERAGE_STYLES = {
  covered: {
    label: 'Covered',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    icon: CheckCircle,
    iconClass: 'text-emerald-600',
  },
  partial: {
    label: 'Partial',
    className: 'bg-amber-100 text-amber-800 border-amber-200',
    icon: AlertTriangle,
    iconClass: 'text-amber-600',
  },
  missing: {
    label: 'Missing',
    className: 'bg-red-100 text-red-800 border-red-200',
    icon: XCircle,
    iconClass: 'text-red-600',
  },
  unknown: {
    label: 'Not yet assessed',
    className: 'bg-gray-100 text-gray-700 border-gray-200',
    icon: HelpCircle,
    iconClass: 'text-gray-500',
  },
};

const CRITICALITY_STYLES = {
  High: 'bg-red-50 text-red-700 border-red-200',
  Medium: 'bg-amber-50 text-amber-700 border-amber-200',
  Low: 'bg-blue-50 text-blue-700 border-blue-200',
};

function CoverageBadge({ status }) {
  const cfg = COVERAGE_STYLES[status] || COVERAGE_STYLES.unknown;
  const Icon = cfg.icon;
  return (
    <Badge variant="outline" className={`${cfg.className} font-medium`}>
      <Icon className={`h-3 w-3 mr-1 ${cfg.iconClass}`} />
      {cfg.label}
    </Badge>
  );
}

export default function DeviceBindingAdvisor() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  const organization = user?.organization || 'system';

  const loadReport = async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const data = await deviceBindingApi.getReport(organization, true);
      setReport(data);
    } catch (err) {
      const msg = err?.response?.data?.detail || err.message || 'Failed to load advisor report';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadReport(true);
  }, [organization]); // eslint-disable-line react-hooks/exhaustive-deps

  const coverageBreakdown = useMemo(() => {
    if (!report?.stats) return null;
    const { covered = 0, partial = 0, missing = 0, unknown = 0, total_capabilities = 0 } = report.stats;
    return {
      covered,
      partial,
      missing,
      unknown,
      total: total_capabilities,
      coveredPct: total_capabilities ? Math.round((covered / total_capabilities) * 100) : 0,
      partialPct: total_capabilities ? Math.round((partial / total_capabilities) * 100) : 0,
      missingPct: total_capabilities ? Math.round((missing / total_capabilities) * 100) : 0,
    };
  }, [report]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24" data-testid="dba-loading">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
      </div>
    );
  }

  if (error) {
    return (
      <Card data-testid="dba-error">
        <CardContent className="py-12 text-center">
          <ShieldAlert className="h-10 w-10 mx-auto mb-3 text-red-500 opacity-70" />
          <p className="text-lg font-medium text-gray-900">Could not load advisor</p>
          <p className="text-sm text-muted-foreground mt-1">{error}</p>
          <Button onClick={() => loadReport(true)} className="mt-4">
            <RefreshCw className="h-4 w-4 mr-2" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!report) return null;

  const readiness = report.stats?.readiness_pct || 0;
  const readinessColor =
    readiness >= 70 ? 'text-emerald-600' :
    readiness >= 40 ? 'text-amber-600' : 'text-red-600';
  const readinessGradient =
    readiness >= 70 ? 'from-emerald-500 to-emerald-700' :
    readiness >= 40 ? 'from-amber-500 to-amber-600' : 'from-red-500 to-red-700';

  return (
    <div className="space-y-6" data-testid="device-binding-advisor">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Smartphone className="h-6 w-6 text-emerald-600" />
            Device Binding & RASP Advisor
          </h1>
          <p className="text-muted-foreground mt-1 max-w-3xl">
            Structured guidance on the device binding and Runtime Application
            Self-Protection (RASP) controls every UPI / mobile banking app must
            implement, grounded in NPCI circulars and live coverage data from your
            most recent gap analysis.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => loadReport(false)} disabled={refreshing}>
          {refreshing ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          Refresh
        </Button>
      </div>

      {/* Stats hero */}
      <Card className="border-emerald-100 bg-gradient-to-br from-emerald-50/60 to-white">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
            {/* Readiness gauge */}
            <div className="md:col-span-1 flex items-center gap-4">
              <div className={`text-5xl font-extrabold ${readinessColor}`} data-testid="readiness-pct">
                {readiness}%
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900">RASP Readiness</div>
                <div className="text-xs text-muted-foreground max-w-[160px]">
                  Composite score across {report.stats?.total_capabilities || 0} required capabilities
                </div>
                <div className="mt-2 h-2 w-32 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full bg-gradient-to-r ${readinessGradient} transition-all`}
                    style={{ width: `${readiness}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Coverage breakdown */}
            {coverageBreakdown && (
              <div className="md:col-span-2 grid grid-cols-4 gap-3">
                <div className="text-center p-3 bg-white rounded-lg border border-emerald-100">
                  <div className="text-2xl font-bold text-emerald-600">{coverageBreakdown.covered}</div>
                  <div className="text-xs text-muted-foreground">Covered</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg border border-amber-100">
                  <div className="text-2xl font-bold text-amber-600">{coverageBreakdown.partial}</div>
                  <div className="text-xs text-muted-foreground">Partial</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg border border-red-100">
                  <div className="text-2xl font-bold text-red-600">{coverageBreakdown.missing}</div>
                  <div className="text-xs text-muted-foreground">Missing</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg border border-gray-100">
                  <div className="text-2xl font-bold text-gray-500">{coverageBreakdown.unknown}</div>
                  <div className="text-xs text-muted-foreground">Unknown</div>
                </div>
              </div>
            )}

            {/* Source data */}
            <div className="md:col-span-1 space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <FileText className="h-4 w-4 text-emerald-600" />
                <span className="text-muted-foreground">Relevant circulars:</span>
                <span className="font-semibold">{report.stats?.relevant_circulars || 0}</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <BookOpen className="h-4 w-4 text-emerald-600" />
                <span className="text-muted-foreground">Supporting clauses:</span>
                <span className="font-semibold">{report.stats?.supporting_clauses || 0}</span>
              </div>
              {report.latest_gap_analysis?.analysis_id && (
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-emerald-700"
                  onClick={() => navigate(`/gap-analysis/${report.latest_gap_analysis.analysis_id}`)}
                >
                  View latest gap analysis <ChevronRight className="h-3 w-3" />
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Executive Summary */}
      {report.summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-emerald-600" />
              Executive Briefing
            </CardTitle>
            <CardDescription>
              AI-generated summary grounded in NPCI's UPI security and fraud-risk circulars.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
              {report.summary}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Recommended Actions */}
      {report.recommended_actions?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-600" />
              Top Recommended Actions
            </CardTitle>
            <CardDescription>
              Prioritised checklist of controls to implement first.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {report.recommended_actions.slice(0, 8).map((action, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 hover:bg-gray-50/60 transition-colors"
                >
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs font-bold">
                    {idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <Badge variant="outline" className="text-xs">{action.control_area}</Badge>
                      <Badge
                        variant="outline"
                        className={`text-xs ${CRITICALITY_STYLES[action.criticality] || ''}`}
                      >
                        {action.criticality}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-700">{action.action}</p>
                    {action.rasp_capabilities?.length > 0 && (
                      <div className="mt-1 flex gap-1 flex-wrap">
                        {action.rasp_capabilities.slice(0, 4).map((cap) => (
                          <span
                            key={cap}
                            className="text-[10px] uppercase tracking-wide text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded"
                          >
                            {cap.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Capability Checklist */}
      {report.capability_checklist?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              RASP Capability Checklist
            </CardTitle>
            <CardDescription>
              Specific runtime-protection capabilities the app must implement.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {report.capability_checklist.map((cap) => (
                <div
                  key={cap.capability_id}
                  className="p-3 rounded-lg border border-gray-100 bg-white hover:border-emerald-200 transition-colors"
                  data-testid={`capability-${cap.capability_id}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="font-medium text-sm text-gray-900">{cap.label}</div>
                    <CoverageBadge status={cap.coverage_status} />
                  </div>
                  <p className="text-xs text-muted-foreground">{cap.description}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Control Areas (deep dive) */}
      {report.control_areas?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Lock className="h-4 w-4 text-emerald-600" />
              Control Areas — Deep Dive
            </CardTitle>
            <CardDescription>
              Each control area maps a regulatory expectation to specific app-side controls and the supporting clauses from NPCI circulars.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Accordion type="multiple" className="w-full">
              {report.control_areas.map((area) => {
                const totalCaps = area.rasp_capabilities?.length || 0;
                const covered = (area.rasp_capabilities || []).filter(c => c.coverage_status === 'covered').length;
                const missing = (area.rasp_capabilities || []).filter(c => c.coverage_status === 'missing').length;
                const partial = (area.rasp_capabilities || []).filter(c => c.coverage_status === 'partial').length;
                return (
                  <AccordionItem key={area.area_id} value={area.area_id}>
                    <AccordionTrigger className="text-sm hover:no-underline">
                      <div className="flex items-center gap-3 flex-1 text-left pr-3">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">{area.title}</div>
                          <div className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                            {area.description}
                          </div>
                        </div>
                        <div className="hidden sm:flex items-center gap-1 text-xs flex-shrink-0">
                          {covered > 0 && (
                            <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                              {covered}/{totalCaps} covered
                            </Badge>
                          )}
                          {partial > 0 && (
                            <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                              {partial} partial
                            </Badge>
                          )}
                          {missing > 0 && (
                            <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                              {missing} missing
                            </Badge>
                          )}
                        </div>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-4 pt-2">
                        {/* Description */}
                        <p className="text-sm text-gray-700">{area.description}</p>

                        {/* NPCI Basis */}
                        {area.npci_basis?.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1">
                              NPCI / RBI Basis
                            </div>
                            <ul className="space-y-1">
                              {area.npci_basis.map((b, idx) => (
                                <li key={idx} className="text-xs text-gray-600 flex items-start gap-1.5">
                                  <span className="text-emerald-500 flex-shrink-0">•</span>
                                  <span>{b}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Requirements */}
                        {area.requirements?.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1">
                              Required Controls
                            </div>
                            <ul className="space-y-1">
                              {area.requirements.map((req, idx) => (
                                <li key={idx} className="text-sm text-gray-700 flex items-start gap-2">
                                  <CheckCircle className="h-3.5 w-3.5 text-emerald-600 flex-shrink-0 mt-0.5" />
                                  <span>{req}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* RASP Capabilities */}
                        {area.rasp_capabilities?.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">
                              Supporting RASP Capabilities
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {area.rasp_capabilities.map((cap) => (
                                <div
                                  key={cap.capability_id}
                                  className="p-2 rounded border border-gray-100 bg-gray-50/50 flex items-start justify-between gap-2"
                                >
                                  <div className="min-w-0">
                                    <div className="text-xs font-medium text-gray-900">{cap.label}</div>
                                    <div className="text-[11px] text-muted-foreground">{cap.description}</div>
                                  </div>
                                  <CoverageBadge status={cap.coverage_status} />
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Supporting clauses */}
                        {area.supporting_clauses?.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1">
                              Supporting NPCI clauses (live)
                            </div>
                            <div className="space-y-2">
                              {area.supporting_clauses.map((cl, idx) => (
                                <div
                                  key={idx}
                                  className="p-2 rounded border border-blue-100 bg-blue-50/40 text-xs text-gray-700"
                                >
                                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                                    <Badge variant="outline" className="text-[10px]">
                                      {cl.circular_reference?.slice(0, 80) || cl.clause_id}
                                    </Badge>
                                    {cl.compliance_impact && (
                                      <Badge
                                        variant="outline"
                                        className={`text-[10px] ${
                                          cl.compliance_impact === 'high' ? 'border-red-300 text-red-700' :
                                          cl.compliance_impact === 'medium' ? 'border-amber-300 text-amber-700' :
                                          'border-emerald-300 text-emerald-700'
                                        }`}
                                      >
                                        {cl.compliance_impact}
                                      </Badge>
                                    )}
                                    {cl.category && (
                                      <Badge variant="secondary" className="text-[10px]">{cl.category}</Badge>
                                    )}
                                  </div>
                                  <p className="line-clamp-3">{cl.clause_text}</p>
                                </div>
                              ))}
                            </div>
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

      {/* Source Circulars */}
      {report.circulars?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4 text-emerald-600" />
              Source NPCI Circulars
            </CardTitle>
            <CardDescription>
              Scraped circulars relevant to device binding, UPI security and fraud risk that fed into this advisor.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {report.circulars.slice(0, 12).map((c) => (
                <div
                  key={c._id}
                  className="flex items-center justify-between gap-2 p-2 rounded border border-gray-100 hover:bg-gray-50/60 transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <Badge variant="outline" className="text-xs flex-shrink-0">
                      {c.product_label || c.product}
                    </Badge>
                    <Badge variant="outline" className="text-xs flex-shrink-0">{c.year}</Badge>
                    {c.processing_status === 'completed' ? (
                      <Badge className="bg-emerald-100 text-emerald-800 text-xs flex-shrink-0">
                        <CheckCircle className="h-3 w-3 mr-1" /> AI Processed
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs flex-shrink-0">
                        {c.processing_status || 'pending'}
                      </Badge>
                    )}
                    <span
                      className="text-sm text-gray-800 truncate cursor-pointer hover:text-emerald-700"
                      title={c.title}
                      onClick={() => navigate('/npci-circulars')}
                    >
                      {c.title}
                    </span>
                  </div>
                  {c.pdf_url && (
                    <Button variant="ghost" size="sm" asChild>
                      <a href={c.pdf_url} target="_blank" rel="noopener noreferrer" title="Open PDF">
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </Button>
                  )}
                </div>
              ))}
            </div>
            {report.circulars.length === 0 && (
              <div className="text-sm text-muted-foreground text-center py-6">
                No security-relevant circulars scraped yet. Go to{' '}
                <Button
                  variant="link"
                  className="h-auto p-0 text-emerald-700"
                  onClick={() => navigate('/npci-circulars')}
                >
                  NPCI Circulars
                </Button>
                {' '}and scrape UPI 2024-2025 to populate this view.
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Footer hint */}
      <div className="text-xs text-muted-foreground text-center">
        Generated {report.generated_at ? new Date(report.generated_at).toLocaleString() : 'just now'} ·{' '}
        Coverage data is derived from your most recent gap analysis run for organization{' '}
        <span className="font-mono">{report.organization}</span>.
      </div>
    </div>
  );
}
