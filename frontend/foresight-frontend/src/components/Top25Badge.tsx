/**
 * Top25Badge Component
 *
 * Displays an indicator when a card has relevance to CMO Top 25 priorities:
 * - Small star/flag icon
 * - Tooltip showing list of aligned Top 25 priorities
 */

import React from 'react';
import { Star, Flag, Award, Target } from 'lucide-react';
import { Tooltip } from './ui/Tooltip';
import { cn } from '../lib/utils';
import { getTop25ByTitle, getPillarByCode, type Top25Priority } from '../data/taxonomy';

export interface Top25BadgeProps {
  /** Array of Top 25 priority titles that this card is relevant to */
  priorities: string[];
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Icon variant */
  icon?: 'star' | 'flag' | 'award' | 'target';
  /** Whether to show the count */
  showCount?: boolean;
  /** Additional className */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
}

const iconMap = {
  star: Star,
  flag: Flag,
  award: Award,
  target: Target,
};

/**
 * Get size classes
 */
function getSizeClasses(size: 'sm' | 'md' | 'lg'): {
  container: string;
  icon: number;
  text: string;
} {
  const sizeMap = {
    sm: { container: 'p-0.5', icon: 12, text: 'text-[10px]' },
    md: { container: 'p-1', icon: 14, text: 'text-xs' },
    lg: { container: 'p-1.5', icon: 16, text: 'text-sm' },
  };
  return sizeMap[size];
}

/**
 * Get pillar color classes for a priority
 */
function getPillarColorClasses(pillarCode: string): {
  bg: string;
  text: string;
} {
  const colorMap: Record<string, { bg: string; text: string }> = {
    CH: { bg: 'bg-green-100', text: 'text-green-700' },
    EW: { bg: 'bg-blue-100', text: 'text-blue-700' },
    HG: { bg: 'bg-indigo-100', text: 'text-indigo-700' },
    HH: { bg: 'bg-pink-100', text: 'text-pink-700' },
    MC: { bg: 'bg-amber-100', text: 'text-amber-700' },
    PS: { bg: 'bg-red-100', text: 'text-red-700' },
  };
  return colorMap[pillarCode] || { bg: 'bg-gray-100', text: 'text-gray-700' };
}

/**
 * Tooltip content component showing all priorities
 */
function Top25TooltipContent({ priorities }: { priorities: string[] }) {
  // Group priorities by pillar
  const priorityData = priorities
    .map((title) => getTop25ByTitle(title))
    .filter((p): p is Top25Priority => p !== undefined);

  // Group by pillar
  const byPillar = priorityData.reduce(
    (acc, priority) => {
      if (!acc[priority.pillarCode]) {
        acc[priority.pillarCode] = [];
      }
      acc[priority.pillarCode].push(priority);
      return acc;
    },
    {} as Record<string, Top25Priority[]>
  );

  return (
    <div className="space-y-3 min-w-[240px] max-w-[320px]">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="p-1.5 rounded-md bg-amber-100">
          <Star className="h-4 w-4 text-amber-600 fill-amber-400" />
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            Top 25 Priorities
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {priorities.length} aligned {priorities.length === 1 ? 'priority' : 'priorities'}
          </div>
        </div>
      </div>

      {/* Priorities grouped by pillar */}
      <div className="space-y-2">
        {Object.entries(byPillar).map(([pillarCode, pillarPriorities]) => {
          const pillar = getPillarByCode(pillarCode);
          const colors = getPillarColorClasses(pillarCode);

          return (
            <div key={pillarCode}>
              <div className="flex items-center gap-1.5 mb-1">
                <span
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[10px] font-semibold',
                    colors.bg,
                    colors.text
                  )}
                >
                  {pillarCode}
                </span>
                {pillar && (
                  <span className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {pillar.name}
                  </span>
                )}
              </div>
              <ul className="space-y-0.5 pl-1">
                {pillarPriorities.map((priority) => (
                  <li
                    key={priority.id}
                    className="text-xs text-gray-600 dark:text-gray-300 flex items-start gap-1"
                  >
                    <span className="text-gray-400 mt-1">-</span>
                    <span>{priority.title}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}

        {/* Handle priorities not found in taxonomy */}
        {priorities.filter((title) => !getTop25ByTitle(title)).length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1">Other</div>
            <ul className="space-y-0.5 pl-1">
              {priorities
                .filter((title) => !getTop25ByTitle(title))
                .map((title) => (
                  <li
                    key={title}
                    className="text-xs text-gray-600 dark:text-gray-300 flex items-start gap-1"
                  >
                    <span className="text-gray-400 mt-1">-</span>
                    <span>{title}</span>
                  </li>
                ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Top25Badge component
 */
export function Top25Badge({
  priorities,
  size = 'md',
  icon = 'star',
  showCount = false,
  className,
  disableTooltip = false,
}: Top25BadgeProps) {
  // Don't render if no priorities
  if (!priorities || priorities.length === 0) {
    return null;
  }

  const Icon = iconMap[icon];
  const sizeClasses = getSizeClasses(size);

  const badge = (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 rounded-full cursor-default',
        'bg-amber-100 text-amber-600 border border-amber-300',
        sizeClasses.container,
        !disableTooltip && 'cursor-pointer hover:bg-amber-200 transition-colors',
        className
      )}
      role="status"
      aria-label={`Relevant to ${priorities.length} Top 25 ${priorities.length === 1 ? 'priority' : 'priorities'}`}
    >
      <Icon
        className="fill-amber-400"
        size={sizeClasses.icon}
      />
      {showCount && priorities.length > 1 && (
        <span className={cn('font-medium', sizeClasses.text)}>
          {priorities.length}
        </span>
      )}
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={<Top25TooltipContent priorities={priorities} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

/**
 * Expanded Top 25 badge showing priority count and expandable list
 */
export interface Top25ExpandedBadgeProps {
  /** Array of Top 25 priority titles */
  priorities: string[];
  /** Additional className */
  className?: string;
}

export function Top25ExpandedBadge({
  priorities,
  className,
}: Top25ExpandedBadgeProps) {
  if (!priorities || priorities.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 px-2.5 py-1.5 rounded-md',
        'bg-amber-50 border border-amber-200',
        className
      )}
    >
      <Star className="h-4 w-4 text-amber-600 fill-amber-400 shrink-0" />
      <div className="text-sm">
        <span className="font-medium text-amber-800">Top 25</span>
        <span className="text-amber-600 ml-1">
          ({priorities.length} {priorities.length === 1 ? 'priority' : 'priorities'})
        </span>
      </div>
    </div>
  );
}

/**
 * Top 25 priority list component
 */
export interface Top25ListProps {
  /** Array of Top 25 priority titles */
  priorities: string[];
  /** Maximum items to show before "show more" */
  maxVisible?: number;
  /** Additional className */
  className?: string;
}

export function Top25List({
  priorities,
  maxVisible = 3,
  className,
}: Top25ListProps) {
  const [expanded, setExpanded] = React.useState(false);

  if (!priorities || priorities.length === 0) {
    return null;
  }

  const visiblePriorities = expanded
    ? priorities
    : priorities.slice(0, maxVisible);
  const remainingCount = priorities.length - maxVisible;

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center gap-2">
        <Star className="h-4 w-4 text-amber-600 fill-amber-400" />
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Top 25 Priorities
        </span>
      </div>
      <ul className="space-y-1 pl-6">
        {visiblePriorities.map((title) => {
          const priority = getTop25ByTitle(title);
          const colors = priority
            ? getPillarColorClasses(priority.pillarCode)
            : { bg: 'bg-gray-100', text: 'text-gray-700' };

          return (
            <li
              key={title}
              className="text-sm text-gray-600 dark:text-gray-300 flex items-start gap-2"
            >
              {priority && (
                <span
                  className={cn(
                    'px-1 py-0.5 rounded text-[10px] font-medium shrink-0 mt-0.5',
                    colors.bg,
                    colors.text
                  )}
                >
                  {priority.pillarCode}
                </span>
              )}
              <span>{title}</span>
            </li>
          );
        })}
      </ul>
      {remainingCount > 0 && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline pl-6"
        >
          Show {remainingCount} more
        </button>
      )}
      {expanded && priorities.length > maxVisible && (
        <button
          onClick={() => setExpanded(false)}
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline pl-6"
        >
          Show less
        </button>
      )}
    </div>
  );
}

export default Top25Badge;
