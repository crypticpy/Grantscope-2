/**
 * DeadlineUrgencyBadge Component
 *
 * Displays a deadline urgency indicator with:
 * - Color coding: urgent=red, approaching=amber, planning=green
 * - Days remaining countdown
 * - Tooltip showing urgency tier, days remaining, and formatted deadline date
 */

import { AlertTriangle, Clock, Calendar } from "lucide-react";
import { Tooltip } from "./ui/Tooltip";
import { cn } from "../lib/utils";
import { getDeadlineUrgency, type DeadlineUrgency } from "../data/taxonomy";
import {
  getBadgeBaseClasses,
  getSizeClasses,
  getIconSize,
} from "../lib/badge-utils";

export interface DeadlineUrgencyBadgeProps {
  /** Deadline date as string, Date, null, or undefined */
  deadline: string | Date | null | undefined;
  /** Size variant */
  size?: "sm" | "md" | "lg";
  /** Additional className */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
}

/**
 * Map urgency codes to lucide-react icon components
 */
const URGENCY_ICON_MAP: Record<string, typeof AlertTriangle> = {
  urgent: AlertTriangle,
  approaching: Clock,
  planning: Calendar,
};

/**
 * Get Tailwind color classes based on urgency tier
 */
function getUrgencyColorClasses(urgencyCode: string): {
  bg: string;
  text: string;
  border: string;
  iconBg: string;
} {
  const colorMap: Record<
    string,
    { bg: string; text: string; border: string; iconBg: string }
  > = {
    urgent: {
      bg: "bg-red-50 dark:bg-red-900/30",
      text: "text-red-700 dark:text-red-200",
      border: "border-red-300 dark:border-red-600",
      iconBg: "bg-red-200 dark:bg-red-800",
    },
    approaching: {
      bg: "bg-amber-50 dark:bg-amber-900/30",
      text: "text-amber-700 dark:text-amber-200",
      border: "border-amber-300 dark:border-amber-600",
      iconBg: "bg-amber-200 dark:bg-amber-800",
    },
    planning: {
      bg: "bg-green-50 dark:bg-green-900/30",
      text: "text-green-700 dark:text-green-200",
      border: "border-green-300 dark:border-green-600",
      iconBg: "bg-green-200 dark:bg-green-800",
    },
  };

  return (
    colorMap[urgencyCode] || {
      bg: "bg-gray-50 dark:bg-gray-800/50",
      text: "text-gray-600 dark:text-gray-300",
      border: "border-gray-300 dark:border-gray-600",
      iconBg: "bg-gray-200 dark:bg-gray-700",
    }
  );
}

/**
 * Compute days remaining from now to deadline
 */
function getDaysRemaining(deadline: Date): number {
  const now = new Date();
  return Math.ceil(
    (deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
  );
}

/**
 * Format a date for display in the tooltip
 */
function formatDeadlineDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Tooltip content component for deadline urgency
 */
function DeadlineTooltipContent({
  urgency,
  daysRemaining,
  deadlineDate,
}: {
  urgency: DeadlineUrgency;
  daysRemaining: number;
  deadlineDate: Date;
}) {
  const colors = getUrgencyColorClasses(urgency.code);
  const Icon = URGENCY_ICON_MAP[urgency.code] || Calendar;

  return (
    <div className="space-y-2 min-w-[180px] max-w-[240px]">
      {/* Header with icon */}
      <div className="flex items-center gap-2">
        <div className={cn("p-1.5 rounded-md", colors.iconBg)}>
          <Icon className={cn("h-4 w-4", colors.text)} />
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {urgency.name}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {urgency.description}
          </div>
        </div>
      </div>

      {/* Days remaining */}
      <div className="flex items-baseline gap-1">
        <span className={cn("text-lg font-bold", colors.text)}>
          {daysRemaining}
        </span>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {daysRemaining === 1 ? "day" : "days"} remaining
        </span>
      </div>

      {/* Deadline date */}
      <div className="text-xs text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700 pt-1">
        Deadline: {formatDeadlineDate(deadlineDate)}
      </div>
    </div>
  );
}

/**
 * DeadlineUrgencyBadge component
 */
export function DeadlineUrgencyBadge({
  deadline,
  size = "md",
  className,
  disableTooltip = false,
}: DeadlineUrgencyBadgeProps) {
  if (!deadline) return null;

  const deadlineDate =
    typeof deadline === "string" ? new Date(deadline) : deadline;
  const urgency = getDeadlineUrgency(deadlineDate);

  // No urgency means deadline is in the past
  if (!urgency) return null;

  const daysRemaining = getDaysRemaining(deadlineDate);
  const colors = getUrgencyColorClasses(urgency.code);
  const Icon = URGENCY_ICON_MAP[urgency.code] || Calendar;
  const iconSize = getIconSize(size, "small");

  const daysLabel =
    daysRemaining === 0
      ? "Today"
      : daysRemaining === 1
        ? "1 day"
        : `${daysRemaining}d`;

  const badge = (
    <span
      className={cn(
        getBadgeBaseClasses({ hasTooltip: !disableTooltip }),
        colors.bg,
        colors.text,
        colors.border,
        getSizeClasses(size, { includeGap: true }),
        className,
      )}
      role="status"
      aria-label={`Deadline ${urgency.name.toLowerCase()}: ${daysRemaining} days remaining`}
    >
      <Icon className="shrink-0" size={iconSize} />
      <span>{daysLabel}</span>
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={
        <DeadlineTooltipContent
          urgency={urgency}
          daysRemaining={daysRemaining}
          deadlineDate={deadlineDate}
        />
      }
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

export default DeadlineUrgencyBadge;
