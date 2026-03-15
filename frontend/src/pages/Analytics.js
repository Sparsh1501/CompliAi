import React, { useEffect, useState, useRef } from 'react';
import { analyticsApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Progress } from '../components/ui/progress';
import { BarChart3, TrendingUp, AlertTriangle, Download, Clock, Target, Shield, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';
import { MOCK_COMPLIANCE_DATA, MOCK_SLA_DATA, MOCK_HEATMAP_DATA, MOCK_EVIDENCE_PROGRESS_DATA, MOCK_REGULATION_COVERAGE_DATA } from '../lib/mockData';

export default function Analytics() {
  const [complianceData, setComplianceData] = useState(null);
  const [slaData, setSlaData] = useState(null);
  const [heatmapData, setHeatmapData] = useState(null);
  const [evidenceProgressData, setEvidenceProgressData] = useState(null);
  const [regulationCoverageData, setRegulationCoverageData] = useState(null);
  const [expandedRegulation, setExpandedRegulation] = useState(null);
  const [expandedHeatmapRow, setExpandedHeatmapRow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('compliance');

  // Feature #193: Prevent stale API responses from overwriting fresh data
  const analyticsRequestIdRef = useRef(0);

  useEffect(() => { loadAnalytics(); }, []);

  const loadAnalytics = async () => {
    const requestId = ++analyticsRequestIdRef.current;
    try {
      const [compliance, sla, heatmap, evidenceProgress, regulationCoverage] = await Promise.all([
        analyticsApi.getComplianceScore().catch(() => null),
        analyticsApi.getSlaPerformance().catch(() => null),
        analyticsApi.getGapsHeatmap().catch(() => null),
        analyticsApi.getEvidenceProgress().catch(() => null),
        analyticsApi.getRegulationCoverage().catch(() => null),
      ]);
      // Feature #193: Only update state if this is still the latest request
      if (requestId !== analyticsRequestIdRef.current) return;
      // Use mock data as fallback when API returns null/empty
      setComplianceData(compliance || MOCK_COMPLIANCE_DATA);
      setSlaData(sla || MOCK_SLA_DATA);
      setHeatmapData(heatmap || MOCK_HEATMAP_DATA);
      setEvidenceProgressData(evidenceProgress || MOCK_EVIDENCE_PROGRESS_DATA);
      setRegulationCoverageData(regulationCoverage || MOCK_REGULATION_COVERAGE_DATA);
    } catch (error) {
      if (requestId !== analyticsRequestIdRef.current) return;
      // Fallback to mock data for demo
      setComplianceData(MOCK_COMPLIANCE_DATA);
      setSlaData(MOCK_SLA_DATA);
      setHeatmapData(MOCK_HEATMAP_DATA);
      setEvidenceProgressData(MOCK_EVIDENCE_PROGRESS_DATA);
      setRegulationCoverageData(MOCK_REGULATION_COVERAGE_DATA);
      console.log('Using mock analytics data for demo');
    } finally {
      if (requestId === analyticsRequestIdRef.current) {
        setLoading(false);
      }
    }
  };

  const handleExport = async (type) => {
    try {
      toast.info(`Exporting analytics as ${type.toUpperCase()}...`);
      const response = await analyticsApi.exportReport(type);
      const blob = new Blob([response.data], { type: response.headers['content-type'] });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = type === 'excel' ? 'xlsx' : type;
      a.download = `analytics-export.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success(`Analytics exported as ${type.toUpperCase()} successfully!`);
    } catch (error) {
      toast.error('Export failed: ' + (error.message || 'Unknown error'));
    }
  };

  const getScoreColor = (score) => {
    if (score >= 75) return 'text-green-600';
    if (score >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getHeatColor = (score) => {
    if (score >= 80) return 'bg-green-100 text-green-800';
    if (score >= 60) return 'bg-yellow-100 text-yellow-800';
    if (score >= 40) return 'bg-orange-100 text-orange-800';
    return 'bg-red-100 text-red-800';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="analytics-loading">
        <div className="text-muted-foreground">Loading analytics...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="analytics-page">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-600 to-emerald-800 flex items-center justify-center shadow-lg">
            <BarChart3 className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold" data-testid="analytics-title">Analytics</h1>
            <p className="text-muted-foreground">Compliance metrics and performance insights</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => handleExport('pdf')} data-testid="export-pdf-button">
            <Download className="mr-2 h-4 w-4" /> Export PDF
          </Button>
          <Button variant="outline" onClick={() => handleExport('excel')} data-testid="export-excel-button">
            <Download className="mr-2 h-4 w-4" /> Export Excel
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="compliance" data-testid="compliance-tab">
            <Target className="h-4 w-4 mr-2" /> Compliance Score
          </TabsTrigger>
          <TabsTrigger value="sla" data-testid="sla-tab">
            <Clock className="h-4 w-4 mr-2" /> SLA Performance
          </TabsTrigger>
          <TabsTrigger value="heatmap" data-testid="heatmap-tab">
            <AlertTriangle className="h-4 w-4 mr-2" /> Gaps Heatmap
          </TabsTrigger>
          <TabsTrigger value="evidence" data-testid="evidence-tab">
            <TrendingUp className="h-4 w-4 mr-2" /> Evidence Progress
          </TabsTrigger>
          <TabsTrigger value="regulation-coverage" data-testid="regulation-coverage-tab">
            <Shield className="h-4 w-4 mr-2" /> Regulation Coverage
          </TabsTrigger>
        </TabsList>

        {/* Compliance Score Tab */}
        <TabsContent value="compliance" data-testid="compliance-content">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <Card data-testid="overall-score-card">
              <CardContent className="p-6 text-center">
                <div className={`text-5xl font-bold mb-2 ${getScoreColor(complianceData?.overall_score || 0)}`} data-testid="overall-compliance-score">
                  {complianceData?.overall_score || 0}%
                </div>
                <div className="text-sm text-gray-500">Overall Compliance Score</div>
                <Progress value={complianceData?.overall_score || 0} className="mt-3" />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6 text-center">
                <div className="text-3xl font-bold text-blue-600 mb-2">
                  {Object.keys(complianceData?.regulation_scores || {}).length}
                </div>
                <div className="text-sm text-gray-500">Regulations Assessed</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6 text-center">
                <div className="text-3xl font-bold text-purple-600 mb-2">
                  {Object.keys(complianceData?.policy_scores || {}).length}
                </div>
                <div className="text-sm text-gray-500">Policies Evaluated</div>
              </CardContent>
            </Card>
          </div>

          {complianceData?.regulation_scores && Object.keys(complianceData.regulation_scores).length > 0 && (
            <Card className="mb-6" data-testid="regulation-breakdown">
              <CardHeader><CardTitle>Per-Regulation Compliance</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Object.entries(complianceData.regulation_scores).map(([name, score]) => (
                    <div key={name} className="flex items-center gap-4">
                      <div className="w-48 text-sm font-medium truncate" title={name}>{name}</div>
                      <div className="flex-1"><Progress value={score} /></div>
                      <div className={`w-16 text-right font-bold ${getScoreColor(score)}`}>{score}%</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {complianceData?.policy_scores && Object.keys(complianceData.policy_scores).length > 0 && (
            <Card data-testid="policy-breakdown">
              <CardHeader><CardTitle>Per-Policy Compliance</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Object.entries(complianceData.policy_scores).map(([name, score]) => (
                    <div key={name} className="flex items-center gap-4">
                      <div className="w-48 text-sm font-medium truncate" title={name}>{name}</div>
                      <div className="flex-1"><Progress value={score} /></div>
                      <div className={`w-16 text-right font-bold ${getScoreColor(score)}`}>{score}%</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {complianceData?.trend?.length > 0 && (
            <Card className="mt-6" data-testid="compliance-trend">
              <CardHeader><CardTitle className="flex items-center gap-2"><TrendingUp className="h-5 w-5" /> Compliance Trend</CardTitle></CardHeader>
              <CardContent>
                <div className="flex items-end gap-4 h-40">
                  {complianceData.trend.map((point, i) => (
                    <div key={i} className="flex flex-col items-center flex-1">
                      <div className="text-xs font-bold mb-1">{point.score}%</div>
                      <div className={`w-full rounded-t ${point.score >= 75 ? 'bg-green-400' : point.score >= 50 ? 'bg-yellow-400' : 'bg-red-400'}`} style={{ height: `${Math.max(point.score, 5)}%` }} />
                      <div className="text-xs text-gray-500 mt-1 truncate w-full text-center">{point.date}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* SLA Performance Tab */}
        <TabsContent value="sla" data-testid="sla-content">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
            <Card>
              <CardContent className="p-6 text-center">
                <div className="text-3xl font-bold text-emerald-600" data-testid="sla-rate">{slaData?.sla_rate != null ? slaData.sla_rate : 100}%</div>
                <div className="text-sm text-gray-500">SLA Compliance Rate</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6 text-center">
                <div className="text-3xl font-bold">{slaData?.total_tasks || 0}</div>
                <div className="text-sm text-gray-500">Total Tasks</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6 text-center">
                <div className="text-3xl font-bold text-green-600">{slaData?.on_time || 0}</div>
                <div className="text-sm text-gray-500">On Time</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6 text-center">
                <div className="text-3xl font-bold text-red-600" data-testid="sla-overdue">{slaData?.overdue || 0}</div>
                <div className="text-sm text-gray-500">Overdue</div>
              </CardContent>
            </Card>
          </div>

          {slaData?.by_priority && (
            <Card className="mb-6" data-testid="sla-by-priority">
              <CardHeader><CardTitle>By Priority</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Priority</TableHead>
                      <TableHead>Total</TableHead>
                      <TableHead>Completed</TableHead>
                      <TableHead>Overdue</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Object.entries(slaData.by_priority).map(([priority, data]) => (
                      <TableRow key={priority}>
                        <TableCell className="font-medium capitalize">{priority}</TableCell>
                        <TableCell>{data.total}</TableCell>
                        <TableCell className="text-green-600">{data.completed}</TableCell>
                        <TableCell className="text-red-600">{data.overdue}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {slaData?.by_team?.length > 0 && (
            <Card data-testid="sla-by-team">
              <CardHeader><CardTitle>By Team</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Department</TableHead>
                      <TableHead>Total</TableHead>
                      <TableHead>Completed</TableHead>
                      <TableHead>Overdue</TableHead>
                      <TableHead>Rate</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {slaData.by_team.map((team) => (
                      <TableRow key={team.department}>
                        <TableCell className="font-medium">{team.department}</TableCell>
                        <TableCell>{team.total}</TableCell>
                        <TableCell className="text-green-600">{team.completed}</TableCell>
                        <TableCell className="text-red-600">{team.overdue}</TableCell>
                        <TableCell className="font-bold">{team.total > 0 ? Math.round(team.completed / team.total * 100) : 100}%</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Gaps Heatmap Tab */}
        <TabsContent value="heatmap" data-testid="heatmap-content">
          {heatmapData?.heatmap?.length > 0 ? (
            <Card data-testid="gaps-heatmap">
              <CardHeader><CardTitle>Critical Gaps Heatmap</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Policy</TableHead>
                      <TableHead>Regulation</TableHead>
                      <TableHead>Total Gaps</TableHead>
                      <TableHead>Critical</TableHead>
                      <TableHead>High</TableHead>
                      <TableHead>Medium</TableHead>
                      <TableHead>Low</TableHead>
                      <TableHead>Score</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {heatmapData.heatmap.map((row, i) => (
                      <React.Fragment key={i}>
                        <TableRow
                          data-testid={`heatmap-row-${i}`}
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => setExpandedHeatmapRow(expandedHeatmapRow === i ? null : i)}
                        >
                          <TableCell className="font-medium">
                            {expandedHeatmapRow === i ? <ChevronUp className="h-4 w-4 inline mr-1" /> : <ChevronDown className="h-4 w-4 inline mr-1" />}
                            {row.policy}
                          </TableCell>
                          <TableCell>{row.regulation}</TableCell>
                          <TableCell><Badge variant="secondary">{row.total_gaps}</Badge></TableCell>
                          <TableCell>{row.severity_distribution?.Critical > 0 && <Badge className="bg-red-100 text-red-800">{row.severity_distribution.Critical}</Badge>}</TableCell>
                          <TableCell>{row.severity_distribution?.High > 0 && <Badge className="bg-orange-100 text-orange-800">{row.severity_distribution.High}</Badge>}</TableCell>
                          <TableCell>{row.severity_distribution?.Medium > 0 && <Badge className="bg-yellow-100 text-yellow-800">{row.severity_distribution.Medium}</Badge>}</TableCell>
                          <TableCell>{row.severity_distribution?.Low > 0 && <Badge className="bg-green-100 text-green-800">{row.severity_distribution.Low}</Badge>}</TableCell>
                          <TableCell><Badge className={getHeatColor(row.compliance_score)}>{row.compliance_score}%</Badge></TableCell>
                        </TableRow>
                        {expandedHeatmapRow === i && (
                          <TableRow data-testid={`heatmap-detail-${i}`}>
                            <TableCell colSpan={8} className="bg-muted/50 p-4">
                              <div className="space-y-3">
                                <div className="text-sm font-semibold">Gap Details ({row.total_gaps} gaps found)</div>
                                {row.gaps && row.gaps.length > 0 ? (
                                  <div className="space-y-2">
                                    {row.gaps.map((gap, gi) => (
                                      <div key={gi} className="flex items-start gap-3 p-2 bg-background rounded border" data-testid={`gap-detail-${gi}`}>
                                        <Badge className={
                                          gap.severity === 'Critical' ? 'bg-red-100 text-red-800' :
                                          gap.severity === 'High' ? 'bg-orange-100 text-orange-800' :
                                          gap.severity === 'Medium' ? 'bg-yellow-100 text-yellow-800' :
                                          'bg-green-100 text-green-800'
                                        }>{gap.severity}</Badge>
                                        <div className="flex-1">
                                          <div className="text-sm">{gap.description || 'No description available'}</div>
                                          {gap.remediation && (
                                            <div className="text-xs text-muted-foreground mt-1">
                                              <span className="font-medium">Remediation:</span> {gap.remediation}
                                            </div>
                                          )}
                                        </div>
                                        <Badge variant="outline" className="text-xs">{gap.type}</Badge>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <div className="text-sm text-muted-foreground">No detailed gap information available</div>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </React.Fragment>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ) : (
            <Card className="flex flex-col items-center justify-center h-64" data-testid="heatmap-empty">
              <CardContent className="text-center py-8">
                <AlertTriangle className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Gap Analysis Data</h3>
                <p className="text-muted-foreground">Run a gap analysis to see the heatmap</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Evidence Progress Tab */}
        <TabsContent value="evidence" data-testid="evidence-content">
          {evidenceProgressData ? (
            <div className="space-y-6">
              {/* Summary Card */}
              <Card data-testid="evidence-summary-card">
                <CardHeader>
                  <CardTitle>Evidence Collection Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Total Required Items</p>
                      <p className="text-2xl font-bold">{evidenceProgressData.summary?.total_required_items || 0}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Total Submitted Items</p>
                      <p className="text-2xl font-bold">{evidenceProgressData.summary?.total_submitted_items || 0}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Overall Completion</p>
                      <div className="flex items-center gap-2">
                        <Progress value={evidenceProgressData.summary?.overall_completion || 0} className="flex-1" />
                        <span className="text-lg font-bold">{evidenceProgressData.summary?.overall_completion || 0}%</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Per-Policy Evidence Progress */}
              {evidenceProgressData.policies && evidenceProgressData.policies.length > 0 && (
                <Card data-testid="policy-evidence-card">
                  <CardHeader>
                    <CardTitle>Evidence Progress per Policy</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Policy Name</TableHead>
                          <TableHead className="text-center">Required Items</TableHead>
                          <TableHead className="text-center">Submitted Items</TableHead>
                          <TableHead>Completion</TableHead>
                          <TableHead className="text-center">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {evidenceProgressData.policies.map((policy, idx) => (
                          <TableRow key={idx} data-testid={`policy-evidence-row-${idx}`}>
                            <TableCell className="font-medium">{policy.policy_name}</TableCell>
                            <TableCell className="text-center">{policy.required_items}</TableCell>
                            <TableCell className="text-center">{policy.submitted_items}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Progress value={policy.completion_percentage} className="flex-1" />
                                <span className="text-sm font-medium w-12">{policy.completion_percentage}%</span>
                              </div>
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge
                                variant={policy.rag_status === 'green' ? 'default' : policy.rag_status === 'amber' ? 'secondary' : 'destructive'}
                                data-testid={`policy-rag-${policy.rag_status}`}
                              >
                                {policy.rag_status.toUpperCase()}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}

              {/* Per-Regulation Evidence Progress */}
              {evidenceProgressData.regulations && evidenceProgressData.regulations.length > 0 && (
                <Card data-testid="regulation-evidence-card">
                  <CardHeader>
                    <CardTitle>Evidence Progress per Regulation</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Regulation Name</TableHead>
                          <TableHead className="text-center">Required Items</TableHead>
                          <TableHead className="text-center">Submitted Items</TableHead>
                          <TableHead>Completion</TableHead>
                          <TableHead className="text-center">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {evidenceProgressData.regulations.map((regulation, idx) => (
                          <TableRow key={idx} data-testid={`regulation-evidence-row-${idx}`}>
                            <TableCell className="font-medium">{regulation.regulation_name}</TableCell>
                            <TableCell className="text-center">{regulation.required_items}</TableCell>
                            <TableCell className="text-center">{regulation.submitted_items}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Progress value={regulation.completion_percentage} className="flex-1" />
                                <span className="text-sm font-medium w-12">{regulation.completion_percentage}%</span>
                              </div>
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge
                                variant={regulation.rag_status === 'green' ? 'default' : regulation.rag_status === 'amber' ? 'secondary' : 'destructive'}
                                data-testid={`regulation-rag-${regulation.rag_status}`}
                              >
                                {regulation.rag_status.toUpperCase()}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}

              {/* Empty state */}
              {(!evidenceProgressData.policies || evidenceProgressData.policies.length === 0) &&
               (!evidenceProgressData.regulations || evidenceProgressData.regulations.length === 0) && (
                <Card className="flex flex-col items-center justify-center h-64" data-testid="evidence-empty">
                  <CardContent className="text-center py-8">
                    <TrendingUp className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                    <h3 className="text-lg font-semibold mb-2">No Evidence Data</h3>
                    <p className="text-muted-foreground">Upload policies and regulations to track evidence progress</p>
                  </CardContent>
                </Card>
              )}
            </div>
          ) : (
            <Card className="flex flex-col items-center justify-center h-64" data-testid="evidence-loading">
              <CardContent className="text-center py-8">
                <TrendingUp className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Evidence Data</h3>
                <p className="text-muted-foreground">Evidence progress analytics not available</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Regulation Coverage Tab */}
        <TabsContent value="regulation-coverage" data-testid="regulation-coverage-content">
          {regulationCoverageData ? (
            <div className="space-y-6">
              {/* Coverage Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <Card data-testid="coverage-percentage-card">
                  <CardContent className="p-6 text-center">
                    <div className={`text-5xl font-bold mb-2 ${
                      regulationCoverageData.coverage_percentage >= 75 ? 'text-green-600' :
                      regulationCoverageData.coverage_percentage >= 50 ? 'text-yellow-600' : 'text-red-600'
                    }`} data-testid="coverage-percentage">
                      {regulationCoverageData.coverage_percentage}%
                    </div>
                    <div className="text-sm text-gray-500">Regulation Coverage</div>
                    <Progress value={regulationCoverageData.coverage_percentage} className="mt-3" />
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6 text-center">
                    <div className="text-3xl font-bold text-blue-600 mb-2" data-testid="total-regulations">
                      {regulationCoverageData.total_regulations}
                    </div>
                    <div className="text-sm text-gray-500">Total Regulations</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6 text-center">
                    <div className="text-3xl font-bold text-green-600 mb-2" data-testid="mapped-count">
                      {regulationCoverageData.mapped_regulations}
                    </div>
                    <div className="text-sm text-gray-500">Mapped to Policies</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6 text-center">
                    <div className={`text-3xl font-bold mb-2 ${regulationCoverageData.unmapped_regulations > 0 ? 'text-red-600' : 'text-green-600'}`} data-testid="unmapped-count">
                      {regulationCoverageData.unmapped_regulations}
                    </div>
                    <div className="text-sm text-gray-500">Unmapped Regulations</div>
                  </CardContent>
                </Card>
              </div>

              {/* Regulation Details Table */}
              {regulationCoverageData.regulations && regulationCoverageData.regulations.length > 0 ? (
                <Card data-testid="regulation-coverage-table">
                  <CardHeader>
                    <CardTitle>Regulation Coverage Details</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Regulation Name</TableHead>
                          <TableHead>Regulator</TableHead>
                          <TableHead className="text-center">Coverage Status</TableHead>
                          <TableHead className="text-center">Mapped Policies</TableHead>
                          <TableHead className="text-center">Details</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {regulationCoverageData.regulations.map((reg, idx) => (
                          <React.Fragment key={reg.id || idx}>
                            <TableRow
                              className={!reg.is_mapped ? 'bg-red-50 dark:bg-red-950/20' : ''}
                              data-testid={`regulation-row-${idx}`}
                              data-mapped={reg.is_mapped ? 'true' : 'false'}
                            >
                              <TableCell className="font-medium">
                                {!reg.is_mapped && (
                                  <AlertTriangle className="h-4 w-4 text-red-500 inline mr-2" />
                                )}
                                {reg.name}
                              </TableCell>
                              <TableCell>{reg.regulator}</TableCell>
                              <TableCell className="text-center">
                                <Badge
                                  variant={reg.is_mapped ? 'default' : 'destructive'}
                                  data-testid={`coverage-status-${reg.is_mapped ? 'mapped' : 'unmapped'}`}
                                >
                                  {reg.is_mapped ? 'Mapped' : 'Unmapped'}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-center">{reg.policy_count}</TableCell>
                              <TableCell className="text-center">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setExpandedRegulation(expandedRegulation === reg.id ? null : reg.id)}
                                  data-testid={`drill-down-${idx}`}
                                >
                                  {expandedRegulation === reg.id ? (
                                    <ChevronUp className="h-4 w-4" />
                                  ) : (
                                    <ChevronDown className="h-4 w-4" />
                                  )}
                                </Button>
                              </TableCell>
                            </TableRow>
                            {expandedRegulation === reg.id && (
                              <TableRow data-testid={`regulation-detail-${idx}`}>
                                <TableCell colSpan={5} className="bg-muted/50 p-4">
                                  <div className="space-y-2">
                                    <div className="text-sm font-semibold">Mapped Policies:</div>
                                    {reg.mapped_policies && reg.mapped_policies.length > 0 ? (
                                      <div className="flex flex-wrap gap-2">
                                        {reg.mapped_policies.map((policy, pIdx) => (
                                          <Badge key={pIdx} variant="outline">{policy}</Badge>
                                        ))}
                                      </div>
                                    ) : (
                                      <div className="text-sm text-red-500 flex items-center gap-2">
                                        <AlertTriangle className="h-4 w-4" />
                                        No policies mapped to this regulation. Consider creating a gap analysis.
                                      </div>
                                    )}
                                  </div>
                                </TableCell>
                              </TableRow>
                            )}
                          </React.Fragment>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              ) : (
                <Card className="flex flex-col items-center justify-center h-64" data-testid="regulation-coverage-empty">
                  <CardContent className="text-center py-8">
                    <Shield className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                    <h3 className="text-lg font-semibold mb-2">No Regulations Found</h3>
                    <p className="text-muted-foreground">Upload regulations to track coverage metrics</p>
                  </CardContent>
                </Card>
              )}
            </div>
          ) : (
            <Card className="flex flex-col items-center justify-center h-64" data-testid="regulation-coverage-loading">
              <CardContent className="text-center py-8">
                <Shield className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Regulation Coverage Data</h3>
                <p className="text-muted-foreground">Upload regulations and policies to see coverage metrics</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
