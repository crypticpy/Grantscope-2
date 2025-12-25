/**
 * Badge Utilities
 *
 * Shared utility functions and types for badge components.
 * This module reduces duplication across PillarBadge, HorizonBadge,
 * ConfidenceBadge, StageBadge, AnchorBadge, and Top25Badge.
 */

import React from 'react';
import { Tooltip } from '../components/ui/Tooltip';

// =============================================================================
// Types
// =============================================================================

/**
 * Badge size variants used across all badge components.
 *
 * Size mappings:
 * - `'sm'` - Small: Compact badges for dense UIs (text-xs, px-1.5 py-0.5)
 * - `'md'` - Medium: Default size for most use cases (text-sm, px-2 py-1)
 * - `'lg'` - Large: Prominent badges for emphasis (text-base, px-3 py-1.5)
 *
 * @example
 * // Component prop definition
 * interface BadgeProps {
 *   size?: BadgeSize;
 * }
 */
export type BadgeSize = 'sm' | 'md' | 'lg';

/**
 * Base color classes for badge styling.
 *
 * Provides the essential Tailwind CSS classes for badge appearance.
 * Used by all badge components to maintain consistent color theming.
 *
 * @example
 * const colors: ColorClasses = {
 *   bg: 'bg-blue-100 dark:bg-blue-900',
 *   text: 'text-blue-700 dark:text-blue-300',
 *   border: 'border-blue-200 dark:border-blue-800',
 * };
 */
export interface ColorClasses {
  /** Background color classes (e.g., 'bg-blue-100 dark:bg-blue-900') */
  bg: string;
  /** Text color classes (e.g., 'text-blue-700 dark:text-blue-300') */
  text: string;
  /** Border color classes (e.g., 'border-blue-200 dark:border-blue-800') */
  border: string;
}

/**
 * Extended color classes with optional icon background and progress colors.
 *
 * Extends {@link ColorClasses} with additional optional properties for
 * badges that have icon backgrounds or progress indicators.
 *
 * @example
 * // Stage badge with progress colors
 * const stageColors: ExtendedColorClasses = {
 *   bg: 'bg-emerald-100 dark:bg-emerald-900',
 *   text: 'text-emerald-700 dark:text-emerald-300',
 *   border: 'border-emerald-200 dark:border-emerald-800',
 *   iconBg: 'bg-emerald-500',
 *   progress: 'bg-emerald-400',
 * };
 */
export interface ExtendedColorClasses extends ColorClasses {
  /** Background color for icon containers (e.g., 'bg-emerald-500') */
  iconBg?: string;
  /** Color for progress indicators (e.g., 'bg-emerald-400') */
  progress?: string;
}

/**
 * Icon size scale variants for badge icons.
 *
 * Different badge components use different icon scales based on their design:
 * - `'default'` - Standard scale: sm=12px, md=14px, lg=16px
 *   Used by: PillarBadge, AnchorBadge, Top25Badge
 * - `'small'` - Compact scale: sm=10px, md=12px, lg=14px
 *   Used by: HorizonBadge, ConfidenceBadge
 *
 * @see {@link getIconSize} for the function that uses this type
 *
 * @example
 * // Get icon size for different badges
 * const pillarIconSize = getIconSize('md', 'default');  // 14
 * const horizonIconSize = getIconSize('md', 'small');   // 12
 */
export type IconScale = 'default' | 'small';

/**
 * Icon size mappings for each scale
 */
const ICON_SIZE_MAP: Record<IconScale, Record<BadgeSize, number>> = {
  default: { sm: 12, md: 14, lg: 16 },
  small: { sm: 10, md: 12, lg: 14 },
};

/**
 * Get the icon size in pixels for a given badge size and scale.
 *
 * @param size - The badge size ('sm' | 'md' | 'lg')
 * @param scale - The icon scale ('default' | 'small'), defaults to 'default'
 * @returns The icon size in pixels
 *
 * @example
 * // Default scale (PillarBadge, AnchorBadge)
 * getIconSize('sm'); // 12
 * getIconSize('md'); // 14
 * getIconSize('lg'); // 16
 *
 * @example
 * // Small scale (HorizonBadge, ConfidenceBadge)
 * getIconSize('sm', 'small'); // 10
 * getIconSize('md', 'small'); // 12
 * getIconSize('lg', 'small'); // 14
 */
export function getIconSize(size: BadgeSize, scale: IconScale = 'default'): number {
  return ICON_SIZE_MAP[scale][size];
}

/**
 * Options for generating badge base classes
 */
export interface BadgeBaseClassesOptions {
  /**
   * Whether to use pill styling (rounded-full instead of rounded)
   * @default false
   */
  pill?: boolean;
  /**
   * Whether the badge has an active tooltip (changes cursor to pointer)
   * @default false
   */
  hasTooltip?: boolean;
}

/**
 * Get the common base classes for badge components.
 *
 * Returns a string of Tailwind classes that provide consistent styling
 * across all badge components: layout, rounding, font weight, border, and cursor.
 *
 * @param options - Configuration options for the base classes
 * @returns A string of Tailwind CSS classes
 *
 * @example
 * // Default badge styling
 * getBadgeBaseClasses();
 * // Returns: 'inline-flex items-center rounded font-medium border cursor-default'
 *
 * @example
 * // Pill variant
 * getBadgeBaseClasses({ pill: true });
 * // Returns: 'inline-flex items-center rounded-full font-medium border cursor-default'
 *
 * @example
 * // Badge with tooltip (clickable cursor)
 * getBadgeBaseClasses({ hasTooltip: true });
 * // Returns: 'inline-flex items-center rounded font-medium border cursor-pointer'
 *
 * @example
 * // Pill variant with tooltip
 * getBadgeBaseClasses({ pill: true, hasTooltip: true });
 * // Returns: 'inline-flex items-center rounded-full font-medium border cursor-pointer'
 */
export function getBadgeBaseClasses(options: BadgeBaseClassesOptions = {}): string {
  const { pill = false, hasTooltip = false } = options;

  const rounding = pill ? 'rounded-full' : 'rounded';
  const cursor = hasTooltip ? 'cursor-pointer' : 'cursor-default';

  return `inline-flex items-center ${rounding} font-medium border ${cursor}`;
}

// =============================================================================
// Size Classes
// =============================================================================

/**
 * Options for getSizeClasses function
 */
export interface GetSizeClassesOptions {
  /**
   * Include gap classes for icon spacing
   * - sm: gap-1
   * - md: gap-1.5
   * - lg: gap-2
   * @default false
   */
  includeGap?: boolean;

  /**
   * Use pill variant padding (slightly more horizontal padding)
   * - sm: px-2 (instead of px-1.5)
   * - md: px-2.5 (instead of px-2)
   * - lg: px-3 (same)
   * @default 'badge'
   */
  variant?: 'badge' | 'pill';
}

/**
 * Get Tailwind CSS classes for badge sizing.
 *
 * Base patterns:
 * - sm: px-1.5 py-0.5 text-xs
 * - md: px-2 py-1 text-sm
 * - lg: px-3 py-1.5 text-base
 *
 * @param size - The badge size variant
 * @param options - Optional configuration for gap and variant
 * @returns Tailwind CSS class string
 *
 * @example
 * // Basic usage
 * getSizeClasses('md'); // 'px-2 py-1 text-sm'
 *
 * @example
 * // With gap classes for badges with icons
 * getSizeClasses('md', { includeGap: true }); // 'px-2 py-1 text-sm gap-1.5'
 *
 * @example
 * // Pill variant with more horizontal padding
 * getSizeClasses('sm', { variant: 'pill' }); // 'px-2 py-0.5 text-xs'
 *
 * @example
 * // Combined options
 * getSizeClasses('lg', { includeGap: true, variant: 'pill' }); // 'px-3 py-1.5 text-base gap-2'
 */
export function getSizeClasses(
  size: BadgeSize,
  options: GetSizeClassesOptions = {}
): string {
  const { includeGap = false, variant = 'badge' } = options;

  // Base size classes (padding and text)
  const baseSizeMap: Record<BadgeSize, { padding: string; text: string }> = {
    sm: { padding: 'px-1.5 py-0.5', text: 'text-xs' },
    md: { padding: 'px-2 py-1', text: 'text-sm' },
    lg: { padding: 'px-3 py-1.5', text: 'text-base' },
  };

  // Pill variant has slightly more horizontal padding for sm and md
  const pillSizeMap: Record<BadgeSize, { padding: string; text: string }> = {
    sm: { padding: 'px-2 py-0.5', text: 'text-xs' },
    md: { padding: 'px-2.5 py-1', text: 'text-sm' },
    lg: { padding: 'px-3 py-1.5', text: 'text-base' },
  };

  // Gap classes for icon spacing
  const gapMap: Record<BadgeSize, string> = {
    sm: 'gap-1',
    md: 'gap-1.5',
    lg: 'gap-2',
  };

  const sizeMap = variant === 'pill' ? pillSizeMap : baseSizeMap;
  const { padding, text } = sizeMap[size];

  const classes = [padding, text];

  if (includeGap) {
    classes.push(gapMap[size]);
  }

  return classes.join(' ');
}

// =============================================================================
// Badge Tooltip Wrapper
// =============================================================================

/**
 * Props for the BadgeTooltipWrapper component
 */
export interface BadgeTooltipWrapperProps {
  /**
   * The badge element to wrap
   */
  children: React.ReactNode;

  /**
   * Tooltip content - can be string or React node
   */
  content: React.ReactNode;

  /**
   * When true, returns children directly without tooltip wrapper
   * @default false
   */
  disabled?: boolean;
}

/**
 * A wrapper component that encapsulates the common tooltip pattern used by badge components.
 *
 * Provides consistent tooltip positioning and styling across all badge components:
 * - Position: top with center alignment
 * - Padding: p-3 content padding
 *
 * When disabled, returns children directly without the tooltip wrapper.
 *
 * @param props - The component props
 * @returns The badge wrapped in a tooltip, or just the badge if disabled
 *
 * @example
 * // Basic usage
 * <BadgeTooltipWrapper
 *   content={<TooltipContent data={data} />}
 *   disabled={disableTooltip}
 * >
 *   {badge}
 * </BadgeTooltipWrapper>
 *
 * @example
 * // Simple text content
 * <BadgeTooltipWrapper content="Additional information" disabled={false}>
 *   <span className="badge">Label</span>
 * </BadgeTooltipWrapper>
 *
 * @example
 * // With disabled tooltip
 * <BadgeTooltipWrapper content="Won't show" disabled={true}>
 *   {badge}
 * </BadgeTooltipWrapper>
 */
export function BadgeTooltipWrapper({
  children,
  content,
  disabled = false,
}: BadgeTooltipWrapperProps): React.ReactElement {
  if (disabled) {
    return <>{children}</>;
  }

  return (
    <Tooltip
      content={content}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      {children}
    </Tooltip>
  );
}
