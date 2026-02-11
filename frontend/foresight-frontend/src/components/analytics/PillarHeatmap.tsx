/**
 * PillarHeatmap Component
 *
 * Horizontal bar chart displaying card distribution across the 6 strategic pillars.
 * Redesigned from heatmap for better clarity and UX.
 *
 * Features:
 * - Clear horizontal bar visualization
 * - Clickable bars with visual affordances
 * - Tooltip showing full pillar name and stats
 * - Responsive design
 * - Empty/loading states
 */

import React, { useState } from "react";
import { pillars } from "../../data/taxonomy";
import { Filter } from "lucide-react";

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Coverage data for a single pillar (matches backend PillarCoverageItem)
 */
export interface PillarCoverageItem {
  pillar_code: string;
  pillar_name: string;
  count: number;
  percentage: number;
  avg_velocity?: number | null;
  trend_direction?: "up" | "down" | "stable" | null;
}

/**
 * Props for the PillarHeatmap component
 */
export interface PillarHeatmapProps {
  /** Coverage data for each pillar */
  data: PillarCoverageItem[];
  /** Whether data is currently loading */
  loading?: boolean;
  /** Optional height override (default: 300) */
  height?: number;
  /** Optional title for the heatmap */
  title?: string;
  /** Callback when a pillar cell is clicked */
  onPillarClick?: (pillarCode: string) => void;
  /** Whether to show maturity stages on Y-axis (deprecated, kept for compatibility) */
  showStages?: boolean;
  /** Stage breakdown data (deprecated, kept for compatibility) */
  stageBreakdown?: Record<string, Record<number, number>>;
}

// ============================================================================
// Component
// ============================================================================

export const PillarHeatmap: React.FC<PillarHeatmapProps> = ({
  data,
  loading = false,
  height = 300,
  title,
  onPillarClick,
  showStages: _showStages = false,
  stageBreakdown: _stageBreakdown,
}) => {
  const [hoveredPillar, setHoveredPillar] = useState<string | null>(null);

  // Build a map of pillar data for quick lookup
  const pillarDataMap: Record<string, PillarCoverageItem> = {};
  data.forEach((item) => {
    pillarDataMap[item.pillar_code] = item;
  });

  // Calculate maximum count for bar scaling
  const maxCount = Math.max(...data.map((item) => item.count), 1);

  // Loading state
  if (loading) {
    return (
      <div
        className="w-full bg-white dark:bg-[#2d3166] rounded-lg shadow p-6"
        style={{ minHeight: height }}
      >
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            {title}
          </h3>
        )}
        <div
          className="flex items-center justify-center"
          style={{ height: height - 80 }}
        >
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue"></div>
        </div>
      </div>
    );
  }

  // Empty state
  if (data.length === 0) {
    return (
      <div
        className="w-full bg-white dark:bg-[#2d3166] rounded-lg shadow p-6"
        style={{ minHeight: height }}
      >
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            {title}
          </h3>
        )}
        <div
          className="flex items-center justify-center text-gray-500 dark:text-gray-400"
          style={{ height: height - 80 }}
        >
          No data available for selected filters
        </div>
      </div>
    );
  }

  return (
    <div
      className="w-full bg-white dark:bg-[#2d3166] rounded-lg shadow p-6"
      style={{ minHeight: height }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
        )}
        {onPillarClick && (
          <span className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
            <Filter className="h-3 w-3" />
            Click to filter
          </span>
        )}
      </div>

      {/* Explanatory text */}
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Signal distribution across strategic pillars
      </p>

      {/* Horizontal bar chart */}
      <div className="space-y-3">
        {pillars.map((pillar) => {
          const cellData = pillarDataMap[pillar.code];
          const count = cellData?.count ?? 0;
          const percentage = cellData?.percentage ?? 0;
          const avgVelocity = cellData?.avg_velocity;
          const barWidth = maxCount > 0 ? (count / maxCount) * 100 : 0;
          const isHovered = hoveredPillar === pillar.code;
          const isClickable = !!onPillarClick;

          return (
            <div
              key={pillar.code}
              className={`group relative ${isClickable ? "cursor-pointer" : ""}`}
              onMouseEnter={() => setHoveredPillar(pillar.code)}
              onMouseLeave={() => setHoveredPillar(null)}
              onClick={() => onPillarClick && onPillarClick(pillar.code)}
            >
              {/* Row with pillar info and bar */}
              <div className="flex items-center gap-3">
                {/* Pillar label */}
                <div className="w-10 flex-shrink-0">
                  <span
                    className={`inline-flex items-center justify-center w-10 h-6 rounded text-xs font-bold text-white transition-transform ${
                      isClickable && isHovered ? "scale-105" : ""
                    }`}
                    style={{ backgroundColor: pillar.color }}
                  >
                    {pillar.code}
                  </span>
                </div>

                {/* Bar container */}
                <div className="flex-1 relative">
                  {/* Background track */}
                  <div className="h-8 bg-gray-100 dark:bg-gray-700 rounded-md overflow-hidden">
                    {/* Filled bar */}
                    <div
                      className={`h-full rounded-md transition-all duration-300 ${
                        isClickable && isHovered ? "opacity-90" : "opacity-100"
                      }`}
                      style={{
                        width: `${Math.max(barWidth, 2)}%`,
                        backgroundColor: pillar.color,
                      }}
                    />
                  </div>

                  {/* Count overlay on bar */}
                  <div className="absolute inset-0 flex items-center px-3">
                    <span
                      className={`text-sm font-semibold ${
                        barWidth > 30
                          ? "text-white"
                          : "text-gray-700 dark:text-gray-300"
                      }`}
                    >
                      {count} signals
                    </span>
                  </div>
                </div>

                {/* Percentage */}
                <div className="w-16 text-right flex-shrink-0">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
                    {percentage.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Hover tooltip with full name */}
              {isHovered && (
                <div className="absolute left-14 -top-8 z-10 bg-gray-900 dark:bg-gray-800 text-white text-xs px-3 py-2 rounded-lg shadow-lg whitespace-nowrap">
                  <div className="font-semibold">{pillar.name}</div>
                  {avgVelocity !== null && avgVelocity !== undefined && (
                    <div className="text-gray-300">
                      Avg. Velocity: {avgVelocity.toFixed(0)}
                    </div>
                  )}
                  {isClickable && (
                    <div className="text-blue-300 mt-1">
                      Click to filter by this pillar
                    </div>
                  )}
                  {/* Arrow */}
                  <div className="absolute left-4 -bottom-1 w-2 h-2 bg-gray-900 dark:bg-gray-800 rotate-45" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary footer */}
      <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700 flex justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>Total: {data.reduce((sum, d) => sum + d.count, 0)} signals</span>
        <span>{pillars.length} strategic pillars</span>
      </div>
    </div>
  );
};

export default PillarHeatmap;
