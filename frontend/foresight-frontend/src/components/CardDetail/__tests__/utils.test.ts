/**
 * CardDetail Utility Functions Unit Tests
 *
 * Tests the utility functions for:
 * - parseStageNumber: Parsing stage numbers from stage_id strings
 * - getScoreColorClasses: Getting color classes based on score values
 * - formatRelativeTime: Formatting dates as relative time strings
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  parseStageNumber,
  getScoreColorClasses,
  formatRelativeTime,
} from '../utils';

// ============================================================================
// parseStageNumber Tests
// ============================================================================

describe('parseStageNumber', () => {
  describe('Valid Stage IDs', () => {
    it('parses "1_concept" to 1', () => {
      expect(parseStageNumber('1_concept')).toBe(1);
    });

    it('parses "2_explore" to 2', () => {
      expect(parseStageNumber('2_explore')).toBe(2);
    });

    it('parses "3_prototype" to 3', () => {
      expect(parseStageNumber('3_prototype')).toBe(3);
    });

    it('parses "4_pilot" to 4', () => {
      expect(parseStageNumber('4_pilot')).toBe(4);
    });

    it('parses "5_scale" to 5', () => {
      expect(parseStageNumber('5_scale')).toBe(5);
    });

    it('parses "6_sustain" to 6', () => {
      expect(parseStageNumber('6_sustain')).toBe(6);
    });
  });

  describe('Multi-digit Stage Numbers', () => {
    it('parses "10_future" to 10', () => {
      expect(parseStageNumber('10_future')).toBe(10);
    });

    it('parses "123_test" to 123', () => {
      expect(parseStageNumber('123_test')).toBe(123);
    });
  });

  describe('Edge Cases', () => {
    it('returns null for empty string', () => {
      expect(parseStageNumber('')).toBeNull();
    });

    it('returns null for string without leading number', () => {
      expect(parseStageNumber('concept')).toBeNull();
    });

    it('returns null for string with letter prefix', () => {
      expect(parseStageNumber('a1_concept')).toBeNull();
    });

    it('returns null for string starting with underscore', () => {
      expect(parseStageNumber('_1_concept')).toBeNull();
    });

    it('parses stage with only number', () => {
      expect(parseStageNumber('5')).toBe(5);
    });

    it('parses number without underscore', () => {
      expect(parseStageNumber('3prototype')).toBe(3);
    });

    it('parses number with spaces', () => {
      expect(parseStageNumber('2 explore')).toBe(2);
    });

    it('parses zero as valid stage number', () => {
      expect(parseStageNumber('0_initial')).toBe(0);
    });
  });
});

// ============================================================================
// getScoreColorClasses Tests
// ============================================================================

describe('getScoreColorClasses', () => {
  describe('Green Range (80-100)', () => {
    it('returns green classes for score of 100', () => {
      const result = getScoreColorClasses(100);
      expect(result.bg).toContain('green');
      expect(result.text).toContain('green');
      expect(result.border).toContain('green');
    });

    it('returns green classes for score of 80 (boundary)', () => {
      const result = getScoreColorClasses(80);
      expect(result.bg).toContain('green');
      expect(result.text).toContain('green');
      expect(result.border).toContain('green');
    });

    it('returns green classes for score of 95', () => {
      const result = getScoreColorClasses(95);
      expect(result.bg).toBe('bg-green-100 dark:bg-green-900/40');
      expect(result.text).toBe('text-green-800 dark:text-green-200');
      expect(result.border).toBe('border-green-400 dark:border-green-600');
    });
  });

  describe('Amber Range (60-79)', () => {
    it('returns amber classes for score of 79', () => {
      const result = getScoreColorClasses(79);
      expect(result.bg).toContain('amber');
      expect(result.text).toContain('amber');
      expect(result.border).toContain('amber');
    });

    it('returns amber classes for score of 60 (boundary)', () => {
      const result = getScoreColorClasses(60);
      expect(result.bg).toContain('amber');
      expect(result.text).toContain('amber');
      expect(result.border).toContain('amber');
    });

    it('returns amber classes for score of 70', () => {
      const result = getScoreColorClasses(70);
      expect(result.bg).toBe('bg-amber-100 dark:bg-amber-900/40');
      expect(result.text).toBe('text-amber-800 dark:text-amber-200');
      expect(result.border).toBe('border-amber-400 dark:border-amber-600');
    });
  });

  describe('Orange Range (40-59)', () => {
    it('returns orange classes for score of 59', () => {
      const result = getScoreColorClasses(59);
      expect(result.bg).toContain('orange');
      expect(result.text).toContain('orange');
      expect(result.border).toContain('orange');
    });

    it('returns orange classes for score of 40 (boundary)', () => {
      const result = getScoreColorClasses(40);
      expect(result.bg).toContain('orange');
      expect(result.text).toContain('orange');
      expect(result.border).toContain('orange');
    });

    it('returns orange classes for score of 50', () => {
      const result = getScoreColorClasses(50);
      expect(result.bg).toBe('bg-orange-100 dark:bg-orange-900/40');
      expect(result.text).toBe('text-orange-800 dark:text-orange-200');
      expect(result.border).toBe('border-orange-400 dark:border-orange-600');
    });
  });

  describe('Red Range (0-39)', () => {
    it('returns red classes for score of 39', () => {
      const result = getScoreColorClasses(39);
      expect(result.bg).toContain('red');
      expect(result.text).toContain('red');
      expect(result.border).toContain('red');
    });

    it('returns red classes for score of 0', () => {
      const result = getScoreColorClasses(0);
      expect(result.bg).toContain('red');
      expect(result.text).toContain('red');
      expect(result.border).toContain('red');
    });

    it('returns red classes for score of 20', () => {
      const result = getScoreColorClasses(20);
      expect(result.bg).toBe('bg-red-100 dark:bg-red-900/40');
      expect(result.text).toBe('text-red-800 dark:text-red-200');
      expect(result.border).toBe('border-red-400 dark:border-red-600');
    });
  });

  describe('Dark Mode Classes', () => {
    it('includes dark mode classes for green range', () => {
      const result = getScoreColorClasses(85);
      expect(result.bg).toContain('dark:bg-green-900/40');
      expect(result.text).toContain('dark:text-green-200');
      expect(result.border).toContain('dark:border-green-600');
    });

    it('includes dark mode classes for amber range', () => {
      const result = getScoreColorClasses(65);
      expect(result.bg).toContain('dark:bg-amber-900/40');
      expect(result.text).toContain('dark:text-amber-200');
      expect(result.border).toContain('dark:border-amber-600');
    });

    it('includes dark mode classes for orange range', () => {
      const result = getScoreColorClasses(45);
      expect(result.bg).toContain('dark:bg-orange-900/40');
      expect(result.text).toContain('dark:text-orange-200');
      expect(result.border).toContain('dark:border-orange-600');
    });

    it('includes dark mode classes for red range', () => {
      const result = getScoreColorClasses(25);
      expect(result.bg).toContain('dark:bg-red-900/40');
      expect(result.text).toContain('dark:text-red-200');
      expect(result.border).toContain('dark:border-red-600');
    });
  });

  describe('Return Type', () => {
    it('returns object with bg, text, and border keys', () => {
      const result = getScoreColorClasses(75);
      expect(result).toHaveProperty('bg');
      expect(result).toHaveProperty('text');
      expect(result).toHaveProperty('border');
    });

    it('returns string values for all properties', () => {
      const result = getScoreColorClasses(50);
      expect(typeof result.bg).toBe('string');
      expect(typeof result.text).toBe('string');
      expect(typeof result.border).toBe('string');
    });
  });
});

// ============================================================================
// formatRelativeTime Tests
// ============================================================================

describe('formatRelativeTime', () => {
  // Store original Date to restore after tests
  const RealDate = Date;

  beforeEach(() => {
    // Mock the current date to 2024-01-15T12:00:00Z
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Undefined/Empty Input', () => {
    it('returns "Never" for undefined input', () => {
      expect(formatRelativeTime(undefined)).toBe('Never');
    });
  });

  describe('Just Now (< 1 minute)', () => {
    it('returns "Just now" for current time', () => {
      expect(formatRelativeTime('2024-01-15T12:00:00Z')).toBe('Just now');
    });

    it('returns "Just now" for 30 seconds ago', () => {
      expect(formatRelativeTime('2024-01-15T11:59:30Z')).toBe('Just now');
    });

    it('returns "Just now" for 59 seconds ago', () => {
      expect(formatRelativeTime('2024-01-15T11:59:01Z')).toBe('Just now');
    });
  });

  describe('Minutes Ago (1-59 minutes)', () => {
    it('returns "1m ago" for 1 minute ago', () => {
      expect(formatRelativeTime('2024-01-15T11:59:00Z')).toBe('1m ago');
    });

    it('returns "5m ago" for 5 minutes ago', () => {
      expect(formatRelativeTime('2024-01-15T11:55:00Z')).toBe('5m ago');
    });

    it('returns "30m ago" for 30 minutes ago', () => {
      expect(formatRelativeTime('2024-01-15T11:30:00Z')).toBe('30m ago');
    });

    it('returns "59m ago" for 59 minutes ago', () => {
      expect(formatRelativeTime('2024-01-15T11:01:00Z')).toBe('59m ago');
    });
  });

  describe('Hours Ago (1-23 hours)', () => {
    it('returns "1h ago" for 1 hour ago', () => {
      expect(formatRelativeTime('2024-01-15T11:00:00Z')).toBe('1h ago');
    });

    it('returns "6h ago" for 6 hours ago', () => {
      expect(formatRelativeTime('2024-01-15T06:00:00Z')).toBe('6h ago');
    });

    it('returns "12h ago" for 12 hours ago', () => {
      expect(formatRelativeTime('2024-01-15T00:00:00Z')).toBe('12h ago');
    });

    it('returns "23h ago" for 23 hours ago', () => {
      expect(formatRelativeTime('2024-01-14T13:00:00Z')).toBe('23h ago');
    });
  });

  describe('Days Ago (1-6 days)', () => {
    it('returns "1d ago" for 1 day ago', () => {
      expect(formatRelativeTime('2024-01-14T12:00:00Z')).toBe('1d ago');
    });

    it('returns "3d ago" for 3 days ago', () => {
      expect(formatRelativeTime('2024-01-12T12:00:00Z')).toBe('3d ago');
    });

    it('returns "6d ago" for 6 days ago', () => {
      expect(formatRelativeTime('2024-01-09T12:00:00Z')).toBe('6d ago');
    });
  });

  describe('Full Date (>= 7 days)', () => {
    it('returns formatted date for 7 days ago', () => {
      const result = formatRelativeTime('2024-01-08T12:00:00Z');
      // The exact format depends on locale, but should be a date string
      expect(result).not.toContain('ago');
      expect(result).not.toBe('Never');
      expect(result).not.toBe('Just now');
    });

    it('returns formatted date for 30 days ago', () => {
      const result = formatRelativeTime('2023-12-16T12:00:00Z');
      expect(result).not.toContain('ago');
    });

    it('returns formatted date for 1 year ago', () => {
      const result = formatRelativeTime('2023-01-15T12:00:00Z');
      expect(result).not.toContain('ago');
    });
  });

  describe('Edge Cases', () => {
    it('handles date at exact minute boundary', () => {
      // Exactly 1 minute = 60 seconds ago
      expect(formatRelativeTime('2024-01-15T11:59:00Z')).toBe('1m ago');
    });

    it('handles date at exact hour boundary', () => {
      // Exactly 1 hour = 60 minutes ago
      expect(formatRelativeTime('2024-01-15T11:00:00Z')).toBe('1h ago');
    });

    it('handles date at exact day boundary', () => {
      // Exactly 1 day = 24 hours ago
      expect(formatRelativeTime('2024-01-14T12:00:00Z')).toBe('1d ago');
    });

    it('handles ISO string with timezone offset', () => {
      // 1 hour ago in different timezone notation
      expect(formatRelativeTime('2024-01-15T06:00:00-05:00')).toBe('1h ago');
    });
  });
});
