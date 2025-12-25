import { describe, it, expect } from 'vitest';
import { parseStageNumber } from './stage-utils';

describe('parseStageNumber', () => {
  describe('valid stage IDs', () => {
    it('parses stage 1 from "1_concept"', () => {
      expect(parseStageNumber('1_concept')).toBe(1);
    });

    it('parses stage 2 from "2_emerging"', () => {
      expect(parseStageNumber('2_emerging')).toBe(2);
    });

    it('parses stage 3 from "3_growth"', () => {
      expect(parseStageNumber('3_growth')).toBe(3);
    });

    it('parses stage 4 from "4_mature"', () => {
      expect(parseStageNumber('4_mature')).toBe(4);
    });

    it('parses stage 5 from "5_decline"', () => {
      expect(parseStageNumber('5_decline')).toBe(5);
    });

    it('parses double-digit stage numbers', () => {
      expect(parseStageNumber('10_something')).toBe(10);
      expect(parseStageNumber('99_test')).toBe(99);
    });

    it('parses stage numbers without underscore suffix', () => {
      expect(parseStageNumber('1')).toBe(1);
      expect(parseStageNumber('42')).toBe(42);
    });

    it('parses stage numbers with various suffixes', () => {
      expect(parseStageNumber('3_with_multiple_underscores')).toBe(3);
      expect(parseStageNumber('7-with-dashes')).toBe(7);
      expect(parseStageNumber('5 with spaces')).toBe(5);
    });
  });

  describe('null and undefined inputs', () => {
    it('returns null for null input', () => {
      expect(parseStageNumber(null)).toBeNull();
    });

    it('returns null for undefined input', () => {
      expect(parseStageNumber(undefined)).toBeNull();
    });
  });

  describe('empty and whitespace strings', () => {
    it('returns null for empty string', () => {
      expect(parseStageNumber('')).toBeNull();
    });

    it('returns null for whitespace-only string', () => {
      expect(parseStageNumber('   ')).toBeNull();
    });
  });

  describe('invalid formats', () => {
    it('returns null for strings without leading numbers', () => {
      expect(parseStageNumber('concept')).toBeNull();
      expect(parseStageNumber('no_number')).toBeNull();
      expect(parseStageNumber('abc123')).toBeNull();
    });

    it('returns null for strings starting with underscore', () => {
      expect(parseStageNumber('_1_concept')).toBeNull();
    });

    it('returns null for strings starting with special characters', () => {
      expect(parseStageNumber('-1_negative')).toBeNull();
      expect(parseStageNumber('#1_hashtag')).toBeNull();
    });
  });

  describe('edge cases', () => {
    it('handles leading zeros correctly', () => {
      // parseInt with radix 10 handles leading zeros correctly
      expect(parseStageNumber('01_first')).toBe(1);
      expect(parseStageNumber('007_bond')).toBe(7);
    });

    it('handles very large numbers', () => {
      expect(parseStageNumber('999999_large')).toBe(999999);
    });

    it('extracts only the leading number portion', () => {
      // Should only get the leading digits, not embedded ones
      expect(parseStageNumber('1_stage2')).toBe(1);
      expect(parseStageNumber('12_test34')).toBe(12);
    });
  });
});
