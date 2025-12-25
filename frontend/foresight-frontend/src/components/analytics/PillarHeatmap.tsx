/**
 * PillarHeatmap Component
 *
 * Custom SVG heatmap displaying activity distribution across the 6 strategic pillars.
 * Uses pillar colors from taxonomy and shows intensity based on card counts/percentages.
 *
 * Features:
 * - Custom SVG grid (Recharts doesn't provide native heatmap)
 * - Color intensity based on activity level
 * - Interactive tooltips on hover
 * - Responsive design with ResponsiveContainer
 * - Empty state handling
 * - Loading state support
 */

import React, { useState, useMemo } from 'react';
import { pillars, getPillarByCode, stages, type Pillar } from '../../data/taxonomy';

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
  trend_direction?: 'up' | 'down' | 'stable' | null;
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
  /** Whether to show maturity stages on Y-axis */
  showStages?: boolean;
  /** Stage breakdown data (pillar_code -> stage -> count) */
  stageBreakdown?: Record<string, Record<number, number>>;
}

/**
 * Tooltip content for hovered cell
 */
interface TooltipData {
  pillarCode: string;
  pillarName: string;
  count: number;
  percentage: number;
  avgVelocity?: number | null;
  trendDirection?: 'up' | 'down' | 'stable' | null;
  stage?: number;
  x: number;
  y: number;
}

// ============================================================================
// Constants
// ============================================================================

const CELL_PADDING = 4;
const LABEL_HEIGHT = 40;
const LEGEND_HEIGHT = 40;
const STAGE_LABEL_WIDTH = 80;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate color intensity based on value relative to max
 * Returns a value between 0.1 and 1.0 for non-zero values
 */
function calculateIntensity(value: number, maxValue: number): number {
  if (maxValue === 0 || value === 0) return 0.1;
  // Scale from 0.2 to 1.0 to ensure even low values are visible
  return 0.2 + (value / maxValue) * 0.8;
}

/**
 * Generate color with opacity based on pillar color and intensity
 */
function getColorWithIntensity(color: string, intensity: number): string {
  // Convert hex to rgba with intensity as alpha
  const hex = color.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${intensity})`;
}

/**
 * Get trend direction arrow
 */
function getTrendArrow(direction?: 'up' | 'down' | 'stable' | null): string {
  switch (direction) {
    case 'up':
      return '\u2191'; // ↑
    case 'down':
      return '\u2193'; // ↓
    case 'stable':
      return '\u2192'; // →
    default:
      return '';
  }
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
  showStages = false,
  stageBreakdown,
}) => {
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const containerRef = React.useRef<HTMLDivElement>(null);

  // Observe container width for responsive sizing
  React.useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) {
        setContainerWidth(entries[0].contentRect.width);
      }
    });

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  // Calculate maximum count for intensity scaling
  const maxCount = useMemo(() => {
    if (data.length === 0) return 1;
    return Math.max(...data.map((item) => item.count), 1);
  }, [data]);

  // Build a map of pillar data for quick lookup
  const pillarDataMap = useMemo(() => {
    const map: Record<string, PillarCoverageItem> = {};
    data.forEach((item) => {
      map[item.pillar_code] = item;
    });
    return map;
  }, [data]);

  // Calculate grid dimensions
  const numCols = pillars.length;
  const numRows = showStages ? stages.length : 1;
  const effectiveWidth = containerWidth - (showStages ? STAGE_LABEL_WIDTH : 0);
  const cellWidth = effectiveWidth > 0 ? (effectiveWidth - CELL_PADDING * (numCols + 1)) / numCols : 80;
  const cellHeight = showStages ? 40 : height - LABEL_HEIGHT - LEGEND_HEIGHT;
  const svgWidth = containerWidth || 600;
  const svgHeight = showStages
    ? LABEL_HEIGHT + numRows * (cellHeight + CELL_PADDING) + LEGEND_HEIGHT + CELL_PADDING
    : height;

  // Handle mouse enter on cell
  const handleMouseEnter = (
    pillarCode: string,
    pillarName: string,
    count: number,
    percentage: number,
    avgVelocity: number | null | undefined,
    trendDirection: 'up' | 'down' | 'stable' | null | undefined,
    x: number,
    y: number,
    stage?: number
  ) => {
    setTooltip({
      pillarCode,
      pillarName,
      count,
      percentage,
      avgVelocity,
      trendDirection,
      stage,
      x,
      y,
    });
  };

  const handleMouseLeave = () => {
    setTooltip(null);
  };

  // Handle cell click
  const handleCellClick = (pillarCode: string) => {
    if (onPillarClick) {
      onPillarClick(pillarCode);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div
        ref={containerRef}
        className="w-full bg-white dark:bg-[#2d3166] rounded-lg shadow p-4"
        style={{ height }}
      >
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            {title}
          </h3>
        )}
        <div className="flex items-center justify-center h-full">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue"></div>
        </div>
      </div>
    );
  }

  // Empty state
  if (data.length === 0) {
    return (
      <div
        ref={containerRef}
        className="w-full bg-white dark:bg-[#2d3166] rounded-lg shadow p-4"
        style={{ height }}
      >
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            {title}
          </h3>
        )}
        <div className="flex items-center justify-center h-full text-gray-500 dark:text-gray-400">
          No data available for selected filters
        </div>
      </div>
    );
  }

  // Render simple single-row heatmap (default mode)
  const renderSimpleHeatmap = () => {
    const startX = showStages ? STAGE_LABEL_WIDTH : CELL_PADDING;
    const startY = LABEL_HEIGHT;

    return (
      <g>
        {/* Column labels (pillar codes) */}
        {pillars.map((pillar, colIndex) => {
          const x = startX + colIndex * (cellWidth + CELL_PADDING) + cellWidth / 2;
          return (
            <text
              key={`label-${pillar.code}`}
              x={x}
              y={LABEL_HEIGHT / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-gray-700 dark:fill-gray-300 text-xs font-medium"
            >
              {pillar.code}
            </text>
          );
        })}

        {/* Heatmap cells */}
        {pillars.map((pillar, colIndex) => {
          const cellData = pillarDataMap[pillar.code];
          const count = cellData?.count ?? 0;
          const percentage = cellData?.percentage ?? 0;
          const avgVelocity = cellData?.avg_velocity;
          const trendDirection = cellData?.trend_direction;
          const intensity = calculateIntensity(count, maxCount);
          const fillColor = getColorWithIntensity(pillar.color, intensity);
          const x = startX + colIndex * (cellWidth + CELL_PADDING);
          const y = startY;

          return (
            <g key={`cell-${pillar.code}`}>
              <rect
                x={x}
                y={y}
                width={cellWidth}
                height={cellHeight}
                rx={4}
                ry={4}
                fill={fillColor}
                stroke={pillar.color}
                strokeWidth={1}
                className={`transition-all duration-200 ${
                  onPillarClick ? 'cursor-pointer hover:stroke-2' : ''
                }`}
                onMouseEnter={() =>
                  handleMouseEnter(
                    pillar.code,
                    pillar.name,
                    count,
                    percentage,
                    avgVelocity,
                    trendDirection,
                    x + cellWidth / 2,
                    y
                  )
                }
                onMouseLeave={handleMouseLeave}
                onClick={() => handleCellClick(pillar.code)}
              />
              {/* Count text */}
              <text
                x={x + cellWidth / 2}
                y={y + cellHeight / 2 - 8}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-gray-900 dark:fill-white text-lg font-bold pointer-events-none"
              >
                {count}
              </text>
              {/* Percentage text */}
              <text
                x={x + cellWidth / 2}
                y={y + cellHeight / 2 + 12}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-gray-600 dark:fill-gray-300 text-sm pointer-events-none"
              >
                {percentage.toFixed(1)}%
              </text>
            </g>
          );
        })}

        {/* Legend */}
        {renderLegend(startY + cellHeight + CELL_PADDING * 2)}
      </g>
    );
  };

  // Render legend showing color scale
  const renderLegend = (yPosition: number) => {
    const legendWidth = 200;
    const legendX = (svgWidth - legendWidth) / 2;
    const gradientStops = [0, 0.25, 0.5, 0.75, 1];

    return (
      <g>
        {/* Legend title */}
        <text
          x={legendX - 10}
          y={yPosition + 10}
          textAnchor="end"
          dominantBaseline="middle"
          className="fill-gray-500 dark:fill-gray-400 text-xs"
        >
          Less
        </text>

        {/* Color gradient */}
        <defs>
          <linearGradient id="heatmap-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            {gradientStops.map((stop, index) => (
              <stop
                key={index}
                offset={`${stop * 100}%`}
                stopColor={`rgba(59, 130, 246, ${0.2 + stop * 0.8})`}
              />
            ))}
          </linearGradient>
        </defs>
        <rect
          x={legendX}
          y={yPosition}
          width={legendWidth}
          height={20}
          rx={4}
          fill="url(#heatmap-gradient)"
          stroke="#e5e7eb"
          strokeWidth={1}
        />

        {/* Legend end label */}
        <text
          x={legendX + legendWidth + 10}
          y={yPosition + 10}
          textAnchor="start"
          dominantBaseline="middle"
          className="fill-gray-500 dark:fill-gray-400 text-xs"
        >
          More
        </text>
      </g>
    );
  };

  return (
    <div
      ref={containerRef}
      className="w-full bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 relative"
      style={{ minHeight: height }}
    >
      {title && (
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {title}
        </h3>
      )}

      <svg
        width="100%"
        height={svgHeight - (title ? 32 : 0)}
        viewBox={`0 0 ${svgWidth} ${svgHeight - (title ? 32 : 0)}`}
        preserveAspectRatio="xMidYMid meet"
        className="overflow-visible"
      >
        {renderSimpleHeatmap()}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute z-10 bg-gray-900 dark:bg-gray-800 text-white px-3 py-2 rounded-lg shadow-lg text-sm pointer-events-none transform -translate-x-1/2"
          style={{
            left: tooltip.x,
            top: tooltip.y - 10,
          }}
        >
          <div className="font-semibold">{tooltip.pillarName}</div>
          <div className="text-gray-300">
            <span className="font-medium">{tooltip.count}</span> cards ({tooltip.percentage.toFixed(1)}%)
          </div>
          {tooltip.avgVelocity !== null && tooltip.avgVelocity !== undefined && (
            <div className="text-gray-300">
              Avg. Velocity: <span className="font-medium">{tooltip.avgVelocity.toFixed(0)}</span>
              {tooltip.trendDirection && (
                <span className="ml-1">{getTrendArrow(tooltip.trendDirection)}</span>
              )}
            </div>
          )}
          {tooltip.stage && (
            <div className="text-gray-300">
              Stage: <span className="font-medium">{tooltip.stage}</span>
            </div>
          )}
          {/* Tooltip arrow */}
          <div className="absolute left-1/2 -bottom-1 transform -translate-x-1/2 w-2 h-2 bg-gray-900 dark:bg-gray-800 rotate-45"></div>
        </div>
      )}

      {/* Pillar legend below chart */}
      <div className="mt-4 flex flex-wrap justify-center gap-3 text-xs">
        {pillars.map((pillar) => (
          <div
            key={pillar.code}
            className={`flex items-center gap-1 ${
              onPillarClick ? 'cursor-pointer hover:opacity-75' : ''
            }`}
            onClick={() => onPillarClick && handleCellClick(pillar.code)}
          >
            <div
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: pillar.color }}
            />
            <span className="text-gray-600 dark:text-gray-400">{pillar.code}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PillarHeatmap;
