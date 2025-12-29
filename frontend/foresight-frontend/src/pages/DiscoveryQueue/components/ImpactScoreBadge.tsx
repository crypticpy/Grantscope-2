import React from 'react';
import { Zap } from 'lucide-react';
import { Tooltip } from '../../../components/ui/Tooltip';
import { cn } from '../../../lib/utils';
import { getImpactLevel } from '../utils';

/**
 * Tooltip content for impact score - shows detailed breakdown
 */
function ImpactScoreTooltipContent({ score }: { score: number }) {
  const impactInfo = getImpactLevel(score);

  return (
    <div className="space-y-3 min-w-[200px] max-w-[260px]">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className={cn('p-1.5 rounded-md', impactInfo.bgColor)}>
          <Zap className={cn('h-4 w-4', impactInfo.color)} />
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {impactInfo.label}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Impact Score: {score}/100
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {impactInfo.description}
      </p>

      {/* Score bar */}
      <div>
        <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              impactInfo.level === 'high' && 'bg-purple-500 dark:bg-purple-400',
              impactInfo.level === 'medium' && 'bg-indigo-500 dark:bg-indigo-400',
              impactInfo.level === 'low' && 'bg-slate-500 dark:bg-slate-400'
            )}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>
    </div>
  );
}

/**
 * Props for ImpactScoreBadge component
 */
export interface ImpactScoreBadgeProps {
  /** Impact score value (0-100) */
  score: number;
  /** Badge size variant */
  size?: 'sm' | 'md';
}

/**
 * Impact score indicator badge for at-a-glance display
 * Shows a compact badge with the score and expands to detailed tooltip on hover
 */
export const ImpactScoreBadge = React.memo(function ImpactScoreBadge({
  score,
  size = 'sm',
}: ImpactScoreBadgeProps) {
  const impactInfo = getImpactLevel(score);

  const sizeClasses = size === 'sm'
    ? 'px-1.5 py-0.5 text-xs gap-1'
    : 'px-2 py-1 text-sm gap-1.5';

  const iconSize = size === 'sm' ? 10 : 12;

  return (
    <Tooltip
      content={<ImpactScoreTooltipContent score={score} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      <span
        className={cn(
          'inline-flex items-center rounded-full font-medium border cursor-pointer',
          impactInfo.bgColor,
          impactInfo.color,
          impactInfo.borderColor,
          sizeClasses
        )}
        role="status"
        aria-label={`${impactInfo.label}: ${score}/100`}
      >
        <Zap className="shrink-0" size={iconSize} />
        <span>{score}</span>
      </span>
    </Tooltip>
  );
});

export default ImpactScoreBadge;
