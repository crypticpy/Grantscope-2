/**
 * StageProgressionTimeline Component
 *
 * Visualizes stage transitions over time for a card, showing:
 * - Stage transitions with dates
 * - Stage labels 1-8 with horizon-based coloring
 * - Direction indicators for progression/regression
 * - Horizon color coding (H1=green, H2=amber, H3=purple)
 */

import React from 'react';
import { format } from 'date-fns';
import { Tooltip } from '../ui/Tooltip';
import { cn } from '../../lib/utils';
import {
  getStageByNumber,
} from '../../data/taxonomy';
import type { StageHistory } from '../../lib/discovery-api';

export interface StageProgressionTimelineProps {
  /** Array of stage transitions (ordered newest to oldest) */
  stageHistory: StageHistory[];
  /** Current stage if no history exists */
  currentStage?: number;
  /** Additional className */
  className?: string;
  /** Whether to show compact view */
  compact?: boolean;
}

/**
 * Get color classes based on horizon alignment
 * Consistent with StageBadge.tsx colors
 */
function getHorizonColorClasses(horizonCode: string): {
  bg: string;
  text: string;
  border: string;
  dot: string;
  line: string;
} {
  const colorMap: Record<string, { bg: string; text: string; border: string; dot: string; line: string }> = {
    H1: {
      bg: 'bg-green-50 dark:bg-green-900/30',
      text: 'text-green-800 dark:text-green-200',
      border: 'border-green-400 dark:border-green-600',
      dot: 'bg-green-500 dark:bg-green-400',
      line: 'bg-green-300 dark:bg-green-700',
    },
    H2: {
      bg: 'bg-amber-50 dark:bg-amber-900/30',
      text: 'text-amber-800 dark:text-amber-200',
      border: 'border-amber-400 dark:border-amber-600',
      dot: 'bg-amber-500 dark:bg-amber-400',
      line: 'bg-amber-300 dark:bg-amber-700',
    },
    H3: {
      bg: 'bg-purple-50 dark:bg-purple-900/30',
      text: 'text-purple-800 dark:text-purple-200',
      border: 'border-purple-400 dark:border-purple-600',
      dot: 'bg-purple-500 dark:bg-purple-400',
      line: 'bg-purple-300 dark:bg-purple-700',
    },
  };

  return colorMap[horizonCode] || {
    bg: 'bg-gray-50 dark:bg-dark-surface',
    text: 'text-gray-800 dark:text-gray-200',
    border: 'border-gray-400 dark:border-gray-600',
    dot: 'bg-gray-500 dark:bg-gray-400',
    line: 'bg-gray-300 dark:bg-gray-700',
  };
}

/**
 * Get direction indicator for stage transition
 */
function getDirectionIndicator(
  oldStage: number,
  newStage: number
): { icon: string; label: string; color: string } {
  if (newStage > oldStage) {
    return {
      icon: '\u2191', // Up arrow
      label: 'Progressed',
      color: 'text-green-600 dark:text-green-400',
    };
  } else if (newStage < oldStage) {
    return {
      icon: '\u2193', // Down arrow
      label: 'Regressed',
      color: 'text-red-600 dark:text-red-400',
    };
  }
  return {
    icon: '\u2022', // Bullet
    label: 'No change',
    color: 'text-gray-500 dark:text-gray-400',
  };
}

/**
 * Stage node component for timeline
 */
interface StageNodeProps {
  stage: number;
  horizonCode: string;
  isActive?: boolean;
  size?: 'sm' | 'md';
}

function StageNode({ stage, horizonCode, isActive = false, size = 'md' }: StageNodeProps) {
  const stageData = getStageByNumber(stage);
  const colors = getHorizonColorClasses(horizonCode);

  const sizeClasses = size === 'sm'
    ? 'w-6 h-6 text-xs'
    : 'w-8 h-8 text-sm';

  return (
    <Tooltip
      content={
        stageData ? (
          <div className="text-sm">
            <div className="font-semibold">{stageData.name}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              Stage {stage} - {horizonCode}
            </div>
            <p className="mt-1 text-xs text-gray-600 dark:text-gray-300">
              {stageData.description}
            </p>
          </div>
        ) : (
          `Stage ${stage}`
        )
      }
      side="top"
    >
      <div
        className={cn(
          'rounded-full flex items-center justify-center font-bold border-2 transition-all cursor-pointer',
          sizeClasses,
          colors.bg,
          colors.text,
          colors.border,
          isActive && 'ring-2 ring-offset-2 ring-gray-400 dark:ring-gray-600'
        )}
        role="status"
        aria-label={stageData ? `Stage ${stage}: ${stageData.name}` : `Stage ${stage}`}
      >
        {stage}
      </div>
    </Tooltip>
  );
}

/**
 * Transition arrow component
 */
interface TransitionArrowProps {
  oldStage: number;
  newStage: number;
  compact?: boolean;
}

function TransitionArrow({ oldStage, newStage, compact = false }: TransitionArrowProps) {
  const direction = getDirectionIndicator(oldStage, newStage);

  return (
    <div
      className={cn(
        'flex items-center justify-center',
        compact ? 'px-1' : 'px-2'
      )}
    >
      <span
        className={cn(
          'font-bold',
          compact ? 'text-base' : 'text-lg',
          direction.color
        )}
        aria-label={direction.label}
      >
        {compact ? '\u2192' : `${direction.icon} \u2192`}
      </span>
    </div>
  );
}

/**
 * Single transition item in the timeline
 */
interface TransitionItemProps {
  transition: StageHistory;
  isFirst: boolean;
  isLast: boolean;
  compact?: boolean;
}

function TransitionItem({ transition, isFirst, isLast, compact = false }: TransitionItemProps) {
  const oldStageData = getStageByNumber(transition.old_stage_id);
  const newStageData = getStageByNumber(transition.new_stage_id);
  const direction = getDirectionIndicator(transition.old_stage_id, transition.new_stage_id);
  const newColors = getHorizonColorClasses(transition.new_horizon || 'H1');

  const formattedDate = format(new Date(transition.changed_at), 'MMM d, yyyy');
  const formattedTime = format(new Date(transition.changed_at), 'h:mm a');

  if (compact) {
    return (
      <div className="flex items-center gap-1">
        <StageNode
          stage={transition.old_stage_id}
          horizonCode={transition.old_horizon || 'H1'}
          size="sm"
        />
        <TransitionArrow
          oldStage={transition.old_stage_id}
          newStage={transition.new_stage_id}
          compact
        />
        <StageNode
          stage={transition.new_stage_id}
          horizonCode={transition.new_horizon || 'H1'}
          size="sm"
          isActive={isFirst}
        />
        <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
          {formattedDate}
        </span>
      </div>
    );
  }

  return (
    <div className="relative flex items-start gap-4">
      {/* Timeline connector */}
      {!isLast && (
        <div
          className={cn(
            'absolute left-4 top-10 w-0.5 h-full -ml-px',
            newColors.line
          )}
          aria-hidden="true"
        />
      )}

      {/* Timeline dot */}
      <div className="relative flex-shrink-0">
        <div
          className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center',
            newColors.dot
          )}
        >
          <span className="text-white font-bold text-sm">{direction.icon}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pb-6">
        <div className="flex items-center gap-3 flex-wrap">
          {/* Stage transition badges */}
          <div className="flex items-center gap-2">
            <StageNode
              stage={transition.old_stage_id}
              horizonCode={transition.old_horizon || 'H1'}
            />
            <span className={cn('text-xl', direction.color)}>\u2192</span>
            <StageNode
              stage={transition.new_stage_id}
              horizonCode={transition.new_horizon || 'H1'}
              isActive={isFirst}
            />
          </div>

          {/* Stage names */}
          <div className="text-sm">
            <span className="text-gray-600 dark:text-gray-400">
              {oldStageData?.name || `Stage ${transition.old_stage_id}`}
            </span>
            <span className="mx-2 text-gray-400">\u2192</span>
            <span className={cn('font-medium', newColors.text)}>
              {newStageData?.name || `Stage ${transition.new_stage_id}`}
            </span>
          </div>
        </div>

        {/* Metadata */}
        <div className="mt-2 flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
          <time dateTime={transition.changed_at}>
            {formattedDate} at {formattedTime}
          </time>
          {transition.trigger && (
            <span className="flex items-center gap-1">
              <span className="text-gray-400">\u2022</span>
              <span className="capitalize">{transition.trigger}</span>
            </span>
          )}
        </div>

        {/* Horizon change indicator */}
        {transition.old_horizon !== transition.new_horizon && (
          <div className="mt-2">
            <span
              className={cn(
                'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
                newColors.bg,
                newColors.text
              )}
            >
              Horizon: {transition.old_horizon} \u2192 {transition.new_horizon}
            </span>
          </div>
        )}

        {/* Reason if provided */}
        {transition.reason && (
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-300 italic">
            "{transition.reason}"
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * Empty state when no stage history exists
 */
interface EmptyStateProps {
  currentStage?: number;
}

function EmptyState({ currentStage }: EmptyStateProps) {
  const stageData = currentStage ? getStageByNumber(currentStage) : null;
  const horizon = stageData?.horizon || 'H1';
  const _colors = getHorizonColorClasses(horizon);

  return (
    <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
      {currentStage && stageData ? (
        <>
          <StageNode
            stage={currentStage}
            horizonCode={horizon}
            isActive
          />
          <p className="mt-3 text-sm font-medium text-gray-900 dark:text-gray-100">
            {stageData.name}
          </p>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Current stage - no transitions recorded yet
          </p>
        </>
      ) : (
        <>
          <div className="w-12 h-12 rounded-full bg-gray-100 dark:bg-dark-surface flex items-center justify-center">
            <svg
              className="w-6 h-6 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
          </div>
          <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
            No stage transitions recorded
          </p>
        </>
      )}
    </div>
  );
}

/**
 * Stage overview bar showing all 8 stages
 */
interface StageOverviewBarProps {
  currentStage?: number;
  highlightedStages?: number[];
}

function StageOverviewBar({ currentStage, highlightedStages = [] }: StageOverviewBarProps) {
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between text-[10px] text-gray-400 dark:text-gray-500 mb-1">
        <span>Concept</span>
        <span>Mature</span>
      </div>
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5, 6, 7, 8].map((stage) => {
          const stageData = getStageByNumber(stage);
          const horizon = stageData?.horizon || 'H1';
          const colors = getHorizonColorClasses(horizon);
          const isHighlighted = highlightedStages.includes(stage);
          const isCurrent = stage === currentStage;

          return (
            <Tooltip
              key={stage}
              content={stageData ? `${stage}. ${stageData.name} (${horizon})` : `Stage ${stage}`}
              side="top"
            >
              <div
                className={cn(
                  'flex-1 h-2 transition-all cursor-pointer',
                  stage === 1 && 'rounded-l-full',
                  stage === 8 && 'rounded-r-full',
                  isHighlighted || (currentStage && stage <= currentStage)
                    ? colors.dot
                    : 'bg-gray-200 dark:bg-gray-700',
                  isCurrent && 'ring-2 ring-offset-1 ring-gray-400 dark:ring-gray-500'
                )}
              />
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}

/**
 * StageProgressionTimeline component
 *
 * Visualizes the history of stage transitions for a card.
 * Shows transitions with dates, stage labels, horizon colors, and direction indicators.
 */
export function StageProgressionTimeline({
  stageHistory,
  currentStage,
  className,
  compact = false,
}: StageProgressionTimelineProps) {
  // Get all stages involved in transitions for the overview bar
  const highlightedStages = React.useMemo(() => {
    const stages = new Set<number>();
    stageHistory.forEach((t) => {
      stages.add(t.old_stage_id);
      stages.add(t.new_stage_id);
    });
    if (currentStage) stages.add(currentStage);
    return Array.from(stages);
  }, [stageHistory, currentStage]);

  // Determine current stage from most recent transition if not provided
  const effectiveCurrentStage = currentStage ||
    (stageHistory.length > 0 ? stageHistory[0].new_stage_id : undefined);

  // Handle empty state
  if (stageHistory.length === 0) {
    return (
      <div className={cn('rounded-lg border border-gray-200 dark:border-gray-700', className)}>
        <div className="px-4 pt-4">
          <StageOverviewBar
            currentStage={effectiveCurrentStage}
            highlightedStages={effectiveCurrentStage ? [effectiveCurrentStage] : []}
          />
        </div>
        <EmptyState currentStage={effectiveCurrentStage} />
      </div>
    );
  }

  return (
    <div className={cn('rounded-lg border border-gray-200 dark:border-gray-700', className)}>
      {/* Stage overview bar */}
      <div className="px-4 pt-4">
        <StageOverviewBar
          currentStage={effectiveCurrentStage}
          highlightedStages={highlightedStages}
        />
      </div>

      {/* Transitions list */}
      <div className={cn('p-4', compact ? 'space-y-2' : '')}>
        {compact ? (
          // Compact view: horizontal list of transitions
          <div className="flex flex-wrap gap-3">
            {stageHistory.map((transition, index) => (
              <TransitionItem
                key={transition.id}
                transition={transition}
                isFirst={index === 0}
                isLast={index === stageHistory.length - 1}
                compact
              />
            ))}
          </div>
        ) : (
          // Full view: vertical timeline
          <div className="relative">
            {stageHistory.map((transition, index) => (
              <TransitionItem
                key={transition.id}
                transition={transition}
                isFirst={index === 0}
                isLast={index === stageHistory.length - 1}
              />
            ))}
          </div>
        )}
      </div>

      {/* Summary footer */}
      {stageHistory.length > 0 && !compact && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>
              {stageHistory.length} transition{stageHistory.length !== 1 ? 's' : ''} recorded
            </span>
            {stageHistory.length > 0 && (
              <span>
                First recorded:{' '}
                {format(
                  new Date(stageHistory[stageHistory.length - 1].changed_at),
                  'MMM d, yyyy'
                )}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default StageProgressionTimeline;
