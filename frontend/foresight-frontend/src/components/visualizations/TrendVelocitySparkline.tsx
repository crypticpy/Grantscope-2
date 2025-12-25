/**
 * TrendVelocitySparkline Component
 *
 * A compact sparkline chart showing velocity trend at a glance.
 * Displays velocity_score trend over the last 30 days without axes.
 * Used inline in card detail views and card list items.
 */

import React, { useMemo } from 'react';
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts';
import { cn } from '../../lib/utils';
import type { ScoreHistory } from '../../lib/discovery-api';
import { subDays, isAfter, parseISO, format } from 'date-fns';

export interface TrendVelocitySparklineProps {
  /** Historical score data to visualize */
  data: ScoreHistory[];
  /** Width of the sparkline container (default: 80px) */
  width?: number | string;
  /** Height of the sparkline container (default: 24px) */
  height?: number | string;
  /** Line color (default: #22c55e - green) */
  strokeColor?: string;
  /** Line stroke width (default: 2) */
  strokeWidth?: number;
  /** Whether to show a tooltip on hover */
  showTooltip?: boolean;
  /** Additional className for the container */
  className?: string;
  /** Minimum data points required to render (default: 2) */
  minDataPoints?: number;
  /** Days to look back for data (default: 30) */
  daysToShow?: number;
}

/**
 * Custom tooltip for sparkline hover
 */
function SparklineTooltip({ active, payload }: { active?: boolean; payload?: { value: number; payload: { recorded_at: string } }[] }) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const value = payload[0]?.value;
  const date = payload[0]?.payload?.recorded_at;

  return (
    <div className="bg-gray-900/95 text-white text-[10px] px-1.5 py-1 rounded shadow-lg">
      <div className="font-medium">{value?.toFixed(0)}</div>
      {date && (
        <div className="text-gray-400 text-[9px]">
          {format(parseISO(date), 'MMM d')}
        </div>
      )}
    </div>
  );
}

/**
 * Filters data to the last N days and prepares it for the chart
 */
function prepareChartData(
  data: ScoreHistory[],
  daysToShow: number
): { recorded_at: string; velocity_score: number }[] {
  const cutoffDate = subDays(new Date(), daysToShow);

  return data
    .filter((item) => {
      // Filter to records within the date range
      const recordDate = parseISO(item.recorded_at);
      return isAfter(recordDate, cutoffDate);
    })
    .filter((item) => item.velocity_score !== null && item.velocity_score !== undefined)
    .map((item) => ({
      recorded_at: item.recorded_at,
      velocity_score: item.velocity_score as number,
    }))
    .sort((a, b) => parseISO(a.recorded_at).getTime() - parseISO(b.recorded_at).getTime());
}

/**
 * Calculate trend direction for accessibility
 */
function getTrendDirection(data: { velocity_score: number }[]): 'up' | 'down' | 'stable' {
  if (data.length < 2) return 'stable';

  const first = data[0].velocity_score;
  const last = data[data.length - 1].velocity_score;
  const diff = last - first;

  if (Math.abs(diff) < 5) return 'stable';
  return diff > 0 ? 'up' : 'down';
}

/**
 * TrendVelocitySparkline component
 *
 * Renders a compact sparkline showing velocity trend over time.
 * Designed to be used inline in card metadata sections.
 */
export function TrendVelocitySparkline({
  data,
  width = 80,
  height = 24,
  strokeColor = '#22c55e', // green-500
  strokeWidth = 2,
  showTooltip = true,
  className,
  minDataPoints = 2,
  daysToShow = 30,
}: TrendVelocitySparklineProps) {
  // Prepare chart data - filter to last 30 days and sort
  const chartData = useMemo(
    () => prepareChartData(data, daysToShow),
    [data, daysToShow]
  );

  // Calculate trend for accessibility
  const trendDirection = useMemo(
    () => getTrendDirection(chartData),
    [chartData]
  );

  // Handle insufficient data
  if (chartData.length < minDataPoints) {
    return (
      <div
        className={cn(
          'inline-flex items-center justify-center text-[10px] text-gray-400',
          className
        )}
        style={{ width, height }}
        role="img"
        aria-label="Insufficient data for velocity trend"
      >
        <span className="opacity-60">No trend data</span>
      </div>
    );
  }

  // Calculate domain for Y axis (with padding)
  const velocityValues = chartData.map((d) => d.velocity_score);
  const minValue = Math.max(0, Math.min(...velocityValues) - 5);
  const maxValue = Math.min(100, Math.max(...velocityValues) + 5);

  return (
    <div
      className={cn('inline-flex items-center', className)}
      style={{ width, height }}
      role="img"
      aria-label={`Velocity trend over ${daysToShow} days: ${trendDirection === 'up' ? 'increasing' : trendDirection === 'down' ? 'decreasing' : 'stable'}. Current value: ${chartData[chartData.length - 1]?.velocity_score?.toFixed(0) ?? 'unknown'}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={chartData}
          margin={{ top: 2, right: 2, bottom: 2, left: 2 }}
        >
          {showTooltip && (
            <Tooltip
              content={<SparklineTooltip />}
              cursor={false}
              wrapperStyle={{ outline: 'none' }}
            />
          )}
          <Line
            type="monotone"
            dataKey="velocity_score"
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            dot={false}
            isAnimationActive={false}
            // Use calculated domain for better visualization
            yAxisId={0}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Compact variant specifically for card list items
 * Smaller size and no tooltip for better performance in lists
 */
export function TrendVelocitySparklineCompact({
  data,
  className,
}: Pick<TrendVelocitySparklineProps, 'data' | 'className'>) {
  return (
    <TrendVelocitySparkline
      data={data}
      width={60}
      height={20}
      showTooltip={false}
      strokeWidth={1.5}
      className={className}
    />
  );
}

/**
 * Loading placeholder for sparkline
 * Shows a subtle pulsing animation while data is loading
 */
export function TrendVelocitySparklineSkeleton({
  width = 80,
  height = 24,
  className,
}: Pick<TrendVelocitySparklineProps, 'width' | 'height' | 'className'>) {
  return (
    <div
      className={cn(
        'inline-flex items-center justify-center animate-pulse',
        className
      )}
      style={{ width, height }}
      role="status"
      aria-label="Loading velocity trend"
    >
      <div
        className="bg-gray-200 dark:bg-gray-700 rounded"
        style={{ width: '100%', height: '50%' }}
      />
    </div>
  );
}

export default TrendVelocitySparkline;
