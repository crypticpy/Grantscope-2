/**
 * LoadingButton Component
 *
 * A flexible button component with built-in loading state support.
 * Features:
 * - Spinner animation using Loader2 from lucide-react
 * - Customizable loading text
 * - Multiple variants (primary, secondary, danger)
 * - Multiple sizes (sm, md, lg)
 * - Support for asChild pattern via @radix-ui/react-slot
 * - Dark mode support
 * - Full accessibility with aria attributes
 *
 * @example Basic usage
 * ```tsx
 * <LoadingButton loading={isSubmitting} loadingText="Saving...">
 *   Save Changes
 * </LoadingButton>
 * ```
 *
 * @example With variants
 * ```tsx
 * <LoadingButton variant="danger" loading={isDeleting} loadingText="Deleting...">
 *   Delete Item
 * </LoadingButton>
 * ```
 *
 * @example With sizes
 * ```tsx
 * <LoadingButton size="lg" loading={loading}>
 *   Large Button
 * </LoadingButton>
 * ```
 *
 * @example As child (Slot pattern)
 * ```tsx
 * <LoadingButton asChild>
 *   <Link to="/dashboard">Go to Dashboard</Link>
 * </LoadingButton>
 * ```
 */

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

// ============================================================================
// Variants Configuration
// ============================================================================

const loadingButtonVariants = cva(
  // Base styles
  [
    'inline-flex items-center justify-center',
    'font-medium rounded-md',
    'transition-colors duration-200',
    'focus:outline-none focus:ring-2 focus:ring-offset-2',
    'disabled:opacity-50 disabled:cursor-not-allowed',
    'dark:focus:ring-offset-dark-surface',
  ],
  {
    variants: {
      variant: {
        primary: [
          'bg-brand-blue text-white',
          'hover:bg-brand-dark-blue',
          'focus:ring-brand-blue',
        ],
        secondary: [
          'bg-white text-gray-700 border border-gray-300',
          'hover:bg-gray-50',
          'focus:ring-brand-blue',
          'dark:bg-dark-surface-elevated dark:text-gray-300 dark:border-gray-600',
          'dark:hover:bg-dark-surface-hover',
        ],
        danger: [
          'bg-red-600 text-white',
          'hover:bg-red-700',
          'focus:ring-red-500',
          'dark:bg-red-700 dark:hover:bg-red-800',
        ],
      },
      size: {
        sm: 'px-3 py-1.5 text-sm',
        md: 'px-4 py-2 text-sm',
        lg: 'px-6 py-3 text-base',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

// ============================================================================
// Types
// ============================================================================

export interface LoadingButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof loadingButtonVariants> {
  /** Whether the button is in a loading state */
  loading?: boolean;
  /** Text to display while loading (optional, shows children if not provided) */
  loadingText?: string;
  /** Use Slot component for composition (asChild pattern) */
  asChild?: boolean;
}

// ============================================================================
// Component
// ============================================================================

/**
 * LoadingButton - A button component with built-in loading state
 *
 * Renders a button that shows a spinner and optional loading text when
 * in a loading state. Automatically disables the button during loading.
 */
export const LoadingButton = React.forwardRef<HTMLButtonElement, LoadingButtonProps>(
  (
    {
      className,
      variant,
      size,
      loading = false,
      loadingText,
      disabled,
      children,
      asChild = false,
      ...props
    },
    ref
  ) => {
    // Use Slot for asChild pattern, otherwise use button
    const Comp = asChild ? Slot : 'button';

    // Button is disabled when loading or explicitly disabled
    const isDisabled = disabled || loading;

    // Determine what content to show
    const buttonContent = loading ? (
      <>
        <Loader2
          className={cn(
            'animate-spin',
            size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4',
            (loadingText || children) && 'mr-2'
          )}
          aria-hidden="true"
        />
        {loadingText ?? children}
      </>
    ) : (
      children
    );

    return (
      <Comp
        ref={ref}
        className={cn(loadingButtonVariants({ variant, size }), className)}
        disabled={isDisabled}
        aria-disabled={isDisabled}
        aria-busy={loading}
        {...props}
      >
        {buttonContent}
      </Comp>
    );
  }
);

LoadingButton.displayName = 'LoadingButton';

// ============================================================================
// Exports
// ============================================================================

export { loadingButtonVariants };
export default LoadingButton;
