/**
 * StageBadge Component
 *
 * Displays a maturity stage indicator with:
 * - Stage number and name
 * - Visual progress indicator
 * - Tooltip showing description, typical signals, and horizon alignment
 */

import React from 'react';
import { Tooltip } from './ui/Tooltip';
import { cn } from '../lib/utils';
import {
  getStageByNumber,
  getHorizonByCode,
  type MaturityStage,
} from '../data/taxonomy';

export interface StageBadgeProps {
  /** Stage number (1-8) */
  stage: number;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show the stage name */
  showName?: boolean;
  /** Additional className */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
  /** Display variant */
  variant?: 'badge' | 'progress' | 'minimal';
}

/**
 * Get color classes based on horizon alignment
 */
function getStageColorClasses(horizonCode: string): {
  bg: string;
  text: string;
  border: string;
  progress: string;
} {
  const colorMap: Record<string, { bg: string; text: string; border: string; progress: string }> = {
    H1: {
      bg: 'bg-green-50',
      text: 'text-green-700',
      border: 'border-green-300',
      progress: 'bg-green-500',
    },
    H2: {
      bg: 'bg-amber-50',
      text: 'text-amber-700',
      border: 'border-amber-300',
      progress: 'bg-amber-500',
    },
    H3: {
      bg: 'bg-purple-50',
      text: 'text-purple-700',
      border: 'border-purple-300',
      progress: 'bg-purple-500',
    },
  };

  return colorMap[horizonCode] || {
    bg: 'bg-gray-50',
    text: 'text-gray-700',
    border: 'border-gray-300',
    progress: 'bg-gray-500',
  };
}

/**
 * Get size classes for the badge
 */
function getSizeClasses(size: 'sm' | 'md' | 'lg'): {
  container: string;
  text: string;
  number: string;
} {
  const sizeMap = {
    sm: {
      container: 'px-1.5 py-0.5 gap-1',
      text: 'text-xs',
      number: 'text-xs',
    },
    md: {
      container: 'px-2 py-1 gap-1.5',
      text: 'text-sm',
      number: 'text-sm',
    },
    lg: {
      container: 'px-3 py-1.5 gap-2',
      text: 'text-base',
      number: 'text-base',
    },
  };
  return sizeMap[size];
}

/**
 * Tooltip content component for stage
 */
function StageTooltipContent({ stageData }: { stageData: MaturityStage }) {
  const horizon = getHorizonByCode(stageData.horizon);
  const colors = getStageColorClasses(stageData.horizon);
  const progressPercent = (stageData.stage / 8) * 100;

  return (
    <div className="space-y-3 min-w-[220px] max-w-[280px]">
      {/* Header with stage number */}
      <div className="flex items-start gap-3">
        <div
          className={cn(
            'w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg',
            colors.bg,
            colors.text,
            'border-2',
            colors.border
          )}
        >
          {stageData.stage}
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {stageData.name}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Stage {stageData.stage} of 8
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {stageData.description}
      </p>

      {/* Signals */}
      <div>
        <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
          Typical Signals
        </div>
        <p className="text-xs text-gray-600 dark:text-gray-300 italic">
          "{stageData.signals}"
        </p>
      </div>

      {/* Horizon alignment */}
      {horizon && (
        <div className="flex items-center gap-2 pt-1 border-t border-gray-200 dark:border-gray-700">
          <span
            className={cn(
              'px-2 py-0.5 rounded text-xs font-medium',
              colors.bg,
              colors.text
            )}
          >
            {stageData.horizon}
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {horizon.name} ({horizon.timeframe})
          </span>
        </div>
      )}

      {/* Progress bar */}
      <div className="pt-1">
        <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all', colors.progress)}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="flex justify-between mt-1 text-[10px] text-gray-400">
          <span>Concept</span>
          <span>Mature</span>
        </div>
      </div>
    </div>
  );
}

/**
 * StageBadge component
 */
export function StageBadge({
  stage,
  size = 'md',
  showName = true,
  className,
  disableTooltip = false,
  variant = 'badge',
}: StageBadgeProps) {
  const stageData = getStageByNumber(stage);

  if (!stageData) {
    return (
      <span
        className={cn(
          'inline-flex items-center rounded font-medium border',
          'bg-gray-100 text-gray-600 border-gray-300',
          getSizeClasses(size).container,
          getSizeClasses(size).text,
          className
        )}
      >
        Stage {stage}
      </span>
    );
  }

  const colors = getStageColorClasses(stageData.horizon);
  const sizeClasses = getSizeClasses(size);

  // Minimal variant - just the number
  if (variant === 'minimal') {
    const badge = (
      <span
        className={cn(
          'inline-flex items-center justify-center rounded-full font-semibold border cursor-default',
          colors.bg,
          colors.text,
          colors.border,
          size === 'sm' && 'w-5 h-5 text-xs',
          size === 'md' && 'w-6 h-6 text-sm',
          size === 'lg' && 'w-8 h-8 text-base',
          !disableTooltip && 'cursor-pointer',
          className
        )}
        role="status"
        aria-label={`Stage ${stage}: ${stageData.name}`}
      >
        {stage}
      </span>
    );

    if (disableTooltip) {
      return badge;
    }

    return (
      <Tooltip
        content={<StageTooltipContent stageData={stageData} />}
        side="top"
        align="center"
        contentClassName="p-3"
      >
        {badge}
      </Tooltip>
    );
  }

  // Progress variant - horizontal bar with indicator
  if (variant === 'progress') {
    const progressPercent = (stage / 8) * 100;

    const badge = (
      <div
        className={cn(
          'inline-flex flex-col gap-1 cursor-default',
          !disableTooltip && 'cursor-pointer',
          className
        )}
        role="status"
        aria-label={`Stage ${stage}: ${stageData.name}`}
      >
        <div className="flex items-center justify-between">
          <span className={cn('font-medium', colors.text, sizeClasses.text)}>
            {stageData.name}
          </span>
          <span className={cn('text-gray-500', sizeClasses.number)}>
            {stage}/8
          </span>
        </div>
        <div className="w-full h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all', colors.progress)}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
    );

    if (disableTooltip) {
      return badge;
    }

    return (
      <Tooltip
        content={<StageTooltipContent stageData={stageData} />}
        side="top"
        align="center"
        contentClassName="p-3"
      >
        {badge}
      </Tooltip>
    );
  }

  // Default badge variant
  const badge = (
    <span
      className={cn(
        'inline-flex items-center rounded font-medium border cursor-default',
        colors.bg,
        colors.text,
        colors.border,
        sizeClasses.container,
        !disableTooltip && 'cursor-pointer',
        className
      )}
      role="status"
      aria-label={`Stage ${stage}: ${stageData.name}`}
    >
      <span
        className={cn(
          'inline-flex items-center justify-center rounded-full font-semibold bg-white dark:bg-gray-800',
          size === 'sm' && 'w-4 h-4 text-[10px]',
          size === 'md' && 'w-5 h-5 text-xs',
          size === 'lg' && 'w-6 h-6 text-sm'
        )}
      >
        {stage}
      </span>
      {showName && <span className={sizeClasses.text}>{stageData.name}</span>}
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={<StageTooltipContent stageData={stageData} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

/**
 * Stage progress indicator showing all 8 stages
 */
export interface StageProgressProps {
  /** Current stage (1-8) */
  stage: number;
  /** Whether to show stage labels */
  showLabels?: boolean;
  /** Additional className */
  className?: string;
}

export function StageProgress({
  stage,
  showLabels = false,
  className,
}: StageProgressProps) {
  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => {
          const stageData = getStageByNumber(s);
          const colors = stageData ? getStageColorClasses(stageData.horizon) : null;
          const isActive = s <= stage;
          const isCurrent = s === stage;

          return (
            <div
              key={s}
              className={cn(
                'flex-1 h-2 transition-all',
                s === 1 && 'rounded-l-full',
                s === 8 && 'rounded-r-full',
                isActive && colors
                  ? colors.progress
                  : 'bg-gray-200 dark:bg-gray-700',
                isCurrent && 'ring-2 ring-offset-1 ring-gray-400'
              )}
            />
          );
        })}
      </div>
      {showLabels && (
        <div className="flex justify-between text-[10px] text-gray-400">
          <span>1</span>
          <span>8</span>
        </div>
      )}
    </div>
  );
}

export default StageBadge;
