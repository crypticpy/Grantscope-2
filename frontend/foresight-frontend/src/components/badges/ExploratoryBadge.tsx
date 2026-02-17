/**
 * ExploratoryBadge Component
 *
 * A distinct badge for cards marked as "Exploratory" -- those that do not
 * align with a specific strategic pillar but represent emerging or
 * cross-cutting topics worth monitoring.
 *
 * Uses a purple/violet color scheme to visually distinguish from
 * pillar-specific badges (CH, MC, HH, etc.).
 *
 * @example
 * ```tsx
 * <ExploratoryBadge />
 * <ExploratoryBadge size="sm" />
 * ```
 *
 * @module badges/ExploratoryBadge
 */

import { Compass } from "lucide-react";
import { Tooltip } from "../ui/Tooltip";
import { cn } from "../../lib/utils";
import { getSizeClasses, getIconSize } from "../../lib/badge-utils";

// =============================================================================
// Types
// =============================================================================

export interface ExploratoryBadgeProps {
  /** Size variant for the badge */
  size?: "sm" | "md";
  /** Additional CSS classes */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
}

// =============================================================================
// Tooltip Content
// =============================================================================

/**
 * Tooltip content for the Exploratory badge
 */
function ExploratoryTooltipContent() {
  return (
    <div className="space-y-2 min-w-[200px] max-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="p-1.5 rounded-md bg-violet-200 dark:bg-violet-800">
          <Compass className="h-4 w-4 text-violet-700 dark:text-violet-300" />
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            Exploratory
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Cross-cutting topic
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        This opportunity is exploratory — it was discovered recently and may
        need further verification before acting on it.
      </p>

      {/* Footer hint */}
      <div className="text-[10px] text-gray-400 dark:text-gray-500 pt-1 border-t border-gray-200 dark:border-gray-700">
        Not aligned to a specific strategic pillar
      </div>
    </div>
  );
}

// =============================================================================
// Component
// =============================================================================

/**
 * ExploratoryBadge renders a purple/violet badge with a compass icon
 * to indicate a card is exploratory and not tied to a specific pillar.
 */
export function ExploratoryBadge({
  size = "md",
  className,
  disableTooltip = false,
}: ExploratoryBadgeProps) {
  const iconSize = getIconSize(size);

  const badge = (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded font-medium border cursor-default",
        "bg-violet-100 text-violet-800 border-violet-300",
        "dark:bg-violet-900/40 dark:text-violet-300 dark:border-violet-700",
        getSizeClasses(size),
        !disableTooltip && "cursor-pointer",
        className,
      )}
      role="status"
      aria-label="Exploratory opportunity"
    >
      <Compass className="shrink-0" size={iconSize} aria-hidden="true" />
      <span>Exploratory</span>
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={<ExploratoryTooltipContent />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

export default ExploratoryBadge;
