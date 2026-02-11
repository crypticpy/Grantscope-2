/**
 * QualityScoreBadge Component
 *
 * Displays a quality score with color-coded severity:
 * - >= 80: Green (Excellent)
 * - >= 60: Amber (Good)
 * - >= 40: Orange (Fair)
 * - < 40: Red (Low)
 * - null/undefined: Gray (No score)
 */

import React from "react";
import { cn } from "../lib/utils";
import { getSizeClasses, type BadgeSize } from "../lib/badge-utils";

export interface QualityScoreBadgeProps {
  /** Quality score value (0-100) or null/undefined for unscored */
  score: number | null | undefined;
  /** Size variant */
  size?: BadgeSize;
  /** Whether to show the text label alongside the score */
  showLabel?: boolean;
  /** Additional className */
  className?: string;
}

/**
 * Get color classes for a quality score
 */
function getScoreConfig(score: number | null | undefined): {
  bg: string;
  text: string;
  border: string;
  label: string;
} {
  if (score == null) {
    return {
      bg: "bg-gray-100 dark:bg-gray-700",
      text: "text-gray-500 dark:text-gray-400",
      border: "border-gray-200 dark:border-gray-600",
      label: "No score",
    };
  }
  if (score >= 80) {
    return {
      bg: "bg-green-50 dark:bg-green-900/30",
      text: "text-green-700 dark:text-green-400",
      border: "border-green-200 dark:border-green-800",
      label: "Excellent",
    };
  }
  if (score >= 60) {
    return {
      bg: "bg-amber-50 dark:bg-amber-900/30",
      text: "text-amber-700 dark:text-amber-400",
      border: "border-amber-200 dark:border-amber-800",
      label: "Good",
    };
  }
  if (score >= 40) {
    return {
      bg: "bg-orange-50 dark:bg-orange-900/30",
      text: "text-orange-700 dark:text-orange-400",
      border: "border-orange-200 dark:border-orange-800",
      label: "Fair",
    };
  }
  return {
    bg: "bg-red-50 dark:bg-red-900/30",
    text: "text-red-700 dark:text-red-400",
    border: "border-red-200 dark:border-red-800",
    label: "Low",
  };
}

/**
 * QualityScoreBadge component
 */
export function QualityScoreBadge({
  score,
  size = "md",
  showLabel = false,
  className,
}: QualityScoreBadgeProps) {
  const config = getScoreConfig(score);
  const ariaText =
    score != null
      ? `Quality score: ${score} out of 100, ${config.label}`
      : "Quality score: Not scored";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium border cursor-default",
        config.bg,
        config.text,
        config.border,
        getSizeClasses(size, { variant: "pill" }),
        className,
      )}
      role="status"
      aria-label={ariaText}
      title={`Quality: ${score != null ? `${score}/100 (${config.label})` : "Not scored"}`}
    >
      {score != null ? score : "\u2014"}
      {showLabel && (
        <span className="opacity-75">{score != null ? config.label : ""}</span>
      )}
    </span>
  );
}

export default QualityScoreBadge;
