import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import {
  Shield, LayoutDashboard, FileText, Sparkles, ListTodo, LogOut,
  CheckCircle, Building2, Calendar as CalendarIcon, MessageCircle,
  Menu, X, ChevronLeft, ChevronRight, Search, Bell, User,
  BarChart3, Settings, CreditCard, ChevronDown, TrendingUp, CheckSquare,
  Cloud, Server, Landmark
} from 'lucide-react';
import { llmApi } from '../lib/api';
import { toast } from 'sonner';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Policies', href: '/policies', icon: FileText },
  { name: 'Regulations', href: '/regulations', icon: Shield },
  { name: 'Regulatory Updates', href: '/regulatory-updates', icon: TrendingUp },
  { name: 'NPCI Circulars', href: '/npci-circulars', icon: Landmark },
  { name: 'Gap Analysis', href: '/gap-analysis', icon: Sparkles },
  { name: 'Compliance', href: '/compliance-dashboard', icon: Shield },
  { name: 'Tasks', href: '/tasks', icon: ListTodo },
  { name: 'Evidence', href: '/evidence', icon: CheckCircle },
  { name: 'Audit', href: '/audit', icon: Building2 },
  { name: 'LOS/LMS', href: '/los-lms', icon: CreditCard },
  { name: 'Calendar', href: '/calendar', icon: CalendarIcon },
  { name: 'Checklists', href: '/checklists', icon: CheckSquare },
  { name: 'Chat', href: '/chat', icon: MessageCircle },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Notifications', href: '/notifications', icon: Bell },
  { name: 'Settings', href: '/settings', icon: Settings },
];

// Route name mapping for breadcrumbs
const routeNames = {
  'dashboard': 'Dashboard',
  'policies': 'Policies',
  'regulations': 'Regulations',
  'regulatory-updates': 'Regulatory Updates',
  'npci-circulars': 'NPCI Circulars',
  'gap-analysis': 'Gap Analysis',
  'tasks': 'Tasks',
  'evidence': 'Evidence',
  'audit': 'Audit',
  'los-lms': 'LOS/LMS',
  'calendar': 'Calendar',
  'chat': 'Chat',
  'checklists': 'Checklists',
  'analytics': 'Analytics',
  'notifications': 'Notifications',
  'settings': 'Settings',
  'departments': 'Departments',
};

function Breadcrumbs() {
  const location = useLocation();
  const pathSegments = location.pathname.split('/').filter(Boolean);

  if (pathSegments.length === 0) return null;

  const breadcrumbs = pathSegments.map((segment, index) => {
    const path = '/' + pathSegments.slice(0, index + 1).join('/');
    const isLast = index === pathSegments.length - 1;
    const name = routeNames[segment] || segment.replace(/-/g, ' ');

    // Capitalize if not in routeNames
    const displayName = routeNames[segment] ? name : name.charAt(0).toUpperCase() + name.slice(1);

    return { path, name: displayName, isLast };
  });

  return (
    <nav aria-label="Breadcrumb" data-testid="breadcrumb">
      <ol className="flex items-center gap-1.5 text-sm">
        <li>
          <Link
            to="/dashboard"
            className="text-gray-500 hover:text-gray-900 transition-colors"
            data-testid="breadcrumb-dashboard"
          >
            Dashboard
          </Link>
        </li>
        {breadcrumbs.map((crumb, index) => {
          // Skip "dashboard" since we already show it as root
          if (crumb.path === '/dashboard' && index === 0) return null;
          return (
            <li key={crumb.path} className="flex items-center gap-1.5">
              <span className="text-gray-400">/</span>
              {crumb.isLast ? (
                <span className="text-gray-900 font-medium" data-testid={`breadcrumb-current`}>
                  {crumb.name}
                </span>
              ) : (
                <Link
                  to={crumb.path}
                  className="text-gray-500 hover:text-gray-900 transition-colors"
                  data-testid={`breadcrumb-${crumb.name.toLowerCase().replace(/ /g, '-')}`}
                >
                  {crumb.name}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default function Layout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [llmStatus, setLlmStatus] = useState(null);
  const [llmDropdownOpen, setLlmDropdownOpen] = useState(false);
  const [llmSwitching, setLlmSwitching] = useState(false);
  const [ollamaReachable, setOllamaReachable] = useState(null); // null = unknown, true/false
  const profileRef = useRef(null);
  const notificationRef = useRef(null);
  const llmDropdownRef = useRef(null);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
      if (window.innerWidth >= 768) {
        setSidebarOpen(false);
      }
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Close mobile sidebar on navigation
  useEffect(() => {
    if (isMobile) {
      setSidebarOpen(false);
    }
  }, [location.pathname, isMobile]);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setProfileOpen(false);
      }
      if (notificationRef.current && !notificationRef.current.contains(event.target)) {
        setNotificationOpen(false);
      }
      if (llmDropdownRef.current && !llmDropdownRef.current.contains(event.target)) {
        setLlmDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch notifications and unread count
  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;

        const [notifResponse, countResponse] = await Promise.all([
          fetch('http://localhost:8000/api/notifications', {
            headers: { 'Authorization': `Bearer ${token}` }
          }),
          fetch('http://localhost:8000/api/notifications/unread-count', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
        ]);

        if (notifResponse.ok) {
          const data = await notifResponse.json();
          setNotifications(data.slice(0, 5)); // Show only recent 5
        }

        if (countResponse.ok) {
          const countData = await countResponse.json();
          setUnreadCount(countData.count || 0);
        }
      } catch (error) {
        console.error('Failed to fetch notifications:', error);
      }
    };

    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Feature #214: Fetch LLM status using settings endpoint, check Ollama reachability
  useEffect(() => {
    const fetchLlmStatus = async () => {
      try {
        const status = await llmApi.getSettingsMode();
        setLlmStatus(status);

        // Check if Ollama is reachable based on health info
        if (status.mode === 'local') {
          setOllamaReachable(status.health === 'connected');
        } else {
          // When in cloud mode, we check Ollama health separately via the health_message
          // If mode is cloud, ollama_url is null - we need to probe
          // We'll check on dropdown open instead for better UX
          // For now, mark as unknown
          if (ollamaReachable === null) {
            setOllamaReachable(null);
          }
        }
      } catch (error) {
        console.debug('LLM status not available:', error.message);
      }
    };

    fetchLlmStatus();
    const interval = setInterval(fetchLlmStatus, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Feature #214: Check Ollama reachability when dropdown opens
  useEffect(() => {
    if (!llmDropdownOpen) return;
    const checkOllama = async () => {
      try {
        // Quick probe - switch to local, check health, then switch back if needed
        const status = await llmApi.getStatus();
        // The status endpoint now includes Ollama reachability info
        // If we're in cloud mode, we don't get Ollama health directly
        // So we make a quick test request
        if (status.mode === 'local') {
          setOllamaReachable(status.health === 'connected');
        } else {
          // Try to check Ollama health indirectly
          try {
            const resp = await fetch('http://localhost:11434/api/tags', {
              method: 'GET',
              signal: AbortSignal.timeout(3000)
            });
            setOllamaReachable(resp.ok);
          } catch {
            setOllamaReachable(false);
          }
        }
      } catch {
        // Keep current state
      }
    };
    checkOllama();
  }, [llmDropdownOpen]);

  // Feature #214: Handle LLM mode switch from dropdown
  const handleLlmModeSwitch = async (newMode) => {
    if (llmSwitching || (llmStatus && llmStatus.mode === newMode)) {
      setLlmDropdownOpen(false);
      return;
    }
    setLlmSwitching(true);
    setLlmDropdownOpen(false);
    try {
      const result = await llmApi.setSettingsMode(newMode);
      setLlmStatus(prev => ({
        ...prev,
        mode: result.mode,
        provider: result.provider,
        model: result.model,
        services: result.services,
      }));
      const label = result.mode === 'local'
        ? `Local LLM - ${result.model || 'qwen2.5:32b-instruct-q4_K_M'}`
        : `Cloud AI - ${result.model || 'claude-sonnet-4'}`;
      toast.success(`Switched to ${label}`);
      // Refresh full status
      try {
        const freshStatus = await llmApi.getSettingsMode();
        setLlmStatus(freshStatus);
      } catch { }
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Failed to switch LLM mode');
    } finally {
      setLlmSwitching(false);
    }
  };

  const handleLogout = () => {
    setProfileOpen(false);
    logout();
    navigate('/login');
  };

  const sidebarWidth = sidebarCollapsed ? 'w-16' : 'w-64';

  // Get user initials for avatar
  const userInitials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  return (
    <div className="min-h-screen bg-gray-50" data-testid="layout">
      {/* Mobile overlay */}
      {isMobile && sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div className="flex">
        {/* Sidebar */}
        <aside
          className={`
            sidebar fixed left-0 top-0 h-screen z-50
            ${isMobile ? (sidebarOpen ? 'translate-x-0 w-64' : '-translate-x-full w-64') : sidebarWidth}
            transition-all duration-300 ease-in-out
          `}
          data-testid="sidebar"
          data-collapsed={sidebarCollapsed}
        >
          {/* Logo Section */}
          <div className="p-4 border-b border-gray-200 flex-shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-500/20 flex-shrink-0">
                  <Shield className="h-5 w-5 text-white" />
                </div>
                {(!sidebarCollapsed || isMobile) && (
                  <div className="transition-opacity duration-200">
                    <h2 className="text-lg font-bold text-emerald-800" data-testid="app-title">CompliAI</h2>
                    <p className="text-xs text-gray-500">{user?.organization || 'Compliance OS'}</p>
                  </div>
                )}
              </div>
              {isMobile && (
                <Button variant="ghost" size="sm" onClick={() => setSidebarOpen(false)} className="text-gray-500 hover:text-gray-700 hover:bg-gray-100">
                  <X className="h-5 w-5" />
                </Button>
              )}
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-3 space-y-1 overflow-y-auto" data-testid="navigation">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.href ||
                (item.href !== '/dashboard' && location.pathname.startsWith(item.href));
              return (
                <button
                  key={item.name}
                  onClick={() => navigate(item.href)}
                  data-testid={`nav-${item.name.toLowerCase().replace(/[/ ]/g, '-')}`}
                  title={sidebarCollapsed ? item.name : undefined}
                  className={`
                    nav-item w-full
                    ${isActive ? 'active' : ''}
                    ${sidebarCollapsed && !isMobile ? 'justify-center px-2' : ''}
                  `}
                >
                  <Icon className={`h-5 w-5 flex-shrink-0 ${isActive ? 'text-emerald-700' : ''}`} />
                  {(!sidebarCollapsed || isMobile) && (
                    <span className="truncate">{item.name}</span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* User Section */}
          <div className="p-3 border-t border-gray-200 flex-shrink-0" data-testid="user-section">
            {(!sidebarCollapsed || isMobile) && (
              <div className="mb-3 px-2">
                <div className="text-sm font-medium text-gray-900 truncate" data-testid="user-name">{user?.full_name}</div>
                <div className="text-xs text-gray-500 truncate" data-testid="user-org">{user?.organization}</div>
              </div>
            )}
            <Button
              variant="outline"
              className={`w-full btn-silver ${sidebarCollapsed && !isMobile ? 'px-2' : ''}`}
              onClick={handleLogout}
              data-testid="logout-button"
              title={sidebarCollapsed ? 'Logout' : undefined}
            >
              <LogOut className={`h-4 w-4 ${!sidebarCollapsed || isMobile ? 'mr-2' : ''}`} />
              {(!sidebarCollapsed || isMobile) && 'Logout'}
            </Button>
          </div>

          {/* Collapse Toggle (Desktop only) */}
          {!isMobile && (
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              data-testid="sidebar-collapse-button"
              className="absolute -right-3 top-20 w-6 h-6 bg-white border border-gray-200 rounded-full flex items-center justify-center shadow-sm hover:bg-gray-50 hover:border-gray-300 transition-colors text-gray-400 hover:text-gray-600"
            >
              {sidebarCollapsed ? (
                <ChevronRight className="h-3 w-3" />
              ) : (
                <ChevronLeft className="h-3 w-3" />
              )}
            </button>
          )}
        </aside>

        {/* Main Content */}
        <main className={`flex-1 min-h-screen transition-all duration-300 ${isMobile ? 'ml-0' : (sidebarCollapsed ? 'ml-16' : 'ml-64')}`} data-testid="main-area">
          {/* Top Header */}
          <div className="sticky top-0 bg-white/90 backdrop-blur-sm border-b border-gray-200 z-30" data-testid="top-bar">
            <div className="px-4 md:px-8 py-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {/* Mobile menu button */}
                {isMobile && (
                  <Button variant="ghost" size="sm" onClick={() => setSidebarOpen(true)} className="md:hidden text-gray-500 hover:text-gray-700 hover:bg-gray-100">
                    <Menu className="h-5 w-5" />
                  </Button>
                )}
                {/* Breadcrumbs */}
                <Breadcrumbs />
              </div>

              {/* Right side: Search, Notifications, Profile */}
              <div className="flex items-center gap-2 md:gap-4">
                {/* Search */}
                <div className="relative hidden md:block" data-testid="search-container">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-48 lg:w-64 pl-9 pr-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-colors"
                    data-testid="search-input"
                  />
                </div>
                {/* Mobile search icon */}
                <button
                  className="md:hidden p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                  data-testid="search-icon-mobile"
                >
                  <Search className="h-5 w-5" />
                </button>

                {/* Feature #214: LLM Model Selector Dropdown */}
                <div className="relative" ref={llmDropdownRef}>
                  <button
                    onClick={() => setLlmDropdownOpen(!llmDropdownOpen)}
                    className={`hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-all border ${llmSwitching ? 'opacity-60 pointer-events-none' : ''
                      } ${llmStatus?.mode === 'local'
                        ? 'bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100 hover:border-purple-300'
                        : 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100 hover:border-blue-300'
                      }`}
                    title={llmStatus ? `${llmStatus.mode === 'local' ? 'Local LLM' : 'Cloud AI'}: ${llmStatus.model}` : 'AI Provider'}
                    data-testid="llm-mode-badge"
                  >
                    {llmStatus?.mode === 'local' ? (
                      <Server className="h-3.5 w-3.5" />
                    ) : (
                      <Cloud className="h-3.5 w-3.5" />
                    )}
                    <span className="max-w-[120px] truncate">
                      {llmStatus
                        ? (llmStatus.mode === 'local'
                          ? (llmStatus.model || 'Local LLM')
                          : (llmStatus.model || 'Cloud AI'))
                        : 'AI Provider'}
                    </span>
                    <span
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${llmStatus?.health === 'connected' ? 'bg-green-500' : 'bg-red-500'
                        }`}
                      data-testid="llm-health-dot"
                    />
                    <ChevronDown className={`h-3 w-3 transition-transform ${llmDropdownOpen ? 'rotate-180' : ''}`} />
                  </button>

                  {/* LLM Selector Dropdown */}
                  {llmDropdownOpen && (
                    <div
                      className="absolute right-0 top-full mt-2 w-72 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden"
                      data-testid="llm-selector-dropdown"
                    >
                      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
                        <h3 className="text-sm font-semibold text-gray-900">AI Provider</h3>
                        <p className="text-xs text-gray-500 mt-0.5">Select which model to use for all AI operations</p>
                      </div>

                      <div className="py-1">
                        {/* Claude (Cloud) Option */}
                        <button
                          onClick={() => handleLlmModeSwitch('cloud')}
                          className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors flex items-start gap-3 ${llmStatus?.mode === 'cloud' ? 'bg-blue-50/60' : ''
                            }`}
                          data-testid="llm-option-cloud"
                        >
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${llmStatus?.mode === 'cloud' ? 'bg-blue-100' : 'bg-gray-100'
                            }`}>
                            <Cloud className={`h-4 w-4 ${llmStatus?.mode === 'cloud' ? 'text-blue-600' : 'text-gray-500'}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-gray-900">Claude Sonnet (Cloud)</span>
                              {llmStatus?.mode === 'cloud' && llmStatus?.health === 'connected' && (
                                <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" title="Connected" />
                              )}
                              {llmStatus?.mode === 'cloud' && llmStatus?.health !== 'connected' && (
                                <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" title="Disconnected" />
                              )}
                              {llmStatus?.mode !== 'cloud' && (
                                <span className="w-2 h-2 rounded-full bg-gray-300 flex-shrink-0" />
                              )}
                            </div>
                            <p className="text-xs text-gray-500 mt-0.5 font-mono truncate">
                              {llmStatus?.mode === 'cloud' ? llmStatus?.model : 'claude-sonnet-4-20250514'}
                            </p>
                            <p className="text-xs text-gray-400 mt-0.5">Anthropic API (paid per token)</p>
                          </div>
                          {llmStatus?.mode === 'cloud' && (
                            <span className="text-xs font-medium text-blue-600 bg-blue-100 px-2 py-0.5 rounded-full flex-shrink-0">Active</span>
                          )}
                        </button>

                        {/* Ollama (Local) Option */}
                        <button
                          onClick={() => {
                            if (ollamaReachable === false) return; // disabled
                            handleLlmModeSwitch('local');
                          }}
                          className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors flex items-start gap-3 ${llmStatus?.mode === 'local' ? 'bg-purple-50/60' : ''
                            } ${ollamaReachable === false && llmStatus?.mode !== 'local' ? 'opacity-50 cursor-not-allowed' : ''}`}
                          disabled={ollamaReachable === false && llmStatus?.mode !== 'local'}
                          title={ollamaReachable === false ? 'Ollama is not running. Start it with: ollama serve' : ''}
                          data-testid="llm-option-local"
                        >
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${llmStatus?.mode === 'local' ? 'bg-purple-100' : 'bg-gray-100'
                            }`}>
                            <Server className={`h-4 w-4 ${llmStatus?.mode === 'local' ? 'text-purple-600' : 'text-gray-500'}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-gray-900">Local LLM (Ollama)</span>
                              {llmStatus?.mode === 'local' && llmStatus?.health === 'connected' && (
                                <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" title="Connected" />
                              )}
                              {llmStatus?.mode === 'local' && llmStatus?.health !== 'connected' && (
                                <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" title="Disconnected" />
                              )}
                              {llmStatus?.mode !== 'local' && ollamaReachable === true && (
                                <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" title="Available" />
                              )}
                              {llmStatus?.mode !== 'local' && ollamaReachable === false && (
                                <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" title="Offline" />
                              )}
                              {llmStatus?.mode !== 'local' && ollamaReachable === null && (
                                <span className="w-2 h-2 rounded-full bg-gray-300 flex-shrink-0" title="Unknown" />
                              )}
                            </div>
                            <p className="text-xs text-gray-500 mt-0.5 font-mono truncate">
                              {llmStatus?.mode === 'local' ? llmStatus?.model : 'qwen2.5:32b-instruct-q4_K_M'}
                            </p>
                            {ollamaReachable === false && llmStatus?.mode !== 'local' ? (
                              <p className="text-xs text-red-500 mt-0.5">
                                Offline — Start with: <code className="bg-red-50 px-1 rounded">ollama serve</code>
                              </p>
                            ) : (
                              <p className="text-xs text-gray-400 mt-0.5">Free, runs locally (zero cost)</p>
                            )}
                          </div>
                          {llmStatus?.mode === 'local' && (
                            <span className="text-xs font-medium text-purple-600 bg-purple-100 px-2 py-0.5 rounded-full flex-shrink-0">Active</span>
                          )}
                        </button>
                      </div>

                      {/* Footer with link to settings */}
                      <div className="px-4 py-2.5 border-t border-gray-100 bg-gray-50">
                        <button
                          onClick={() => {
                            setLlmDropdownOpen(false);
                            navigate('/settings?tab=llm');
                          }}
                          className="w-full text-xs text-center text-emerald-600 hover:text-emerald-700 font-medium"
                          data-testid="llm-dropdown-settings-link"
                        >
                          Advanced AI Settings →
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Notification Bell */}
                <div className="relative" ref={notificationRef}>
                  <button
                    onClick={() => setNotificationOpen(!notificationOpen)}
                    className="relative p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                    data-testid="notification-bell"
                  >
                    <Bell className="h-5 w-5" />
                    {/* Notification badge with count */}
                    {unreadCount > 0 && (
                      <span className="absolute top-1 right-1 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1" data-testid="notification-badge">
                        {unreadCount > 9 ? '9+' : unreadCount}
                      </span>
                    )}
                  </button>

                  {/* Notification Dropdown Panel */}
                  {notificationOpen && (
                    <div
                      className="absolute right-0 top-full mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-[400px] flex flex-col"
                      data-testid="notification-panel"
                    >
                      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
                        {unreadCount > 0 && (
                          <span className="text-xs text-gray-500">{unreadCount} unread</span>
                        )}
                      </div>
                      <div className="overflow-y-auto flex-1">
                        {notifications.length === 0 ? (
                          <div className="px-4 py-8 text-center">
                            <Bell className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                            <p className="text-sm text-gray-500">No notifications</p>
                          </div>
                        ) : (
                          <div className="py-1">
                            {notifications.map((notification) => (
                              <button
                                key={notification._id}
                                onClick={async () => {
                                  // Mark as read
                                  const token = localStorage.getItem('token');
                                  try {
                                    await fetch(`http://localhost:8000/api/notifications/${notification._id}/read`, {
                                      method: 'POST',
                                      headers: { 'Authorization': `Bearer ${token}` }
                                    });
                                    setNotifications(prev => prev.map(n =>
                                      n._id === notification._id ? { ...n, read: true } : n
                                    ));
                                    setUnreadCount(prev => Math.max(0, prev - 1));
                                  } catch (error) {
                                    console.error('Failed to mark as read:', error);
                                  }
                                  setNotificationOpen(false);
                                  if (notification.link) {
                                    navigate(notification.link);
                                  }
                                }}
                                className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-b-0 ${!notification.read ? 'bg-blue-50/50' : ''
                                  }`}
                                data-testid={`notification-item-${notification._id}`}
                              >
                                <div className="flex items-start gap-3">
                                  {!notification.read && (
                                    <div className="w-2 h-2 bg-blue-500 rounded-full mt-1.5 flex-shrink-0"></div>
                                  )}
                                  <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-gray-900 truncate">
                                      {notification.title}
                                    </p>
                                    <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                                      {notification.message}
                                    </p>
                                    <p className="text-xs text-gray-400 mt-1">
                                      {new Date(notification.created_at).toLocaleDateString()}
                                    </p>
                                  </div>
                                </div>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="px-4 py-2 border-t border-gray-100">
                        <button
                          onClick={() => {
                            setNotificationOpen(false);
                            navigate('/notifications');
                          }}
                          className="w-full text-sm text-center text-emerald-600 hover:text-emerald-700 font-medium py-1"
                          data-testid="view-all-notifications"
                        >
                          View all notifications
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* User Profile */}
                <div className="relative" ref={profileRef}>
                  <button
                    onClick={() => setProfileOpen(!profileOpen)}
                    className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                    data-testid="user-profile-button"
                  >
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-white text-xs font-bold" data-testid="user-avatar">
                      {userInitials}
                    </div>
                    <ChevronDown className={`h-4 w-4 text-gray-400 hidden md:block transition-transform ${profileOpen ? 'rotate-180' : ''}`} />
                  </button>

                  {/* Profile Dropdown */}
                  {profileOpen && (
                    <div
                      className="absolute right-0 top-full mt-2 w-56 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50"
                      data-testid="profile-dropdown"
                    >
                      <div className="px-4 py-3 border-b border-gray-100">
                        <p className="text-sm font-medium text-gray-900 truncate" data-testid="dropdown-user-name">{user?.full_name}</p>
                        <p className="text-xs text-gray-500 truncate" data-testid="dropdown-user-email">{user?.email}</p>
                      </div>
                      <button
                        onClick={() => { setProfileOpen(false); navigate('/settings'); }}
                        className="w-full text-left px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-colors flex items-center gap-2"
                        data-testid="dropdown-settings"
                      >
                        <Settings className="h-4 w-4" />
                        Settings
                      </button>
                      <button
                        onClick={handleLogout}
                        className="w-full text-left px-4 py-2 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors flex items-center gap-2"
                        data-testid="dropdown-logout"
                      >
                        <LogOut className="h-4 w-4" />
                        Logout
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
          <div className="p-4 md:p-8" data-testid="main-content">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
