/**
 * GettingStartedChecklist
 *
 * A progress checklist widget for the Dashboard that guides new users through
 * key actions. Supports both localStorage-tracked and data-detected completions.
 * Auto-dismisses after all steps are completed.
 */

import { useMemo, useEffect, useRef, useCallback } from "react";
import { X, Check, ChevronRight, Circle, CheckCircle2 } from "lucide-react";
import { cn } from "../../lib/utils";
import { GETTING_STARTED_ITEMS } from "../../lib/onboarding-content";
import { getCompletedSteps } from "../../lib/onboarding-state";

interface GettingStartedChecklistProps {
  /** Current user stats for auto-detecting completed steps */
  stats: {
    following: number;
    workstreams: number;
  };
  /** Called when user clicks on a step's action link */
  onStepClick?: (href: string) => void;
  /** Called when user dismisses the checklist */
  onDismiss: () => void;
  /** Additional className */
  className?: string;
}

export function GettingStartedChecklist({
  stats,
  onStepClick,
  onDismiss,
  className,
}: GettingStartedChecklistProps) {
  const autoDismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  // Compute which steps are completed
  const completedSet = useMemo(() => {
    const localSteps = new Set(getCompletedSteps());

    // Data-detected completions
    if (stats.following > 0) {
      localSteps.add("follow-opportunity");
    }
    if (stats.workstreams > 0) {
      localSteps.add("create-program");
    }

    return localSteps;
  }, [stats.following, stats.workstreams]);

  const completedCount = useMemo(
    () =>
      GETTING_STARTED_ITEMS.filter((item) => completedSet.has(item.id)).length,
    [completedSet],
  );

  const totalCount = GETTING_STARTED_ITEMS.length;
  const allComplete = completedCount === totalCount;
  const progressPercent =
    totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  // Auto-dismiss 5 seconds after all steps are complete
  const handleDismiss = useCallback(() => {
    if (autoDismissTimerRef.current) {
      clearTimeout(autoDismissTimerRef.current);
      autoDismissTimerRef.current = null;
    }
    onDismiss();
  }, [onDismiss]);

  useEffect(() => {
    if (allComplete) {
      autoDismissTimerRef.current = setTimeout(() => {
        onDismiss();
      }, 5000);
    }

    return () => {
      if (autoDismissTimerRef.current) {
        clearTimeout(autoDismissTimerRef.current);
      }
    };
  }, [allComplete, onDismiss]);

  return (
    <div
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden",
        className,
      )}
    >
      {/* Gradient accent strip */}
      <div className="bg-gradient-to-r from-brand-blue to-brand-green h-1 rounded-t-lg" />

      <div className="px-5 py-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
              Getting Started
            </h3>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {completedCount} of {totalCount} complete
            </span>
          </div>
          <button
            onClick={handleDismiss}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded transition-colors flex-shrink-0"
            aria-label="Dismiss getting started checklist"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden mb-4">
          <div
            className="h-full bg-brand-blue rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progressPercent}%` }}
            role="progressbar"
            aria-valuenow={completedCount}
            aria-valuemin={0}
            aria-valuemax={totalCount}
            aria-label={`${completedCount} of ${totalCount} steps complete`}
          />
        </div>

        {/* All complete celebration */}
        {allComplete ? (
          <div className="flex items-center gap-3 py-3">
            <div className="flex-shrink-0 motion-safe:animate-in motion-safe:zoom-in-0 motion-safe:duration-300">
              <CheckCircle2 className="h-8 w-8 text-brand-green" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                You're all set!
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                You know your way around GrantScope2.
              </p>
            </div>
          </div>
        ) : (
          /* Checklist items */
          <ul className="space-y-1">
            {GETTING_STARTED_ITEMS.map((item) => {
              const isComplete = completedSet.has(item.id);

              return (
                <li key={item.id}>
                  {isComplete ? (
                    <div className="flex items-center gap-3 py-2.5 px-2 rounded-lg">
                      <div className="flex-shrink-0 motion-safe:animate-in motion-safe:zoom-in-0 motion-safe:duration-200">
                        <div className="w-5 h-5 rounded-full bg-brand-green/15 dark:bg-brand-green/20 flex items-center justify-center">
                          <Check className="h-3 w-3 text-brand-green" />
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm text-gray-400 dark:text-gray-500 line-through">
                          {item.label}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => onStepClick?.(item.href)}
                      className={cn(
                        "w-full flex items-center gap-3 py-2.5 px-2 rounded-lg text-left",
                        "hover:bg-gray-50 dark:hover:bg-dark-surface-elevated",
                        "transition-colors duration-150",
                        "group",
                      )}
                    >
                      <div className="flex-shrink-0">
                        <Circle className="h-5 w-5 text-gray-300 dark:text-gray-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">
                          {item.label}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {item.description}
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-gray-400 group-hover:text-brand-blue transition-colors flex-shrink-0" />
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

export default GettingStartedChecklist;
