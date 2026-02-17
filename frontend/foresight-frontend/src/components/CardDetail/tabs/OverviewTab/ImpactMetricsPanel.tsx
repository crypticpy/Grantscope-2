/**
 * ImpactMetricsPanel Component
 *
 * Displays the impact metrics sidebar panel showing all 6 score metrics:
 * Impact, Relevance, Velocity, Novelty, Opportunity, and Risk.
 *
 * Each metric displays with a tooltip description and color-coded score badge
 * following WCAG 2.1 AA compliant color schemes.
 *
 * @module CardDetail/tabs/OverviewTab/ImpactMetricsPanel
 */

import React from "react";
import { Info } from "lucide-react";
import { Tooltip } from "../../../../components/ui/Tooltip";
import { cn } from "../../../../lib/utils";
import { getScoreColorClasses, metricDefinitions } from "../../utils";
import type { MetricKey } from "../../types";

/**
 * Individual metric score configuration
 */
interface MetricScore {
  /** Metric key identifier */
  key: MetricKey;
  /** Score value (0-100) */
  score: number;
}

/**
 * Props for the ImpactMetricsPanel component
 */
export interface ImpactMetricsPanelProps {
  /**
   * Impact score (0-100): Potential magnitude of effect on operations
   */
  impactScore: number;

  /**
   * Relevance score (0-100): Alignment with current priorities
   */
  relevanceScore: number;

  /**
   * Velocity score (0-100): Speed of development and adoption
   */
  velocityScore: number;

  /**
   * Novelty score (0-100): How new or unprecedented this signal is
   */
  noveltyScore: number;

  /**
   * Opportunity score (0-100): Potential benefits if adopted
   */
  opportunityScore: number;

  /**
   * Risk score (0-100): Potential negative consequences
   */
  riskScore: number;

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;

  /**
   * Optional title for the panel (defaults to "Impact Metrics")
   */
  title?: string;
}

/**
 * ImpactMetricsPanel displays all six impact metrics with tooltips and color-coded scores.
 *
 * Features:
 * - All 6 metrics displayed in a consistent layout
 * - Tooltips with metric descriptions on hover
 * - Color-coded score badges (green/amber/orange/red based on value)
 * - WCAG 2.1 AA compliant color contrast
 * - Dark mode support
 * - Responsive padding
 *
 * @example
 * ```tsx
 * <ImpactMetricsPanel
 *   impactScore={75}
 *   relevanceScore={82}
 *   velocityScore={60}
 *   noveltyScore={45}
 *   opportunityScore={88}
 *   riskScore={35}
 * />
 * ```
 *
 * @example
 * ```tsx
 * // Using with a card object
 * <ImpactMetricsPanel
 *   impactScore={card.impact_score}
 *   relevanceScore={card.relevance_score}
 *   velocityScore={card.velocity_score}
 *   noveltyScore={card.novelty_score}
 *   opportunityScore={card.opportunity_score}
 *   riskScore={card.risk_score}
 * />
 * ```
 */
export const ImpactMetricsPanel: React.FC<ImpactMetricsPanelProps> = ({
  impactScore,
  relevanceScore,
  velocityScore,
  noveltyScore,
  opportunityScore,
  riskScore,
  className = "",
  title = "Impact Metrics",
}) => {
  // Define metrics array for consistent rendering
  const metrics: MetricScore[] = [
    { key: "impact", score: impactScore },
    { key: "relevance", score: relevanceScore },
    { key: "velocity", score: velocityScore },
    { key: "novelty", score: noveltyScore },
    { key: "opportunity", score: opportunityScore },
    { key: "risk", score: riskScore },
  ];

  return (
    <div
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6",
        className,
      )}
    >
      {/* Header with title and info tooltip */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          {title}
        </h3>
        <Tooltip
          content={
            <div className="space-y-1">
              <p className="font-medium">Score Interpretation</p>
              <p className="text-xs text-gray-500">
                Scores range from 0-100, with higher scores indicating stronger
                opportunities.
              </p>
            </div>
          }
          side="left"
        >
          <button
            type="button"
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Score interpretation information"
          >
            <Info className="h-4 w-4" />
          </button>
        </Tooltip>
      </div>

      {/* Metrics list */}
      <div className="space-y-3">
        {metrics.map((metric) => {
          const definition = metricDefinitions[metric.key];
          const colors = getScoreColorClasses(metric.score);

          return (
            <div key={metric.key} className="flex items-center justify-between">
              {/* Metric label with tooltip */}
              <Tooltip
                content={
                  <div className="max-w-[200px]">
                    <p className="font-medium mb-1">{definition.label}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {definition.description}
                    </p>
                  </div>
                }
                side="left"
              >
                <span className="text-sm text-gray-700 dark:text-gray-200 cursor-help border-b border-dotted border-gray-400 dark:border-gray-500">
                  {definition.label}
                </span>
              </Tooltip>

              {/* Score badge */}
              <span
                className={cn(
                  "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
                  colors.bg,
                  colors.text,
                  colors.border,
                )}
              >
                {metric.score}/100
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ImpactMetricsPanel;
