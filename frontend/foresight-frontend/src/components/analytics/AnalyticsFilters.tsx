/**
 * AnalyticsFilters Component
 *
 * Provides filter controls for analytics dashboard including:
 * - CSP Pillar selection (multi-select)
 * - Maturity Stage selection (multi-select)
 * - Time range selection (preset + custom date range)
 *
 * Features:
 * - Responsive layout (stacks on mobile)
 * - Clear visual feedback for active filters
 * - Reset functionality
 * - Callback for filter changes
 */

import React, { useState, useCallback, useMemo } from "react";
import {
  Filter,
  X,
  Calendar,
  ChevronDown,
  Check,
  RotateCcw,
  Heart,
  Briefcase,
  Building2,
  Home,
  Car,
  Shield,
  type LucideIcon,
} from "lucide-react";
import { format, subDays, subMonths, startOfMonth, parseISO } from "date-fns";
import { cn } from "../../lib/utils";
import {
  pillars,
  pipelineStatuses,
  pipelinePhases,
  type PipelinePhase,
} from "../../data/taxonomy";

// ============================================================================
// Type Definitions
// ============================================================================

export interface AnalyticsFiltersState {
  /** Selected pillar codes (e.g., ['CH', 'MC']) */
  selectedPillars: string[];
  /** Selected stage numbers (e.g., [1, 2, 3]) - @deprecated use selectedPipelineStatuses */
  selectedStages: number[];
  /** Selected pipeline status IDs (e.g., ['discovered', 'evaluating']) */
  selectedPipelineStatuses: string[];
  /** Time range preset or 'custom' */
  timeRange: TimeRangePreset;
  /** Custom date range (only used when timeRange is 'custom') */
  customDateRange: {
    start: string | null;
    end: string | null;
  };
}

export type TimeRangePreset =
  | "7d"
  | "30d"
  | "90d"
  | "6m"
  | "1y"
  | "mtd"
  | "ytd"
  | "all"
  | "custom";

export interface AnalyticsFiltersProps {
  /** Current filter state */
  filters: AnalyticsFiltersState;
  /** Called when filters change */
  onFiltersChange: (filters: AnalyticsFiltersState) => void;
  /** Whether to show compact version */
  compact?: boolean;
  /** Additional className */
  className?: string;
  /** Disable filters (e.g., while loading) */
  disabled?: boolean;
}

// ============================================================================
// Constants
// ============================================================================

const TIME_RANGE_OPTIONS: {
  value: TimeRangePreset;
  label: string;
  shortLabel: string;
}[] = [
  { value: "7d", label: "Last 7 days", shortLabel: "7D" },
  { value: "30d", label: "Last 30 days", shortLabel: "30D" },
  { value: "90d", label: "Last 90 days", shortLabel: "90D" },
  { value: "6m", label: "Last 6 months", shortLabel: "6M" },
  { value: "1y", label: "Last year", shortLabel: "1Y" },
  { value: "mtd", label: "Month to date", shortLabel: "MTD" },
  { value: "ytd", label: "Year to date", shortLabel: "YTD" },
  { value: "all", label: "All time", shortLabel: "All" },
  { value: "custom", label: "Custom range", shortLabel: "Custom" },
];

const PILLAR_ICONS: Record<string, LucideIcon> = {
  Heart: Heart,
  Briefcase: Briefcase,
  Building2: Building2,
  Home: Home,
  Car: Car,
  Shield: Shield,
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get computed date range from preset
 */
export function getDateRangeFromPreset(
  preset: TimeRangePreset,
): { start: string; end: string } | null {
  const now = new Date();
  const endDate = format(now, "yyyy-MM-dd");

  switch (preset) {
    case "7d":
      return { start: format(subDays(now, 7), "yyyy-MM-dd"), end: endDate };
    case "30d":
      return { start: format(subDays(now, 30), "yyyy-MM-dd"), end: endDate };
    case "90d":
      return { start: format(subDays(now, 90), "yyyy-MM-dd"), end: endDate };
    case "6m":
      return { start: format(subMonths(now, 6), "yyyy-MM-dd"), end: endDate };
    case "1y":
      return { start: format(subMonths(now, 12), "yyyy-MM-dd"), end: endDate };
    case "mtd":
      return { start: format(startOfMonth(now), "yyyy-MM-dd"), end: endDate };
    case "ytd":
      return {
        start: format(new Date(now.getFullYear(), 0, 1), "yyyy-MM-dd"),
        end: endDate,
      };
    case "all":
      return null;
    case "custom":
      return null;
    default:
      return null;
  }
}

/**
 * Get pillar color classes
 */
function getPillarColorClasses(pillarCode: string): {
  bg: string;
  text: string;
  border: string;
} {
  const colorMap: Record<string, { bg: string; text: string; border: string }> =
    {
      CH: {
        bg: "bg-green-100 dark:bg-green-900/30",
        text: "text-green-800 dark:text-green-200",
        border: "border-green-400",
      },
      EW: {
        bg: "bg-blue-100 dark:bg-blue-900/30",
        text: "text-blue-800 dark:text-blue-200",
        border: "border-blue-400",
      },
      HG: {
        bg: "bg-indigo-100 dark:bg-indigo-900/30",
        text: "text-indigo-800 dark:text-indigo-200",
        border: "border-indigo-400",
      },
      HH: {
        bg: "bg-pink-100 dark:bg-pink-900/30",
        text: "text-pink-800 dark:text-pink-200",
        border: "border-pink-400",
      },
      MC: {
        bg: "bg-amber-100 dark:bg-amber-900/30",
        text: "text-amber-800 dark:text-amber-200",
        border: "border-amber-400",
      },
      PS: {
        bg: "bg-red-100 dark:bg-red-900/30",
        text: "text-red-800 dark:text-red-200",
        border: "border-red-400",
      },
    };
  return (
    colorMap[pillarCode] || {
      bg: "bg-gray-100",
      text: "text-gray-800",
      border: "border-gray-400",
    }
  );
}

/**
 * @deprecated - Horizon colors are no longer used. Use pipeline phase colors instead.
 */

// ============================================================================
// Default Filter State
// ============================================================================

export const DEFAULT_ANALYTICS_FILTERS: AnalyticsFiltersState = {
  selectedPillars: [],
  selectedStages: [],
  selectedPipelineStatuses: [],
  timeRange: "30d",
  customDateRange: { start: null, end: null },
};

// ============================================================================
// Dropdown Component
// ============================================================================

interface DropdownProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  align?: "left" | "right";
  className?: string;
}

const Dropdown: React.FC<DropdownProps> = ({
  trigger,
  children,
  isOpen,
  onOpenChange,
  align = "left",
  className,
}) => {
  return (
    <div className={cn("relative", className)}>
      <div onClick={() => onOpenChange(!isOpen)}>{trigger}</div>
      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => onOpenChange(false)}
            aria-hidden="true"
          />
          <div
            className={cn(
              "absolute z-20 mt-2 w-64 bg-white dark:bg-dark-surface rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 max-h-80 overflow-y-auto",
              align === "left" ? "left-0" : "right-0",
            )}
          >
            {children}
          </div>
        </>
      )}
    </div>
  );
};

// ============================================================================
// Pillar Filter Dropdown
// ============================================================================

interface PillarFilterDropdownProps {
  selectedPillars: string[];
  onTogglePillar: (pillarCode: string) => void;
  onClearAll: () => void;
  disabled?: boolean;
}

const PillarFilterDropdown: React.FC<PillarFilterDropdownProps> = ({
  selectedPillars,
  onTogglePillar,
  onClearAll,
  disabled,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const hasSelection = selectedPillars.length > 0;

  return (
    <Dropdown
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      trigger={
        <button
          disabled={disabled}
          className={cn(
            "inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors",
            "text-sm font-medium",
            hasSelection
              ? "bg-brand-blue/10 border-brand-blue text-brand-blue"
              : "bg-white dark:bg-dark-surface border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300",
            "hover:bg-gray-50 dark:hover:bg-gray-700",
            disabled && "opacity-50 cursor-not-allowed",
          )}
        >
          <Filter className="h-4 w-4" />
          <span>Pillars</span>
          {hasSelection && (
            <span className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 rounded-full bg-brand-blue text-white text-xs">
              {selectedPillars.length}
            </span>
          )}
          <ChevronDown
            className={cn(
              "h-4 w-4 transition-transform",
              isOpen && "rotate-180",
            )}
          />
        </button>
      }
    >
      {/* Header with clear action */}
      <div className="flex items-center justify-between px-3 pb-2 mb-2 border-b border-gray-200 dark:border-gray-700">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          CSP Pillars
        </span>
        {hasSelection && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClearAll();
            }}
            className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Pillar options */}
      {pillars.map((pillar) => {
        const isSelected = selectedPillars.includes(pillar.code);
        const colors = getPillarColorClasses(pillar.code);
        const Icon = PILLAR_ICONS[pillar.icon];

        return (
          <button
            key={pillar.code}
            onClick={(e) => {
              e.stopPropagation();
              onTogglePillar(pillar.code);
            }}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 text-left transition-colors",
              "hover:bg-gray-50 dark:hover:bg-gray-700/50",
              isSelected && colors.bg,
            )}
          >
            <span
              className={cn(
                "flex items-center justify-center w-6 h-6 rounded border",
                isSelected
                  ? cn(colors.bg, colors.border, colors.text)
                  : "border-gray-300 dark:border-gray-600",
              )}
            >
              {isSelected && <Check className="h-4 w-4" />}
            </span>
            <div className="flex items-center gap-2 flex-1 min-w-0">
              {Icon && (
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    isSelected ? colors.text : "text-gray-400",
                  )}
                />
              )}
              <div className="min-w-0">
                <div
                  className={cn(
                    "text-sm font-medium truncate",
                    isSelected ? colors.text : "text-gray-900 dark:text-white",
                  )}
                >
                  {pillar.code}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {pillar.name}
                </div>
              </div>
            </div>
          </button>
        );
      })}
    </Dropdown>
  );
};

// ============================================================================
// Pipeline Status Filter Dropdown
// ============================================================================

interface PipelineStatusFilterDropdownProps {
  selectedStatuses: string[];
  onToggleStatus: (statusId: string) => void;
  onClearAll: () => void;
  disabled?: boolean;
}

const PipelineStatusFilterDropdown: React.FC<
  PipelineStatusFilterDropdownProps
> = ({ selectedStatuses, onToggleStatus, onClearAll, disabled }) => {
  const [isOpen, setIsOpen] = useState(false);
  const hasSelection = selectedStatuses.length > 0;

  // Phase color mapping
  const phaseColorMap: Record<string, { bg: string; text: string }> = {
    pipeline: {
      bg: "bg-blue-100 dark:bg-blue-900/30",
      text: "text-blue-800 dark:text-blue-200",
    },
    pursuing: {
      bg: "bg-amber-100 dark:bg-amber-900/30",
      text: "text-amber-800 dark:text-amber-200",
    },
    active: {
      bg: "bg-green-100 dark:bg-green-900/30",
      text: "text-green-800 dark:text-green-200",
    },
    archived: {
      bg: "bg-gray-100 dark:bg-gray-800/50",
      text: "text-gray-700 dark:text-gray-300",
    },
  };

  return (
    <Dropdown
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      trigger={
        <button
          disabled={disabled}
          className={cn(
            "inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors",
            "text-sm font-medium",
            hasSelection
              ? "bg-brand-blue/10 border-brand-blue text-brand-blue"
              : "bg-white dark:bg-dark-surface border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300",
            "hover:bg-gray-50 dark:hover:bg-gray-700",
            disabled && "opacity-50 cursor-not-allowed",
          )}
        >
          <span>Pipeline Status</span>
          {hasSelection && (
            <span className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 rounded-full bg-brand-blue text-white text-xs">
              {selectedStatuses.length}
            </span>
          )}
          <ChevronDown
            className={cn(
              "h-4 w-4 transition-transform",
              isOpen && "rotate-180",
            )}
          />
        </button>
      }
    >
      {/* Header with clear action */}
      <div className="flex items-center justify-between px-3 pb-2 mb-2 border-b border-gray-200 dark:border-gray-700">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          Pipeline Statuses
        </span>
        {hasSelection && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClearAll();
            }}
            className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Statuses grouped by phase */}
      {(Object.keys(pipelinePhases) as PipelinePhase[]).map((phaseKey) => {
        const phase = pipelinePhases[phaseKey];
        const phaseStatuses = pipelineStatuses.filter((s) =>
          (phase.statuses as readonly string[]).includes(s.id),
        );
        const colors = phaseColorMap[phaseKey] ??
          phaseColorMap["archived"] ?? { bg: "", text: "" };

        if (phaseStatuses.length === 0) return null;

        return (
          <div key={phaseKey} className="mb-2">
            <div className={cn("px-3 py-1 text-xs font-medium", colors.text)}>
              {phase.label}
            </div>
            {phaseStatuses.map((status) => {
              const isSelected = selectedStatuses.includes(status.id);

              return (
                <button
                  key={status.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleStatus(status.id);
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-1.5 text-left transition-colors",
                    "hover:bg-gray-50 dark:hover:bg-gray-700/50",
                    isSelected && colors.bg,
                  )}
                >
                  <span
                    className={cn(
                      "flex items-center justify-center w-5 h-5 rounded border",
                      isSelected
                        ? cn(colors.bg, colors.text, "border-current")
                        : "border-gray-300 dark:border-gray-600 text-gray-500",
                    )}
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                  </span>
                  <span
                    className={cn(
                      "text-sm",
                      isSelected
                        ? colors.text
                        : "text-gray-700 dark:text-gray-300",
                    )}
                  >
                    {status.name}
                  </span>
                </button>
              );
            })}
          </div>
        );
      })}
    </Dropdown>
  );
};

// ============================================================================
// Time Range Filter
// ============================================================================

interface TimeRangeFilterProps {
  timeRange: TimeRangePreset;
  customDateRange: { start: string | null; end: string | null };
  onTimeRangeChange: (range: TimeRangePreset) => void;
  onCustomDateChange: (start: string | null, end: string | null) => void;
  disabled?: boolean;
}

const TimeRangeFilter: React.FC<TimeRangeFilterProps> = ({
  timeRange,
  customDateRange,
  onTimeRangeChange,
  onCustomDateChange,
  disabled,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [showCustomInputs, setShowCustomInputs] = useState(
    timeRange === "custom",
  );

  const currentOption = TIME_RANGE_OPTIONS.find(
    (opt) => opt.value === timeRange,
  );

  const handleTimeRangeSelect = (value: TimeRangePreset) => {
    onTimeRangeChange(value);
    if (value === "custom") {
      setShowCustomInputs(true);
    } else {
      setShowCustomInputs(false);
      setIsOpen(false);
    }
  };

  const displayLabel = useMemo(() => {
    if (
      timeRange === "custom" &&
      customDateRange.start &&
      customDateRange.end
    ) {
      try {
        const startStr = format(parseISO(customDateRange.start), "MMM d");
        const endStr = format(parseISO(customDateRange.end), "MMM d, yyyy");
        return `${startStr} - ${endStr}`;
      } catch {
        return "Custom range";
      }
    }
    return currentOption?.label || "Select range";
  }, [timeRange, customDateRange, currentOption]);

  return (
    <Dropdown
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      align="right"
      trigger={
        <button
          disabled={disabled}
          className={cn(
            "inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors",
            "text-sm font-medium",
            "bg-white dark:bg-dark-surface border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300",
            "hover:bg-gray-50 dark:hover:bg-gray-700",
            disabled && "opacity-50 cursor-not-allowed",
          )}
        >
          <Calendar className="h-4 w-4" />
          <span className="max-w-[150px] truncate">{displayLabel}</span>
          <ChevronDown
            className={cn(
              "h-4 w-4 transition-transform",
              isOpen && "rotate-180",
            )}
          />
        </button>
      }
    >
      {/* Preset options */}
      <div className="px-1">
        {TIME_RANGE_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={(e) => {
              e.stopPropagation();
              handleTimeRangeSelect(option.value);
            }}
            className={cn(
              "w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors",
              "hover:bg-gray-50 dark:hover:bg-gray-700/50",
              timeRange === option.value && "bg-brand-blue/10 text-brand-blue",
            )}
          >
            <span>{option.label}</span>
            {timeRange === option.value && <Check className="h-4 w-4" />}
          </button>
        ))}
      </div>

      {/* Custom date inputs */}
      {showCustomInputs && (
        <div className="px-3 pt-3 mt-2 border-t border-gray-200 dark:border-gray-700">
          <div className="space-y-2">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Start date
              </label>
              <input
                type="date"
                value={customDateRange.start || ""}
                onChange={(e) =>
                  onCustomDateChange(
                    e.target.value || null,
                    customDateRange.end,
                  )
                }
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  "w-full px-2.5 py-1.5 rounded-md border text-sm",
                  "border-gray-300 dark:border-gray-600",
                  "bg-white dark:bg-gray-700",
                  "text-gray-900 dark:text-white",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
                )}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                End date
              </label>
              <input
                type="date"
                value={customDateRange.end || ""}
                onChange={(e) =>
                  onCustomDateChange(
                    customDateRange.start,
                    e.target.value || null,
                  )
                }
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  "w-full px-2.5 py-1.5 rounded-md border text-sm",
                  "border-gray-300 dark:border-gray-600",
                  "bg-white dark:bg-gray-700",
                  "text-gray-900 dark:text-white",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
                )}
              />
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsOpen(false);
              }}
              className="w-full py-1.5 mt-1 rounded-md bg-brand-blue text-white text-sm font-medium hover:bg-brand-blue/90 transition-colors"
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </Dropdown>
  );
};

// ============================================================================
// Active Filter Chips
// ============================================================================

interface ActiveFiltersProps {
  filters: AnalyticsFiltersState;
  onRemovePillar: (pillarCode: string) => void;
  onRemovePipelineStatus: (statusId: string) => void;
  onClearAll: () => void;
}

const ActiveFilters: React.FC<ActiveFiltersProps> = ({
  filters,
  onRemovePillar,
  onRemovePipelineStatus,
  onClearAll,
}) => {
  const hasActiveFilters =
    filters.selectedPillars.length > 0 ||
    filters.selectedPipelineStatuses.length > 0;

  if (!hasActiveFilters) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 mt-3">
      <span className="text-xs text-gray-500 dark:text-gray-400">Active:</span>

      {/* Pillar chips */}
      {filters.selectedPillars.map((pillarCode) => {
        const pillar = pillars.find((p) => p.code === pillarCode);
        const colors = getPillarColorClasses(pillarCode);

        return (
          <button
            key={pillarCode}
            onClick={() => onRemovePillar(pillarCode)}
            className={cn(
              "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors",
              colors.bg,
              colors.text,
              "hover:opacity-80",
            )}
          >
            {pillar?.code || pillarCode}
            <X className="h-3 w-3" />
          </button>
        );
      })}

      {/* Pipeline status chips */}
      {filters.selectedPipelineStatuses.map((statusId) => {
        const status = pipelineStatuses.find((s) => s.id === statusId);

        return (
          <button
            key={statusId}
            onClick={() => onRemovePipelineStatus(statusId)}
            className={cn(
              "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors",
              "bg-blue-100 dark:bg-blue-900/30",
              "text-blue-800 dark:text-blue-200",
              "hover:opacity-80",
            )}
          >
            {status?.name || statusId}
            <X className="h-3 w-3" />
          </button>
        );
      })}

      {/* Clear all button */}
      <button
        onClick={onClearAll}
        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
      >
        <RotateCcw className="h-3 w-3" />
        Clear all
      </button>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

export const AnalyticsFilters: React.FC<AnalyticsFiltersProps> = ({
  filters,
  onFiltersChange,
  compact = false,
  className,
  disabled = false,
}) => {
  // Handlers
  const handleTogglePillar = useCallback(
    (pillarCode: string) => {
      const newSelection = filters.selectedPillars.includes(pillarCode)
        ? filters.selectedPillars.filter((p) => p !== pillarCode)
        : [...filters.selectedPillars, pillarCode];
      onFiltersChange({ ...filters, selectedPillars: newSelection });
    },
    [filters, onFiltersChange],
  );

  const handleClearPillars = useCallback(() => {
    onFiltersChange({ ...filters, selectedPillars: [] });
  }, [filters, onFiltersChange]);

  const handleTogglePipelineStatus = useCallback(
    (statusId: string) => {
      const current = filters.selectedPipelineStatuses || [];
      const newSelection = current.includes(statusId)
        ? current.filter((s) => s !== statusId)
        : [...current, statusId];
      onFiltersChange({ ...filters, selectedPipelineStatuses: newSelection });
    },
    [filters, onFiltersChange],
  );

  const handleClearPipelineStatuses = useCallback(() => {
    onFiltersChange({ ...filters, selectedPipelineStatuses: [] });
  }, [filters, onFiltersChange]);

  const handleTimeRangeChange = useCallback(
    (range: TimeRangePreset) => {
      onFiltersChange({
        ...filters,
        timeRange: range,
        customDateRange:
          range !== "custom"
            ? { start: null, end: null }
            : filters.customDateRange,
      });
    },
    [filters, onFiltersChange],
  );

  const handleCustomDateChange = useCallback(
    (start: string | null, end: string | null) => {
      onFiltersChange({
        ...filters,
        customDateRange: { start, end },
      });
    },
    [filters, onFiltersChange],
  );

  const handleRemovePillar = useCallback(
    (pillarCode: string) => {
      onFiltersChange({
        ...filters,
        selectedPillars: filters.selectedPillars.filter(
          (p) => p !== pillarCode,
        ),
      });
    },
    [filters, onFiltersChange],
  );

  const handleRemovePipelineStatus = useCallback(
    (statusId: string) => {
      onFiltersChange({
        ...filters,
        selectedPipelineStatuses: (
          filters.selectedPipelineStatuses || []
        ).filter((s) => s !== statusId),
      });
    },
    [filters, onFiltersChange],
  );

  const handleClearAll = useCallback(() => {
    onFiltersChange({
      ...DEFAULT_ANALYTICS_FILTERS,
      timeRange: filters.timeRange,
      customDateRange: filters.customDateRange,
    });
  }, [filters, onFiltersChange]);

  return (
    <div className={cn("", className)}>
      <div
        className={cn(
          "flex flex-wrap items-center gap-2",
          compact ? "gap-2" : "gap-3",
        )}
      >
        {/* Pillar filter */}
        <PillarFilterDropdown
          selectedPillars={filters.selectedPillars}
          onTogglePillar={handleTogglePillar}
          onClearAll={handleClearPillars}
          disabled={disabled}
        />

        {/* Pipeline Status filter */}
        <PipelineStatusFilterDropdown
          selectedStatuses={filters.selectedPipelineStatuses || []}
          onToggleStatus={handleTogglePipelineStatus}
          onClearAll={handleClearPipelineStatuses}
          disabled={disabled}
        />

        {/* Spacer */}
        <div className="flex-1" />

        {/* Time range filter */}
        <TimeRangeFilter
          timeRange={filters.timeRange}
          customDateRange={filters.customDateRange}
          onTimeRangeChange={handleTimeRangeChange}
          onCustomDateChange={handleCustomDateChange}
          disabled={disabled}
        />
      </div>

      {/* Active filter chips */}
      {!compact && (
        <ActiveFilters
          filters={filters}
          onRemovePillar={handleRemovePillar}
          onRemovePipelineStatus={handleRemovePipelineStatus}
          onClearAll={handleClearAll}
        />
      )}
    </div>
  );
};

export default AnalyticsFilters;
