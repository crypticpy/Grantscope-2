/**
 * TrendBadge Component
 *
 * Displays the overall trend trajectory of a signal based on source
 * publication patterns. Distinct from VelocityBadge which tracks
 * velocity score changes over time.
 *
 * Values: accelerating | stable | emerging | declining | unknown
 */

import {
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Sparkles,
  HelpCircle,
} from "lucide-react";
import { Tooltip } from "./ui/Tooltip";
import { cn } from "../lib/utils";

// =============================================================================
// Types
// =============================================================================

export type TrendDirection =
  | "accelerating"
  | "stable"
  | "emerging"
  | "declining"
  | "unknown";

export interface TrendBadgeProps {
  /** The trend direction classification */
  direction: TrendDirection | null | undefined;
  /** Additional className */
  className?: string;
  /** Whether to show the text label (default: true) */
  showLabel?: boolean;
}

// =============================================================================
// Configuration
// =============================================================================

interface DirectionConfig {
  label: string;
  tooltip: string;
  icon: typeof TrendingUp;
  colors: {
    bg: string;
    text: string;
    border: string;
  };
}

const DIRECTION_CONFIG: Record<TrendDirection, DirectionConfig> = {
  accelerating: {
    label: "Accelerating",
    tooltip: "Rapidly increasing coverage and momentum across sources",
    icon: TrendingUp,
    colors: {
      bg: "bg-emerald-50 dark:bg-emerald-900/20",
      text: "text-emerald-600 dark:text-emerald-400",
      border: "border-emerald-200 dark:border-emerald-800",
    },
  },
  stable: {
    label: "Steady",
    tooltip: "Consistent coverage with no major shifts in momentum",
    icon: ArrowRight,
    colors: {
      bg: "bg-sky-50 dark:bg-sky-900/20",
      text: "text-sky-600 dark:text-sky-400",
      border: "border-sky-200 dark:border-sky-800",
    },
  },
  emerging: {
    label: "Emerging",
    tooltip: "Early-stage signal with growing but sparse coverage",
    icon: Sparkles,
    colors: {
      bg: "bg-violet-50 dark:bg-violet-900/20",
      text: "text-violet-600 dark:text-violet-400",
      border: "border-violet-200 dark:border-violet-800",
    },
  },
  declining: {
    label: "Declining",
    tooltip: "Decreasing coverage and fading from active discussion",
    icon: TrendingDown,
    colors: {
      bg: "bg-orange-50 dark:bg-orange-900/20",
      text: "text-orange-600 dark:text-orange-400",
      border: "border-orange-200 dark:border-orange-800",
    },
  },
  unknown: {
    label: "Unclassified",
    tooltip: "Not enough data to determine trend trajectory",
    icon: HelpCircle,
    colors: {
      bg: "bg-gray-100 dark:bg-gray-800/40",
      text: "text-gray-400 dark:text-gray-500",
      border: "border-gray-200 dark:border-gray-700",
    },
  },
};

// =============================================================================
// Component
// =============================================================================

export function TrendBadge({
  direction,
  className,
  showLabel = true,
}: TrendBadgeProps) {
  if (!direction || direction === "unknown") {
    return null;
  }

  const config = DIRECTION_CONFIG[direction];
  if (!config) {
    return null;
  }

  const Icon = config.icon;

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
      aria-label={`Trend: ${config.label}`}
    >
      <Icon className="h-3 w-3 shrink-0" />
      {showLabel && <span>{config.label}</span>}
    </span>
  );

  return (
    <Tooltip content={config.tooltip} side="top" align="center">
      {badge}
    </Tooltip>
  );
}

export default TrendBadge;
