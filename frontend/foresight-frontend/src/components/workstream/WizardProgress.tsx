/**
 * WizardProgress - Horizontal step indicator for the workstream wizard
 *
 * Shows completed, current, and future steps with connecting lines.
 * Uses brand-blue for active/completed states and gray for future.
 */

import { Check } from "lucide-react";
import { cn } from "../../lib/utils";

interface WizardProgressProps {
  currentStep: number;
  totalSteps: number;
}

const STEP_LABELS = ["Program", "Interests", "Readiness", "Search", "Launch"];

export function WizardProgress({
  currentStep,
  totalSteps,
}: WizardProgressProps) {
  return (
    <div className="px-6 py-5 border-b border-gray-200 dark:border-gray-700">
      {/* Step counter text */}
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-3 text-center">
        Step {currentStep} of {totalSteps}
      </p>

      {/* Step indicator */}
      <div className="flex items-center justify-between relative">
        {STEP_LABELS.map((label, index) => {
          const stepNumber = index + 1;
          const isCompleted = stepNumber < currentStep;
          const isCurrent = stepNumber === currentStep;
          const isFuture = stepNumber > currentStep;

          return (
            <div
              key={label}
              className="flex flex-col items-center relative z-10"
              style={{
                flex:
                  index === 0 || index === STEP_LABELS.length - 1
                    ? "0 0 auto"
                    : "1 1 0",
              }}
            >
              {/* Circle */}
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all duration-200",
                  isCompleted && "bg-brand-blue text-white",
                  isCurrent &&
                    "bg-brand-blue text-white ring-4 ring-brand-blue/20 dark:ring-brand-blue/30",
                  isFuture &&
                    "bg-gray-200 dark:bg-gray-600 text-gray-500 dark:text-gray-400 border-2 border-gray-300 dark:border-gray-500",
                )}
                aria-current={isCurrent ? "step" : undefined}
              >
                {isCompleted ? <Check className="h-4 w-4" /> : stepNumber}
              </div>

              {/* Pulse animation for current step */}
              {isCurrent && (
                <div className="absolute top-0 w-8 h-8 rounded-full bg-brand-blue/30 animate-ping" />
              )}

              {/* Label */}
              <span
                className={cn(
                  "mt-2 text-xs font-medium transition-colors",
                  isCompleted && "text-brand-blue dark:text-brand-light-blue",
                  isCurrent && "text-brand-blue dark:text-brand-light-blue",
                  isFuture && "text-gray-400 dark:text-gray-500",
                )}
              >
                {label}
              </span>
            </div>
          );
        })}

        {/* Connecting lines */}
        <div className="absolute top-4 left-4 right-4 h-0.5 -translate-y-1/2 flex z-0">
          {Array.from({ length: totalSteps - 1 }).map((_, index) => {
            const isCompleted = index + 1 < currentStep;
            return (
              <div
                key={index}
                className={cn(
                  "flex-1 transition-colors duration-200",
                  isCompleted
                    ? "bg-brand-blue"
                    : "bg-gray-200 dark:bg-gray-600",
                )}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
