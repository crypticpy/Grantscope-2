/**
 * QualityBadge Component
 *
 * A reusable traffic-light badge that displays the Source Quality Index (SQI)
 * tier for a card. Uses a green/amber/red/gray color scheme to communicate
 * confidence level at a glance, consistent with the badge patterns used
 * throughout the Foresight app (PillarBadge, HorizonBadge, etc.).
 *
 * Visual design:
 * - High Confidence (>= 75): green background
 * - Moderate (50-74): amber background
 * - Needs Verification (0-49): red background
 * - No Sources (null/undefined): gray background
 *
 * Integrates with the shared Tooltip component for hover detail and reuses
 * the badge-utils size/base-class helpers for consistency.
 *
 * @module QualityBadge
 */

import React from "react";
import { Link } from "react-router-dom";
import { Tooltip } from "./ui/Tooltip";
import { cn } from "../lib/utils";
import {
  getBadgeBaseClasses,
  getSizeClasses,
  type BadgeSize,
} from "../lib/badge-utils";

// =============================================================================
// Types
// =============================================================================

/**
 * Props for the QualityBadge component.
 */
export interface QualityBadgeProps {
  /** SQI score from 0-100. null/undefined indicates no sources available. */
  score: number | null | undefined;

  /**
   * Badge size variant controlling padding and font size.
   * - `'sm'` - Compact (text-xs, px-1.5 py-0.5)
   * - `'md'` - Default (text-sm, px-2 py-1)
   * - `'lg'` - Prominent (text-base, px-3 py-1.5)
   * @default 'md'
   */
  size?: BadgeSize;

  /**
   * When true, the numeric score is displayed next to the tier label
   * (e.g. "High Confidence 85").
   * @default false
   */
  showScore?: boolean;

  /**
   * Optional source count shown in the tooltip alongside the score.
   * Omitted from the tooltip when undefined.
   */
  sourceCount?: number;

  /** Additional CSS class names applied to the badge element. */
  className?: string;
}

// =============================================================================
// Tier Helpers
// =============================================================================

/** Quality tier classification. */
type QualityTier = "high" | "moderate" | "low" | "none";

/**
 * Tier visual configuration: label + Tailwind color classes (light & dark mode).
 */
interface TierConfig {
  label: string;
  bg: string;
  text: string;
  border: string;
}

const TIER_CONFIGS: Record<QualityTier, TierConfig> = {
  high: {
    label: "High Confidence",
    bg: "bg-green-100 dark:bg-green-900",
    text: "text-green-800 dark:text-green-200",
    border: "border-green-200 dark:border-green-700",
  },
  moderate: {
    label: "Moderate",
    bg: "bg-amber-100 dark:bg-amber-900",
    text: "text-amber-800 dark:text-amber-200",
    border: "border-amber-200 dark:border-amber-700",
  },
  low: {
    label: "Needs Verification",
    bg: "bg-red-100 dark:bg-red-900",
    text: "text-red-800 dark:text-red-200",
    border: "border-red-200 dark:border-red-700",
  },
  none: {
    label: "No Sources",
    bg: "bg-gray-100 dark:bg-gray-800",
    text: "text-gray-500 dark:text-gray-400",
    border: "border-gray-200 dark:border-gray-700",
  },
};

/**
 * Classify a raw SQI score into one of the four quality tiers.
 *
 * @param score - SQI score 0-100, or null/undefined
 * @returns The quality tier key
 */
function getQualityTier(score: number | null | undefined): QualityTier {
  if (score == null) return "none";
  if (score >= 75) return "high";
  if (score >= 50) return "moderate";
  return "low";
}

// =============================================================================
// Component
// =============================================================================

/**
 * QualityBadge renders a traffic-light badge communicating the SQI quality tier.
 *
 * @example
 * ```tsx
 * // Basic usage
 * <QualityBadge score={82} />
 *
 * // With numeric score and source count
 * <QualityBadge score={65} showScore sourceCount={4} size="lg" />
 *
 * // Null score renders "No Sources"
 * <QualityBadge score={null} />
 * ```
 */
export const QualityBadge: React.FC<QualityBadgeProps> = ({
  score,
  size = "md",
  showScore = false,
  sourceCount,
  className,
}) => {
  const tier = getQualityTier(score);
  const config = TIER_CONFIGS[tier];

  // Build the tooltip content with a deep link to the methodology page
  const tooltipParts: string[] = [];
  if (score != null) {
    tooltipParts.push(`Quality Score: ${score}/100`);
  } else {
    tooltipParts.push("No quality score available");
  }
  if (sourceCount != null) {
    tooltipParts.push(`${sourceCount} source${sourceCount !== 1 ? "s" : ""}`);
  }
  const tooltipSummary = tooltipParts.join(" \u2022 ");

  const tooltipContent = (
    <div className="space-y-1">
      <p>{tooltipSummary}</p>
      <Link
        to="/methodology#sqi"
        className="inline-block text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
      >
        Learn more &rarr;
      </Link>
    </div>
  );

  const badge = (
    <span
      className={cn(
        getBadgeBaseClasses({ hasTooltip: true }),
        getSizeClasses(size),
        config.bg,
        config.text,
        config.border,
        className,
      )}
    >
      {config.label}
      {showScore && score != null && (
        <span className="ml-1 opacity-75">{score}</span>
      )}
    </span>
  );

  return (
    <Tooltip content={tooltipContent} side="top" align="center">
      {badge}
    </Tooltip>
  );
};

export default QualityBadge;
