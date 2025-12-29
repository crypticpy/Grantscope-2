import React from 'react';
import { CheckCircle, XCircle, Clock, Undo2, X } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { UNDO_TIMEOUT_MS, type UndoAction } from '../types';

/**
 * Get human-readable action description for toast
 */
function getActionDescription(action: UndoAction): { verb: string; icon: React.ReactNode } {
  switch (action.type) {
    case 'approve':
      return { verb: 'approved', icon: <CheckCircle className="h-4 w-4 text-green-500" /> };
    case 'reject':
      return { verb: 'rejected', icon: <XCircle className="h-4 w-4 text-red-500" /> };
    case 'dismiss':
      return { verb: 'dismissed', icon: <XCircle className="h-4 w-4 text-gray-500" /> };
    case 'defer':
      return { verb: 'deferred', icon: <Clock className="h-4 w-4 text-amber-500" /> };
  }
}

/**
 * Props for UndoToast component
 */
export interface UndoToastProps {
  /** The action that can be undone */
  action: UndoAction;
  /** Callback when user clicks undo */
  onUndo: () => void;
  /** Callback when user dismisses the toast */
  onDismiss: () => void;
  /** Time remaining in ms until auto-dismiss */
  timeRemaining: number;
}

/**
 * UndoToast Component
 * Displays a toast notification with an undo button after actions
 * Auto-dismisses after UNDO_TIMEOUT_MS with a visual countdown
 *
 * Memoization:
 * - Wrapped with React.memo to prevent unnecessary re-renders
 * - onUndo and onDismiss callbacks should be memoized at call site (via useCallback)
 * - timeRemaining will change frequently, but other props remain stable
 */
export const UndoToast = React.memo(function UndoToast({
  action,
  onUndo,
  onDismiss,
  timeRemaining,
}: UndoToastProps) {
  const { verb, icon } = getActionDescription(action);
  const progressPercent = Math.max(0, (timeRemaining / UNDO_TIMEOUT_MS) * 100);

  // Truncate card name based on screen size (shorter on mobile)
  const maxLength = typeof window !== 'undefined' && window.innerWidth < 640 ? 20 : 40;
  const cardName = action.card.name.length > maxLength
    ? `${action.card.name.substring(0, maxLength - 3)}...`
    : action.card.name;

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        'fixed bottom-4 sm:bottom-6 left-3 right-3 sm:left-1/2 sm:right-auto sm:-translate-x-1/2 z-50',
        'flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg shadow-lg',
        'bg-white dark:bg-[#3d4176] border border-gray-200 dark:border-gray-600',
        'animate-in slide-in-from-bottom-4 fade-in duration-200'
      )}
    >
      {/* Icon */}
      {icon}

      {/* Message */}
      <span className="text-xs sm:text-sm text-gray-700 dark:text-gray-200 flex-1 min-w-0 truncate">
        <span className="font-medium">&quot;{cardName}&quot;</span> {verb}
      </span>

      {/* Undo Button - min 44px touch target */}
      <button
        onClick={onUndo}
        className={cn(
          'inline-flex items-center justify-center gap-1 sm:gap-1.5 px-3 sm:px-3 py-2.5 sm:py-1.5',
          'min-h-[44px] min-w-[44px]',
          'text-xs sm:text-sm font-medium rounded-md transition-colors flex-shrink-0',
          'bg-brand-blue/10 text-brand-blue hover:bg-brand-blue/20',
          'dark:bg-brand-blue/20 dark:hover:bg-brand-blue/30',
          'active:scale-95'
        )}
      >
        <Undo2 className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
        Undo
      </button>

      {/* Close Button - min 44px touch target */}
      <button
        onClick={onDismiss}
        className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors flex-shrink-0 active:scale-95"
        aria-label="Dismiss notification"
      >
        <X className="h-5 w-5" />
      </button>

      {/* Progress bar showing time remaining */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200 dark:bg-gray-600 rounded-b-lg overflow-hidden">
        <div
          className="h-full bg-brand-blue transition-all duration-100 ease-linear"
          style={{ width: `${progressPercent}%` }}
        />
      </div>
    </div>
  );
});

export default UndoToast;
