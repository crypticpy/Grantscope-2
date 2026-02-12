/**
 * VelocityBadge Component
 *
 * Displays a signal velocity trend indicator with:
 * - Color-coded pill based on trend direction
 * - Contextual icon (TrendingUp, TrendingDown, Sparkles, etc.)
 * - Tooltip showing velocity score percentage
 * - Dark mode support
 *
 * Matches the visual weight and patterns of HorizonBadge and StageBadge.
 */

import {
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Sparkles,
  Clock,
} from "lucide-react";
import { Tooltip } from "./ui/Tooltip";
import { cn } from "../lib/utils";

// =============================================================================
// Types
// =============================================================================

export type VelocityTrend =
  | "accelerating"
  | "stable"
  | "decelerating"
  | "emerging"
  | "stale";

export interface VelocityBadgeProps {
  /** The velocity trend classification */
  trend: VelocityTrend | null | undefined;
  /** Numeric velocity score (positive = accelerating, negative = decelerating) */
  score?: number;
  /** Additional className */
  className?: string;
  /** Whether to show the text label (default: true) */
  showLabel?: boolean;
}

// =============================================================================
// Configuration
// =============================================================================

interface TrendConfig {
  label: string;
  icon: typeof TrendingUp;
  colors: {
    bg: string;
    text: string;
    border: string;
  };
}

const TREND_CONFIG: Record<VelocityTrend, TrendConfig> = {
  accelerating: {
    label: "Accelerating",
    icon: TrendingUp,
    colors: {
      bg: "bg-green-50 dark:bg-green-900/20",
      text: "text-green-600 dark:text-green-400",
      border: "border-green-200 dark:border-green-800",
    },
  },
  stable: {
    label: "Stable",
    icon: ArrowRight,
    colors: {
      bg: "bg-gray-100 dark:bg-gray-800/40",
      text: "text-gray-500 dark:text-gray-400",
      border: "border-gray-200 dark:border-gray-700",
    },
  },
  decelerating: {
    label: "Slowing",
    icon: TrendingDown,
    colors: {
      bg: "bg-amber-50 dark:bg-amber-900/20",
      text: "text-amber-600 dark:text-amber-400",
      border: "border-amber-200 dark:border-amber-800",
    },
  },
  emerging: {
    label: "Emerging",
    icon: Sparkles,
    colors: {
      bg: "bg-brand-blue/10 dark:bg-brand-blue/20",
      text: "text-brand-blue dark:text-blue-400",
      border: "border-brand-blue/20 dark:border-blue-800",
    },
  },
  stale: {
    label: "Stale",
    icon: Clock,
    colors: {
      bg: "bg-gray-100 dark:bg-gray-800/40",
      text: "text-gray-400 dark:text-gray-500",
      border: "border-gray-200 dark:border-gray-700",
    },
  },
};

// =============================================================================
// Helpers
// =============================================================================

function getTooltipText(trend: VelocityTrend, score?: number): string {
  if (trend === "emerging") {
    return "New signal";
  }
  if (trend === "stale") {
    return "No recent activity";
  }
  if (score === undefined || score === null) {
    return TREND_CONFIG[trend].label;
  }
  const prefix = score >= 0 ? "+" : "";
  return `${prefix}${score.toFixed(0)}% velocity`;
}

// =============================================================================
// Component
// =============================================================================

export function VelocityBadge({
  trend,
  score,
  className,
  showLabel = true,
}: VelocityBadgeProps) {
  // Don't render anything for null/undefined trends
  if (!trend) {
    return null;
  }

  const config = TREND_CONFIG[trend];
  if (!config) {
    return null;
  }

  const Icon = config.icon;
  const tooltipText = getTooltipText(trend, score);

  const badge = (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border",
        "cursor-default transition-colors",
        config.colors.bg,
        config.colors.text,
        config.colors.border,
        className,
      )}
      role="status"
      aria-label={`Velocity: ${config.label}`}
    >
      <Icon className="h-3 w-3 shrink-0" />
      {showLabel && <span>{config.label}</span>}
    </span>
  );

  return (
    <Tooltip content={tooltipText} side="top" align="center">
      {badge}
    </Tooltip>
  );
}

export default VelocityBadge;
