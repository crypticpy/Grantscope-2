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

import { Tooltip } from "./ui/Tooltip";
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
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
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
 * Get tier-specific description for quality score tooltip
 */
function getTierDescription(score: number | null | undefined): string {
  if (score == null) {
    return "This opportunity has not been scored yet.";
  }
  if (score >= 80) {
    return "This opportunity has been verified by multiple sources and meets high data quality standards.";
  }
  if (score >= 60) {
    return "This opportunity has been reviewed and contains reliable information.";
  }
  if (score >= 40) {
    return "This opportunity contains basic information but may benefit from additional verification.";
  }
  return "This opportunity has limited information available and should be verified independently.";
}

/**
 * Tooltip content for quality score badge
 */
function QualityScoreTooltipContent({
  score,
  config,
}: {
  score: number | null | undefined;
  config: ReturnType<typeof getScoreConfig>;
}) {
  return (
    <div className="space-y-2 min-w-[200px] max-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div
          className={cn(
            "w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg border-2",
            config.bg,
            config.text,
            config.border,
          )}
        >
          {score != null ? score : "\u2014"}
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            Quality Score{score != null ? `: ${score}/100` : ""}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {config.label}
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {getTierDescription(score)}
      </p>

      {/* Score bar */}
      {score != null && (
        <div className="pt-1">
          <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-200",
                score >= 80 && "bg-green-500 dark:bg-green-400",
                score >= 60 && score < 80 && "bg-amber-500 dark:bg-amber-400",
                score >= 40 && score < 60 && "bg-orange-500 dark:bg-orange-400",
                score < 40 && "bg-red-500 dark:bg-red-400",
              )}
              style={{ width: `${score}%` }}
            />
          </div>
          <div className="flex justify-between mt-1 text-[10px] text-gray-400">
            <span>0</span>
            <span>100</span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * QualityScoreBadge component
 */
export function QualityScoreBadge({
  score,
  size = "md",
  showLabel = false,
  className,
  disableTooltip = false,
}: QualityScoreBadgeProps) {
  const config = getScoreConfig(score);
  const ariaText =
    score != null
      ? `Quality score: ${score} out of 100, ${config.label}`
      : "Quality score: Not scored";

  const badge = (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium border cursor-default",
        config.bg,
        config.text,
        config.border,
        getSizeClasses(size, { variant: "pill" }),
        !disableTooltip && "cursor-pointer",
        className,
      )}
      role="status"
      aria-label={ariaText}
    >
      {score != null ? score : "\u2014"}
      {showLabel && (
        <span className="opacity-75">{score != null ? config.label : ""}</span>
      )}
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={<QualityScoreTooltipContent score={score} config={config} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

export default QualityScoreBadge;
