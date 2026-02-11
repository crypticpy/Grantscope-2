/**
 * RelevanceSelector Component
 *
 * A segmented pill-style control for selecting a relevance level.
 * Each option has a distinct color to provide at-a-glance visual
 * feedback about the selected relevance tier.
 *
 * Features:
 * - 4 relevance options: High, Medium, Low, Not Relevant
 * - Color-coded backgrounds when selected (green, amber, orange, gray)
 * - Keyboard accessible
 * - Read-only mode for display contexts
 * - Dark mode support
 *
 * @module SourceRating/RelevanceSelector
 */

import React, { useCallback } from "react";
import { cn } from "../../lib/utils";

/**
 * Props for the RelevanceSelector component
 */
export interface RelevanceSelectorProps {
  /** Current selected relevance value */
  value: string;
  /** Callback fired when the user selects a relevance level */
  onChange: (value: string) => void;
  /** If true, disables interaction and shows current value only */
  readonly?: boolean;
  /** Optional additional CSS classes for the container */
  className?: string;
}

/**
 * Configuration for a single relevance option, including its
 * display label and color classes for the selected state.
 */
interface RelevanceOption {
  /** Internal value sent to the API */
  value: string;
  /** Display label shown in the UI */
  label: string;
  /** Tailwind classes applied when this option is selected */
  selectedClasses: string;
}

/**
 * Available relevance options with their visual styling.
 * Colors are chosen for clear visual hierarchy and WCAG AA compliance.
 */
const RELEVANCE_OPTIONS: RelevanceOption[] = [
  {
    value: "high",
    label: "High",
    selectedClasses:
      "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/40 dark:text-green-300 dark:border-green-700",
  },
  {
    value: "medium",
    label: "Medium",
    selectedClasses:
      "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/40 dark:text-amber-300 dark:border-amber-700",
  },
  {
    value: "low",
    label: "Low",
    selectedClasses:
      "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900/40 dark:text-orange-300 dark:border-orange-700",
  },
  {
    value: "not_relevant",
    label: "Not Relevant",
    selectedClasses:
      "bg-gray-200 text-gray-700 border-gray-400 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-500",
  },
];

/**
 * RelevanceSelector displays a row of pill-style buttons for selecting
 * a relevance level. The selected option receives a color-coded background
 * while unselected options appear in a neutral style.
 *
 * @example
 * ```tsx
 * <RelevanceSelector
 *   value="high"
 *   onChange={(val) => setRelevance(val)}
 * />
 * <RelevanceSelector value="low" onChange={() => {}} readonly />
 * ```
 */
export const RelevanceSelector: React.FC<RelevanceSelectorProps> = ({
  value,
  onChange,
  readonly = false,
  className,
}) => {
  const handleSelect = useCallback(
    (optionValue: string) => {
      if (!readonly) {
        onChange(optionValue);
      }
    },
    [readonly, onChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, optionValue: string) => {
      if (!readonly && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        onChange(optionValue);
      }
    },
    [readonly, onChange],
  );

  return (
    <div
      className={cn("inline-flex items-center gap-1 flex-wrap", className)}
      role="radiogroup"
      aria-label="Relevance rating"
    >
      {RELEVANCE_OPTIONS.map((option) => {
        const isSelected = value === option.value;

        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isSelected}
            aria-label={`${option.label} relevance`}
            tabIndex={readonly ? -1 : 0}
            disabled={readonly}
            onClick={() => handleSelect(option.value)}
            onKeyDown={(e) => handleKeyDown(e, option.value)}
            className={cn(
              "px-2.5 py-1 rounded-full text-xs font-medium border transition-all duration-200",
              isSelected
                ? option.selectedClasses
                : "bg-white text-gray-500 border-gray-200 dark:bg-dark-surface dark:text-gray-400 dark:border-gray-600",
              !readonly &&
                !isSelected &&
                "hover:bg-gray-50 hover:border-gray-300 dark:hover:bg-gray-700 dark:hover:border-gray-500",
              !readonly &&
                "cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-1",
              readonly && "cursor-default opacity-90",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
};

export default RelevanceSelector;
