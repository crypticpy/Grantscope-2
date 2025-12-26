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

import React, { useState, useCallback, useMemo } from 'react';
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
} from 'lucide-react';
import { format, subDays, subMonths, startOfMonth, parseISO } from 'date-fns';
import { cn } from '../../lib/utils';
import { pillars, stages, horizons, type MaturityStage } from '../../data/taxonomy';

// ============================================================================
// Type Definitions
// ============================================================================

export interface AnalyticsFiltersState {
  /** Selected pillar codes (e.g., ['CH', 'MC']) */
  selectedPillars: string[];
  /** Selected stage numbers (e.g., [1, 2, 3]) */
  selectedStages: number[];
  /** Time range preset or 'custom' */
  timeRange: TimeRangePreset;
  /** Custom date range (only used when timeRange is 'custom') */
  customDateRange: {
    start: string | null;
    end: string | null;
  };
}

export type TimeRangePreset =
  | '7d'
  | '30d'
  | '90d'
  | '6m'
  | '1y'
  | 'mtd'
  | 'ytd'
  | 'all'
  | 'custom';

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

const TIME_RANGE_OPTIONS: { value: TimeRangePreset; label: string; shortLabel: string }[] = [
  { value: '7d', label: 'Last 7 days', shortLabel: '7D' },
  { value: '30d', label: 'Last 30 days', shortLabel: '30D' },
  { value: '90d', label: 'Last 90 days', shortLabel: '90D' },
  { value: '6m', label: 'Last 6 months', shortLabel: '6M' },
  { value: '1y', label: 'Last year', shortLabel: '1Y' },
  { value: 'mtd', label: 'Month to date', shortLabel: 'MTD' },
  { value: 'ytd', label: 'Year to date', shortLabel: 'YTD' },
  { value: 'all', label: 'All time', shortLabel: 'All' },
  { value: 'custom', label: 'Custom range', shortLabel: 'Custom' },
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
export function getDateRangeFromPreset(preset: TimeRangePreset): { start: string; end: string } | null {
  const now = new Date();
  const endDate = format(now, 'yyyy-MM-dd');

  switch (preset) {
    case '7d':
      return { start: format(subDays(now, 7), 'yyyy-MM-dd'), end: endDate };
    case '30d':
      return { start: format(subDays(now, 30), 'yyyy-MM-dd'), end: endDate };
    case '90d':
      return { start: format(subDays(now, 90), 'yyyy-MM-dd'), end: endDate };
    case '6m':
      return { start: format(subMonths(now, 6), 'yyyy-MM-dd'), end: endDate };
    case '1y':
      return { start: format(subMonths(now, 12), 'yyyy-MM-dd'), end: endDate };
    case 'mtd':
      return { start: format(startOfMonth(now), 'yyyy-MM-dd'), end: endDate };
    case 'ytd':
      return { start: format(new Date(now.getFullYear(), 0, 1), 'yyyy-MM-dd'), end: endDate };
    case 'all':
      return null;
    case 'custom':
      return null;
    default:
      return null;
  }
}

/**
 * Get pillar color classes
 */
function getPillarColorClasses(pillarCode: string): { bg: string; text: string; border: string } {
  const colorMap: Record<string, { bg: string; text: string; border: string }> = {
    CH: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-800 dark:text-green-200', border: 'border-green-400' },
    EW: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-800 dark:text-blue-200', border: 'border-blue-400' },
    HG: { bg: 'bg-indigo-100 dark:bg-indigo-900/30', text: 'text-indigo-800 dark:text-indigo-200', border: 'border-indigo-400' },
    HH: { bg: 'bg-pink-100 dark:bg-pink-900/30', text: 'text-pink-800 dark:text-pink-200', border: 'border-pink-400' },
    MC: { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-800 dark:text-amber-200', border: 'border-amber-400' },
    PS: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-800 dark:text-red-200', border: 'border-red-400' },
  };
  return colorMap[pillarCode] || { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-400' };
}

/**
 * Get stage/horizon color classes
 */
function getHorizonColorClasses(horizonCode: string): { bg: string; text: string } {
  const colorMap: Record<string, { bg: string; text: string }> = {
    H1: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-800 dark:text-green-200' },
    H2: { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-800 dark:text-amber-200' },
    H3: { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-800 dark:text-purple-200' },
  };
  return colorMap[horizonCode] || { bg: 'bg-gray-100', text: 'text-gray-800' };
}

// ============================================================================
// Default Filter State
// ============================================================================

export const DEFAULT_ANALYTICS_FILTERS: AnalyticsFiltersState = {
  selectedPillars: [],
  selectedStages: [],
  timeRange: '30d',
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
  align?: 'left' | 'right';
  className?: string;
}

const Dropdown: React.FC<DropdownProps> = ({
  trigger,
  children,
  isOpen,
  onOpenChange,
  align = 'left',
  className,
}) => {
  return (
    <div className={cn('relative', className)}>
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
              'absolute z-20 mt-2 w-64 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 max-h-80 overflow-y-auto',
              align === 'left' ? 'left-0' : 'right-0'
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
            'inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors',
            'text-sm font-medium',
            hasSelection
              ? 'bg-brand-blue/10 border-brand-blue text-brand-blue'
              : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300',
            'hover:bg-gray-50 dark:hover:bg-gray-700',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <Filter className="h-4 w-4" />
          <span>Pillars</span>
          {hasSelection && (
            <span className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 rounded-full bg-brand-blue text-white text-xs">
              {selectedPillars.length}
            </span>
          )}
          <ChevronDown className={cn('h-4 w-4 transition-transform', isOpen && 'rotate-180')} />
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
              'w-full flex items-center gap-3 px-3 py-2 text-left transition-colors',
              'hover:bg-gray-50 dark:hover:bg-gray-700/50',
              isSelected && colors.bg
            )}
          >
            <span
              className={cn(
                'flex items-center justify-center w-6 h-6 rounded border',
                isSelected
                  ? cn(colors.bg, colors.border, colors.text)
                  : 'border-gray-300 dark:border-gray-600'
              )}
            >
              {isSelected && <Check className="h-4 w-4" />}
            </span>
            <div className="flex items-center gap-2 flex-1 min-w-0">
              {Icon && (
                <Icon className={cn('h-4 w-4 shrink-0', isSelected ? colors.text : 'text-gray-400')} />
              )}
              <div className="min-w-0">
                <div className={cn('text-sm font-medium truncate', isSelected ? colors.text : 'text-gray-900 dark:text-white')}>
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
// Stage Filter Dropdown
// ============================================================================

interface StageFilterDropdownProps {
  selectedStages: number[];
  onToggleStage: (stageNum: number) => void;
  onClearAll: () => void;
  disabled?: boolean;
}

const StageFilterDropdown: React.FC<StageFilterDropdownProps> = ({
  selectedStages,
  onToggleStage,
  onClearAll,
  disabled,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const hasSelection = selectedStages.length > 0;

  // Group stages by horizon
  const stagesByHorizon = useMemo(() => {
    const grouped: Record<string, MaturityStage[]> = { H3: [], H2: [], H1: [] };
    stages.forEach((stage) => {
      grouped[stage.horizon].push(stage);
    });
    return grouped;
  }, []);

  return (
    <Dropdown
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      trigger={
        <button
          disabled={disabled}
          className={cn(
            'inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors',
            'text-sm font-medium',
            hasSelection
              ? 'bg-brand-blue/10 border-brand-blue text-brand-blue'
              : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300',
            'hover:bg-gray-50 dark:hover:bg-gray-700',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <span>Stages</span>
          {hasSelection && (
            <span className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 rounded-full bg-brand-blue text-white text-xs">
              {selectedStages.length}
            </span>
          )}
          <ChevronDown className={cn('h-4 w-4 transition-transform', isOpen && 'rotate-180')} />
        </button>
      }
    >
      {/* Header with clear action */}
      <div className="flex items-center justify-between px-3 pb-2 mb-2 border-b border-gray-200 dark:border-gray-700">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          Maturity Stages
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

      {/* Stages grouped by horizon */}
      {(['H3', 'H2', 'H1'] as const).map((horizonCode) => {
        const horizon = horizons.find((h) => h.code === horizonCode);
        const horizonStages = stagesByHorizon[horizonCode];
        const colors = getHorizonColorClasses(horizonCode);

        if (horizonStages.length === 0) return null;

        return (
          <div key={horizonCode} className="mb-2">
            <div className={cn('px-3 py-1 text-xs font-medium', colors.text)}>
              {horizon?.name} ({horizon?.timeframe})
            </div>
            {horizonStages.map((stage) => {
              const isSelected = selectedStages.includes(stage.stage);

              return (
                <button
                  key={stage.stage}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleStage(stage.stage);
                  }}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-1.5 text-left transition-colors',
                    'hover:bg-gray-50 dark:hover:bg-gray-700/50',
                    isSelected && colors.bg
                  )}
                >
                  <span
                    className={cn(
                      'flex items-center justify-center w-5 h-5 rounded text-xs font-semibold border',
                      isSelected
                        ? cn(colors.bg, colors.text, 'border-current')
                        : 'border-gray-300 dark:border-gray-600 text-gray-500'
                    )}
                  >
                    {isSelected ? <Check className="h-3 w-3" /> : stage.stage}
                  </span>
                  <span className={cn('text-sm', isSelected ? colors.text : 'text-gray-700 dark:text-gray-300')}>
                    {stage.name}
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
  const [showCustomInputs, setShowCustomInputs] = useState(timeRange === 'custom');

  const currentOption = TIME_RANGE_OPTIONS.find((opt) => opt.value === timeRange);

  const handleTimeRangeSelect = (value: TimeRangePreset) => {
    onTimeRangeChange(value);
    if (value === 'custom') {
      setShowCustomInputs(true);
    } else {
      setShowCustomInputs(false);
      setIsOpen(false);
    }
  };

  const displayLabel = useMemo(() => {
    if (timeRange === 'custom' && customDateRange.start && customDateRange.end) {
      try {
        const startStr = format(parseISO(customDateRange.start), 'MMM d');
        const endStr = format(parseISO(customDateRange.end), 'MMM d, yyyy');
        return `${startStr} - ${endStr}`;
      } catch {
        return 'Custom range';
      }
    }
    return currentOption?.label || 'Select range';
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
            'inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors',
            'text-sm font-medium',
            'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300',
            'hover:bg-gray-50 dark:hover:bg-gray-700',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <Calendar className="h-4 w-4" />
          <span className="max-w-[150px] truncate">{displayLabel}</span>
          <ChevronDown className={cn('h-4 w-4 transition-transform', isOpen && 'rotate-180')} />
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
              'w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors',
              'hover:bg-gray-50 dark:hover:bg-gray-700/50',
              timeRange === option.value && 'bg-brand-blue/10 text-brand-blue'
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
                value={customDateRange.start || ''}
                onChange={(e) => onCustomDateChange(e.target.value || null, customDateRange.end)}
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  'w-full px-2.5 py-1.5 rounded-md border text-sm',
                  'border-gray-300 dark:border-gray-600',
                  'bg-white dark:bg-gray-700',
                  'text-gray-900 dark:text-white',
                  'focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent'
                )}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                End date
              </label>
              <input
                type="date"
                value={customDateRange.end || ''}
                onChange={(e) => onCustomDateChange(customDateRange.start, e.target.value || null)}
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  'w-full px-2.5 py-1.5 rounded-md border text-sm',
                  'border-gray-300 dark:border-gray-600',
                  'bg-white dark:bg-gray-700',
                  'text-gray-900 dark:text-white',
                  'focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent'
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
  onRemoveStage: (stageNum: number) => void;
  onClearAll: () => void;
}

const ActiveFilters: React.FC<ActiveFiltersProps> = ({
  filters,
  onRemovePillar,
  onRemoveStage,
  onClearAll,
}) => {
  const hasActiveFilters = filters.selectedPillars.length > 0 || filters.selectedStages.length > 0;

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
              'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors',
              colors.bg,
              colors.text,
              'hover:opacity-80'
            )}
          >
            {pillar?.code || pillarCode}
            <X className="h-3 w-3" />
          </button>
        );
      })}

      {/* Stage chips */}
      {filters.selectedStages.map((stageNum) => {
        const stage = stages.find((s) => s.stage === stageNum);
        const colors = stage ? getHorizonColorClasses(stage.horizon) : { bg: 'bg-gray-100', text: 'text-gray-800' };

        return (
          <button
            key={stageNum}
            onClick={() => onRemoveStage(stageNum)}
            className={cn(
              'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors',
              colors.bg,
              colors.text,
              'hover:opacity-80'
            )}
          >
            S{stageNum}: {stage?.name || 'Unknown'}
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
    [filters, onFiltersChange]
  );

  const handleClearPillars = useCallback(() => {
    onFiltersChange({ ...filters, selectedPillars: [] });
  }, [filters, onFiltersChange]);

  const handleToggleStage = useCallback(
    (stageNum: number) => {
      const newSelection = filters.selectedStages.includes(stageNum)
        ? filters.selectedStages.filter((s) => s !== stageNum)
        : [...filters.selectedStages, stageNum];
      onFiltersChange({ ...filters, selectedStages: newSelection });
    },
    [filters, onFiltersChange]
  );

  const handleClearStages = useCallback(() => {
    onFiltersChange({ ...filters, selectedStages: [] });
  }, [filters, onFiltersChange]);

  const handleTimeRangeChange = useCallback(
    (range: TimeRangePreset) => {
      onFiltersChange({
        ...filters,
        timeRange: range,
        customDateRange: range !== 'custom' ? { start: null, end: null } : filters.customDateRange,
      });
    },
    [filters, onFiltersChange]
  );

  const handleCustomDateChange = useCallback(
    (start: string | null, end: string | null) => {
      onFiltersChange({
        ...filters,
        customDateRange: { start, end },
      });
    },
    [filters, onFiltersChange]
  );

  const handleRemovePillar = useCallback(
    (pillarCode: string) => {
      onFiltersChange({
        ...filters,
        selectedPillars: filters.selectedPillars.filter((p) => p !== pillarCode),
      });
    },
    [filters, onFiltersChange]
  );

  const handleRemoveStage = useCallback(
    (stageNum: number) => {
      onFiltersChange({
        ...filters,
        selectedStages: filters.selectedStages.filter((s) => s !== stageNum),
      });
    },
    [filters, onFiltersChange]
  );

  const handleClearAll = useCallback(() => {
    onFiltersChange({
      ...DEFAULT_ANALYTICS_FILTERS,
      timeRange: filters.timeRange,
      customDateRange: filters.customDateRange,
    });
  }, [filters, onFiltersChange]);

  return (
    <div className={cn('', className)}>
      <div
        className={cn(
          'flex flex-wrap items-center gap-2',
          compact ? 'gap-2' : 'gap-3'
        )}
      >
        {/* Pillar filter */}
        <PillarFilterDropdown
          selectedPillars={filters.selectedPillars}
          onTogglePillar={handleTogglePillar}
          onClearAll={handleClearPillars}
          disabled={disabled}
        />

        {/* Stage filter */}
        <StageFilterDropdown
          selectedStages={filters.selectedStages}
          onToggleStage={handleToggleStage}
          onClearAll={handleClearStages}
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
          onRemoveStage={handleRemoveStage}
          onClearAll={handleClearAll}
        />
      )}
    </div>
  );
};

export default AnalyticsFilters;
