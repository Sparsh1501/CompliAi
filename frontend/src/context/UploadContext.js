import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getWebSocketUrl, uploadJobsApi } from '../lib/api';
import { useAuth } from './AuthContext';

const UploadContext = createContext();

export const useUpload = () => {
  const context = useContext(UploadContext);
  if (!context) {
    throw new Error('useUpload must be used within an UploadProvider');
  }
  return context;
};

export const UploadProvider = ({ children }) => {
  const { user } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [activeJobs, setActiveJobs] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);

  // Add a notification
  const addNotification = useCallback((notification) => {
    const id = Date.now();
    const newNotification = { ...notification, id, timestamp: new Date() };
    setNotifications(prev => [newNotification, ...prev].slice(0, 10)); // Keep last 10
    
    // Auto-dismiss success/info notifications after 5 seconds
    if (notification.type === 'success' || notification.type === 'info') {
      setTimeout(() => {
        dismissNotification(id);
      }, 5000);
    }
    
    return id;
  }, []);

  // Dismiss a notification
  const dismissNotification = useCallback((id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  // Clear all notifications
  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  // Handle WebSocket message
  const handleMessage = useCallback((event) => {
    try {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'job_created':
          setJobs(prev => [data.job, ...prev]);
          setActiveJobs(prev => [data.job, ...prev]);
          addNotification({
            type: 'info',
            title: 'Upload Started',
            message: `Processing ${data.job.file_name}...`,
            jobId: data.job.id
          });
          break;
          
        case 'job_progress':
          setJobs(prev => prev.map(j => j.id === data.job.id ? data.job : j));
          setActiveJobs(prev => prev.map(j => j.id === data.job.id ? data.job : j));
          break;
          
        case 'job_completed':
          setJobs(prev => prev.map(j => j.id === data.job.id ? data.job : j));
          setActiveJobs(prev => prev.filter(j => j.id !== data.job.id));
          addNotification({
            type: 'success',
            title: 'Upload Complete',
            message: `${data.job.file_name} processed successfully! ${data.job.clauses_extracted || 0} clauses extracted.`,
            jobId: data.job.id,
            resultId: data.job.result_id,
            jobType: data.job.job_type
          });
          break;
          
        case 'job_failed':
          setJobs(prev => prev.map(j => j.id === data.job.id ? data.job : j));
          setActiveJobs(prev => prev.filter(j => j.id !== data.job.id));
          addNotification({
            type: 'error',
            title: 'Upload Failed',
            message: data.job.error_message || `Failed to process ${data.job.file_name}`,
            jobId: data.job.id,
            persistent: true // Error notifications don't auto-dismiss
          });
          break;
          
        case 'job_cancelled':
          setJobs(prev => prev.map(j => j.id === data.job.id ? data.job : j));
          setActiveJobs(prev => prev.filter(j => j.id !== data.job.id));
          addNotification({
            type: 'info',
            title: 'Upload Cancelled',
            message: `Cancelled processing of ${data.job.file_name}`,
            jobId: data.job.id
          });
          break;
          
        case 'active_jobs':
        case 'initial_jobs':
          setActiveJobs(data.jobs || []);
          setJobs(prev => {
            const existingIds = new Set(prev.map(j => j.id));
            const newJobs = (data.jobs || []).filter(j => !existingIds.has(j.id));
            return [...newJobs, ...prev];
          });
          break;
          
        case 'pong':
          // Heartbeat response, connection is alive
          break;
          
        default:
          console.log('Unknown WebSocket message type:', data.type);
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }, [addNotification]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!user || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const token = localStorage.getItem('token');
    if (!token) {
      console.log('No token available for WebSocket connection');
      return;
    }

    try {
      const wsUrl = getWebSocketUrl();
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        
        // Start ping interval to keep connection alive
        pingIntervalRef.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000); // Ping every 30 seconds
      };

      wsRef.current.onmessage = handleMessage;

      wsRef.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);
        
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        // Attempt to reconnect after 5 seconds if not intentionally closed
        if (event.code !== 1000 && user) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('Attempting to reconnect...');
            connect();
          }, 5000);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }, [user, handleMessage]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'User logged out');
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  // Fetch jobs from API (fallback/initial load)
  const fetchJobs = useCallback(async () => {
    try {
      const allJobs = await uploadJobsApi.getAll(true, 50);
      setJobs(allJobs);
      setActiveJobs(allJobs.filter(j => 
        !['completed', 'failed', 'cancelled'].includes(j.status)
      ));
    } catch (error) {
      console.error('Error fetching upload jobs:', error);
    }
  }, []);

  // Cancel a job
  const cancelJob = useCallback(async (jobId) => {
    try {
      await uploadJobsApi.cancel(jobId);
      // WebSocket will update the state
    } catch (error) {
      console.error('Error cancelling job:', error);
      throw error;
    }
  }, []);

  // Delete a job from history
  const deleteJob = useCallback(async (jobId) => {
    try {
      await uploadJobsApi.delete(jobId);
      setJobs(prev => prev.filter(j => j.id !== jobId));
    } catch (error) {
      console.error('Error deleting job:', error);
      throw error;
    }
  }, []);

  // Clear completed jobs
  const clearCompletedJobs = useCallback(async () => {
    try {
      await uploadJobsApi.clearCompleted();
      setJobs(prev => prev.filter(j => 
        !['completed', 'failed', 'cancelled'].includes(j.status)
      ));
    } catch (error) {
      console.error('Error clearing completed jobs:', error);
      throw error;
    }
  }, []);

  // Connect when user logs in
  useEffect(() => {
    if (user) {
      connect();
      fetchJobs();
    } else {
      disconnect();
      setJobs([]);
      setActiveJobs([]);
      setNotifications([]);
    }

    return () => {
      disconnect();
    };
  }, [user, connect, disconnect, fetchJobs]);

  const value = {
    // State
    jobs,
    activeJobs,
    notifications,
    isConnected,
    showPanel,
    
    // Actions
    setShowPanel,
    cancelJob,
    deleteJob,
    clearCompletedJobs,
    fetchJobs,
    addNotification,
    dismissNotification,
    clearNotifications,
    
    // Computed
    hasActiveJobs: activeJobs.length > 0,
    activeJobCount: activeJobs.length,
  };

  return (
    <UploadContext.Provider value={value}>
      {children}
    </UploadContext.Provider>
  );
};

export default UploadContext;
