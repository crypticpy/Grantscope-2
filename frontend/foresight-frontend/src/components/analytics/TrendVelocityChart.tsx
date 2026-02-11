/**
 * TrendVelocityChart Component
 *
 * Displays trend velocity data as a time-series line chart using Recharts.
 * Shows aggregated velocity metrics over time with optional week-over-week comparison.
 *
 * Features:
 * - Responsive container for dynamic sizing
 * - Custom tooltip with detailed metrics
 * - Loading and empty state handling
 * - Performance optimization for large datasets (animations disabled > 100 points)
 */

import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { format, parseISO } from "date-fns";
import { TrendingUp, TrendingDown, Minus, Loader2 } from "lucide-react";

// ============================================================================
// Type Definitions
// ============================================================================

export interface VelocityDataPoint {
  date: string;
  velocity: number;
  count: number;
  avg_velocity_score?: number | null;
}

export interface TrendVelocityChartProps {
  /** Time-series velocity data points */
  data: VelocityDataPoint[];
  /** Loading state indicator */
  isLoading?: boolean;
  /** Week-over-week change percentage */
  weekOverWeekChange?: number | null;
  /** Total cards analyzed in the period */
  totalCardsAnalyzed?: number;
  /** Chart height in pixels */
  height?: number;
  /** Period start date for display */
  periodStart?: string | null;
  /** Period end date for display */
  periodEnd?: string | null;
  /** Custom class name for container */
  className?: string;
}

// ============================================================================
// Custom Tooltip Component
// ============================================================================

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    value: number;
    dataKey: string;
    color: string;
    payload: VelocityDataPoint;
  }>;
  label?: string;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({
  active,
  payload,
  label,
}) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const dataPoint = payload[0]?.payload;
  if (!dataPoint) return null;

  let formattedDate = label || "";
  try {
    formattedDate = format(parseISO(dataPoint.date), "MMM dd, yyyy");
  } catch {
    formattedDate = dataPoint.date;
  }

  return (
    <div className="bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
      <p className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
        {formattedDate}
      </p>
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Total Velocity:
          </span>
          <span className="text-sm font-medium text-brand-blue">
            {dataPoint.velocity.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Signals:
          </span>
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            {dataPoint.count}
          </span>
        </div>
        {dataPoint.avg_velocity_score != null && (
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Avg Score:
            </span>
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              {dataPoint.avg_velocity_score.toFixed(1)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// Week-over-Week Change Badge
// ============================================================================

interface WoWChangeBadgeProps {
  change: number | null | undefined;
}

const WoWChangeBadge: React.FC<WoWChangeBadgeProps> = ({ change }) => {
  if (change == null) return null;

  const isPositive = change > 0;
  const isNeutral = change === 0;

  const Icon = isPositive ? TrendingUp : isNeutral ? Minus : TrendingDown;
  const colorClass = isPositive
    ? "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30"
    : isNeutral
      ? "text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-dark-surface"
      : "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30";

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium ${colorClass}`}
    >
      <Icon className="h-4 w-4" />
      <span>
        {isPositive ? "+" : ""}
        {change.toFixed(1)}%
      </span>
      <span className="text-xs opacity-75">WoW</span>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

export const TrendVelocityChart: React.FC<TrendVelocityChartProps> = ({
  data,
  isLoading = false,
  weekOverWeekChange,
  totalCardsAnalyzed,
  height = 400,
  periodStart,
  periodEnd,
  className = "",
}) => {
  // Format date labels for X-axis
  const formatXAxisDate = (dateStr: string): string => {
    try {
      return format(parseISO(dateStr), "MMM dd");
    } catch {
      return dateStr;
    }
  };

  // Calculate average velocity for reference line
  const avgVelocity =
    data.length > 0
      ? data.reduce((sum, point) => sum + point.velocity, 0) / data.length
      : 0;

  // Disable animations for large datasets (performance optimization)
  const disableAnimations = data.length > 100;

  // Loading state
  if (isLoading) {
    return (
      <div
        className={`flex flex-col items-center justify-center bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 ${className}`}
        style={{ height }}
      >
        <Loader2 className="h-8 w-8 animate-spin text-brand-blue" />
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          Loading velocity data...
        </p>
      </div>
    );
  }

  // Empty state
  if (data.length === 0) {
    return (
      <div
        className={`flex flex-col items-center justify-center bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 ${className}`}
        style={{ height }}
      >
        <TrendingUp className="h-12 w-12 text-gray-300 dark:text-gray-600" />
        <p className="mt-4 text-gray-500 dark:text-gray-400">
          No velocity data available for selected filters
        </p>
        <p className="text-sm text-gray-400 dark:text-gray-500">
          Try adjusting the date range or filters
        </p>
      </div>
    );
  }

  // Format period display
  let periodDisplay = "";
  try {
    if (periodStart && periodEnd) {
      const startFormatted = format(parseISO(periodStart), "MMM dd, yyyy");
      const endFormatted = format(parseISO(periodEnd), "MMM dd, yyyy");
      periodDisplay = `${startFormatted} - ${endFormatted}`;
    }
  } catch {
    // If parsing fails, don't show period
  }

  return (
    <div
      className={`bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 ${className}`}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Trend Velocity Over Time
          </h3>
          {periodDisplay && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {periodDisplay}
            </p>
          )}
        </div>
        <div className="flex items-center gap-4">
          {totalCardsAnalyzed != null && totalCardsAnalyzed > 0 && (
            <div className="text-sm text-gray-500 dark:text-gray-400">
              <span className="font-medium text-gray-900 dark:text-white">
                {totalCardsAnalyzed.toLocaleString()}
              </span>{" "}
              signals analyzed
            </div>
          )}
          <WoWChangeBadge change={weekOverWeekChange} />
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height - 80}>
        <LineChart
          data={data}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#e5e7eb"
            className="dark:stroke-gray-700"
          />
          <XAxis
            dataKey="date"
            tickFormatter={formatXAxisDate}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            tickLine={{ stroke: "#d1d5db" }}
            axisLine={{ stroke: "#d1d5db" }}
            interval="preserveStartEnd"
            minTickGap={50}
          />
          <YAxis
            tick={{ fontSize: 12, fill: "#6b7280" }}
            tickLine={{ stroke: "#d1d5db" }}
            axisLine={{ stroke: "#d1d5db" }}
            tickFormatter={(value) => value.toLocaleString()}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: "10px" }}
            formatter={(value) => (
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {value}
              </span>
            )}
          />
          {/* Average velocity reference line */}
          {avgVelocity > 0 && (
            <ReferenceLine
              y={avgVelocity}
              stroke="#9ca3af"
              strokeDasharray="5 5"
              label={{
                value: `Avg: ${avgVelocity.toFixed(0)}`,
                position: "right",
                fill: "#6b7280",
                fontSize: 11,
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="velocity"
            name="Total Velocity"
            stroke="#44499C"
            strokeWidth={2}
            dot={{ fill: "#44499C", strokeWidth: 2, r: 3 }}
            activeDot={{
              r: 6,
              fill: "#44499C",
              stroke: "#fff",
              strokeWidth: 2,
            }}
            animationDuration={disableAnimations ? 0 : 500}
          />
          <Line
            type="monotone"
            dataKey="count"
            name="Signal Count"
            stroke="#009F4D"
            strokeWidth={2}
            dot={{ fill: "#009F4D", strokeWidth: 2, r: 3 }}
            activeDot={{
              r: 6,
              fill: "#009F4D",
              stroke: "#fff",
              strokeWidth: 2,
            }}
            animationDuration={disableAnimations ? 0 : 500}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TrendVelocityChart;
