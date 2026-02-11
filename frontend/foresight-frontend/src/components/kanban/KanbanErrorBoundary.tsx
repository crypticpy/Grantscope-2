/**
 * KanbanErrorBoundary Component
 *
 * Error boundary to gracefully handle errors in the Kanban board.
 * Catches React rendering errors and displays a user-friendly fallback UI
 * instead of crashing the entire application.
 */

import React, { Component, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '../../lib/utils';

// =============================================================================
// Types
// =============================================================================

interface KanbanErrorBoundaryProps {
  /** Child components to render */
  children: ReactNode;
  /** Optional callback when an error occurs */
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  /** Optional custom fallback UI */
  fallback?: ReactNode;
}

interface KanbanErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

// =============================================================================
// Component
// =============================================================================

/**
 * Error boundary specifically for the Kanban board.
 *
 * Catches errors during rendering and displays a recovery UI
 * that allows users to retry without refreshing the page.
 */
export class KanbanErrorBoundary extends Component<
  KanbanErrorBoundaryProps,
  KanbanErrorBoundaryState
> {
  constructor(props: KanbanErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): KanbanErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log error for debugging
    console.error('KanbanBoard Error:', error, errorInfo);

    // Call optional error callback
    this.props.onError?.(error, errorInfo);
  }

  /**
   * Reset error state to allow retry
   */
  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default fallback UI
      return (
        <div
          className={cn(
            'flex flex-col items-center justify-center',
            'min-h-[400px] p-8',
            'bg-gray-50 dark:bg-dark-surface-deep',
            'rounded-xl border border-gray-200 dark:border-gray-800'
          )}
        >
          <div className="flex flex-col items-center text-center max-w-md">
            {/* Error Icon */}
            <div
              className={cn(
                'flex items-center justify-center',
                'w-16 h-16 mb-6 rounded-full',
                'bg-amber-100 dark:bg-amber-900/30'
              )}
            >
              <AlertTriangle className="w-8 h-8 text-amber-600 dark:text-amber-400" />
            </div>

            {/* Error Message */}
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Something went wrong
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              The Kanban board encountered an error. Your data is safe, and you
              can try again.
            </p>

            {/* Error Details (development only) */}
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <div
                className={cn(
                  'w-full mb-6 p-4 rounded-lg',
                  'bg-gray-100 dark:bg-dark-surface',
                  'border border-gray-200 dark:border-gray-700',
                  'text-left overflow-auto max-h-32'
                )}
              >
                <p className="text-xs font-mono text-red-600 dark:text-red-400">
                  {this.state.error.message}
                </p>
              </div>
            )}

            {/* Retry Button */}
            <button
              onClick={this.handleRetry}
              className={cn(
                'inline-flex items-center gap-2',
                'px-4 py-2 rounded-lg',
                'bg-brand-blue text-white',
                'hover:bg-brand-dark-blue',
                'transition-colors',
                'font-medium text-sm'
              )}
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default KanbanErrorBoundary;
