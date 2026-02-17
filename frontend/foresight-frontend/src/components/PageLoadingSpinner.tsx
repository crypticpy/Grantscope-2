/**
 * PageLoadingSpinner Component
 *
 * Full-page loading spinner for use as Suspense fallback when lazy-loading routes.
 * Matches the existing app loading state styling with brand colors and dark mode support.
 */

import { cn } from "../lib/utils";

export interface PageLoadingSpinnerProps {
  /** Optional loading message to display below the spinner */
  message?: string;
  /** Additional className for the container */
  className?: string;
  /** Size of the spinner */
  size?: "sm" | "md" | "lg";
}

/**
 * Get spinner size classes based on size prop
 */
function getSpinnerSizeClasses(size: "sm" | "md" | "lg"): string {
  const sizeMap = {
    sm: "h-16 w-16",
    md: "h-24 w-24",
    lg: "h-32 w-32",
  };
  return sizeMap[size];
}

/**
 * PageLoadingSpinner - A full-page centered loading spinner
 *
 * Used as the fallback component for React.Suspense when lazy-loading route components.
 * Displays a spinning circle with brand colors that adapts to light/dark mode.
 *
 * @example
 * // Basic usage as Suspense fallback
 * <Suspense fallback={<PageLoadingSpinner />}>
 *   <LazyComponent />
 * </Suspense>
 *
 * @example
 * // With custom loading message
 * <Suspense fallback={<PageLoadingSpinner message="Loading dashboard..." />}>
 *   <LazyDashboard />
 * </Suspense>
 */
export function PageLoadingSpinner({
  message,
  className,
  size = "lg",
}: PageLoadingSpinnerProps) {
  return (
    <div
      className={cn(
        "min-h-screen flex flex-col items-center justify-center",
        "bg-brand-faded-white dark:bg-brand-dark-blue",
        "transition-colors",
        className,
      )}
      role="status"
      aria-label={message || "Loading"}
      aria-live="polite"
    >
      <div
        className={cn(
          "animate-spin rounded-full border-b-2 border-brand-blue",
          getSpinnerSizeClasses(size),
        )}
        aria-hidden="true"
      />
      {message && (
        <p className="mt-4 text-sm text-gray-600 dark:text-gray-400">
          {message}
        </p>
      )}
      {/* Screen reader text for accessibility */}
      <span className="sr-only">{message || "Loading page content..."}</span>
    </div>
  );
}

export default PageLoadingSpinner;
