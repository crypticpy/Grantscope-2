/**
 * CardClassification Component
 *
 * Displays the classification section of a card showing all taxonomy metadata:
 * - Pillar with PillarBadge
 * - Goal code and name
 * - Anchor with AnchorBadge
 * - Pipeline status with PipelineBadge and PipelineProgress
 * - Deadline with DeadlineUrgencyBadge
 * - Top 25 priorities with Top25List
 *
 * This component is used in the Overview tab of CardDetail.
 */

import React from "react";

// Badge Components
import { PillarBadge } from "../../../PillarBadge";
import { PipelineBadge, PipelineProgress } from "../../../PipelineBadge";
import { DeadlineUrgencyBadge } from "../../../DeadlineUrgencyBadge";
import { AnchorBadge } from "../../../AnchorBadge";
import { Top25List } from "../../../Top25Badge";

// Types
import type { Card } from "../../types";

// Taxonomy helpers
import { getGoalByCode, type Goal } from "../../../../data/taxonomy";

/**
 * Props for the CardClassification component
 */
export interface CardClassificationProps {
  /** The card data to display */
  card: Card;
}

/**
 * Individual classification row component for consistent styling
 */
interface ClassificationRowProps {
  /** Label for the row */
  label: string;
  /** Content to display */
  children: React.ReactNode;
}

const ClassificationRow: React.FC<ClassificationRowProps> = ({
  label,
  children,
}) => (
  <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4">
    <div className="w-auto sm:w-24 text-xs sm:text-sm font-medium text-gray-500 shrink-0">
      {label}
    </div>
    <div className="flex-1">{children}</div>
  </div>
);

/**
 * CardClassification displays all classification metadata for a card.
 *
 * Features:
 * - Responsive layout with label-value pairs
 * - Badge components for visual taxonomy representation
 * - Stage progress visualization with optional history timeline
 * - Graceful handling of missing/optional fields
 * - Dark mode support
 *
 * @example
 * ```tsx
 * <CardClassification
 *   card={card}
 *   stageHistory={stageHistory}
 *   stageHistoryLoading={stageHistoryLoading}
 * />
 * ```
 */
export const CardClassification: React.FC<CardClassificationProps> = ({
  card,
}) => {
  // Get goal information from taxonomy
  const goal: Goal | undefined = card.goal_id
    ? getGoalByCode(card.goal_id)
    : undefined;

  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6">
      <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
        Classification
      </h2>
      <div className="space-y-3 sm:space-y-4">
        {/* Pillar */}
        <ClassificationRow label="Pillar">
          <PillarBadge
            pillarId={card.pillar_id}
            goalId={card.goal_id}
            showIcon
            size="md"
          />
        </ClassificationRow>

        {/* Goal */}
        {goal && (
          <ClassificationRow label="Goal">
            <span className="inline-flex items-center flex-wrap gap-2 text-sm text-gray-700 dark:text-gray-300">
              <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                {goal.code}
              </span>
              <span className="break-words">{goal.name}</span>
            </span>
          </ClassificationRow>
        )}

        {/* Anchor */}
        <ClassificationRow label="Anchor">
          {card.anchor_id ? (
            <AnchorBadge anchor={card.anchor_id} size="md" />
          ) : (
            <span className="text-sm text-gray-400 italic">Not assigned</span>
          )}
        </ClassificationRow>

        {/* Pipeline Status */}
        <ClassificationRow label="Pipeline">
          <div className="space-y-2">
            <PipelineBadge
              status={card.pipeline_status || "discovered"}
              size="md"
            />
            <div className="max-w-full sm:max-w-xs">
              <PipelineProgress
                status={card.pipeline_status || "discovered"}
                showLabels
              />
            </div>
          </div>
        </ClassificationRow>

        {/* Deadline */}
        <ClassificationRow label="Deadline">
          <DeadlineUrgencyBadge deadline={card.deadline} size="md" />
        </ClassificationRow>

        {/* Top 25 */}
        <ClassificationRow label="Top 25">
          {card.top25_relevance && card.top25_relevance.length > 0 ? (
            <Top25List priorities={card.top25_relevance} maxVisible={3} />
          ) : (
            <span className="text-sm text-gray-400 italic">
              Not aligned with Top 25 priorities
            </span>
          )}
        </ClassificationRow>
      </div>
    </div>
  );
};

export default CardClassification;
