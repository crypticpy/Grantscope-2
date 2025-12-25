/**
 * Badge Utilities
 *
 * Shared utility functions and types for badge components.
 * This module reduces duplication across PillarBadge, HorizonBadge,
 * ConfidenceBadge, StageBadge, AnchorBadge, and Top25Badge.
 */

// =============================================================================
// Types
// =============================================================================

/**
 * Badge size variants
 */
export type BadgeSize = 'sm' | 'md' | 'lg';

/**
 * Base color classes for badge styling
 */
export interface ColorClasses {
  bg: string;
  text: string;
  border: string;
}

/**
 * Extended color classes with optional icon background and progress colors
 */
export interface ExtendedColorClasses extends ColorClasses {
  iconBg?: string;
  progress?: string;
}

/**
 * Icon size scale variants
 * - 'default': sm=12, md=14, lg=16 (used by PillarBadge, AnchorBadge)
 * - 'small': sm=10, md=12, lg=14 (used by HorizonBadge, ConfidenceBadge)
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
