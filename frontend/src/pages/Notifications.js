import React, { useEffect, useState } from 'react';
import { notificationsApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { ScrollArea } from '../components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Bell, BellOff, Check, CheckCheck, AlertCircle, Info, AlertTriangle, Settings, Trash2, Mail, Clock } from 'lucide-react';
import { toast } from 'sonner';

export default function Notifications() {
  const [notifications, setNotifications] = useState([]);
  const [preferences, setPreferences] = useState(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [activeTab, setActiveTab] = useState('notifications');

  useEffect(() => { loadNotifications(); }, []);

  const loadNotifications = async () => {
    try {
      const [notifs, prefs, count] = await Promise.all([
        notificationsApi.getAll().catch(() => []),
        notificationsApi.getPreferences().catch(() => null),
        notificationsApi.getUnreadCount().catch(() => ({ count: 0 })),
      ]);
      setNotifications(Array.isArray(notifs) ? notifs : []);
      setPreferences(prefs);
      setUnreadCount(count?.count || 0);
    } catch (error) {
      toast.error('Failed to load notifications');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkRead = async (id) => {
    try {
      await notificationsApi.markRead(id);
      setNotifications(prev => prev.map(n => n.id === id || n._id === id ? { ...n, read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
      toast.success('Marked as read');
    } catch (error) {
      toast.error('Failed to mark as read');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
      toast.success('All notifications marked as read');
    } catch (error) {
      toast.error('Failed to mark all as read');
    }
  };

  const handleUpdatePreferences = async (key, value) => {
    try {
      const updated = { ...preferences, [key]: value };
      await notificationsApi.updatePreferences(updated);
      setPreferences(updated);
      toast.success('Preferences updated');
    } catch (error) {
      toast.error('Failed to update preferences');
    }
  };

  const getIcon = (type) => {
    switch (type) {
      case 'error': case 'critical': return <AlertCircle className="h-5 w-5 text-red-500" />;
      case 'warning': return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
      case 'success': return <Check className="h-5 w-5 text-green-500" />;
      default: return <Info className="h-5 w-5 text-blue-500" />;
    }
  };

  const filteredNotifications = notifications.filter(n => {
    if (filter === 'unread') return !n.read;
    if (filter === 'read') return n.read;
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="notifications-loading">
        <div className="text-muted-foreground">Loading notifications...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="notifications-page">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center shadow-lg">
            <Bell className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold" data-testid="notifications-title">Notifications</h1>
            <p className="text-muted-foreground">
              {unreadCount > 0 ? `${unreadCount} unread notification${unreadCount > 1 ? 's' : ''}` : 'All caught up!'}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {unreadCount > 0 && (
            <Button variant="outline" onClick={handleMarkAllRead} data-testid="mark-all-read-button">
              <CheckCheck className="mr-2 h-4 w-4" /> Mark All Read
            </Button>
          )}
          <Badge variant="secondary" data-testid="unread-count-badge">{unreadCount} unread</Badge>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="notifications" data-testid="notifications-tab">
            <Bell className="h-4 w-4 mr-2" /> Notifications
          </TabsTrigger>
          <TabsTrigger value="preferences" data-testid="preferences-tab">
            <Settings className="h-4 w-4 mr-2" /> Preferences
          </TabsTrigger>
        </TabsList>

        <TabsContent value="notifications" data-testid="notifications-list">
          <div className="flex gap-2 mb-4">
            <Button variant={filter === 'all' ? 'default' : 'outline'} size="sm" onClick={() => setFilter('all')} data-testid="filter-all">All</Button>
            <Button variant={filter === 'unread' ? 'default' : 'outline'} size="sm" onClick={() => setFilter('unread')} data-testid="filter-unread">Unread</Button>
            <Button variant={filter === 'read' ? 'default' : 'outline'} size="sm" onClick={() => setFilter('read')} data-testid="filter-read">Read</Button>
          </div>

          {filteredNotifications.length === 0 ? (
            <Card className="flex flex-col items-center justify-center h-64" data-testid="notifications-empty">
              <CardContent className="text-center py-8">
                <BellOff className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Notifications</h3>
                <p className="text-muted-foreground">
                  {filter === 'unread' ? 'No unread notifications' : 'No notifications yet'}
                </p>
              </CardContent>
            </Card>
          ) : (
            <ScrollArea className="h-[calc(100vh-22rem)]">
              <div className="space-y-2">
                {filteredNotifications.map((notification) => {
                  const nId = notification.id || notification._id;
                  return (
                    <Card
                      key={nId}
                      className={`transition-colors ${!notification.read ? 'border-l-4 border-l-blue-500 bg-blue-500/5' : ''}`}
                      data-testid={`notification-item-${nId}`}
                    >
                      <CardContent className="flex items-start gap-4 p-4">
                        <div className="mt-1">{getIcon(notification.type)}</div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm" data-testid={`notification-title-${nId}`}>
                              {notification.title}
                            </span>
                            {!notification.read && <Badge className="bg-blue-500 text-white text-xs">New</Badge>}
                          </div>
                          <p className="text-sm text-muted-foreground mt-1" data-testid={`notification-message-${nId}`}>
                            {notification.message}
                          </p>
                          <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                            {notification.category && <Badge variant="outline" className="text-xs">{notification.category}</Badge>}
                            <span>{notification.created_at ? new Date(notification.created_at).toLocaleString() : ''}</span>
                          </div>
                        </div>
                        {!notification.read && (
                          <Button variant="ghost" size="sm" onClick={() => handleMarkRead(nId)} data-testid={`mark-read-${nId}`}>
                            <Check className="h-4 w-4" />
                          </Button>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </ScrollArea>
          )}
        </TabsContent>

        <TabsContent value="preferences" data-testid="notification-preferences">
          <Card>
            <CardHeader><CardTitle>Notification Preferences</CardTitle></CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between" data-testid="pref-email">
                <div>
                  <Label className="font-medium">Email Notifications</Label>
                  <p className="text-sm text-muted-foreground">Receive notifications via email</p>
                </div>
                <Switch
                  checked={preferences?.email_enabled ?? true}
                  onCheckedChange={(v) => handleUpdatePreferences('email_enabled', v)}
                  data-testid="email-toggle"
                />
              </div>
              <div className="flex items-center justify-between" data-testid="pref-email-frequency">
                <div>
                  <Label className="font-medium flex items-center gap-2">
                    <Clock className="h-4 w-4" /> Email Digest Frequency
                  </Label>
                  <p className="text-sm text-muted-foreground">How often to receive email notification digests</p>
                </div>
                <Select
                  value={preferences?.email_frequency || 'daily'}
                  onValueChange={(v) => handleUpdatePreferences('email_frequency', v)}
                >
                  <SelectTrigger className="w-[160px]" data-testid="email-frequency-select">
                    <SelectValue placeholder="Select frequency" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="realtime" data-testid="freq-realtime">Real-time</SelectItem>
                    <SelectItem value="daily" data-testid="freq-daily">Daily</SelectItem>
                    <SelectItem value="weekly" data-testid="freq-weekly">Weekly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center justify-between" data-testid="pref-push">
                <div>
                  <Label className="font-medium">Push Notifications</Label>
                  <p className="text-sm text-muted-foreground">Browser push notifications</p>
                </div>
                <Switch
                  checked={preferences?.push_enabled ?? true}
                  onCheckedChange={(v) => handleUpdatePreferences('push_enabled', v)}
                  data-testid="push-toggle"
                />
              </div>
              <div className="flex items-center justify-between" data-testid="pref-compliance">
                <div>
                  <Label className="font-medium">Compliance Alerts</Label>
                  <p className="text-sm text-muted-foreground">Critical compliance deadline alerts</p>
                </div>
                <Switch
                  checked={preferences?.compliance_alerts ?? true}
                  onCheckedChange={(v) => handleUpdatePreferences('compliance_alerts', v)}
                  data-testid="compliance-alerts-toggle"
                />
              </div>
              <div className="flex items-center justify-between" data-testid="pref-gap">
                <div>
                  <Label className="font-medium">Gap Analysis Updates</Label>
                  <p className="text-sm text-muted-foreground">Notify when gap analyses complete</p>
                </div>
                <Switch
                  checked={preferences?.gap_analysis_updates ?? true}
                  onCheckedChange={(v) => handleUpdatePreferences('gap_analysis_updates', v)}
                  data-testid="gap-updates-toggle"
                />
              </div>
              <div className="flex items-center justify-between" data-testid="pref-task">
                <div>
                  <Label className="font-medium">Task Assignments</Label>
                  <p className="text-sm text-muted-foreground">Notify when tasks are assigned to you</p>
                </div>
                <Switch
                  checked={preferences?.task_assignments ?? true}
                  onCheckedChange={(v) => handleUpdatePreferences('task_assignments', v)}
                  data-testid="task-assignments-toggle"
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
