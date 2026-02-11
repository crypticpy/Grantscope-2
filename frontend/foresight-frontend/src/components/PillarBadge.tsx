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
 * Get extended description for each pillar with strategic context
 */
function getPillarExtendedInfo(code: string): { focus: string; keyDepartments: string[] } {
  const infoMap: Record<string, { focus: string; keyDepartments: string[] }> = {
    CH: {
      focus: 'Focuses on public health equity, park access, climate action, emergency preparedness, and animal welfare to build a healthier, more resilient Austin.',
      keyDepartments: ['Austin Public Health', 'Parks & Recreation', 'Office of Sustainability', 'Homeland Security & Emergency Mgmt'],
    },
    EW: {
      focus: 'Drives economic mobility through workforce development, small business support, and preserving Austin\'s creative and cultural economy.',
      keyDepartments: ['Economic Development', 'Workforce Solutions', 'Small Business Program', 'Cultural Arts Division'],
    },
    HG: {
      focus: 'Ensures fiscal responsibility, modernizes technology and data capabilities, builds a diverse workforce, and strengthens community engagement.',
      keyDepartments: ['Financial Services', 'Communications & Technology Mgmt', 'Human Resources', 'Communications & Public Info'],
    },
    HH: {
      focus: 'Creates complete communities with accessible services, expands affordable housing, and reduces homelessness through coordinated care.',
      keyDepartments: ['Housing & Planning', 'Homeless Services', 'Neighborhood Housing', 'Austin Housing Finance Corp'],
    },
    MC: {
      focus: 'Prioritizes transportation safety, invests in transit expansion including Project Connect, and maintains resilient utility infrastructure.',
      keyDepartments: ['Austin Transportation', 'Capital Metro', 'Austin Energy', 'Austin Water', 'Building Services'],
    },
    PS: {
      focus: 'Builds community trust, ensures equitable public safety services, and prepares for disasters through cross-sector partnerships.',
      keyDepartments: ['Austin Police', 'Austin Fire', 'EMS', 'Municipal Court', 'Office of Police Oversight'],
    },
  };
  return infoMap[code] || { focus: '', keyDepartments: [] };
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
  const extendedInfo = getPillarExtendedInfo(pillar.code);

  return (
    <div className="space-y-3 min-w-[240px] max-w-[320px]">
      {/* Header */}
      <div className="flex items-start gap-2">
        {Icon && (
          <div
            className={cn(
              'p-2 rounded-lg',
              colors.bg
            )}
          >
            <Icon className={cn('h-5 w-5', colors.text)} />
          </div>
        )}
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {pillar.name}
          </div>
          <div className="text-xs font-mono text-gray-500 dark:text-gray-400">
            City Strategic Plan Pillar {pillar.code}
          </div>
        </div>
      </div>

      {/* Extended Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {extendedInfo.focus || pillar.description}
      </p>

      {/* Key Departments */}
      {extendedInfo.keyDepartments.length > 0 && (
        <div className={cn('rounded-md p-2', colors.bg)}>
          <div className="text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
            Key Departments
          </div>
          <div className="flex flex-wrap gap-1">
            {extendedInfo.keyDepartments.map((dept) => (
              <span
                key={dept}
                className="text-[10px] px-1.5 py-0.5 rounded bg-white/60 dark:bg-dark-surface/60 text-gray-700 dark:text-gray-300"
              >
                {dept}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Goals */}
      {goals.length > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">
            Strategic Goals ({goals.length})
          </div>
          <ul className="space-y-1 max-h-32 overflow-y-auto">
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

      {/* Footer hint */}
      <div className="text-[10px] text-gray-400 dark:text-gray-500 pt-1 border-t border-gray-200 dark:border-gray-700">
        Part of Austin's Comprehensive Strategic Plan
      </div>
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
