import React from 'react';
import { useUpload } from '../context/UploadContext';
import { X, CheckCircle, XCircle, AlertCircle, Loader2, Upload, ChevronUp, ChevronDown, Clock, FileText, Trash2 } from 'lucide-react';
import { cn } from '../lib/utils';

// Progress bar component
const ProgressBar = ({ progress, status }) => {
  const getColor = () => {
    switch (status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'cancelled':
        return 'bg-gray-500';
      default:
        return 'bg-blue-500';
    }
  };

  return (
    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
      <div
        className={cn("h-full transition-all duration-300 ease-out", getColor())}
        style={{ width: `${Math.min(100, Math.max(0, progress || 0))}%` }}
      />
    </div>
  );
};

// Status icon component
const StatusIcon = ({ status, className }) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className={cn("text-green-500", className)} />;
    case 'failed':
      return <XCircle className={cn("text-red-500", className)} />;
    case 'cancelled':
      return <AlertCircle className={cn("text-gray-500", className)} />;
    default:
      return <Loader2 className={cn("text-blue-500 animate-spin", className)} />;
  }
};

// Single job item component
const JobItem = ({ job, onCancel, compact = false }) => {
  const isActive = !['completed', 'failed', 'cancelled'].includes(job.status);
  
  return (
    <div className={cn(
      "bg-white border rounded-lg shadow-sm transition-all duration-200",
      compact ? "p-2" : "p-3"
    )}>
      <div className="flex items-start gap-2">
        <StatusIcon status={job.status} className={compact ? "h-4 w-4 mt-0.5" : "h-5 w-5 mt-0.5"} />
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <p className={cn(
              "font-medium truncate",
              compact ? "text-xs" : "text-sm"
            )}>
              {job.file_name}
            </p>
            
            {isActive && onCancel && (
              <button
                onClick={() => onCancel(job.id)}
                className="text-gray-400 hover:text-red-500 transition-colors"
                title="Cancel upload"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          
          {isActive && (
            <>
              <p className="text-xs text-gray-500 mt-1">
                {job.current_step || 'Processing...'}
              </p>
              <div className="mt-2">
                <ProgressBar progress={job.progress} status={job.status} />
              </div>
              <p className="text-xs text-gray-400 mt-1">
                {job.progress || 0}% complete
              </p>
            </>
          )}
          
          {job.status === 'completed' && (
            <p className="text-xs text-green-600 mt-1">
              {job.clauses_extracted ? `${job.clauses_extracted} clauses extracted` : 'Completed successfully'}
            </p>
          )}
          
          {job.status === 'failed' && (
            <p className="text-xs text-red-600 mt-1 line-clamp-2">
              {job.error_message || 'Processing failed'}
            </p>
          )}
          
          {job.status === 'cancelled' && (
            <p className="text-xs text-gray-500 mt-1">
              Cancelled
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

// Notification toast component
const NotificationToast = ({ notification, onDismiss }) => {
  const getIcon = () => {
    switch (notification.type) {
      case 'success':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'error':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'info':
        return <AlertCircle className="h-5 w-5 text-blue-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-gray-500" />;
    }
  };

  const getBorderColor = () => {
    switch (notification.type) {
      case 'success':
        return 'border-l-green-500';
      case 'error':
        return 'border-l-red-500';
      case 'info':
        return 'border-l-blue-500';
      default:
        return 'border-l-gray-500';
    }
  };

  return (
    <div className={cn(
      "bg-white border border-l-4 rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-right duration-300",
      getBorderColor()
    )}>
      <div className="flex items-start gap-3">
        {getIcon()}
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm text-gray-900">{notification.title}</p>
          <p className="text-sm text-gray-600 mt-1">{notification.message}</p>
        </div>
        <button
          onClick={() => onDismiss(notification.id)}
          className="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

// Main floating upload progress component
export const UploadProgressFloat = () => {
  const {
    activeJobs,
    notifications,
    showPanel,
    setShowPanel,
    cancelJob,
    dismissNotification,
    hasActiveJobs,
    activeJobCount
  } = useUpload();

  // Don't render anything if no active jobs and no notifications
  if (!hasActiveJobs && notifications.length === 0 && !showPanel) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
      {/* Notification toasts */}
      <div className="flex flex-col gap-2">
        {notifications.map(notification => (
          <NotificationToast
            key={notification.id}
            notification={notification}
            onDismiss={dismissNotification}
          />
        ))}
      </div>

      {/* Active uploads panel */}
      {hasActiveJobs && (
        <div className="bg-white border rounded-lg shadow-lg overflow-hidden w-80">
          {/* Header */}
          <div
            className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b cursor-pointer hover:bg-gray-100 transition-colors"
            onClick={() => setShowPanel(!showPanel)}
          >
            <div className="flex items-center gap-2">
              <Upload className="h-4 w-4 text-blue-500" />
              <span className="text-sm font-medium">
                {activeJobCount} upload{activeJobCount !== 1 ? 's' : ''} in progress
              </span>
            </div>
            {showPanel ? (
              <ChevronDown className="h-4 w-4 text-gray-500" />
            ) : (
              <ChevronUp className="h-4 w-4 text-gray-500" />
            )}
          </div>

          {/* Jobs list */}
          {showPanel && (
            <div className="max-h-80 overflow-y-auto p-2 space-y-2">
              {activeJobs.map(job => (
                <JobItem
                  key={job.id}
                  job={job}
                  onCancel={cancelJob}
                  compact
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Upload history panel component (for sidebar or dedicated page)
export const UploadHistoryPanel = ({ className }) => {
  const {
    jobs,
    cancelJob,
    deleteJob,
    clearCompletedJobs,
    fetchJobs,
    hasActiveJobs
  } = useUpload();

  const [filter, setFilter] = React.useState('all');

  const filteredJobs = React.useMemo(() => {
    if (filter === 'all') return jobs;
    if (filter === 'active') return jobs.filter(j => !['completed', 'failed', 'cancelled'].includes(j.status));
    if (filter === 'completed') return jobs.filter(j => j.status === 'completed');
    if (filter === 'failed') return jobs.filter(j => j.status === 'failed');
    return jobs;
  }, [jobs, filter]);

  const completedCount = jobs.filter(j => ['completed', 'failed', 'cancelled'].includes(j.status)).length;

  return (
    <div className={cn("bg-white rounded-lg border", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-gray-500" />
          <h3 className="font-medium">Upload History</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchJobs}
            className="text-sm text-gray-500 hover:text-gray-700"
            title="Refresh"
          >
            <Loader2 className="h-4 w-4" />
          </button>
          {completedCount > 0 && (
            <button
              onClick={clearCompletedJobs}
              className="text-xs text-gray-500 hover:text-red-500 flex items-center gap-1"
              title="Clear completed"
            >
              <Trash2 className="h-3 w-3" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-1 px-4 py-2 border-b bg-gray-50">
        {['all', 'active', 'completed', 'failed'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "px-2 py-1 text-xs rounded transition-colors capitalize",
              filter === f
                ? "bg-blue-500 text-white"
                : "text-gray-600 hover:bg-gray-200"
            )}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Jobs list */}
      <div className="max-h-96 overflow-y-auto p-2 space-y-2">
        {filteredJobs.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No uploads found</p>
          </div>
        ) : (
          filteredJobs.map(job => (
            <div key={job.id} className="relative group">
              <JobItem
                job={job}
                onCancel={cancelJob}
              />
              {['completed', 'failed', 'cancelled'].includes(job.status) && (
                <button
                  onClick={() => deleteJob(job.id)}
                  className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all"
                  title="Remove from history"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default UploadProgressFloat;
