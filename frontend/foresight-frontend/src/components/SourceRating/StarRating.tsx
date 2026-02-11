/**
 * StarRating Component
 *
 * An interactive 1-5 star rating input with hover preview and
 * optimistic UI updates. Supports read-only mode for display contexts.
 *
 * Features:
 * - Filled/outline star rendering based on current value
 * - Hover preview: stars fill on hover before committing
 * - Click to set rating value
 * - Two sizes: 'sm' (16px) and 'md' (20px)
 * - Keyboard accessible (Enter/Space to select)
 * - Dark mode support
 *
 * @module SourceRating/StarRating
 */

import React, { useState, useCallback } from "react";
import { cn } from "../../lib/utils";

/**
 * Props for the StarRating component
 */
export interface StarRatingProps {
  /** Current rating value (1-5). Use 0 for unrated. */
  value: number;
  /** Callback fired when the user selects a rating */
  onChange: (value: number) => void;
  /** If true, disables interaction and shows current value only */
  readonly?: boolean;
  /** Size variant for the star icons */
  size?: "sm" | "md";
  /** Optional additional CSS classes for the container */
  className?: string;
}

/** Size classes for each size variant */
const sizeClasses = {
  sm: "w-4 h-4 text-base",
  md: "w-5 h-5 text-xl",
} as const;

/**
 * Renders a single star icon, either filled or outlined.
 *
 * @param filled - Whether the star should be rendered as filled
 * @param sizeClass - Tailwind size classes
 */
function StarIcon({
  filled,
  sizeClass,
}: {
  filled: boolean;
  sizeClass: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center select-none",
        sizeClass,
        filled ? "text-amber-400" : "text-gray-300 dark:text-gray-600",
      )}
      aria-hidden="true"
    >
      {filled ? "\u2605" : "\u2606"}
    </span>
  );
}

/**
 * StarRating displays an interactive row of 5 stars for quality rating.
 *
 * Stars fill on hover to preview the selection, and clicking commits
 * the value via the onChange callback. In read-only mode, interaction
 * is disabled and the component simply displays the current value.
 *
 * @example
 * ```tsx
 * <StarRating value={3} onChange={(v) => setRating(v)} />
 * <StarRating value={4} onChange={() => {}} readonly size="sm" />
 * ```
 */
export const StarRating: React.FC<StarRatingProps> = ({
  value,
  onChange,
  readonly = false,
  size = "md",
  className,
}) => {
  const [hoverValue, setHoverValue] = useState<number>(0);

  const handleMouseEnter = useCallback(
    (star: number) => {
      if (!readonly) {
        setHoverValue(star);
      }
    },
    [readonly],
  );

  const handleMouseLeave = useCallback(() => {
    setHoverValue(0);
  }, []);

  const handleClick = useCallback(
    (star: number) => {
      if (!readonly) {
        onChange(star);
      }
    },
    [readonly, onChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, star: number) => {
      if (!readonly && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        onChange(star);
      }
    },
    [readonly, onChange],
  );

  const displayValue = hoverValue || value;
  const sizeClass = sizeClasses[size];

  return (
    <div
      className={cn("inline-flex items-center gap-0.5", className)}
      onMouseLeave={handleMouseLeave}
      role="radiogroup"
      aria-label="Quality rating"
    >
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          className={cn(
            "p-0 border-0 bg-transparent transition-transform duration-100",
            !readonly &&
              "cursor-pointer hover:scale-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-1 rounded-sm",
            readonly && "cursor-default",
          )}
          onClick={() => handleClick(star)}
          onMouseEnter={() => handleMouseEnter(star)}
          onKeyDown={(e) => handleKeyDown(e, star)}
          disabled={readonly}
          role="radio"
          aria-checked={value === star}
          aria-label={`${star} star${star > 1 ? "s" : ""}`}
          tabIndex={readonly ? -1 : 0}
        >
          <StarIcon filled={star <= displayValue} sizeClass={sizeClass} />
        </button>
      ))}
    </div>
  );
};

export default StarRating;
