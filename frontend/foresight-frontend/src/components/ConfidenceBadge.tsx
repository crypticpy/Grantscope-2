/**
 * ConfidenceBadge Component
 *
 * Displays an AI confidence score as a visual badge with:
 * - Color coding: green (>0.9), amber (0.7-0.9), red (<0.7)
 * - Tooltip explaining the confidence level
 * - Optional percentage display
 */

import React from 'react';
import { Brain, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { Tooltip } from './ui/Tooltip';
import { cn } from '../lib/utils';

export interface ConfidenceBadgeProps {
  /** Confidence score between 0 and 1 */
  confidence: number;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show the percentage value */
  showValue?: boolean;
  /** Whether to show an icon */
  showIcon?: boolean;
  /** Additional className */
  className?: string;
  /** Whether tooltip is disabled */
  disableTooltip?: boolean;
  /** Display variant */
  variant?: 'badge' | 'pill' | 'minimal';
}

/**
 * Get confidence level category
 */
function getConfidenceLevel(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= 0.9) return 'high';
  if (confidence >= 0.7) return 'medium';
  return 'low';
}

/**
 * Get color classes based on confidence level
 */
function getConfidenceColorClasses(level: 'high' | 'medium' | 'low'): {
  bg: string;
  text: string;
  border: string;
  iconBg: string;
} {
  const colorMap = {
    high: {
      bg: 'bg-green-100 dark:bg-green-900/30',
      text: 'text-green-700 dark:text-green-300',
      border: 'border-green-300 dark:border-green-700',
      iconBg: 'bg-green-200 dark:bg-green-800',
    },
    medium: {
      bg: 'bg-amber-100 dark:bg-amber-900/30',
      text: 'text-amber-700 dark:text-amber-300',
      border: 'border-amber-300 dark:border-amber-700',
      iconBg: 'bg-amber-200 dark:bg-amber-800',
    },
    low: {
      bg: 'bg-red-100 dark:bg-red-900/30',
      text: 'text-red-700 dark:text-red-300',
      border: 'border-red-300 dark:border-red-700',
      iconBg: 'bg-red-200 dark:bg-red-800',
    },
  };

  return colorMap[level];
}

/**
 * Get the appropriate icon for confidence level
 */
function getConfidenceIcon(level: 'high' | 'medium' | 'low') {
  const iconMap = {
    high: CheckCircle,
    medium: AlertTriangle,
    low: XCircle,
  };
  return iconMap[level];
}

/**
 * Get size classes for the badge
 */
function getSizeClasses(size: 'sm' | 'md' | 'lg', variant: 'badge' | 'pill' | 'minimal'): string {
  if (variant === 'minimal') {
    const sizeMap = {
      sm: 'text-xs',
      md: 'text-sm',
      lg: 'text-base',
    };
    return sizeMap[size];
  }

  const sizeMap = {
    sm: 'px-1.5 py-0.5 text-xs gap-1',
    md: 'px-2 py-1 text-sm gap-1.5',
    lg: 'px-3 py-1.5 text-base gap-2',
  };
  return sizeMap[size];
}

/**
 * Get icon size
 */
function getIconSize(size: 'sm' | 'md' | 'lg'): number {
  const sizeMap = { sm: 10, md: 12, lg: 14 };
  return sizeMap[size];
}

/**
 * Format confidence as percentage
 */
function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Get confidence level label
 */
function getConfidenceLabel(level: 'high' | 'medium' | 'low'): string {
  const labels = {
    high: 'High Confidence',
    medium: 'Medium Confidence',
    low: 'Low Confidence',
  };
  return labels[level];
}

/**
 * Tooltip content for confidence badge
 */
function ConfidenceTooltipContent({
  confidence,
  level,
}: {
  confidence: number;
  level: 'high' | 'medium' | 'low';
}) {
  const colors = getConfidenceColorClasses(level);
  const Icon = getConfidenceIcon(level);

  const descriptions = {
    high: 'The AI system has high confidence in the accuracy and relevance of this discovery. Minimal review may be needed.',
    medium: 'The AI system has moderate confidence. Some aspects may need verification or additional context.',
    low: 'The AI system has lower confidence in this discovery. Careful review is recommended before approval.',
  };

  const recommendations = {
    high: 'This card is likely ready for quick approval with minimal changes.',
    medium: 'Consider reviewing the summary and classification before approval.',
    low: 'Carefully review all fields and consider if this card should be dismissed.',
  };

  return (
    <div className="space-y-3 min-w-[220px] max-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className={cn('p-1.5 rounded-md', colors.iconBg)}>
          <Icon className={cn('h-4 w-4', colors.text)} />
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {getConfidenceLabel(level)}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {formatConfidence(confidence)} AI Confidence
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {descriptions[level]}
      </p>

      {/* Recommendation */}
      <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
        <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
          Recommendation
        </div>
        <p className="text-xs text-gray-600 dark:text-gray-300">
          {recommendations[level]}
        </p>
      </div>

      {/* Confidence bar */}
      <div className="pt-1">
        <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              level === 'high' && 'bg-green-500 dark:bg-green-400',
              level === 'medium' && 'bg-amber-500 dark:bg-amber-400',
              level === 'low' && 'bg-red-500 dark:bg-red-400'
            )}
            style={{ width: `${confidence * 100}%` }}
          />
        </div>
        <div className="flex justify-between mt-1 text-[10px] text-gray-400">
          <span>0%</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  );
}

/**
 * ConfidenceBadge component
 */
export function ConfidenceBadge({
  confidence,
  size = 'md',
  showValue = true,
  showIcon = true,
  className,
  disableTooltip = false,
  variant = 'badge',
}: ConfidenceBadgeProps) {
  // Clamp confidence to 0-1 range
  const clampedConfidence = Math.max(0, Math.min(1, confidence));
  const level = getConfidenceLevel(clampedConfidence);
  const colors = getConfidenceColorClasses(level);
  const Icon = showIcon ? getConfidenceIcon(level) : Brain;
  const iconSize = getIconSize(size);

  // Minimal variant - just colored text
  if (variant === 'minimal') {
    const badge = (
      <span
        className={cn(
          'inline-flex items-center gap-1 font-medium cursor-default',
          colors.text,
          getSizeClasses(size, variant),
          !disableTooltip && 'cursor-pointer',
          className
        )}
        role="status"
        aria-label={`${getConfidenceLabel(level)}: ${formatConfidence(clampedConfidence)}`}
      >
        {showIcon && <Icon className="shrink-0" size={iconSize} />}
        {showValue && <span>{formatConfidence(clampedConfidence)}</span>}
      </span>
    );

    if (disableTooltip) {
      return badge;
    }

    return (
      <Tooltip
        content={<ConfidenceTooltipContent confidence={clampedConfidence} level={level} />}
        side="top"
        align="center"
        contentClassName="p-3"
      >
        {badge}
      </Tooltip>
    );
  }

  // Badge or pill variant
  const badge = (
    <span
      className={cn(
        'inline-flex items-center font-medium border cursor-default',
        colors.bg,
        colors.text,
        colors.border,
        variant === 'pill' ? 'rounded-full' : 'rounded',
        getSizeClasses(size, variant),
        !disableTooltip && 'cursor-pointer',
        className
      )}
      role="status"
      aria-label={`${getConfidenceLabel(level)}: ${formatConfidence(clampedConfidence)}`}
    >
      {showIcon && <Icon className="shrink-0" size={iconSize} />}
      {showValue && <span>{formatConfidence(clampedConfidence)}</span>}
    </span>
  );

  if (disableTooltip) {
    return badge;
  }

  return (
    <Tooltip
      content={<ConfidenceTooltipContent confidence={clampedConfidence} level={level} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {badge}
    </Tooltip>
  );
}

/**
 * Compact confidence indicator for list views
 */
export interface ConfidenceIndicatorProps {
  confidence: number;
  className?: string;
}

export function ConfidenceIndicator({ confidence, className }: ConfidenceIndicatorProps) {
  const level = getConfidenceLevel(confidence);
  const colors = getConfidenceColorClasses(level);

  return (
    <div
      className={cn('flex items-center gap-1', className)}
      title={`${getConfidenceLabel(level)}: ${formatConfidence(confidence)}`}
    >
      <div
        className={cn(
          'w-2 h-2 rounded-full',
          level === 'high' && 'bg-green-500',
          level === 'medium' && 'bg-amber-500',
          level === 'low' && 'bg-red-500'
        )}
      />
      <span className={cn('text-xs font-medium', colors.text)}>
        {formatConfidence(confidence)}
      </span>
    </div>
  );
}

export default ConfidenceBadge;
