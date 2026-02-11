/**
 * ScoreTimelineChart Component
 *
 * Displays a timeline chart showing the evolution of card scores over time.
 * Uses Recharts to visualize all 7 score dimensions (maturity, velocity, novelty,
 * impact, relevance, risk, opportunity) with color-coded lines.
 *
 * Features:
 * - 7 distinct score lines with consistent color scheme
 * - Date-formatted X-axis with adaptive tick spacing
 * - Y-axis fixed at 0-100 range
 * - Interactive tooltips on hover showing all scores
 * - Legend for score type identification
 * - Empty state for insufficient data (<2 points)
 * - Performance optimization: animations disabled for large datasets (>365 points)
 */

import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  TooltipProps,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { TrendingUp, AlertCircle } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { ScoreHistory } from '../../lib/discovery-api';

// ============================================================================
// Type Definitions
// ============================================================================

export interface ScoreTimelineChartProps {
  /** Historical score data array */
  data: ScoreHistory[];
  /** Optional title for the chart section */
  title?: string;
  /** Height of the chart container in pixels */
  height?: number;
  /** Additional className for container */
  className?: string;
  /** Whether the data is currently loading */
  loading?: boolean;
  /** Error message to display */
  error?: string | null;
  /** Callback when retry is clicked (for error state) */
  onRetry?: () => void;
  /** Which score types to show (defaults to all) */
  visibleScores?: ScoreType[];
  /** Compact mode for sidebar display - hides legend, smaller text */
  compact?: boolean;
}

/**
 * Score type identifier
 */
export type ScoreType =
  | 'maturity_score'
  | 'velocity_score'
  | 'novelty_score'
  | 'impact_score'
  | 'relevance_score'
  | 'risk_score'
  | 'opportunity_score';

// ============================================================================
// Score Configuration
// ============================================================================

/**
 * Configuration for each score type including display name, color, and description
 */
interface ScoreConfig {
  key: ScoreType;
  name: string;
  color: string;
  description: string;
}

const SCORE_CONFIGS: ScoreConfig[] = [
  {
    key: 'maturity_score',
    name: 'Maturity',
    color: '#8884d8', // Purple
    description: 'Technology or trend readiness level',
  },
  {
    key: 'velocity_score',
    name: 'Velocity',
    color: '#82ca9d', // Green
    description: 'Rate of change and momentum',
  },
  {
    key: 'novelty_score',
    name: 'Novelty',
    color: '#ffc658', // Yellow/Gold
    description: 'How new or innovative the trend is',
  },
  {
    key: 'impact_score',
    name: 'Impact',
    color: '#ff7c43', // Orange
    description: 'Potential effect on operations or strategy',
  },
  {
    key: 'relevance_score',
    name: 'Relevance',
    color: '#00bcd4', // Cyan
    description: 'Alignment with organizational priorities',
  },
  {
    key: 'risk_score',
    name: 'Risk',
    color: '#ef5350', // Red
    description: 'Associated risks and challenges',
  },
  {
    key: 'opportunity_score',
    name: 'Opportunity',
    color: '#66bb6a', // Light Green
    description: 'Potential for positive outcomes',
  },
];

/**
 * Get the configuration for a specific score type
 */
function getScoreConfig(scoreType: ScoreType): ScoreConfig | undefined {
  return SCORE_CONFIGS.find((config) => config.key === scoreType);
}

// ============================================================================
// Chart Data Transformation
// ============================================================================

/**
 * Transform score history data for Recharts
 * - Sorts by date ascending
 * - Formats dates for display
 * - Handles null values
 */
interface ChartDataPoint {
  date: string;
  dateLabel: string;
  timestamp: number;
  maturity_score: number | null;
  velocity_score: number | null;
  novelty_score: number | null;
  impact_score: number | null;
  relevance_score: number | null;
  risk_score: number | null;
  opportunity_score: number | null;
}

function transformScoreData(data: ScoreHistory[]): ChartDataPoint[] {
  return [...data]
    .sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime())
    .map((record) => ({
      date: record.recorded_at,
      dateLabel: format(parseISO(record.recorded_at), 'MMM d, yyyy'),
      timestamp: new Date(record.recorded_at).getTime(),
      maturity_score: record.maturity_score,
      velocity_score: record.velocity_score,
      novelty_score: record.novelty_score,
      impact_score: record.impact_score,
      relevance_score: record.relevance_score,
      risk_score: record.risk_score,
      opportunity_score: record.opportunity_score,
    }));
}

// ============================================================================
// Custom Tooltip Component
// ============================================================================

interface CustomTooltipProps extends TooltipProps<number, string> {
  visibleScores: ScoreType[];
}

function CustomTooltip({ active, payload, label, visibleScores }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  // Get the date label from the first payload item
  const firstPayload = payload[0]?.payload as ChartDataPoint | undefined;
  const dateLabel = firstPayload?.dateLabel || label;

  return (
    <div className="bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3 min-w-[180px]">
      <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-2 pb-2 border-b border-gray-200 dark:border-gray-700">
        {dateLabel}
      </div>
      <div className="space-y-1.5">
        {payload
          .filter((item) => visibleScores.includes(item.dataKey as ScoreType))
          .map((item) => {
            const config = getScoreConfig(item.dataKey as ScoreType);
            const value = item.value;
            return (
              <div key={item.dataKey} className="flex items-center justify-between gap-4 text-xs">
                <div className="flex items-center gap-2">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-gray-600 dark:text-gray-300">
                    {config?.name || item.dataKey}
                  </span>
                </div>
                <span
                  className={cn(
                    'font-medium',
                    value !== null && value !== undefined
                      ? 'text-gray-900 dark:text-gray-100'
                      : 'text-gray-400 dark:text-gray-500'
                  )}
                >
                  {value !== null && value !== undefined ? Math.round(value) : '-'}
                </span>
              </div>
            );
          })}
      </div>
    </div>
  );
}

// ============================================================================
// Empty State Component
// ============================================================================

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-center px-4">
      <TrendingUp className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-3" />
      <p className="text-gray-500 dark:text-gray-400 text-sm font-medium">
        {message}
      </p>
      <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">
        Score history will appear here once more data is available
      </p>
    </div>
  );
}

// ============================================================================
// Loading State Component
// ============================================================================

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[200px]">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue mb-3" />
      <p className="text-gray-500 dark:text-gray-400 text-sm">Loading score history...</p>
    </div>
  );
}

// ============================================================================
// Error State Component
// ============================================================================

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-center px-4">
      <AlertCircle className="h-12 w-12 text-red-400 mb-3" />
      <p className="text-red-600 dark:text-red-400 text-sm font-medium mb-2">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-brand-blue hover:text-brand-dark-blue text-sm underline"
        >
          Try again
        </button>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ScoreTimelineChart - Visualize card score evolution over time
 */
export function ScoreTimelineChart({
  data,
  title = 'Score History',
  height = 350,
  className,
  loading = false,
  error = null,
  onRetry,
  visibleScores,
  compact = false,
}: ScoreTimelineChartProps) {
  // Determine which scores to display (default: all)
  const activeScores: ScoreType[] = useMemo(() => {
    if (visibleScores && visibleScores.length > 0) {
      return visibleScores;
    }
    return SCORE_CONFIGS.map((config) => config.key);
  }, [visibleScores]);

  // Transform data for Recharts
  const chartData = useMemo(() => transformScoreData(data), [data]);

  // Determine if animations should be disabled (large dataset)
  const shouldAnimate = chartData.length <= 365;

  // Format X-axis ticks based on data range
  const formatXAxisTick = (value: string) => {
    try {
      const date = parseISO(value);
      // Adaptive formatting based on data range
      if (chartData.length > 90) {
        return format(date, 'MMM yyyy');
      }
      if (chartData.length > 30) {
        return format(date, 'MMM d');
      }
      return format(date, 'MMM d');
    } catch {
      return value;
    }
  };

  // Show loading state
  if (loading) {
    return (
      <div className={cn('bg-white dark:bg-dark-surface rounded-lg shadow p-6', className)}>
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-brand-blue" />
            {title}
          </h3>
        )}
        <div style={{ height }}>
          <LoadingState />
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className={cn('bg-white dark:bg-dark-surface rounded-lg shadow p-6', className)}>
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-brand-blue" />
            {title}
          </h3>
        )}
        <div style={{ height }}>
          <ErrorState message={error} onRetry={onRetry} />
        </div>
      </div>
    );
  }

  // Show empty state if insufficient data
  if (chartData.length < 2) {
    return (
      <div className={cn('bg-white dark:bg-dark-surface rounded-lg shadow p-6', className)}>
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-brand-blue" />
            {title}
          </h3>
        )}
        <div style={{ height }}>
          <EmptyState message="Not enough data to show trend" />
        </div>
      </div>
    );
  }

  return (
    <div className={cn('bg-white dark:bg-dark-surface rounded-lg shadow', compact ? 'p-4' : 'p-6', className)}>
      {title && (
        <h3 className={cn(
          'font-semibold text-gray-900 dark:text-white flex items-center gap-2',
          compact ? 'text-sm mb-2' : 'text-lg mb-4'
        )}>
          <TrendingUp className={compact ? 'h-4 w-4 text-brand-blue' : 'h-5 w-5 text-brand-blue'} />
          {title}
        </h3>
      )}
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={compact ? { top: 5, right: 5, left: -20, bottom: 0 } : { top: 5, right: 20, left: 0, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="currentColor"
              className="text-gray-200 dark:text-gray-700"
              opacity={0.5}
            />
            <XAxis
              dataKey="date"
              tickFormatter={formatXAxisTick}
              tick={{ fontSize: compact ? 9 : 11 }}
              tickLine={{ stroke: 'currentColor' }}
              axisLine={{ stroke: 'currentColor' }}
              className="text-gray-500 dark:text-gray-400"
              interval="preserveStartEnd"
              minTickGap={compact ? 30 : 50}
              hide={compact}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: compact ? 9 : 11 }}
              tickLine={{ stroke: 'currentColor' }}
              axisLine={{ stroke: 'currentColor' }}
              className="text-gray-500 dark:text-gray-400"
              tickCount={compact ? 3 : 6}
              width={compact ? 25 : 40}
            />
            <Tooltip
              content={<CustomTooltip visibleScores={activeScores} />}
              cursor={{
                stroke: 'currentColor',
                className: 'text-gray-300 dark:text-gray-600',
                strokeDasharray: '3 3',
              }}
            />
            {!compact && (
              <Legend
                wrapperStyle={{ paddingTop: '20px' }}
                iconType="circle"
                iconSize={8}
                formatter={(value) => {
                  const config = SCORE_CONFIGS.find((c) => c.key === value);
                  return (
                    <span className="text-xs text-gray-600 dark:text-gray-300">
                      {config?.name || value}
                    </span>
                  );
                }}
              />
            )}
            {SCORE_CONFIGS.filter((config) => activeScores.includes(config.key)).map((config) => (
              <Line
                key={config.key}
                type="monotone"
                dataKey={config.key}
                name={config.key}
                stroke={config.color}
                strokeWidth={2}
                dot={chartData.length <= 30}
                activeDot={{ r: 5, strokeWidth: 2 }}
                isAnimationActive={shouldAnimate}
                animationDuration={500}
                connectNulls={true}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// Export score configuration for use in other components
export { SCORE_CONFIGS, getScoreConfig };

export default ScoreTimelineChart;
