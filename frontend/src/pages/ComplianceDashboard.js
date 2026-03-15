import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Shield, CheckCircle, AlertTriangle, AlertCircle, XCircle,
  TrendingUp, Clock, Target, BarChart3, Activity, FileText,
  Building2, RefreshCw, ArrowRight, Loader2
} from 'lucide-react';
import { toast } from 'sonner';
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, Legend, AreaChart, Area, CartesianGrid
} from 'recharts';
import api from '../lib/api';

const SEVERITY_COLORS = {
  Critical: '#DC2626',
  High: '#D97706',
  Medium: '#2563EB',
  Low: '#059669',
};

const STATUS_COLORS = {
  compliant: '#059669',
  needs_evidence: '#D97706',
  non_compliant: '#DC2626',
  partial: '#F59E0B',
};

const getScoreColor = (score) => {
  if (score >= 80) return 'text-emerald-600';
  if (score >= 60) return 'text-amber-500';
  return 'text-red-500';
};

const getScoreBg = (score) => {
  if (score >= 80) return 'bg-emerald-50 border-emerald-200';
  if (score >= 60) return 'bg-amber-50 border-amber-200';
  return 'bg-red-50 border-red-200';
};

export default function ComplianceDashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState(null);
  const [checks, setChecks] = useState(null);
  const [deadlines, setDeadlines] = useState([]);
  const [trend, setTrend] = useState([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewRes, checksRes, deadlinesRes, trendRes] = await Promise.allSettled([
        api.get('/api/compliance/overview'),
        api.get('/api/compliance-checks/comprehensive'),
        api.get('/api/compliance/deadlines'),
        api.get('/api/compliance/trend'),
      ]);

      if (overviewRes.status === 'fulfilled') setOverview(overviewRes.value.data);
      if (checksRes.status === 'fulfilled') setChecks(checksRes.value.data);
      if (deadlinesRes.status === 'fulfilled') setDeadlines(deadlinesRes.value.data?.deadlines || []);
      if (trendRes.status === 'fulfilled') setTrend(trendRes.value.data?.trend || []);
    } catch (err) {
      toast.error('Failed to load compliance data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2 text-muted-foreground">Loading compliance data...</span>
      </div>
    );
  }

  const overallScore = overview?.latest_score || checks?.overall_score || 0;
  const categories = checks?.categories || {};
  const categoryData = Object.entries(categories).map(([key, val]) => ({
    name: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    score: val.score || 0,
    total: val.total_checks || 0,
    compliant: val.compliant || 0,
    key,
  }));

  // Build pie chart data for overall status
  const statusCounts = checks ? [
    { name: 'Compliant', value: checks.compliant || 0, color: STATUS_COLORS.compliant },
    { name: 'Needs Evidence', value: checks.needs_evidence || 0, color: STATUS_COLORS.needs_evidence },
    { name: 'Non-Compliant', value: checks.non_compliant || 0, color: STATUS_COLORS.non_compliant },
  ].filter(d => d.value > 0) : [];

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6 text-primary" />
            PA/PG Compliance Dashboard
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            RBI Master Direction compliance overview
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="h-4 w-4 mr-1" /> Refresh
        </Button>
      </div>

      {/* Score Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className={`border ${getScoreBg(overallScore)}`}>
          <CardContent className="pt-6">
            <div className="text-center">
              <div className={`text-4xl font-bold ${getScoreColor(overallScore)}`}>
                {overallScore}%
              </div>
              <p className="text-sm text-muted-foreground mt-1">Overall Score</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-50">
                <CheckCircle className="h-5 w-5 text-emerald-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">{checks?.compliant || 0}</div>
                <p className="text-xs text-muted-foreground">Compliant</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-50">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">{checks?.needs_evidence || 0}</div>
                <p className="text-xs text-muted-foreground">Needs Evidence</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-red-50">
                <XCircle className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">{checks?.non_compliant || 0}</div>
                <p className="text-xs text-muted-foreground">Non-Compliant</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="heatmap" className="space-y-4">
        <TabsList>
          <TabsTrigger value="heatmap">Category Heatmap</TabsTrigger>
          <TabsTrigger value="trend">Compliance Trend</TabsTrigger>
          <TabsTrigger value="checks">Check Details</TabsTrigger>
          <TabsTrigger value="deadlines">Deadlines</TabsTrigger>
        </TabsList>

        {/* Heatmap Tab */}
        <TabsContent value="heatmap">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Category Compliance Scores</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {categoryData.map(cat => (
                    <div key={cat.key} className="space-y-1">
                      <div className="flex justify-between items-center text-sm">
                        <span className="font-medium">{cat.name}</span>
                        <span className={getScoreColor(cat.score)}>{cat.score}%</span>
                      </div>
                      <Progress
                        value={cat.score}
                        className="h-2"
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{cat.compliant}/{cat.total} checks passed</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Status Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                {statusCounts.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={statusCounts}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        dataKey="value"
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        {statusCounts.map((entry, index) => (
                          <Cell key={index} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="text-center text-muted-foreground py-8">No check data available</div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Trend Tab */}
        <TabsContent value="trend">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Compliance Score Trend</CardTitle>
              <CardDescription>Historical compliance score over time</CardDescription>
            </CardHeader>
            <CardContent>
              {trend.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={trend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Area type="monotone" dataKey="score" stroke="#059669" fill="#059669" fillOpacity={0.1} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-center text-muted-foreground py-12">
                  <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No trend data yet. Run gap analyses to build compliance history.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Check Details Tab */}
        <TabsContent value="checks">
          <div className="space-y-4">
            {Object.entries(categories).map(([catKey, catData]) => (
              <Card key={catKey}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">
                      {catKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </CardTitle>
                    <Badge variant={catData.score >= 80 ? 'default' : catData.score >= 60 ? 'secondary' : 'destructive'}>
                      {catData.score}%
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {(catData.checks || []).map((check, idx) => (
                      <div key={idx} className="flex items-center justify-between py-2 border-b last:border-0">
                        <div className="flex items-center gap-2">
                          {check.status === 'compliant' && <CheckCircle className="h-4 w-4 text-emerald-500" />}
                          {check.status === 'needs_evidence' && <AlertTriangle className="h-4 w-4 text-amber-500" />}
                          {check.status === 'non_compliant' && <XCircle className="h-4 w-4 text-red-500" />}
                          {check.status === 'partial' && <AlertCircle className="h-4 w-4 text-amber-500" />}
                          <span className="text-sm">{check.title}</span>
                        </div>
                        <Badge variant="outline" className="text-xs">
                          {check.requirement_id}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Deadlines Tab */}
        <TabsContent value="deadlines">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Clock className="h-4 w-4" />
                Upcoming Compliance Deadlines
              </CardTitle>
            </CardHeader>
            <CardContent>
              {deadlines.length > 0 ? (
                <div className="space-y-3">
                  {deadlines.map((d, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 rounded-lg border">
                      <div>
                        <p className="font-medium text-sm">{d.title}</p>
                        <p className="text-xs text-muted-foreground">Due: {d.next_due}</p>
                      </div>
                      <Badge
                        variant={d.criticality === 'high' ? 'destructive' : 'secondary'}
                      >
                        {d.criticality}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-8">
                  No upcoming deadlines
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
