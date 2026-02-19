/**
 * PipelineBadge Component
 *
 * Displays a pipeline status indicator with:
 * - Status name and icon
 * - Phase-based color coding
 * - Tooltip showing status details, phase, and mini progress indicator
 */

import {
  Search,
  ClipboardCheck,
  FileEdit,
  Send,
  Trophy,
  Activity,
  Archive,
  XCircle,
  Clock,
} from "lucide-react";
import { Tooltip } from "./ui/Tooltip";
import { cn } from "../lib/utils";
import {
  getPipelineStatusById,
  getPipelinePhase,
  pipelinePhases,
  type PipelineStatus,
  type PipelinePhase,
} from "../data/taxonomy";
import {
  getBadgeBaseClasses,
  getSizeClasses,
  getIconSize,
} from "../lib/badge-utils";

export interface PipelineBadgeProps {
  /** Pipeline status ID (e.g. 'discovered', 'evaluating', 'awarded') */
  status: string;
  /** Size variant */
  size?: "sm" | "md" | "lg";
  /** Whether to show the phase label alongside the status */
  showPhase?: boolean;
  /** Additional className */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
}

/**
 * Map status IDs to lucide-react icon components
 */
const STATUS_ICON_MAP: Record<string, typeof Search> = {
  discovered: Search,
  evaluating: ClipboardCheck,
  applying: FileEdit,
  submitted: Send,
  awarded: Trophy,
  active: Activity,
  closed: Archive,
  declined: XCircle,
  expired: Clock,
};

/**
 * Get Tailwind color classes based on pipeline phase
 */
function getPhaseColorClasses(phase: PipelinePhase): {
  bg: string;
  text: string;
  border: string;
  iconBg: string;
} {
  const colorMap: Record<
    PipelinePhase,
    { bg: string; text: string; border: string; iconBg: string }
  > = {
    pipeline: {
      bg: "bg-blue-50 dark:bg-blue-900/30",
      text: "text-blue-700 dark:text-blue-200",
      border: "border-blue-300 dark:border-blue-600",
      iconBg: "bg-blue-200 dark:bg-blue-800",
    },
    pursuing: {
      bg: "bg-amber-50 dark:bg-amber-900/30",
      text: "text-amber-700 dark:text-amber-200",
      border: "border-amber-300 dark:border-amber-600",
      iconBg: "bg-amber-200 dark:bg-amber-800",
    },
    active: {
      bg: "bg-green-50 dark:bg-green-900/30",
      text: "text-green-700 dark:text-green-200",
      border: "border-green-300 dark:border-green-600",
      iconBg: "bg-green-200 dark:bg-green-800",
    },
    archived: {
      bg: "bg-gray-50 dark:bg-gray-800/50",
      text: "text-gray-600 dark:text-gray-300",
      border: "border-gray-300 dark:border-gray-600",
      iconBg: "bg-gray-200 dark:bg-gray-700",
    },
  };

  return colorMap[phase];
}

/**
 * Tooltip content component for pipeline status
 */
function PipelineTooltipContent({
  statusData,
  phase,
}: {
  statusData: PipelineStatus;
  phase: PipelinePhase;
}) {
  const colors = getPhaseColorClasses(phase);
  const phaseDef = pipelinePhases[phase];
  const Icon = STATUS_ICON_MAP[statusData.id] || Search;

  return (
    <div className="space-y-3 min-w-[220px] max-w-[280px]">
      {/* Header with icon */}
      <div className="flex items-center gap-2">
        <div className={cn("p-1.5 rounded-md", colors.iconBg)}>
          <Icon className={cn("h-4 w-4", colors.text)} />
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {statusData.name}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {phaseDef.label} phase
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {statusData.description}
      </p>

      {/* Phase context */}
      <div className="text-xs text-gray-500 dark:text-gray-400 italic border-t border-gray-200 dark:border-gray-700 pt-1">
        {phaseDef.description}
      </div>

      {/* Mini phase progress indicator */}
      <div className="pt-1">
        <div className="flex items-center gap-1">
          {(Object.keys(pipelinePhases) as PipelinePhase[]).map((p) => {
            const def = pipelinePhases[p];
            const isActive = p === phase;
            return (
              <div
                key={p}
                className="flex-1 flex flex-col items-center gap-0.5"
              >
                <div
                  className={cn(
                    "w-full h-1.5 rounded-full transition-all duration-200",
                    isActive ? "ring-1 ring-offset-1 ring-gray-400" : "",
                  )}
                  style={{
                    backgroundColor: isActive ? def.color : "#e5e7eb",
                  }}
                />
                <span
                  className={cn(
                    "text-[9px] leading-tight",
                    isActive
                      ? "font-medium text-gray-700 dark:text-gray-200"
                      : "text-gray-400 dark:text-gray-500",
                  )}
                >
                  {def.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/**
 * PipelineBadge component
 */
export function PipelineBadge({
  status,
  size = "md",
  showPhase = false,
  className,
  disableTooltip = false,
}: PipelineBadgeProps) {
  const statusData = getPipelineStatusById(status);
  const phase = getPipelinePhase(status);
  const colors = getPhaseColorClasses(phase);
  const Icon = STATUS_ICON_MAP[status] || Search;
  const iconSize = getIconSize(size, "small");

  if (!statusData) {
    return (
      <span
        className={cn(
          getBadgeBaseClasses(),
          "bg-gray-100 text-gray-600 border-gray-300",
          getSizeClasses(size, { includeGap: true }),
          className,
        )}
      >
        {status}
      </span>
    );
  }

  const phaseDef = pipelinePhases[phase];

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
      aria-label={`Pipeline status: ${statusData.name} (${phaseDef.label} phase)`}
    >
      <Icon className="shrink-0" size={iconSize} />
      <span>{statusData.name}</span>
      {showPhase && (
        <span className="opacity-60 text-[0.85em]">({phaseDef.label})</span>
      )}
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={<PipelineTooltipContent statusData={statusData} phase={phase} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

/**
 * Pipeline progress indicator showing all 4 phases
 */
export interface PipelineProgressProps {
  /** Current pipeline status ID */
  status: string;
  /** Whether to show phase labels */
  showLabels?: boolean;
  /** Additional className */
  className?: string;
}

export function PipelineProgress({
  status,
  showLabels = true,
  className,
}: PipelineProgressProps) {
  const currentPhase = getPipelinePhase(status);
  const phaseKeys = Object.keys(pipelinePhases) as PipelinePhase[];
  const currentIndex = phaseKeys.indexOf(currentPhase);

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center gap-1">
        {phaseKeys.map((p, idx) => {
          const def = pipelinePhases[p];
          const isActive = idx <= currentIndex;
          const isCurrent = p === currentPhase;

          return (
            <div
              key={p}
              className={cn(
                "flex-1 h-2 transition-all duration-200",
                idx === 0 && "rounded-l-full",
                idx === phaseKeys.length - 1 && "rounded-r-full",
                isCurrent && "ring-2 ring-offset-1 ring-gray-400",
              )}
              style={{
                backgroundColor: isActive ? def.color : "#e5e7eb",
              }}
            />
          );
        })}
      </div>
      {showLabels && (
        <div className="flex justify-between">
          {phaseKeys.map((p) => {
            const def = pipelinePhases[p];
            const isCurrent = p === currentPhase;
            return (
              <span
                key={p}
                className={cn(
                  "text-[10px]",
                  isCurrent
                    ? "font-medium text-gray-700 dark:text-gray-200"
                    : "text-gray-400 dark:text-gray-500",
                )}
              >
                {def.label}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default PipelineBadge;
