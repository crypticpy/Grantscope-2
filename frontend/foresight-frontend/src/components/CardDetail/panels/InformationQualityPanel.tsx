/**
 * InformationQualityPanel Component
 *
 * Full Source Quality Index (SQI) breakdown panel for the card detail page.
 * Fetches quality data on mount and displays the overall composite score
 * alongside five horizontal progress bars representing each component dimension.
 *
 * Visual design:
 * - Large QualityBadge at the top showing the tier
 * - "Last calculated" timestamp
 * - Five progress bars with labels, scores, and weight percentages
 * - Each bar is color-coded by score value (green/amber/red)
 * - Tooltips on each component label explain what it measures
 * - Link to the scoring methodology page at the bottom
 *
 * Follows the same panel styling conventions as ImpactMetricsPanel and
 * MaturityScorePanel (white card with shadow, rounded corners, consistent spacing).
 *
 * @module CardDetail/panels/InformationQualityPanel
 */

import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Info,
  RefreshCw,
  ExternalLink,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { Tooltip } from "../../ui/Tooltip";
import { QualityBadge } from "../../QualityBadge";
import { cn } from "../../../lib/utils";
import {
  getCardQuality,
  recalculateCardQuality,
  type CardQualityData,
} from "../../../lib/quality-api";

// =============================================================================
// Types
// =============================================================================

/**
 * Props for the InformationQualityPanel component.
 */
export interface InformationQualityPanelProps {
  /** UUID of the card whose quality data to display */
  cardId: string;

  /** Optional additional CSS class names for the outer container */
  className?: string;
}

// =============================================================================
// Component Configuration
// =============================================================================

/**
 * Metadata for each of the five SQI component dimensions.
 * The `key` must match the `name` field returned by the quality API.
 */
interface ComponentMeta {
  /** API component name */
  key: string;
  /** Human-readable label */
  label: string;
  /** Weight expressed as a percentage string */
  weight: string;
  /** Tooltip description explaining what this component measures */
  description: string;
  /** Hash anchor for deep-linking to the Methodology page section for this component */
  methodologyHash: string;
}

const COMPONENT_META: ComponentMeta[] = [
  {
    key: "source_authority",
    label: "Source Authority",
    weight: "30%",
    description:
      "How credible are the sources? Based on domain reputation tiers.",
    methodologyHash: "#source-authority",
  },
  {
    key: "source_diversity",
    label: "Source Diversity",
    weight: "20%",
    description:
      "How varied are the source types? Mix of news, academic, government, etc.",
    methodologyHash: "#source-diversity",
  },
  {
    key: "corroboration",
    label: "Corroboration",
    weight: "20%",
    description:
      "How many independent stories confirm this? Not duplicate coverage.",
    methodologyHash: "#corroboration",
  },
  {
    key: "recency",
    label: "Recency",
    weight: "15%",
    description: "How fresh are the sources? Recent sources score higher.",
    methodologyHash: "#recency",
  },
  {
    key: "municipal_specificity",
    label: "Municipal Specificity",
    weight: "15%",
    description:
      "How relevant to municipal government? Government sources score higher.",
    methodologyHash: "#municipal-specificity",
  },
];

// =============================================================================
// Helpers
// =============================================================================

/**
 * Return Tailwind color classes for a progress bar based on score value.
 *
 * @param score - Component score 0-100
 * @returns Object with `bar` (progress fill) and `track` (background) classes
 */
function getBarColors(score: number): { bar: string; track: string } {
  if (score >= 75) {
    return {
      bar: "bg-green-500 dark:bg-green-400",
      track: "bg-green-100 dark:bg-green-900",
    };
  }
  if (score >= 50) {
    return {
      bar: "bg-amber-500 dark:bg-amber-400",
      track: "bg-amber-100 dark:bg-amber-900",
    };
  }
  return {
    bar: "bg-red-500 dark:bg-red-400",
    track: "bg-red-100 dark:bg-red-900",
  };
}

/**
 * Format an ISO timestamp into a user-friendly relative or absolute string.
 *
 * @param iso - ISO 8601 timestamp string
 * @returns Formatted date string
 */
function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// =============================================================================
// Component
// =============================================================================

/**
 * InformationQualityPanel fetches and displays the SQI breakdown for a card.
 *
 * @example
 * ```tsx
 * <InformationQualityPanel cardId={card.id} />
 * ```
 *
 * @example
 * ```tsx
 * // With custom class
 * <InformationQualityPanel cardId={card.id} className="mt-6" />
 * ```
 */
export const InformationQualityPanel: React.FC<
  InformationQualityPanelProps
> = ({ cardId, className }) => {
  const [quality, setQuality] = useState<CardQualityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recalculating, setRecalculating] = useState(false);

  // ---------------------------------------------------------------------------
  // Data Fetching
  // ---------------------------------------------------------------------------

  const fetchQuality = useCallback(async () => {
    try {
      setError(null);
      const token = localStorage.getItem("gs2_token");
      if (!token) {
        setError("Not authenticated");
        setLoading(false);
        return;
      }
      const data = await getCardQuality(cardId, token);
      setQuality(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load quality data",
      );
    } finally {
      setLoading(false);
    }
  }, [cardId]);

  useEffect(() => {
    fetchQuality();
  }, [fetchQuality]);

  // ---------------------------------------------------------------------------
  // Recalculate Handler
  // ---------------------------------------------------------------------------

  const handleRecalculate = async () => {
    try {
      setRecalculating(true);
      setError(null);
      const token = localStorage.getItem("gs2_token");
      if (!token) {
        setError("Not authenticated");
        return;
      }
      const data = await recalculateCardQuality(cardId, token);
      setQuality(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to recalculate");
    } finally {
      setRecalculating(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render: Loading State
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div
        className={cn(
          "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6",
          className,
        )}
      >
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
            Loading quality data...
          </span>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Error State
  // ---------------------------------------------------------------------------

  if (error && !quality) {
    return (
      <div
        className={cn(
          "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6",
          className,
        )}
      >
        <div className="flex items-center justify-center py-8 text-red-500 dark:text-red-400">
          <AlertCircle className="h-5 w-5 mr-2" />
          <span className="text-sm">{error}</span>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Resolve component scores from API response
  // ---------------------------------------------------------------------------

  /**
   * Look up a component score from the API response by key name.
   * Falls back to 0 if the component is not found.
   */
  function getComponentScore(key: string): number {
    if (!quality) return 0;
    const component = quality.components.find((c) => c.name === key);
    return component ? component.score : 0;
  }

  // ---------------------------------------------------------------------------
  // Render: Main Panel
  // ---------------------------------------------------------------------------

  return (
    <div
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Information Quality
        </h3>
        <Tooltip
          content={
            <div className="space-y-1">
              <p className="font-medium">Source Quality Index (SQI)</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Composite score measuring the credibility and diversity of
                sources backing this card.
              </p>
              <Link
                to="/methodology#sqi"
                className="inline-block text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
              >
                Learn more &rarr;
              </Link>
            </div>
          }
          side="left"
        >
          <button
            type="button"
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Information quality explanation"
          >
            <Info className="h-4 w-4" />
          </button>
        </Tooltip>
      </div>

      {/* Overall Score + Badge */}
      <div className="flex items-center gap-3 mb-2">
        <QualityBadge
          score={quality?.overall_score ?? null}
          size="lg"
          showScore
          sourceCount={quality?.source_count}
        />
      </div>

      {/* Last Calculated + Recalculate */}
      <div className="flex items-center justify-between mb-6">
        {quality?.calculated_at && (
          <span className="text-xs text-gray-400 dark:text-gray-500">
            Last calculated: {formatTimestamp(quality.calculated_at)}
          </span>
        )}
        <Tooltip content="Recalculate quality score" side="top">
          <button
            type="button"
            onClick={handleRecalculate}
            disabled={recalculating}
            className={cn(
              "inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400",
              "hover:text-blue-800 dark:hover:text-blue-300 transition-colors",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
            aria-label="Recalculate quality score"
          >
            <RefreshCw
              className={cn("h-3 w-3", recalculating && "animate-spin")}
            />
            {recalculating ? "Recalculating..." : "Recalculate"}
          </button>
        </Tooltip>
      </div>

      {/* Component Bars */}
      <div className="space-y-4">
        {COMPONENT_META.map((meta) => {
          const score = getComponentScore(meta.key);
          const colors = getBarColors(score);

          return (
            <div key={meta.key}>
              {/* Label row */}
              <div className="flex items-center justify-between mb-1">
                <Tooltip
                  content={
                    <div className="max-w-[220px]">
                      <p className="font-medium mb-1">
                        {meta.label} ({meta.weight})
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mb-1.5">
                        {meta.description}
                      </p>
                      <Link
                        to={`/methodology${meta.methodologyHash}`}
                        className="inline-block text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
                      >
                        Learn more &rarr;
                      </Link>
                    </div>
                  }
                  side="left"
                >
                  <span className="text-sm text-gray-700 dark:text-gray-200 cursor-help border-b border-dotted border-gray-400 dark:border-gray-500">
                    {meta.label}
                  </span>
                </Tooltip>
                <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
                  {score}/100
                </span>
              </div>

              {/* Progress bar */}
              <div
                className={cn(
                  "w-full h-2 rounded-full overflow-hidden",
                  colors.track,
                )}
              >
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500 ease-out",
                    colors.bar,
                  )}
                  style={{ width: `${Math.min(Math.max(score, 0), 100)}%` }}
                  role="progressbar"
                  aria-valuenow={score}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${meta.label} score`}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Error banner (non-blocking, shown alongside stale data) */}
      {error && quality && (
        <div className="mt-4 p-2 rounded bg-red-50 dark:bg-red-900/20 text-xs text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Methodology link */}
      <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
        <Link
          to="/methodology#sqi"
          className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
        >
          <ExternalLink className="h-3 w-3" />
          How is this score calculated?
        </Link>
      </div>
    </div>
  );
};

export default InformationQualityPanel;
