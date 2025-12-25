import React from 'react';
import { RefreshCw, AlertCircle, WifiOff } from 'lucide-react';

/**
 * Props for the ErrorBoundary component
 */
export interface ErrorBoundaryProps {
  /** Child components to render */
  children: React.ReactNode;
  /** Optional callback when retry button is clicked. Shows retry button when provided. */
  onRetry?: () => void;
  /** Optional fallback component to render on error */
  fallback?: React.ReactNode;
  /** Optional custom error message override */
  errorMessage?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: any;
  isRetrying: boolean;
}

/**
 * Serialize an error for display
 */
const serializeError = (error: any): string => {
  if (error instanceof Error) {
    return error.message + '\n' + error.stack;
  }
  return JSON.stringify(error, null, 2);
};

/**
 * Check if the error is a chunk/module load failure
 * These occur when lazy-loaded components fail to load (network issues, etc.)
 */
const isChunkLoadError = (error: any): boolean => {
  if (!error) return false;

  const errorMessage = error.message?.toLowerCase() || '';
  const errorName = error.name?.toLowerCase() || '';

  // Common chunk load error patterns
  return (
    errorMessage.includes('loading chunk') ||
    errorMessage.includes('loading css chunk') ||
    errorMessage.includes('failed to fetch dynamically imported module') ||
    errorMessage.includes('failed to load module script') ||
    errorName.includes('chunkloaderror') ||
    // Vite dynamic import errors
    errorMessage.includes('failed to fetch') && errorMessage.includes('.js') ||
    // Network errors during module loading
    (error.name === 'TypeError' && errorMessage.includes('failed to fetch'))
  );
};

/**
 * Get user-friendly error message based on error type
 */
const getUserFriendlyMessage = (error: any, customMessage?: string): { title: string; description: string } => {
  if (customMessage) {
    return {
      title: 'Something went wrong',
      description: customMessage,
    };
  }

  if (isChunkLoadError(error)) {
    return {
      title: 'Failed to load page',
      description: 'There was a network problem loading this page. Please check your connection and try again.',
    };
  }

  return {
    title: 'Something went wrong',
    description: 'An unexpected error occurred. Please try refreshing the page.',
  };
};

/**
 * ErrorBoundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree and displays
 * a fallback UI. Enhanced with retry functionality for handling lazy-loaded
 * component failures (chunk load errors).
 *
 * @example
 * // Basic usage
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 *
 * @example
 * // With retry functionality for lazy components
 * <ErrorBoundary onRetry={() => window.location.reload()}>
 *   <Suspense fallback={<Loading />}>
 *     <LazyComponent />
 *   </Suspense>
 * </ErrorBoundary>
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, isRetrying: false };
  }

  static getDerivedStateFromError(error: any): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error to console for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  /**
   * Handle retry button click
   * Resets error state and calls the onRetry callback
   */
  handleRetry = () => {
    const { onRetry } = this.props;

    this.setState({ isRetrying: true });

    // Reset the error state to allow re-render attempt
    this.setState({ hasError: false, error: null, isRetrying: false }, () => {
      onRetry?.();
    });
  };

  render() {
    const { children, onRetry, fallback, errorMessage } = this.props;
    const { hasError, error, isRetrying } = this.state;

    if (hasError) {
      // Use custom fallback if provided
      if (fallback) {
        return <>{fallback}</>;
      }

      const isChunkError = isChunkLoadError(error);
      const { title, description } = getUserFriendlyMessage(error, errorMessage);
      const Icon = isChunkError ? WifiOff : AlertCircle;

      return (
        <div className="p-6 border border-red-300 dark:border-red-700 rounded-lg bg-red-50 dark:bg-red-900/20">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 p-2 rounded-full bg-red-100 dark:bg-red-800/40">
              <Icon className="h-6 w-6 text-red-600 dark:text-red-400" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold text-red-700 dark:text-red-300">
                {title}
              </h2>
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                {description}
              </p>

              {/* Retry button - only shown when onRetry prop is provided */}
              {onRetry && (
                <button
                  onClick={this.handleRetry}
                  disabled={isRetrying}
                  className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-600 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 dark:focus:ring-offset-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <RefreshCw className={`h-4 w-4 ${isRetrying ? 'animate-spin' : ''}`} />
                  {isRetrying ? 'Retrying...' : 'Try Again'}
                </button>
              )}

              {/* Technical details - collapsed by default in production */}
              {process.env.NODE_ENV === 'development' && (
                <details className="mt-4">
                  <summary className="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                    Technical details
                  </summary>
                  <pre className="mt-2 p-3 text-xs text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded overflow-auto max-h-48">
                    {serializeError(error)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        </div>
      );
    }

    return children;
  }
}
