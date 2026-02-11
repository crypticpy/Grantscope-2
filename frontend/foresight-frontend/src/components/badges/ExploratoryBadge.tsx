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
}: ExploratoryBadgeProps) {
  const iconSize = getIconSize(size);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded font-medium border cursor-default",
        "bg-violet-100 text-violet-800 border-violet-300",
        "dark:bg-violet-900/40 dark:text-violet-300 dark:border-violet-700",
        getSizeClasses(size),
        className,
      )}
      role="status"
      aria-label="Exploratory signal"
    >
      <Compass className="shrink-0" size={iconSize} aria-hidden="true" />
      <span>Exploratory</span>
    </span>
  );
}

export default ExploratoryBadge;
