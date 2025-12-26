/**
 * HorizonBadge Component
 *
 * Displays a horizon (H1/H2/H3) indicator with:
 * - Color coding: H1=green, H2=amber, H3=purple
 * - Tooltip showing horizon name, timeframe, and description
 */

import React from 'react';
import { Clock, TrendingUp, Sparkles } from 'lucide-react';
import { Tooltip } from './ui/Tooltip';
import { cn } from '../lib/utils';
import { getHorizonByCode, type Horizon } from '../data/taxonomy';
import { getSizeClasses, getIconSize } from '../lib/badge-utils';

export interface HorizonBadgeProps {
  /** Horizon code ('H1', 'H2', or 'H3') */
  horizon: 'H1' | 'H2' | 'H3';
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show an icon */
  showIcon?: boolean;
  /** Additional className */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
  /** Display style: 'badge' or 'pill' */
  variant?: 'badge' | 'pill';
}

/**
 * Get color classes for a horizon
 */
function getHorizonColorClasses(horizonCode: string): {
  bg: string;
  text: string;
  border: string;
  iconBg: string;
} {
  const colorMap: Record<string, { bg: string; text: string; border: string; iconBg: string }> = {
    H1: {
      bg: 'bg-green-100',
      text: 'text-green-700',
      border: 'border-green-300',
      iconBg: 'bg-green-200',
    },
    H2: {
      bg: 'bg-amber-100',
      text: 'text-amber-700',
      border: 'border-amber-300',
      iconBg: 'bg-amber-200',
    },
    H3: {
      bg: 'bg-purple-100',
      text: 'text-purple-700',
      border: 'border-purple-300',
      iconBg: 'bg-purple-200',
    },
  };

  return colorMap[horizonCode] || { bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-300', iconBg: 'bg-gray-200' };
}

/**
 * Get the appropriate icon for a horizon
 */
function getHorizonIcon(horizonCode: string) {
  const iconMap: Record<string, typeof Clock> = {
    H1: Clock,        // Current/Mainstream
    H2: TrendingUp,   // Transitional/Emerging
    H3: Sparkles,     // Transformative/Future
  };
  return iconMap[horizonCode] || Clock;
}


/**
 * Tooltip content component for horizon
 */
function HorizonTooltipContent({ horizon }: { horizon: Horizon }) {
  const colors = getHorizonColorClasses(horizon.code);
  const Icon = getHorizonIcon(horizon.code);

  return (
    <div className="space-y-2 min-w-[180px] max-w-[240px]">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className={cn('p-1.5 rounded-md', colors.iconBg)}>
          <Icon className={cn('h-4 w-4', colors.text)} />
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {horizon.code}: {horizon.name}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {horizon.timeframe}
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {horizon.description}
      </p>

      {/* Timeline indicator */}
      <div className="pt-1">
        <div className="flex items-center gap-1">
          <div className="flex-1 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all',
                horizon.code === 'H1' && 'w-1/3 bg-green-500',
                horizon.code === 'H2' && 'w-2/3 bg-amber-500',
                horizon.code === 'H3' && 'w-full bg-purple-500'
              )}
            />
          </div>
        </div>
        <div className="flex justify-between mt-1 text-[10px] text-gray-400">
          <span>Now</span>
          <span>15+ years</span>
        </div>
      </div>
    </div>
  );
}

/**
 * HorizonBadge component
 */
export function HorizonBadge({
  horizon,
  size = 'md',
  showIcon = false,
  className,
  disableTooltip = false,
  variant = 'badge',
}: HorizonBadgeProps) {
  const horizonData = getHorizonByCode(horizon);

  if (!horizonData) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 font-medium border',
          'bg-gray-100 text-gray-600 border-gray-300',
          variant === 'pill' ? 'rounded-full' : 'rounded',
          getSizeClasses(size, { variant }),
          className
        )}
      >
        {horizon}
      </span>
    );
  }

  const colors = getHorizonColorClasses(horizon);
  const Icon = getHorizonIcon(horizon);
  const iconSize = getIconSize(size, 'small');

  const badge = (
    <span
      className={cn(
        'inline-flex items-center gap-1 font-semibold border cursor-default',
        colors.bg,
        colors.text,
        colors.border,
        variant === 'pill' ? 'rounded-full' : 'rounded',
        getSizeClasses(size, { variant }),
        !disableTooltip && 'cursor-pointer',
        className
      )}
      role="status"
      aria-label={`${horizonData.name} horizon (${horizonData.timeframe})`}
    >
      {showIcon && <Icon className="shrink-0" size={iconSize} />}
      <span>{horizon}</span>
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={<HorizonTooltipContent horizon={horizonData} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

/**
 * Display all three horizons with current one highlighted
 */
export interface HorizonIndicatorProps {
  /** Current horizon */
  horizon: 'H1' | 'H2' | 'H3';
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Additional className */
  className?: string;
}

export function HorizonIndicator({
  horizon,
  size: _size = 'sm',
  className,
}: HorizonIndicatorProps) {
  const horizons: ('H1' | 'H2' | 'H3')[] = ['H1', 'H2', 'H3'];

  return (
    <div className={cn('inline-flex items-center gap-0.5', className)}>
      {horizons.map((h) => {
        const isActive = h === horizon;
        const colors = getHorizonColorClasses(h);

        return (
          <span
            key={h}
            className={cn(
              'text-xs font-medium px-1.5 py-0.5 transition-all',
              h === 'H1' && 'rounded-l',
              h === 'H3' && 'rounded-r',
              isActive
                ? cn(colors.bg, colors.text, 'border', colors.border)
                : 'bg-gray-100 text-gray-400 border border-gray-200'
            )}
          >
            {h}
          </span>
        );
      })}
    </div>
  );
}

export default HorizonBadge;
