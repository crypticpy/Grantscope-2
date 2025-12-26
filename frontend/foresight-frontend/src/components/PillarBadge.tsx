/**
 * PillarBadge Component
 *
 * Displays a CSP pillar code with:
 * - Appropriate background color based on pillar
 * - Optional icon from lucide-react
 * - Tooltip showing full pillar name, description, and related goals
 */

import React from 'react';
import {
  Heart,
  Briefcase,
  Building2,
  Home,
  Car,
  Shield,
  type LucideIcon,
} from 'lucide-react';
import { Tooltip } from './ui/Tooltip';
import { cn } from '../lib/utils';
import { getSizeClasses, getIconSize } from '../lib/badge-utils';
import {
  getPillarByCode,
  getGoalsByPillar,
  type Pillar,
  type Goal,
} from '../data/taxonomy';

// Icon mapping for pillars
const pillarIcons: Record<string, LucideIcon> = {
  Heart: Heart,
  Briefcase: Briefcase,
  Building2: Building2,
  Home: Home,
  Car: Car,
  Shield: Shield,
};

export interface PillarBadgeProps {
  /** Pillar code (e.g., 'CH', 'MC') */
  pillarId: string;
  /** Optional goal code to highlight in tooltip */
  goalId?: string;
  /** Whether to show the pillar icon */
  showIcon?: boolean;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Additional className */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
}

/**
 * Get color classes for a pillar
 */
function getPillarColorClasses(pillar: Pillar): {
  bg: string;
  text: string;
  border: string;
} {
  const colorMap: Record<string, { bg: string; text: string; border: string }> = {
    CH: {
      bg: 'bg-green-100',
      text: 'text-green-800',
      border: 'border-green-300',
    },
    EW: {
      bg: 'bg-blue-100',
      text: 'text-blue-800',
      border: 'border-blue-300',
    },
    HG: {
      bg: 'bg-indigo-100',
      text: 'text-indigo-800',
      border: 'border-indigo-300',
    },
    HH: {
      bg: 'bg-pink-100',
      text: 'text-pink-800',
      border: 'border-pink-300',
    },
    MC: {
      bg: 'bg-amber-100',
      text: 'text-amber-800',
      border: 'border-amber-300',
    },
    PS: {
      bg: 'bg-red-100',
      text: 'text-red-800',
      border: 'border-red-300',
    },
  };

  return colorMap[pillar.code] || { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-300' };
}


/**
 * Tooltip content component for pillar
 */
function PillarTooltipContent({
  pillar,
  goals,
  highlightGoalId,
}: {
  pillar: Pillar;
  goals: Goal[];
  highlightGoalId?: string;
}) {
  const Icon = pillarIcons[pillar.icon];
  const colors = getPillarColorClasses(pillar);

  return (
    <div className="space-y-3 min-w-[200px] max-w-[280px]">
      {/* Header */}
      <div className="flex items-start gap-2">
        {Icon && (
          <div
            className={cn(
              'p-1.5 rounded-md',
              colors.bg
            )}
          >
            <Icon className={cn('h-4 w-4', colors.text)} />
          </div>
        )}
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {pillar.name}
          </div>
          <div className="text-xs font-mono text-gray-500 dark:text-gray-400">
            {pillar.code}
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {pillar.description}
      </p>

      {/* Goals */}
      {goals.length > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">
            Goals
          </div>
          <ul className="space-y-1">
            {goals.map((goal) => (
              <li
                key={goal.code}
                className={cn(
                  'text-xs flex items-start gap-1.5',
                  highlightGoalId === goal.code
                    ? 'text-gray-900 dark:text-gray-100 font-medium'
                    : 'text-gray-600 dark:text-gray-400'
                )}
              >
                <span
                  className={cn(
                    'font-mono shrink-0',
                    highlightGoalId === goal.code
                      ? colors.text
                      : 'text-gray-400 dark:text-gray-500'
                  )}
                >
                  {goal.code}
                </span>
                <span className="line-clamp-2">{goal.name}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * PillarBadge component
 */
export function PillarBadge({
  pillarId,
  goalId,
  showIcon = true,
  size = 'md',
  className,
  disableTooltip = false,
}: PillarBadgeProps) {
  const pillar = getPillarByCode(pillarId);

  if (!pillar) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded font-medium border',
          'bg-gray-100 text-gray-600 border-gray-300',
          getSizeClasses(size),
          className
        )}
      >
        {pillarId}
      </span>
    );
  }

  const colors = getPillarColorClasses(pillar);
  const Icon = showIcon ? pillarIcons[pillar.icon] : null;
  const iconSize = getIconSize(size);
  const goals = getGoalsByPillar(pillarId);

  const badge = (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded font-medium border cursor-default',
        colors.bg,
        colors.text,
        colors.border,
        getSizeClasses(size),
        !disableTooltip && 'cursor-pointer',
        className
      )}
      role="status"
      aria-label={`${pillar.name} pillar`}
    >
      {Icon && <Icon className="shrink-0" size={iconSize} />}
      <span>{pillar.code}</span>
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={
        <PillarTooltipContent
          pillar={pillar}
          goals={goals}
          highlightGoalId={goalId}
        />
      }
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

/**
 * Multiple pillars displayed as a group
 */
export interface PillarBadgeGroupProps {
  /** Array of pillar codes */
  pillarIds: string[];
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show icons */
  showIcon?: boolean;
  /** Maximum number to show before "+N more" */
  maxVisible?: number;
  /** Additional className for the group container */
  className?: string;
}

export function PillarBadgeGroup({
  pillarIds,
  size = 'sm',
  showIcon = true,
  maxVisible = 3,
  className,
}: PillarBadgeGroupProps) {
  const visiblePillars = pillarIds.slice(0, maxVisible);
  const remainingCount = pillarIds.length - maxVisible;

  return (
    <div className={cn('inline-flex items-center gap-1 flex-wrap', className)}>
      {visiblePillars.map((pillarId) => (
        <PillarBadge
          key={pillarId}
          pillarId={pillarId}
          size={size}
          showIcon={showIcon}
        />
      ))}
      {remainingCount > 0 && (
        <span
          className={cn(
            'inline-flex items-center rounded font-medium',
            'bg-gray-100 text-gray-600 border border-gray-300',
            getSizeClasses(size)
          )}
        >
          +{remainingCount}
        </span>
      )}
    </div>
  );
}

export default PillarBadge;
