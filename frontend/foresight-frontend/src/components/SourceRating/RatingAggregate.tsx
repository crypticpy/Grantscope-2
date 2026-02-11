/**
 * RatingAggregate Component
 *
 * Displays aggregate rating information for a source, including
 * the team average quality score, total rating count, and a
 * horizontal bar chart showing the distribution of relevance ratings.
 *
 * Features:
 * - Team average quality with star indicator
 * - Total rating count
 * - Relevance distribution bar chart with color-coded segments
 * - Empty state for sources with no ratings yet
 * - Dark mode support
 *
 * @module SourceRating/RatingAggregate
 */

import React from "react";
import { cn } from "../../lib/utils";
import type { SourceRatingAggregate } from "../../lib/source-rating-api";

/**
 * Props for the RatingAggregate component
 */
export interface RatingAggregateProps {
  /** Aggregate rating data to display */
  aggregate: SourceRatingAggregate;
  /** Optional additional CSS classes for the container */
  className?: string;
}

/**
 * Configuration for relevance distribution bar segments.
 */
interface RelevanceBarConfig {
  /** The relevance key as returned from the API */
  key: string;
  /** Display label */
  label: string;
  /** Tailwind background color class for the bar segment */
  colorClass: string;
}

/**
 * Ordered configuration for each relevance bar segment.
 */
const RELEVANCE_BAR_CONFIG: RelevanceBarConfig[] = [
  { key: "high", label: "High", colorClass: "bg-green-400 dark:bg-green-500" },
  {
    key: "medium",
    label: "Medium",
    colorClass: "bg-amber-400 dark:bg-amber-500",
  },
  { key: "low", label: "Low", colorClass: "bg-orange-400 dark:bg-orange-500" },
  {
    key: "not_relevant",
    label: "Not Relevant",
    colorClass: "bg-gray-400 dark:bg-gray-500",
  },
];

/**
 * RatingAggregate displays the team's collective rating data for a source.
 *
 * When there are ratings, it shows the average quality score, the total
 * number of ratings, and a stacked horizontal bar chart illustrating how
 * team members have categorized the source's relevance.
 *
 * When there are no ratings, it displays an encouraging empty state message.
 *
 * @example
 * ```tsx
 * <RatingAggregate aggregate={sourceRatingData} />
 * ```
 */
export const RatingAggregate: React.FC<RatingAggregateProps> = ({
  aggregate,
  className,
}) => {
  // Empty state
  if (aggregate.total_ratings === 0) {
    return (
      <div
        className={cn(
          "text-sm text-gray-500 dark:text-gray-400 italic py-2",
          className,
        )}
      >
        No ratings yet &mdash; be the first!
      </div>
    );
  }

  const { avg_quality, total_ratings, relevance_distribution } = aggregate;

  // Compute the total across all relevance categories for percentage calculation
  const relevanceTotal = RELEVANCE_BAR_CONFIG.reduce(
    (sum, config) => sum + (relevance_distribution[config.key] || 0),
    0,
  );

  return (
    <div className={cn("space-y-2", className)}>
      {/* Team average and count */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-amber-400 text-base" aria-hidden="true">
          {"\u2605"}
        </span>
        <span className="font-medium text-gray-700 dark:text-gray-200">
          Team: {avg_quality.toFixed(1)}/5
        </span>
        <span className="text-gray-400 dark:text-gray-500">
          ({total_ratings} rating{total_ratings !== 1 ? "s" : ""})
        </span>
      </div>

      {/* Relevance distribution bar chart */}
      {relevanceTotal > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Relevance distribution
          </div>

          {/* Stacked bar */}
          <div
            className="flex w-full h-2 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-700"
            role="img"
            aria-label={`Relevance distribution: ${RELEVANCE_BAR_CONFIG.map(
              (c) => `${c.label}: ${relevance_distribution[c.key] || 0}`,
            ).join(", ")}`}
          >
            {RELEVANCE_BAR_CONFIG.map((config) => {
              const count = relevance_distribution[config.key] || 0;
              if (count === 0) return null;
              const percentage = (count / relevanceTotal) * 100;

              return (
                <div
                  key={config.key}
                  className={cn(
                    "h-full transition-all duration-300",
                    config.colorClass,
                  )}
                  style={{ width: `${percentage}%` }}
                  title={`${config.label}: ${count} (${Math.round(percentage)}%)`}
                />
              );
            })}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-3 flex-wrap">
            {RELEVANCE_BAR_CONFIG.map((config) => {
              const count = relevance_distribution[config.key] || 0;
              if (count === 0) return null;

              return (
                <div key={config.key} className="flex items-center gap-1">
                  <span
                    className={cn(
                      "w-2 h-2 rounded-full inline-block",
                      config.colorClass,
                    )}
                    aria-hidden="true"
                  />
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {config.label}: {count}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default RatingAggregate;
