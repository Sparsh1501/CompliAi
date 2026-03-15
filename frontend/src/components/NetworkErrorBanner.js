import React, { useState, useEffect, useCallback } from 'react';
import { WifiOff, RefreshCw, X, AlertTriangle } from 'lucide-react';

export default function NetworkErrorBanner() {
  const [networkError, setNetworkError] = useState(null);
  const [serverError, setServerError] = useState(null);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    const handleNetworkError = (e) => {
      setNetworkError(e.detail.message);
    };

    const handleServerError = (e) => {
      setServerError(e.detail.message);
      // Auto-dismiss server errors after 8 seconds
      setTimeout(() => setServerError(null), 8000);
    };

    window.addEventListener('network-error', handleNetworkError);
    window.addEventListener('server-error', handleServerError);

    return () => {
      window.removeEventListener('network-error', handleNetworkError);
      window.removeEventListener('server-error', handleServerError);
    };
  }, []);

  const handleRetry = useCallback(async () => {
    setRetrying(true);
    try {
      // Try to reach the backend health endpoint
      const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
      const response = await fetch(`${backendUrl}/api/health`, { method: 'GET' });
      if (response.ok) {
        setNetworkError(null);
        // Reload the page to refresh data
        window.location.reload();
      }
    } catch (err) {
      // Still can't connect
      setNetworkError('Still unable to connect. Please check if the server is running.');
    } finally {
      setRetrying(false);
    }
  }, []);

  const dismissServerError = useCallback(() => {
    setServerError(null);
  }, []);

  if (!networkError && !serverError) return null;

  return (
    <>
      {/* Network Error Banner */}
      {networkError && (
        <div
          className="fixed top-0 left-0 right-0 z-[100] bg-[#F87171]/10 border-b border-[#F87171]/30 px-4 py-3"
          data-testid="network-error-banner"
          role="alert"
        >
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <WifiOff className="h-5 w-5 text-[#F87171] flex-shrink-0" />
              <p className="text-sm text-[#E6E6E9]" data-testid="network-error-message">
                {networkError}
              </p>
            </div>
            <button
              onClick={handleRetry}
              disabled={retrying}
              className="flex items-center gap-2 px-3 py-1.5 bg-[#80FFF9]/10 text-[#80FFF9] rounded-lg hover:bg-[#80FFF9]/20 transition-colors text-sm disabled:opacity-50 flex-shrink-0"
              data-testid="network-retry-button"
            >
              <RefreshCw className={`h-4 w-4 ${retrying ? 'animate-spin' : ''}`} />
              {retrying ? 'Retrying...' : 'Retry'}
            </button>
          </div>
        </div>
      )}

      {/* Server Error Banner */}
      {serverError && (
        <div
          className="fixed top-0 left-0 right-0 z-[99] bg-[#FBAD41]/10 border-b border-[#FBAD41]/30 px-4 py-3"
          data-testid="server-error-banner"
          role="alert"
          style={{ top: networkError ? '52px' : '0' }}
        >
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-[#FBAD41] flex-shrink-0" />
              <p className="text-sm text-[#E6E6E9]" data-testid="server-error-message">
                {serverError}
              </p>
            </div>
            <button
              onClick={dismissServerError}
              className="p-1 text-[#808089] hover:text-[#E6E6E9] transition-colors flex-shrink-0"
              data-testid="server-error-dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
