/**
 * Badge Utilities Unit Tests
 *
 * Tests the badge utility functions for:
 * - getSizeClasses: Returns appropriate Tailwind classes for badge sizing
 * - getIconSize: Returns icon size in pixels based on badge size and scale
 * - getBadgeBaseClasses: Returns common base classes for badge components
 */

import { describe, it, expect } from 'vitest';
import {
  getSizeClasses,
  getIconSize,
  getBadgeBaseClasses,
  type BadgeSize,
  type IconScale,
} from '../badge-utils';

// ============================================================================
// getSizeClasses Tests
// ============================================================================

describe('getSizeClasses', () => {
  describe('Basic Size Classes', () => {
    it('returns correct classes for small size', () => {
      const result = getSizeClasses('sm');
      expect(result).toBe('px-1.5 py-0.5 text-xs');
    });

    it('returns correct classes for medium size', () => {
      const result = getSizeClasses('md');
      expect(result).toBe('px-2 py-1 text-sm');
    });

    it('returns correct classes for large size', () => {
      const result = getSizeClasses('lg');
      expect(result).toBe('px-3 py-1.5 text-base');
    });
  });

  describe('With Gap Classes (includeGap: true)', () => {
    it('includes gap-1 for small size', () => {
      const result = getSizeClasses('sm', { includeGap: true });
      expect(result).toBe('px-1.5 py-0.5 text-xs gap-1');
    });

    it('includes gap-1.5 for medium size', () => {
      const result = getSizeClasses('md', { includeGap: true });
      expect(result).toBe('px-2 py-1 text-sm gap-1.5');
    });

    it('includes gap-2 for large size', () => {
      const result = getSizeClasses('lg', { includeGap: true });
      expect(result).toBe('px-3 py-1.5 text-base gap-2');
    });
  });

  describe('Without Gap Classes (includeGap: false)', () => {
    it('does not include gap for small size', () => {
      const result = getSizeClasses('sm', { includeGap: false });
      expect(result).toBe('px-1.5 py-0.5 text-xs');
      expect(result).not.toContain('gap-');
    });

    it('does not include gap for medium size', () => {
      const result = getSizeClasses('md', { includeGap: false });
      expect(result).toBe('px-2 py-1 text-sm');
      expect(result).not.toContain('gap-');
    });

    it('does not include gap for large size', () => {
      const result = getSizeClasses('lg', { includeGap: false });
      expect(result).toBe('px-3 py-1.5 text-base');
      expect(result).not.toContain('gap-');
    });
  });

  describe('Pill Variant', () => {
    it('uses increased horizontal padding for small pill', () => {
      const result = getSizeClasses('sm', { variant: 'pill' });
      expect(result).toBe('px-2 py-0.5 text-xs');
    });

    it('uses increased horizontal padding for medium pill', () => {
      const result = getSizeClasses('md', { variant: 'pill' });
      expect(result).toBe('px-2.5 py-1 text-sm');
    });

    it('uses same padding for large pill (already px-3)', () => {
      const result = getSizeClasses('lg', { variant: 'pill' });
      expect(result).toBe('px-3 py-1.5 text-base');
    });
  });

  describe('Badge Variant (default)', () => {
    it('uses badge padding for small size', () => {
      const result = getSizeClasses('sm', { variant: 'badge' });
      expect(result).toBe('px-1.5 py-0.5 text-xs');
    });

    it('uses badge padding for medium size', () => {
      const result = getSizeClasses('md', { variant: 'badge' });
      expect(result).toBe('px-2 py-1 text-sm');
    });

    it('uses badge padding for large size', () => {
      const result = getSizeClasses('lg', { variant: 'badge' });
      expect(result).toBe('px-3 py-1.5 text-base');
    });
  });

  describe('Combined Options', () => {
    it('combines pill variant with gap for small', () => {
      const result = getSizeClasses('sm', { variant: 'pill', includeGap: true });
      expect(result).toBe('px-2 py-0.5 text-xs gap-1');
    });

    it('combines pill variant with gap for medium', () => {
      const result = getSizeClasses('md', { variant: 'pill', includeGap: true });
      expect(result).toBe('px-2.5 py-1 text-sm gap-1.5');
    });

    it('combines pill variant with gap for large', () => {
      const result = getSizeClasses('lg', { variant: 'pill', includeGap: true });
      expect(result).toBe('px-3 py-1.5 text-base gap-2');
    });

    it('combines badge variant with gap for medium', () => {
      const result = getSizeClasses('md', { variant: 'badge', includeGap: true });
      expect(result).toBe('px-2 py-1 text-sm gap-1.5');
    });
  });

  describe('Empty Options Object', () => {
    it('uses default values when empty options provided', () => {
      const result = getSizeClasses('md', {});
      expect(result).toBe('px-2 py-1 text-sm');
    });
  });
});

// ============================================================================
// getIconSize Tests
// ============================================================================

describe('getIconSize', () => {
  describe('Default Scale', () => {
    it('returns 12 for small size', () => {
      expect(getIconSize('sm')).toBe(12);
    });

    it('returns 14 for medium size', () => {
      expect(getIconSize('md')).toBe(14);
    });

    it('returns 16 for large size', () => {
      expect(getIconSize('lg')).toBe(16);
    });

    it('returns same values when explicitly passing "default" scale', () => {
      expect(getIconSize('sm', 'default')).toBe(12);
      expect(getIconSize('md', 'default')).toBe(14);
      expect(getIconSize('lg', 'default')).toBe(16);
    });
  });

  describe('Small Scale', () => {
    it('returns 10 for small size', () => {
      expect(getIconSize('sm', 'small')).toBe(10);
    });

    it('returns 12 for medium size', () => {
      expect(getIconSize('md', 'small')).toBe(12);
    });

    it('returns 14 for large size', () => {
      expect(getIconSize('lg', 'small')).toBe(14);
    });
  });

  describe('Scale Comparison', () => {
    it('default scale returns 2 pixels larger than small scale for each size', () => {
      const sizes: BadgeSize[] = ['sm', 'md', 'lg'];
      sizes.forEach((size) => {
        const defaultSize = getIconSize(size, 'default');
        const smallSize = getIconSize(size, 'small');
        expect(defaultSize - smallSize).toBe(2);
      });
    });

    it('all sizes return positive integers', () => {
      const sizes: BadgeSize[] = ['sm', 'md', 'lg'];
      const scales: IconScale[] = ['default', 'small'];

      sizes.forEach((size) => {
        scales.forEach((scale) => {
          const result = getIconSize(size, scale);
          expect(result).toBeGreaterThan(0);
          expect(Number.isInteger(result)).toBe(true);
        });
      });
    });
  });
});

// ============================================================================
// getBadgeBaseClasses Tests
// ============================================================================

describe('getBadgeBaseClasses', () => {
  describe('Default Options', () => {
    it('returns base classes without options', () => {
      const result = getBadgeBaseClasses();
      expect(result).toBe('inline-flex items-center rounded font-medium border cursor-default');
    });

    it('returns same classes with empty options object', () => {
      const result = getBadgeBaseClasses({});
      expect(result).toBe('inline-flex items-center rounded font-medium border cursor-default');
    });
  });

  describe('Pill Option', () => {
    it('uses rounded-full when pill is true', () => {
      const result = getBadgeBaseClasses({ pill: true });
      expect(result).toBe('inline-flex items-center rounded-full font-medium border cursor-default');
      expect(result).toContain('rounded-full');
      expect(result).not.toContain(' rounded '); // space-padded to avoid matching "rounded-full"
    });

    it('uses rounded when pill is false', () => {
      const result = getBadgeBaseClasses({ pill: false });
      expect(result).toBe('inline-flex items-center rounded font-medium border cursor-default');
      expect(result).toContain(' rounded ');
      expect(result).not.toContain('rounded-full');
    });
  });

  describe('HasTooltip Option', () => {
    it('uses cursor-pointer when hasTooltip is true', () => {
      const result = getBadgeBaseClasses({ hasTooltip: true });
      expect(result).toBe('inline-flex items-center rounded font-medium border cursor-pointer');
      expect(result).toContain('cursor-pointer');
      expect(result).not.toContain('cursor-default');
    });

    it('uses cursor-default when hasTooltip is false', () => {
      const result = getBadgeBaseClasses({ hasTooltip: false });
      expect(result).toBe('inline-flex items-center rounded font-medium border cursor-default');
      expect(result).toContain('cursor-default');
      expect(result).not.toContain('cursor-pointer');
    });
  });

  describe('Combined Options', () => {
    it('combines pill and hasTooltip options', () => {
      const result = getBadgeBaseClasses({ pill: true, hasTooltip: true });
      expect(result).toBe('inline-flex items-center rounded-full font-medium border cursor-pointer');
      expect(result).toContain('rounded-full');
      expect(result).toContain('cursor-pointer');
    });

    it('combines pill=true with hasTooltip=false', () => {
      const result = getBadgeBaseClasses({ pill: true, hasTooltip: false });
      expect(result).toBe('inline-flex items-center rounded-full font-medium border cursor-default');
      expect(result).toContain('rounded-full');
      expect(result).toContain('cursor-default');
    });

    it('combines pill=false with hasTooltip=true', () => {
      const result = getBadgeBaseClasses({ pill: false, hasTooltip: true });
      expect(result).toBe('inline-flex items-center rounded font-medium border cursor-pointer');
      expect(result).not.toContain('rounded-full');
      expect(result).toContain('cursor-pointer');
    });
  });

  describe('Common Classes', () => {
    it('always includes inline-flex', () => {
      expect(getBadgeBaseClasses()).toContain('inline-flex');
      expect(getBadgeBaseClasses({ pill: true })).toContain('inline-flex');
      expect(getBadgeBaseClasses({ hasTooltip: true })).toContain('inline-flex');
    });

    it('always includes items-center', () => {
      expect(getBadgeBaseClasses()).toContain('items-center');
      expect(getBadgeBaseClasses({ pill: true })).toContain('items-center');
      expect(getBadgeBaseClasses({ hasTooltip: true })).toContain('items-center');
    });

    it('always includes font-medium', () => {
      expect(getBadgeBaseClasses()).toContain('font-medium');
      expect(getBadgeBaseClasses({ pill: true })).toContain('font-medium');
      expect(getBadgeBaseClasses({ hasTooltip: true })).toContain('font-medium');
    });

    it('always includes border', () => {
      expect(getBadgeBaseClasses()).toContain('border');
      expect(getBadgeBaseClasses({ pill: true })).toContain('border');
      expect(getBadgeBaseClasses({ hasTooltip: true })).toContain('border');
    });
  });
});
