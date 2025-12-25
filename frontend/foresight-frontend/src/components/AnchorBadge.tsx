/**
 * AnchorBadge Component
 *
 * Displays a strategic anchor with:
 * - Icon representing the anchor type
 * - Anchor name
 * - Tooltip showing full description
 */

import React from 'react';
import {
  Scale,
  DollarSign,
  Lightbulb,
  Leaf,
  ShieldCheck,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { Tooltip } from './ui/Tooltip';
import { cn } from '../lib/utils';
import { getSizeClasses, getIconSize, type BadgeSize } from '../lib/badge-utils';
import { getAnchorByName, type Anchor } from '../data/taxonomy';

// Icon mapping for anchors
const anchorIcons: Record<string, LucideIcon> = {
  Scale: Scale,
  DollarSign: DollarSign,
  Lightbulb: Lightbulb,
  Leaf: Leaf,
  ShieldCheck: ShieldCheck,
  Users: Users,
};

// Color mapping for anchors
const anchorColors: Record<string, { bg: string; text: string; border: string }> = {
  Equity: {
    bg: 'bg-violet-100',
    text: 'text-violet-700',
    border: 'border-violet-300',
  },
  Affordability: {
    bg: 'bg-emerald-100',
    text: 'text-emerald-700',
    border: 'border-emerald-300',
  },
  Innovation: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-700',
    border: 'border-yellow-300',
  },
  'Sustainability & Resiliency': {
    bg: 'bg-green-100',
    text: 'text-green-700',
    border: 'border-green-300',
  },
  'Proactive Prevention': {
    bg: 'bg-blue-100',
    text: 'text-blue-700',
    border: 'border-blue-300',
  },
  'Community Trust & Relationships': {
    bg: 'bg-rose-100',
    text: 'text-rose-700',
    border: 'border-rose-300',
  },
};

export interface AnchorBadgeProps {
  /** Anchor name */
  anchor: string;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show the icon */
  showIcon?: boolean;
  /** Whether to show abbreviated name */
  abbreviated?: boolean;
  /** Additional className */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
}

/**
 * Get abbreviated anchor name
 */
function getAbbreviatedName(name: string): string {
  const abbreviations: Record<string, string> = {
    Equity: 'Equity',
    Affordability: 'Afford.',
    Innovation: 'Innov.',
    'Sustainability & Resiliency': 'Sustain.',
    'Proactive Prevention': 'Prevent.',
    'Community Trust & Relationships': 'Trust',
  };
  return abbreviations[name] || name;
}


/**
 * Tooltip content component for anchor
 */
function AnchorTooltipContent({ anchor }: { anchor: Anchor }) {
  const Icon = anchorIcons[anchor.icon];
  const colors = anchorColors[anchor.name] || {
    bg: 'bg-gray-100',
    text: 'text-gray-700',
    border: 'border-gray-300',
  };

  return (
    <div className="space-y-2 min-w-[180px] max-w-[240px]">
      {/* Header */}
      <div className="flex items-center gap-2">
        {Icon && (
          <div className={cn('p-1.5 rounded-md', colors.bg)}>
            <Icon className={cn('h-4 w-4', colors.text)} />
          </div>
        )}
        <div className="font-semibold text-gray-900 dark:text-gray-100">
          {anchor.name}
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {anchor.description}
      </p>
    </div>
  );
}

/**
 * AnchorBadge component
 */
export function AnchorBadge({
  anchor,
  size = 'md',
  showIcon = true,
  abbreviated = false,
  className,
  disableTooltip = false,
}: AnchorBadgeProps) {
  const anchorData = getAnchorByName(anchor);

  if (!anchorData) {
    return (
      <span
        className={cn(
          'inline-flex items-center rounded font-medium border',
          'bg-gray-100 text-gray-600 border-gray-300',
          getSizeClasses(size, { includeGap: true }),
          className
        )}
      >
        {anchor}
      </span>
    );
  }

  const colors = anchorColors[anchor] || {
    bg: 'bg-gray-100',
    text: 'text-gray-700',
    border: 'border-gray-300',
  };
  const Icon = showIcon ? anchorIcons[anchorData.icon] : null;
  const iconSize = getIconSize(size);
  const displayName = abbreviated ? getAbbreviatedName(anchor) : anchor;

  const badge = (
    <span
      className={cn(
        'inline-flex items-center rounded font-medium border cursor-default',
        colors.bg,
        colors.text,
        colors.border,
        getSizeClasses(size, { includeGap: true }),
        !disableTooltip && 'cursor-pointer',
        className
      )}
      role="status"
      aria-label={`Strategic anchor: ${anchor}`}
    >
      {Icon && <Icon className="shrink-0" size={iconSize} />}
      <span>{displayName}</span>
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={<AnchorTooltipContent anchor={anchorData} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

/**
 * Multiple anchors displayed as a group
 */
export interface AnchorBadgeGroupProps {
  /** Array of anchor names */
  anchors: string[];
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show icons */
  showIcon?: boolean;
  /** Whether to abbreviate names */
  abbreviated?: boolean;
  /** Maximum number to show before "+N more" */
  maxVisible?: number;
  /** Additional className for the group container */
  className?: string;
}

export function AnchorBadgeGroup({
  anchors,
  size = 'sm',
  showIcon = true,
  abbreviated = true,
  maxVisible = 2,
  className,
}: AnchorBadgeGroupProps) {
  const visibleAnchors = anchors.slice(0, maxVisible);
  const remainingCount = anchors.length - maxVisible;

  return (
    <div className={cn('inline-flex items-center gap-1 flex-wrap', className)}>
      {visibleAnchors.map((anchor) => (
        <AnchorBadge
          key={anchor}
          anchor={anchor}
          size={size}
          showIcon={showIcon}
          abbreviated={abbreviated}
        />
      ))}
      {remainingCount > 0 && (
        <Tooltip
          content={
            <div className="space-y-1">
              <div className="text-xs font-medium text-gray-500">
                Additional anchors:
              </div>
              <ul className="text-sm">
                {anchors.slice(maxVisible).map((anchor) => (
                  <li key={anchor}>{anchor}</li>
                ))}
              </ul>
            </div>
          }
          side="top"
          contentClassName="p-2"
        >
          <span
            className={cn(
              'inline-flex items-center rounded font-medium cursor-pointer',
              'bg-gray-100 text-gray-600 border border-gray-300',
              getSizeClasses(size, { includeGap: true })
            )}
          >
            +{remainingCount}
          </span>
        </Tooltip>
      )}
    </div>
  );
}

/**
 * Icon-only anchor indicator
 */
export interface AnchorIconProps {
  /** Anchor name */
  anchor: string;
  /** Size in pixels */
  size?: number;
  /** Additional className */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
}

export function AnchorIcon({
  anchor,
  size = 16,
  className,
  disableTooltip = false,
}: AnchorIconProps) {
  const anchorData = getAnchorByName(anchor);

  if (!anchorData) {
    return null;
  }

  const Icon = anchorIcons[anchorData.icon];
  const colors = anchorColors[anchor] || {
    bg: 'bg-gray-100',
    text: 'text-gray-700',
    border: 'border-gray-300',
  };

  if (!Icon) {
    return null;
  }

  const icon = (
    <span
      className={cn(
        'inline-flex items-center justify-center rounded p-1',
        colors.bg,
        !disableTooltip && 'cursor-pointer',
        className
      )}
      role="status"
      aria-label={anchor}
    >
      <Icon className={colors.text} size={size} />
    </span>
  );

  if (disableTooltip) {
    return icon;
  }

  return (
    <Tooltip
      content={<AnchorTooltipContent anchor={anchorData} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {icon}
    </Tooltip>
  );
}

export default AnchorBadge;
