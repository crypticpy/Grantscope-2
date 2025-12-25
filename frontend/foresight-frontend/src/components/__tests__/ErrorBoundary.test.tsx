/**
 * ErrorBoundary Unit Tests
 *
 * Tests the ErrorBoundary component for:
 * - Rendering children when no error occurs
 * - Catching and displaying errors
 * - Retry functionality with onRetry callback
 * - Custom fallback component support
 * - Custom error message override
 * - Chunk load error detection and display
 * - Accessibility features
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary } from '../ErrorBoundary';

// ============================================================================
// Test Helpers
// ============================================================================

/**
 * Component that throws an error on render
 */
const ThrowingComponent = ({ error }: { error: Error }) => {
  throw error;
};

/**
 * Component that renders normally
 */
const WorkingComponent = () => <div>Hello World</div>;

/**
 * Suppress console.error during error boundary tests
 * Error boundaries intentionally log errors
 */
const originalError = console.error;
beforeEach(() => {
  console.error = vi.fn();
});

afterEach(() => {
  console.error = originalError;
});

// ============================================================================
// Tests
// ============================================================================

describe('ErrorBoundary', () => {
  describe('Normal Rendering', () => {
    it('renders children when no error occurs', () => {
      render(
        <ErrorBoundary>
          <WorkingComponent />
        </ErrorBoundary>
      );

      expect(screen.getByText('Hello World')).toBeInTheDocument();
    });

    it('renders multiple children', () => {
      render(
        <ErrorBoundary>
          <div>Child 1</div>
          <div>Child 2</div>
        </ErrorBoundary>
      );

      expect(screen.getByText('Child 1')).toBeInTheDocument();
      expect(screen.getByText('Child 2')).toBeInTheDocument();
    });

    it('renders nested components', () => {
      render(
        <ErrorBoundary>
          <div>
            <span>Nested content</span>
          </div>
        </ErrorBoundary>
      );

      expect(screen.getByText('Nested content')).toBeInTheDocument();
    });
  });

  describe('Error Catching', () => {
    it('catches errors and displays fallback UI', () => {
      const error = new Error('Test error');

      render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('displays generic error description for regular errors', () => {
      const error = new Error('Test error');

      render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(
        screen.getByText('An unexpected error occurred. Please try refreshing the page.')
      ).toBeInTheDocument();
    });

    it('logs error to console', () => {
      const error = new Error('Logged error');

      render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(console.error).toHaveBeenCalled();
    });
  });

  describe('Chunk Load Error Detection', () => {
    it('detects "loading chunk" error message', () => {
      const error = new Error('Error: Loading chunk 123 failed');

      render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText('Failed to load page')).toBeInTheDocument();
      expect(
        screen.getByText('There was a network problem loading this page. Please check your connection and try again.')
      ).toBeInTheDocument();
    });

    it('detects "failed to fetch dynamically imported module" error', () => {
      const error = new Error('Failed to fetch dynamically imported module: /src/pages/Dashboard.tsx');

      render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText('Failed to load page')).toBeInTheDocument();
    });

    it('detects TypeError with "failed to fetch"', () => {
      const error = new TypeError('Failed to fetch');

      render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText('Failed to load page')).toBeInTheDocument();
    });
  });

  describe('Retry Functionality', () => {
    it('does not show retry button by default', () => {
      const error = new Error('Test error');

      render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.queryByRole('button', { name: /try again/i })).not.toBeInTheDocument();
    });

    it('shows retry button when onRetry is provided', () => {
      const error = new Error('Test error');
      const onRetry = vi.fn();

      render(
        <ErrorBoundary onRetry={onRetry}>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    });

    it('calls onRetry callback when retry button is clicked', () => {
      const error = new Error('Test error');
      const onRetry = vi.fn();

      render(
        <ErrorBoundary onRetry={onRetry}>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      fireEvent.click(screen.getByRole('button', { name: /try again/i }));

      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('resets error state when retry button is clicked', () => {
      // Test that clicking retry:
      // 1. Calls the onRetry callback
      // 2. Resets the error boundary state (allowing children to re-render)

      // Use a flag to control whether the component throws
      let throwError = true;

      const ConditionallyThrowingComponent = () => {
        if (throwError) {
          throw new Error('Test error');
        }
        return <div>Recovery successful</div>;
      };

      const onRetry = vi.fn();

      render(
        <ErrorBoundary onRetry={onRetry}>
          <ConditionallyThrowingComponent />
        </ErrorBoundary>
      );

      // Verify error state is shown
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
      expect(screen.queryByText('Recovery successful')).not.toBeInTheDocument();

      // Set throwError to false BEFORE clicking retry
      // This simulates a scenario where the error condition has been resolved
      throwError = false;

      // Click retry - this resets the error state and triggers re-render
      fireEvent.click(screen.getByRole('button', { name: /try again/i }));

      // Verify onRetry was called
      expect(onRetry).toHaveBeenCalledTimes(1);

      // After retry, the component should re-render successfully
      expect(screen.getByText('Recovery successful')).toBeInTheDocument();
      expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    });
  });

  describe('Custom Fallback', () => {
    it('renders custom fallback when provided', () => {
      const error = new Error('Test error');
      const customFallback = <div>Custom error UI</div>;

      render(
        <ErrorBoundary fallback={customFallback}>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText('Custom error UI')).toBeInTheDocument();
      expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    });

    it('renders custom fallback component', () => {
      const error = new Error('Test error');
      const CustomFallbackComponent = () => (
        <div>
          <h1>Oops!</h1>
          <p>Something broke</p>
        </div>
      );

      render(
        <ErrorBoundary fallback={<CustomFallbackComponent />}>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText('Oops!')).toBeInTheDocument();
      expect(screen.getByText('Something broke')).toBeInTheDocument();
    });
  });

  describe('Custom Error Message', () => {
    it('uses custom error message when provided', () => {
      const error = new Error('Test error');
      const customMessage = 'Please contact support for assistance.';

      render(
        <ErrorBoundary errorMessage={customMessage}>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText(customMessage)).toBeInTheDocument();
    });

    it('shows "Something went wrong" title with custom message', () => {
      const error = new Error('Test error');

      render(
        <ErrorBoundary errorMessage="Custom description here">
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });
  });

  describe('Error Display Styling', () => {
    it('renders error container with proper styling', () => {
      const error = new Error('Test error');

      const { container } = render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      const errorContainer = container.querySelector('.rounded-lg');
      expect(errorContainer).toBeInTheDocument();
      expect(errorContainer).toHaveClass('bg-red-50');
    });

    it('has dark mode styling classes', () => {
      const error = new Error('Test error');

      const { container } = render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      const errorContainer = container.querySelector('.border-red-300');
      expect(errorContainer).toHaveClass('dark:border-red-700');
    });
  });

  describe('Icon Display', () => {
    it('shows AlertCircle icon for regular errors', () => {
      const error = new Error('Regular error');

      const { container } = render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      // AlertCircle icon should be rendered in the icon container
      const iconContainer = container.querySelector('.rounded-full');
      expect(iconContainer).toBeInTheDocument();
    });

    it('shows WifiOff icon for chunk load errors', () => {
      const error = new Error('Loading chunk 123 failed');

      const { container } = render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      // WifiOff icon should be rendered for network errors
      const iconContainer = container.querySelector('.rounded-full');
      expect(iconContainer).toBeInTheDocument();
    });
  });

  describe('Props Combinations', () => {
    it('works with onRetry and custom message together', () => {
      const error = new Error('Test error');
      const onRetry = vi.fn();
      const customMessage = 'Network issue detected.';

      render(
        <ErrorBoundary onRetry={onRetry} errorMessage={customMessage}>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText(customMessage)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /try again/i }));
      expect(onRetry).toHaveBeenCalled();
    });

    it('custom fallback takes precedence over errorMessage', () => {
      const error = new Error('Test error');
      const customFallback = <div>Custom fallback</div>;

      render(
        <ErrorBoundary fallback={customFallback} errorMessage="This should not show">
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      expect(screen.getByText('Custom fallback')).toBeInTheDocument();
      expect(screen.queryByText('This should not show')).not.toBeInTheDocument();
    });
  });

  describe('Error Serialization', () => {
    it('handles Error objects', () => {
      const error = new Error('Test error message');

      render(
        <ErrorBoundary>
          <ThrowingComponent error={error} />
        </ErrorBoundary>
      );

      // The error is caught and displayed
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('handles non-Error objects gracefully', () => {
      // Create a custom error object
      const customError = { custom: 'error', code: 500 };
      const ThrowCustomError = () => {
        throw customError;
      };

      render(
        <ErrorBoundary>
          <ThrowCustomError />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('handles string errors', () => {
      const ThrowStringError = () => {
        throw 'String error message';
      };

      render(
        <ErrorBoundary>
          <ThrowStringError />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });
  });
});
