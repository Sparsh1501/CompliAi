import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/dashboard';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#111113] p-4" data-testid="error-boundary">
          <div className="w-full max-w-md text-center">
            <div className="w-16 h-16 rounded-full bg-[#F87171]/10 flex items-center justify-center mx-auto mb-6">
              <AlertTriangle className="h-8 w-8 text-[#F87171]" />
            </div>
            <h2 className="text-2xl font-bold text-[#E6E6E9] mb-2">Something went wrong</h2>
            <p className="text-[#808089] mb-6" data-testid="error-boundary-message">
              An unexpected error occurred. Don't worry, your data is safe. Please try again.
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleRetry}
                className="flex items-center gap-2 px-4 py-2 bg-[#80FFF9]/10 text-[#80FFF9] rounded-lg hover:bg-[#80FFF9]/20 transition-colors"
                data-testid="error-retry-button"
              >
                <RefreshCw className="h-4 w-4" />
                Try Again
              </button>
              <button
                onClick={this.handleGoHome}
                className="flex items-center gap-2 px-4 py-2 bg-[#2A2A2E] text-[#E6E6E9] rounded-lg hover:bg-[#3A3A3E] transition-colors"
                data-testid="error-home-button"
              >
                <Home className="h-4 w-4" />
                Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
