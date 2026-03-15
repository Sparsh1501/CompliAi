import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardApi } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { 
  FileText, Shield, CheckCircle, AlertTriangle, ListTodo, TrendingUp, 
  Building2, Clock, Activity, Target, BarChart3, PieChart as PieChartIcon,
  ArrowUpRight, ArrowDownRight, Calendar, Zap, AlertCircle, RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';
import { 
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, 
  Tooltip, Legend, Line, Area, AreaChart, RadialBarChart, RadialBar,
  CartesianGrid, ComposedChart
} from 'recharts';
import { MOCK_DASHBOARD_STATS } from '../lib/mockData';

// Emerald corporate color palette
const COLORS = {
  primary: '#059669',      // Emerald accent
  secondary: '#4F46E5',    // Indigo accent
  success: '#059669',      // Emerald green
  warning: '#D97706',      // Amber
  danger: '#DC2626',       // Red
  info: '#2563EB',         // Blue
  purple: '#7C3AED',       // Violet
  pink: '#DB2777',         // Pink
  gray: '#6B7280',         // Gray text
  background: '#FFFFFF',   // White
  card: '#FFFFFF',         // Card background
  border: '#E5E7EB',       // Border color
  text: '#111827'          // Primary text
};

const STATUS_COLORS = {
  'Compliant': '#059669',          // Emerald
  'Partially Compliant': '#D97706', // Amber
  'Non-Compliant': '#DC2626',       // Red
  'Noted for Compliance': '#6B7280' // Gray
};

const PRIORITY_COLORS = {
  'Critical': '#DC2626',   // Red
  'High': '#D97706',       // Amber
  'Medium': '#2563EB',     // Blue
  'Low': '#059669'         // Emerald
};

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Determine user role for role-based views
  const userRole = user?.role || 'user';

  // Feature #193: Prevent stale API responses from overwriting fresh data
  const dashRequestIdRef = useRef(0);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async (isRefresh = false) => {
    const requestId = ++dashRequestIdRef.current;
    try {
      if (isRefresh) setRefreshing(true);
      setError(null);
      const response = await dashboardApi.getStats();
      // Feature #193: Only update state if this is still the latest request
      if (requestId !== dashRequestIdRef.current) return;
      // Use mock data as fallback if API returns empty/null
      const hasData = response && (response.total_policies > 0 || response.compliance_score > 0);
      setStats(hasData ? response : MOCK_DASHBOARD_STATS);
      if (isRefresh) toast.success('Dashboard refreshed');
    } catch (err) {
      if (requestId !== dashRequestIdRef.current) return;
      console.error('Dashboard error:', err);
      // Fallback to mock data on error for demo purposes
      setStats(MOCK_DASHBOARD_STATS);
      console.log('Using mock dashboard data for demo');
    } finally {
      if (requestId === dashRequestIdRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
          <p className="text-muted-foreground">Loading compliance dashboard...</p>
        </div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="flex items-center justify-center h-96" data-testid="dashboard-error">
        <div className="flex flex-col items-center gap-4 text-center max-w-md">
          <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center">
            <AlertTriangle className="h-8 w-8 text-red-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Unable to load dashboard</h2>
          <p className="text-gray-500" data-testid="dashboard-error-message">{error}</p>
          <button
            onClick={() => { setLoading(true); loadStats(); }}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-50 text-emerald-600 rounded-lg hover:bg-emerald-100 transition-colors"
            data-testid="dashboard-retry-button"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  const complianceStatusData = Object.entries(stats?.compliance_by_status || {})
    .filter(([_, value]) => value > 0)
    .map(([name, value]) => ({ name, value, fill: STATUS_COLORS[name] || COLORS.gray }));

  const tasksByPriorityData = Object.entries(stats?.tasks_by_priority || {})
    .map(([name, value]) => ({ name, value, fill: PRIORITY_COLORS[name] || COLORS.gray }));

  const gapSeverityData = Object.entries(stats?.gap_severity_distribution || {})
    .map(([name, value]) => ({ name, value, fill: PRIORITY_COLORS[name] || COLORS.gray }));

  const complianceScore = stats?.compliance_score || 0;
  const riskScore = stats?.risk_metrics?.risk_score || 0;

  // Role-based widget visibility
  const showWidget = (widget) => {
    // Compliance Head: strategic view (all widgets)
    if (userRole === 'compliance_head') return true;

    // Auditor: audit-focused (compliance, risk, gaps, audit-related)
    if (userRole === 'auditor') {
      const auditWidgets = ['compliance', 'risk', 'gaps', 'audit', 'regulatory', 'evidence', 'departments'];
      return auditWidgets.includes(widget);
    }

    // Policy Owner/User: task-focused (tasks, deadlines, recent activity)
    if (userRole === 'user' || userRole === 'policy_owner') {
      const taskWidgets = ['tasks', 'deadlines', 'activity', 'policies', 'compliance'];
      return taskWidgets.includes(widget);
    }

    // Default: show all
    return true;
  };

  return (
    <div className="space-y-6 pb-8" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold text-gradient">
            Compliance Dashboard
          </h1>
          <p className="text-base text-muted-foreground mt-1">
            Real-time compliance monitoring and analytics
          </p>
        </div>
        <button 
          onClick={() => loadStats(true)}
          disabled={refreshing}
          className="btn-shiny flex items-center gap-2 px-4 py-2 text-white rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Compliance Score Hero - All roles can see this */}
      {showWidget('compliance') && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6" data-testid="compliance-score-section">
        <Card className="lg:col-span-2 shiny-card border-gray-200">
          <CardContent className="pt-6">
            <div className="flex flex-col md:flex-row items-center gap-8" data-testid="compliance-score-widget">
              <div className="relative">
                <ResponsiveContainer width={200} height={200}>
                  <RadialBarChart 
                    cx="50%" cy="50%" innerRadius="60%" outerRadius="100%" 
                    data={[{ value: complianceScore, fill: complianceScore >= 70 ? COLORS.success : complianceScore >= 50 ? COLORS.warning : COLORS.danger }]}
                    startAngle={90} endAngle={-270}
                  >
                    <RadialBar background={{ fill: '#E5E7EB' }} dataKey="value" cornerRadius={10} max={100} />
                  </RadialBarChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-4xl font-bold text-gray-900" data-testid="compliance-score-value">{complianceScore.toFixed(0)}%</span>
                  <span className="text-sm text-gray-500">Compliance</span>
                </div>
              </div>
              <div className="flex-1 space-y-4">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Overall Compliance Score</h2>
                  <p className="text-gray-500">Based on latest gap analysis and task completion</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 cursor-pointer hover:border-emerald-300 transition-colors" onClick={() => navigate('/gap-analysis')}>
                    <div className="flex items-center gap-2 text-emerald-500">
                      <TrendingUp className="h-4 w-4" />
                      <span className="text-sm font-medium">Compliant Depts</span>
                    </div>
                    <p className="text-2xl font-bold mt-1 text-gray-900">{(stats?.departments_count || 0) - (stats?.non_compliant_departments || 0)}</p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 cursor-pointer hover:border-red-300 transition-colors" onClick={() => navigate('/gap-analysis')}>
                    <div className="flex items-center gap-2 text-red-600">
                      <AlertTriangle className="h-4 w-4" />
                      <span className="text-sm font-medium">Critical Gaps</span>
                    </div>
                    <p className="text-2xl font-bold mt-1 text-gray-900">{stats?.critical_gaps || 0}</p>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Risk Assessment - All roles */}
        {showWidget('risk') && (
        <Card className={`bg-white border-gray-200 ${riskScore > 50 ? 'border-l-4 border-l-red-500' : 'border-l-4 border-l-emerald-500'}`}>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-gray-900">
              <Target className="h-5 w-5 text-emerald-600" />
              Risk Assessment
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="text-center">
                <span className={`text-5xl font-bold ${riskScore > 50 ? 'text-red-600' : 'text-emerald-500'}`}>
                  {riskScore}
                </span>
                <p className="text-sm text-gray-500 mt-1">Risk Score</p>
              </div>
              <Progress value={100 - riskScore} className="h-3" />
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">High Risk:</span>
                  <span className="font-medium text-red-600">{stats?.risk_metrics?.high_risk_items || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Overdue:</span>
                  <span className="font-medium text-amber-600">{stats?.risk_metrics?.overdue_tasks || 0}</span>
                </div>
              </div>
              <Badge 
                variant={stats?.risk_metrics?.trend === 'improving' ? 'default' : 'destructive'} 
                className="w-full justify-center cursor-pointer hover:opacity-80 transition-opacity"
                onClick={() => navigate('/tasks?priority=Critical')}
              >
                {stats?.risk_metrics?.trend === 'improving' ? (
                  <><ArrowUpRight className="h-3 w-3 mr-1" /> Improving</>
                ) : (
                  <><ArrowDownRight className="h-3 w-3 mr-1" /> Needs Attention</>
                )}
              </Badge>
            </div>
          </CardContent>
        </Card>
        )}
      </div>
      )}

      {/* Key Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {[
          { title: 'Policies', value: stats?.total_policies || 0, icon: FileText, color: 'text-blue-500', bg: 'bg-blue-50', widget: 'policies', link: '/policies' },
          { title: 'Regulations', value: stats?.total_regulations || 0, icon: Shield, color: 'text-violet-500', bg: 'bg-violet-50', widget: 'regulatory', link: '/regulations' },
          { title: 'Departments', value: stats?.departments_count || 0, icon: Building2, color: 'text-emerald-600', bg: 'bg-emerald-50', widget: 'departments', link: '/departments' },
          { title: 'Total Tasks', value: stats?.total_tasks || 0, icon: ListTodo, color: 'text-emerald-500', bg: 'bg-emerald-50', widget: 'tasks', link: '/tasks' },
          { title: 'Pending Actions', value: stats?.pending_actionables || 0, icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50', widget: 'tasks', link: '/tasks' },
          { title: 'High Priority', value: stats?.high_priority_tasks || 0, icon: Zap, color: 'text-red-600', bg: 'bg-red-50', widget: 'tasks', link: '/tasks' },
        ].filter(stat => showWidget(stat.widget)).map((stat, index) => {
          const Icon = stat.icon;
          return (
            <Card key={index} className="bg-white border-gray-200 hover:shadow-lg hover:shadow-emerald-100 transition-all hover:-translate-y-1 cursor-pointer" onClick={() => navigate(stat.link)}>
              <CardContent className="pt-4 pb-4">
                <div className={`${stat.bg} w-10 h-10 rounded-lg flex items-center justify-center mb-3`}>
                  <Icon className={`h-5 w-5 ${stat.color}`} />
                </div>
                <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                <p className="text-xs text-gray-500">{stat.title}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Charts Row 1 - Compliance trends (all roles) and Department compliance (compliance_head, auditor) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {showWidget('compliance') && (
        <Card className="bg-white border-gray-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-gray-900">
              <TrendingUp className="h-5 w-5 text-emerald-600" />
              Compliance Trend
            </CardTitle>
            <CardDescription className="text-gray-500">Monthly compliance score progression</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={stats?.compliance_trend || []}>
                <defs>
                  <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.primary} stopOpacity={0.3}/>
                    <stop offset="95%" stopColor={COLORS.primary} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#6B7280' }} stroke="#E5E7EB" />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: '#6B7280' }} stroke="#E5E7EB" />
                <Tooltip contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', color: '#111827' }} formatter={(value) => [`${value}%`, 'Score']} />
                <Area type="monotone" dataKey="score" stroke={COLORS.primary} strokeWidth={2} fillOpacity={1} fill="url(#colorScore)" />
                <Line type="monotone" dataKey="score" stroke={COLORS.primary} strokeWidth={2} dot={{ fill: COLORS.primary }} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        )}

        {showWidget('departments') && (
        <Card className="bg-white border-gray-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-gray-900">
              <Building2 className="h-5 w-5 text-emerald-600" />
              Department Compliance
            </CardTitle>
            <CardDescription className="text-gray-500">Compliance score by department</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={stats?.compliance_by_department || []} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12, fill: '#6B7280' }} stroke="#E5E7EB" />
                <YAxis dataKey="department" type="category" width={100} tick={{ fontSize: 11, fill: '#6B7280' }} stroke="#E5E7EB" />
                <Tooltip contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', color: '#111827' }} formatter={(value) => [`${value}%`, 'Score']} />
                <Bar dataKey="compliance_score" fill={COLORS.primary} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        )}
      </div>

      {/* Charts Row 2 - Compliance status, task priority, gap severity */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {showWidget('compliance') && (
        <Card className="bg-white border-gray-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-gray-900">
              <PieChartIcon className="h-5 w-5 text-emerald-600" />
              Compliance Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            {complianceStatusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={complianceStatusData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value">
                    {complianceStatusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', color: '#111827' }} />
                  <Legend wrapperStyle={{ fontSize: '12px', color: '#6B7280' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-gray-500">No data available</div>
            )}
          </CardContent>
        </Card>
        )}

        {showWidget('tasks') && (
        <Card className="bg-white border-gray-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-gray-900">
              <BarChart3 className="h-5 w-5 text-emerald-600" />
              Tasks by Priority
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={tasksByPriorityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6B7280' }} stroke="#E5E7EB" />
                <YAxis tick={{ fontSize: 12, fill: '#6B7280' }} stroke="#E5E7EB" />
                <Tooltip contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', color: '#111827' }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {tasksByPriorityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        )}

        {showWidget('gaps') && (
        <Card className="bg-white border-gray-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-gray-900">
              <AlertCircle className="h-5 w-5 text-emerald-600" />
              Gap Severity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={gapSeverityData.filter(d => d.value > 0)} cx="50%" cy="50%" outerRadius={80} dataKey="value" 
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                  {gapSeverityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', color: '#111827' }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        )}
      </div>

      {/* Monthly Activity - Tasks (all roles) */}
      {showWidget('tasks') && (
      <Card className="bg-white border-gray-200">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-gray-900">
            <Activity className="h-5 w-5 text-emerald-600" />
            Monthly Task Activity
          </CardTitle>
          <CardDescription className="text-gray-500">Tasks created vs completed over time</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={stats?.monthly_task_completion || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#6B7280' }} stroke="#E5E7EB" />
              <YAxis tick={{ fontSize: 12, fill: '#6B7280' }} stroke="#E5E7EB" />
              <Tooltip contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', color: '#111827' }} />
              <Legend wrapperStyle={{ color: '#6B7280' }} />
              <Bar dataKey="created" name="Created" fill={COLORS.info} radius={[4, 4, 0, 0]} />
              <Bar dataKey="completed" name="Completed" fill={COLORS.success} radius={[4, 4, 0, 0]} />
              <Line type="monotone" dataKey="completed" stroke={COLORS.success} strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      )}

      {/* Bottom Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="bg-white border-gray-200" data-testid="regulation-breakdown">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-gray-900">
              <Shield className="h-5 w-5 text-emerald-600" />
              Regulatory Bodies
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(stats?.regulator_overview || []).map((reg, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200 hover:border-emerald-300 transition-colors cursor-pointer" onClick={() => navigate('/regulations')}>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-emerald-50 flex items-center justify-center">
                      <Shield className="h-5 w-5 text-emerald-600" />
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{reg.regulator}</p>
                      <p className="text-sm text-gray-500">{reg.circulars_count} circulars</p>
                    </div>
                  </div>
                  <Badge variant="outline" className="border-gray-200 text-gray-500">{reg.compliance_status}</Badge>
                </div>
              ))}
              {(!stats?.regulator_overview || stats.regulator_overview.length === 0) && (
                <p className="text-gray-500 text-center py-4">No regulators found</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-gray-900">
              <Calendar className="h-5 w-5 text-emerald-600" />
              Upcoming Deadlines
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(stats?.upcoming_deadlines || []).map((task, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200 cursor-pointer hover:border-emerald-300 transition-colors" onClick={() => navigate('/tasks')}>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate text-gray-900">{task.title}</p>
                    <p className="text-sm text-gray-500">{task.days_remaining} days remaining</p>
                  </div>
                  <Badge variant={task.priority === 'Critical' ? 'destructive' : task.priority === 'High' ? 'default' : 'secondary'}>
                    {task.priority}
                  </Badge>
                </div>
              ))}
              {(!stats?.upcoming_deadlines || stats.upcoming_deadlines.length === 0) && (
                <div className="text-center py-8 text-gray-500">
                  <CheckCircle className="h-12 w-12 mx-auto mb-2 text-emerald-500" />
                  <p>No upcoming deadlines</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-gray-900">
              <FileText className="h-5 w-5 text-emerald-600" />
              Policy Coverage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="text-center">
                <div className="relative inline-flex items-center justify-center cursor-pointer" onClick={() => navigate('/policies')}>
                  <svg className="w-32 h-32 transform -rotate-90">
                    <circle cx="64" cy="64" r="56" stroke="#E5E7EB" strokeWidth="12" fill="none" />
                    <circle cx="64" cy="64" r="56" stroke="#059669" strokeWidth="12" fill="none" 
                      strokeDasharray={`${(stats?.policy_coverage?.percentage || 0) * 3.52} 352`} strokeLinecap="round" />
                  </svg>
                  <span className="absolute text-2xl font-bold text-gray-900">{stats?.policy_coverage?.percentage || 0}%</span>
                </div>
              </div>
              <div className="text-center text-sm text-gray-500">
                {stats?.policy_coverage?.covered || 0} of {stats?.policy_coverage?.total || 0} policy types covered
              </div>
              <div className="flex flex-wrap gap-1 justify-center">
                {(stats?.policy_coverage?.types_covered || []).slice(0, 4).map((type, idx) => (
                  <Badge key={idx} variant="secondary" className="text-xs bg-gray-50 text-gray-500 border border-gray-200">{type}</Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity - All roles */}
      {showWidget('activity') && (
      <Card className="bg-white border-gray-200" data-testid="recent-activity-section">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-gray-900">
            <Activity className="h-5 w-5 text-emerald-600" />
            Recent Activity
          </CardTitle>
          <CardDescription className="text-gray-500">Latest updates across your compliance workflow</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4" data-testid="recent-activity-list">
            {(stats?.recent_activities || []).map((activity, idx) => (
              <div key={idx} className="flex items-center gap-4 p-3 border border-gray-200 rounded-lg bg-gray-50 hover:border-emerald-300 transition-colors cursor-pointer" data-testid={`activity-item-${idx}`}
                onClick={() => {
                  if (activity.type === 'task_update') navigate('/tasks');
                  else if (activity.type === 'policy_update') navigate('/policies');
                }}>
                <div className={`w-2 h-2 rounded-full ${
                  activity.priority === 'Critical' ? 'bg-red-500' :
                  activity.priority === 'High' ? 'bg-amber-500' :
                  activity.priority === 'Medium' ? 'bg-[#60A5FA]' : 'bg-[#34D399]'
                }`} />
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{activity.title}</p>
                  <p className="text-sm text-gray-500" data-testid={`activity-timestamp-${idx}`}>
                    {activity.user && <span>{activity.user} &middot; </span>}
                    Status: {activity.status} {activity.time ? `- ${new Date(activity.time).toLocaleDateString()}` : ''}
                  </p>
                </div>
                <Badge variant="outline" className="border-gray-200 text-gray-500">{activity.status}</Badge>
              </div>
            ))}
            {(!stats?.recent_activities || stats.recent_activities.length === 0) && (
              <div className="text-center py-8 text-gray-500" data-testid="recent-activity-empty">
                <Activity className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                <p>No recent activity</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
      )}

      {/* Alerts - All roles see compliance alerts */}
      {stats?.compliance_score < 70 && (
        <Card className="bg-amber-50 border-[#FBAD41]/30">
          <CardContent className="pt-6">
            <div className="flex items-start gap-4">
              <AlertTriangle className="h-6 w-6 text-amber-600 mt-1 flex-shrink-0" />
              <div>
                <h3 className="font-semibold text-amber-600 mb-1">Compliance Score Below Threshold</h3>
                <p className="text-sm text-gray-900/80">
                  Your compliance score is currently {stats?.compliance_score?.toFixed(1)}%. Consider running gap analyses and addressing critical issues immediately.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {stats?.non_compliant_departments > 0 && (
        <Card className="bg-red-50 border-[#F87171]/30">
          <CardContent className="pt-6">
            <div className="flex items-start gap-4">
              <AlertCircle className="h-6 w-6 text-red-600 mt-1 flex-shrink-0" />
              <div>
                <h3 className="font-semibold text-red-600 mb-1">
                  {stats.non_compliant_departments} Non-Compliant Department{stats.non_compliant_departments > 1 ? 's' : ''}
                </h3>
                <p className="text-sm text-gray-900/80">
                  Some departments require immediate attention to address compliance gaps.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
