/**
 * InfoTooltip
 *
 * A small help-circle icon that displays contextual information on hover (desktop)
 * or click (mobile). Wraps the existing Tooltip component for consistent behavior.
 */

import type { ReactNode } from "react";
import { HelpCircle } from "lucide-react";
import { Tooltip } from "../ui/Tooltip";
import { cn } from "../../lib/utils";

interface InfoTooltipProps {
  /** Tooltip content -- can be a string or rich React node */
  content: ReactNode;
  /** Which side of the icon to show the tooltip */
  side?: "top" | "right" | "bottom" | "left";
  /** Additional className for the icon wrapper */
  className?: string;
}

export function InfoTooltip({
  content,
  side = "top",
  className,
}: InfoTooltipProps) {
  return (
    <Tooltip content={content} side={side} delayDuration={200}>
      <button
        type="button"
        aria-label="More information"
        className={cn(
          "inline-flex items-center justify-center cursor-help",
          "text-gray-400 dark:text-gray-500",
          "hover:text-gray-600 dark:hover:text-gray-300",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:rounded",
          "transition-colors duration-150",
          className,
        )}
      >
        <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </Tooltip>
  );
}

export default InfoTooltip;
