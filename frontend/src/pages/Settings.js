import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { notificationsApi } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Separator } from '../components/ui/separator';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Settings as SettingsIcon, User, Bell, Shield, Palette, Save, Cpu, Cloud, Zap, DollarSign, AlertTriangle, Building2, Users, UserPlus, Globe, Lock, CreditCard } from 'lucide-react';
import { toast } from 'sonner';
import { llmApi } from '../lib/api';
import CharterManagement from '../components/CharterManagement';
import TeamManagement from '../components/TeamManagement';
import InviteManagement from '../components/InviteManagement';
import ThemeSelector from '../components/ThemeSelector';
import OrganizationProfileForm from '../components/OrganizationProfileForm';

export default function Settings() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const defaultTab = searchParams.get('tab') || 'personal';
  const [preferences, setPreferences] = useState({
    email_enabled: true, push_enabled: true, compliance_alerts: true,
    gap_analysis_updates: true, task_assignments: true, audit_reminders: true,
  });
  const [profile, setProfile] = useState({
    name: user?.name || '', email: user?.email || '',
    department: user?.department || '', role: user?.role || '',
  });
  const [general, setGeneral] = useState({
    theme: 'dark', language: 'en', timezone: 'Asia/Kolkata', date_format: 'DD/MM/YYYY',
  });
  const [security, setSecurity] = useState({
    two_factor: false, session_timeout: '30', password_expiry: '90',
  });
  const [llmStatus, setLlmStatus] = useState(null);
  const [llmSwitching, setLlmSwitching] = useState(false);
  const [costSummary, setCostSummary] = useState(null);
  const [showLlmConfirmDialog, setShowLlmConfirmDialog] = useState(false);
  const [pendingLlmMode, setPendingLlmMode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadPreferences();
    loadLlmStatus();
    loadCostSummary();
  }, []);

  const loadPreferences = async () => {
    try {
      const prefs = await notificationsApi.getPreferences().catch(() => null);
      if (prefs) setPreferences(prev => ({ ...prev, ...prefs }));
    } catch (error) {
      // Use defaults
    } finally {
      setLoading(false);
    }
  };

  const loadLlmStatus = async () => {
    try {
      const status = await llmApi.getStatus();
      setLlmStatus(status);
    } catch (error) {
      console.debug('LLM status not available:', error.message);
    }
  };

  const loadCostSummary = async () => {
    try {
      const summary = await llmApi.getCostSummary();
      setCostSummary(summary);
    } catch (error) {
      console.debug('Cost summary not available:', error.message);
    }
  };

  // Feature #213: Show confirmation dialog before toggling
  const handleToggleLlmMode = () => {
    if (!llmStatus || llmSwitching) return;
    const newMode = llmStatus.mode === 'local' ? 'cloud' : 'local';
    setPendingLlmMode(newMode);
    setShowLlmConfirmDialog(true);
  };

  // Feature #213: Actually perform the switch after user confirms
  const handleConfirmLlmSwitch = async () => {
    if (!pendingLlmMode) return;
    setShowLlmConfirmDialog(false);
    setLlmSwitching(true);
    try {
      // Use the settings endpoint (Feature #213) which persists to MongoDB
      const result = await llmApi.setSettingsMode(pendingLlmMode);
      toast.success(`Switched to ${result.mode === 'local' ? 'Local LLM (Ollama)' : 'Cloud AI (Claude)'} mode`);
      // Refresh status
      await loadLlmStatus();
      await loadCostSummary();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Failed to switch LLM mode');
    } finally {
      setLlmSwitching(false);
      setPendingLlmMode(null);
    }
  };

  const handleCancelLlmSwitch = () => {
    setShowLlmConfirmDialog(false);
    setPendingLlmMode(null);
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      // Save to local storage for now
      localStorage.setItem('user_profile', JSON.stringify(profile));
      toast.success('Profile updated');
    } catch (error) {
      toast.error('Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveNotifications = async () => {
    setSaving(true);
    try {
      await notificationsApi.updatePreferences(preferences);
      toast.success('Notification preferences saved');
    } catch (error) {
      toast.error('Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveGeneral = async () => {
    setSaving(true);
    try {
      localStorage.setItem('app_settings', JSON.stringify(general));
      toast.success('Settings saved');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSecurity = async () => {
    setSaving(true);
    try {
      localStorage.setItem('security_settings', JSON.stringify(security));
      toast.success('Security settings saved');
    } catch (error) {
      toast.error('Failed to save security settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="settings-loading">
        <div className="text-muted-foreground">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-gray-600 to-gray-800 flex items-center justify-center shadow-lg">
          <SettingsIcon className="h-6 w-6 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold" data-testid="settings-title">Settings</h1>
          <p className="text-muted-foreground">Manage your account and application preferences</p>
        </div>
      </div>

      <Tabs defaultValue={defaultTab}>
        <TabsList className="grid w-full grid-cols-3 lg:w-auto">
          <TabsTrigger value="personal" data-testid="personal-tab">
            <User className="h-4 w-4 mr-2" /> Personal
          </TabsTrigger>
          {/* Organization tab - only for compliance_head and admin */}
          {(user?.role === 'compliance_head' || user?.role === 'admin') && (
            <TabsTrigger value="organization" data-testid="organization-tab">
              <Building2 className="h-4 w-4 mr-2" /> Organization
            </TabsTrigger>
          )}
          <TabsTrigger value="system" data-testid="system-tab">
            <Shield className="h-4 w-4 mr-2" /> Security & AI
          </TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        {/* Personal Tab - Profile, Preferences, Notifications, Theme */}
        <TabsContent value="personal" data-testid="personal-content" className="space-y-6">
          {/* Profile Section */}
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>Update your personal details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Full Name</Label>
                  <Input value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                    data-testid="profile-name-input" />
                </div>
                <div>
                  <Label>Email</Label>
                  <Input type="email" value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                    data-testid="profile-email-input" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Department</Label>
                  <Input value={profile.department} onChange={(e) => setProfile({ ...profile, department: e.target.value })}
                    placeholder="e.g., Compliance" data-testid="profile-department-input" />
                </div>
                <div>
                  <Label>Role</Label>
                  <Input value={profile.role} onChange={(e) => setProfile({ ...profile, role: e.target.value })}
                    placeholder="e.g., Compliance Officer" data-testid="profile-role-input" />
                </div>
              </div>
              <Button onClick={handleSaveProfile} disabled={saving} data-testid="save-profile-button">
                <Save className="mr-2 h-4 w-4" /> {saving ? 'Saving...' : 'Save Profile'}
              </Button>
            </CardContent>
          </Card>


          {/* Notifications Section */}
          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
              <CardDescription>Control how and when you receive notifications</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between" data-testid="setting-email-notifications">
                <div>
                  <Label className="font-medium">Email Notifications</Label>
                  <p className="text-sm text-muted-foreground">Receive compliance updates via email</p>
                </div>
                <Switch checked={preferences.email_enabled}
                  onCheckedChange={(v) => setPreferences({ ...preferences, email_enabled: v })}
                  data-testid="email-notifications-toggle" />
              </div>
              <Separator />
              <div className="flex items-center justify-between" data-testid="setting-push-notifications">
                <div>
                  <Label className="font-medium">Push Notifications</Label>
                  <p className="text-sm text-muted-foreground">Browser push notifications for urgent items</p>
                </div>
                <Switch checked={preferences.push_enabled}
                  onCheckedChange={(v) => setPreferences({ ...preferences, push_enabled: v })}
                  data-testid="push-notifications-toggle" />
              </div>
              <Separator />
              <div className="flex items-center justify-between" data-testid="setting-compliance-alerts">
                <div>
                  <Label className="font-medium">Compliance Deadline Alerts</Label>
                  <p className="text-sm text-muted-foreground">Alerts for upcoming compliance deadlines</p>
                </div>
                <Switch checked={preferences.compliance_alerts}
                  onCheckedChange={(v) => setPreferences({ ...preferences, compliance_alerts: v })}
                  data-testid="compliance-alerts-toggle" />
              </div>
              <Separator />
              <div className="flex items-center justify-between" data-testid="setting-gap-updates">
                <div>
                  <Label className="font-medium">Gap Analysis Updates</Label>
                  <p className="text-sm text-muted-foreground">Notify when gap analyses complete</p>
                </div>
                <Switch checked={preferences.gap_analysis_updates}
                  onCheckedChange={(v) => setPreferences({ ...preferences, gap_analysis_updates: v })}
                  data-testid="gap-updates-toggle" />
              </div>
              <Separator />
              <div className="flex items-center justify-between" data-testid="setting-task-assignments">
                <div>
                  <Label className="font-medium">Task Assignments</Label>
                  <p className="text-sm text-muted-foreground">Notify when tasks are assigned to you</p>
                </div>
                <Switch checked={preferences.task_assignments}
                  onCheckedChange={(v) => setPreferences({ ...preferences, task_assignments: v })}
                  data-testid="task-assignments-toggle" />
              </div>
              <Separator />
              <div className="flex items-center justify-between" data-testid="setting-audit-reminders">
                <div>
                  <Label className="font-medium">Audit Reminders</Label>
                  <p className="text-sm text-muted-foreground">Reminders for scheduled audits</p>
                </div>
                <Switch checked={preferences.audit_reminders}
                  onCheckedChange={(v) => setPreferences({ ...preferences, audit_reminders: v })}
                  data-testid="audit-reminders-toggle" />
              </div>
              <Button onClick={handleSaveNotifications} disabled={saving} data-testid="save-notifications-button">
                <Save className="mr-2 h-4 w-4" /> {saving ? 'Saving...' : 'Save Preferences'}
              </Button>
            </CardContent>
          </Card>

          {/* General Tab */}

          {/* Preferences Section */}
          <Card>
            <CardHeader>
              <CardTitle>Preferences</CardTitle>
              <CardDescription>Application language, timezone, and date format</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Language</Label>
                  <Select value={general.language} onValueChange={(v) => setGeneral({ ...general, language: v })}>
                    <SelectTrigger data-testid="language-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="hi">Hindi</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Timezone</Label>
                  <Select value={general.timezone} onValueChange={(v) => setGeneral({ ...general, timezone: v })}>
                    <SelectTrigger data-testid="timezone-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Asia/Kolkata">IST (Asia/Kolkata)</SelectItem>
                      <SelectItem value="UTC">UTC</SelectItem>
                      <SelectItem value="America/New_York">EST (New York)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>Date Format</Label>
                <Select value={general.date_format} onValueChange={(v) => setGeneral({ ...general, date_format: v })}>
                  <SelectTrigger data-testid="date-format-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="DD/MM/YYYY">DD/MM/YYYY</SelectItem>
                    <SelectItem value="MM/DD/YYYY">MM/DD/YYYY</SelectItem>
                    <SelectItem value="YYYY-MM-DD">YYYY-MM-DD</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleSaveGeneral} disabled={saving} data-testid="save-general-button">
                <Save className="mr-2 h-4 w-4" /> {saving ? 'Saving...' : 'Save Preferences'}
              </Button>
            </CardContent>
          </Card>

          {/* Theme Section */}
          <Card>
            <CardHeader>
              <CardTitle>Theme & Appearance</CardTitle>
              <CardDescription>Customize the look and feel of your workspace</CardDescription>
            </CardHeader>
            <CardContent>
              <ThemeSelector />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Organization Tab - Charters, Team, Invites */}
        {(user?.role === 'compliance_head' || user?.role === 'admin') && (
          <TabsContent value="organization" data-testid="organization-content" className="space-y-6">
            {/* Organization Profile Section */}
            <Card>
              <CardHeader>
                <CardTitle>Organization Profile</CardTitle>
                <CardDescription>Configure entity type, license status, financial information, and key personnel for compliance scoping</CardDescription>
              </CardHeader>
              <CardContent>
                <OrganizationProfileForm />
              </CardContent>
            </Card>

            {/* Charters Section */}
            <Card>
              <CardHeader>
                <CardTitle>Charter Management</CardTitle>
                <CardDescription>Manage organizational charters and compliance frameworks</CardDescription>
              </CardHeader>
              <CardContent>
                <CharterManagement />
              </CardContent>
            </Card>

            {/* Team Section */}
            <Card>
              <CardHeader>
                <CardTitle>Team Management</CardTitle>
                <CardDescription>Manage team members and their roles</CardDescription>
              </CardHeader>
              <CardContent>
                <TeamManagement />
              </CardContent>
            </Card>

            {/* Invites Section */}
            <Card>
              <CardHeader>
                <CardTitle>Invitations</CardTitle>
                <CardDescription>Send and manage team invitations</CardDescription>
              </CardHeader>
              <CardContent>
                <InviteManagement />
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Security & AI Tab - Security, AI/LLM, Costs */}
        <TabsContent value="system" data-testid="system-content" className="space-y-6">


          {/* Security Section */}
          <Card>
            <CardHeader>
              <CardTitle>Security Settings</CardTitle>
              <CardDescription>Authentication and access control</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between" data-testid="setting-2fa">
                <div>
                  <Label className="font-medium">Two-Factor Authentication</Label>
                  <p className="text-sm text-muted-foreground">Add an extra layer of security to your account</p>
                </div>
                <Switch checked={security.two_factor}
                  onCheckedChange={(v) => setSecurity({ ...security, two_factor: v })}
                  data-testid="two-factor-toggle" />
              </div>
              <Separator />
              <div>
                <Label>Session Timeout (minutes)</Label>
                <Select value={security.session_timeout} onValueChange={(v) => setSecurity({ ...security, session_timeout: v })}>
                  <SelectTrigger className="w-48" data-testid="session-timeout-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="15">15 minutes</SelectItem>
                    <SelectItem value="30">30 minutes</SelectItem>
                    <SelectItem value="60">1 hour</SelectItem>
                    <SelectItem value="120">2 hours</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Password Expiry (days)</Label>
                <Select value={security.password_expiry} onValueChange={(v) => setSecurity({ ...security, password_expiry: v })}>
                  <SelectTrigger className="w-48" data-testid="password-expiry-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="30">30 days</SelectItem>
                    <SelectItem value="60">60 days</SelectItem>
                    <SelectItem value="90">90 days</SelectItem>
                    <SelectItem value="never">Never</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleSaveSecurity} disabled={saving} data-testid="save-security-button">
                <Save className="mr-2 h-4 w-4" /> {saving ? 'Saving...' : 'Save Security Settings'}
              </Button>
            </CardContent>
          </Card>

          {/* AI / LLM Section */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>AI Provider Settings</CardTitle>
                <CardDescription>Configure which AI provider to use for compliance analysis. This is a global toggle that applies to ALL AI-powered services.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Mode Toggle */}
                <div className="flex items-center justify-between" data-testid="setting-llm-mode">
                  <div className="flex items-center gap-3">
                    {llmStatus?.mode === 'local' ? (
                      <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                        <Cpu className="h-5 w-5 text-purple-600" />
                      </div>
                    ) : (
                      <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                        <Cloud className="h-5 w-5 text-blue-600" />
                      </div>
                    )}
                    <div>
                      <Label className="font-medium">
                        {llmStatus?.mode === 'local' ? 'Local LLM Mode' : 'Cloud AI Mode'}
                      </Label>
                      <p className="text-sm text-muted-foreground">
                        {llmStatus?.mode === 'local'
                          ? 'Using local Ollama server for AI operations (zero cost)'
                          : 'Using Anthropic Claude API for AI operations (paid)'}
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={llmStatus?.mode === 'local'}
                    onCheckedChange={handleToggleLlmMode}
                    disabled={llmSwitching}
                    data-testid="llm-mode-toggle"
                  />
                </div>
                <Separator />

                {/* Per-service status (Feature #213) */}
                {llmStatus?.services && (
                  <div data-testid="llm-service-status">
                    <Label className="font-medium mb-2 block">Service Status</Label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {Object.entries(llmStatus.services).map(([svc, info]) => (
                        <div key={svc} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                          <span className="text-sm text-gray-700 capitalize">{svc.replace(/_/g, ' ')}</span>
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${info.mode === 'local'
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-blue-100 text-blue-700'
                            }`}>
                            {info.provider}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <Separator />

                {/* Current Model Info */}
                <div data-testid="llm-model-info">
                  <Label className="font-medium mb-2 block">Current Model</Label>
                  <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500">Provider</span>
                      <span className="text-sm font-medium" data-testid="llm-provider-name">
                        {llmStatus?.provider || 'Loading...'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500">Model</span>
                      <span className="text-sm font-medium font-mono" data-testid="llm-model-name">
                        {llmStatus?.model || 'Loading...'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500">Connection Health</span>
                      <div className="flex items-center gap-2">
                        <span
                          className={`w-2 h-2 rounded-full ${llmStatus?.health === 'connected' ? 'bg-green-500' : 'bg-red-500'
                            }`}
                          data-testid="llm-settings-health-dot"
                        />
                        <span className={`text-sm font-medium ${llmStatus?.health === 'connected' ? 'text-green-600' : 'text-red-600'
                          }`} data-testid="llm-health-status">
                          {llmStatus?.health === 'connected' ? 'Connected' : llmStatus?.health || 'Unknown'}
                        </span>
                      </div>
                    </div>
                    {llmStatus?.health_message && (
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-500">Details</span>
                        <span className="text-sm text-gray-600">{llmStatus.health_message}</span>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Cost Summary Card */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5" />
                  Cost Tracking
                </CardTitle>
                <CardDescription>AI operation costs and savings from local LLM usage</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="cost-summary">
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-gray-500 mb-1">Total Cost</p>
                    <p className="text-lg font-bold text-gray-900" data-testid="cost-total">
                      ${costSummary?.total_cost?.toFixed(4) || '0.0000'}
                    </p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-blue-600 mb-1">Cloud Cost</p>
                    <p className="text-lg font-bold text-blue-700" data-testid="cost-cloud">
                      ${costSummary?.cloud_cost?.toFixed(4) || '0.0000'}
                    </p>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-purple-600 mb-1">Local Cost</p>
                    <p className="text-lg font-bold text-purple-700" data-testid="cost-local">
                      $0.0000
                    </p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-green-600 mb-1">Estimated Savings</p>
                    <p className="text-lg font-bold text-green-700" data-testid="cost-savings">
                      ${costSummary?.estimated_savings?.toFixed(4) || '0.0000'}
                    </p>
                  </div>
                </div>

                {/* Provider breakdown */}
                {costSummary?.providers && costSummary.providers.length > 0 && (
                  <div className="mt-4" data-testid="cost-provider-breakdown">
                    <Label className="font-medium mb-2 block">Cost by Provider</Label>
                    <div className="space-y-2">
                      {costSummary.providers.map((p) => (
                        <div key={p.provider} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                          <div className="flex items-center gap-2">
                            {p.provider === 'ollama' || p.provider === 'local' ? (
                              <Cpu className="h-4 w-4 text-purple-500" />
                            ) : (
                              <Cloud className="h-4 w-4 text-blue-500" />
                            )}
                            <span className="text-sm font-medium capitalize">{p.provider}</span>
                          </div>
                          <div className="text-right">
                            <span className="text-sm font-mono">${p.total_cost.toFixed(4)}</span>
                            <span className="text-xs text-gray-500 ml-2">({p.total_operations} ops)</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Feature #213: LLM Mode Switch Confirmation Dialog */}
      <AlertDialog open={showLlmConfirmDialog} onOpenChange={setShowLlmConfirmDialog}>
        <AlertDialogContent data-testid="llm-switch-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Switch AI Provider?
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>
                You are about to switch from{' '}
                <strong>{llmStatus?.mode === 'local' ? 'Local LLM (Ollama)' : 'Cloud AI (Claude)'}</strong>
                {' '}to{' '}
                <strong>{pendingLlmMode === 'local' ? 'Local LLM (Ollama)' : 'Cloud AI (Claude)'}</strong>.
              </p>
              <p className="text-amber-600 font-medium">
                Warning: Switching mid-session may affect ongoing AI operations such as gap analyses,
                clause extractions, or AI chat sessions currently in progress.
              </p>
              <p>
                This change applies globally to all AI-powered services: clause extraction, gap analysis,
                task AI review, chat/copilot, regulatory analysis, and evidence validation.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleCancelLlmSwitch} data-testid="llm-switch-cancel">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmLlmSwitch}
              className={pendingLlmMode === 'local' ? 'bg-purple-600 hover:bg-purple-700' : 'bg-blue-600 hover:bg-blue-700'}
              data-testid="llm-switch-confirm"
            >
              {pendingLlmMode === 'local' ? (
                <>
                  <Cpu className="h-4 w-4 mr-2" />
                  Switch to Local LLM
                </>
              ) : (
                <>
                  <Cloud className="h-4 w-4 mr-2" />
                  Switch to Cloud AI
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
