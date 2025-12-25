/**
 * useDebounce Hooks Unit Tests
 *
 * Tests for debounce hooks including:
 * - useDebouncedCallback: debounces function calls
 *   - Callback is only called once after debounce period
 *   - Rapid successive calls only result in one execution
 *   - Cancel function prevents pending execution
 *   - Cleanup on unmount
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebouncedCallback } from '../useDebounce';

// ============================================================================
// Test Setup
// ============================================================================

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

// ============================================================================
// useDebouncedCallback Tests
// ============================================================================

describe('useDebouncedCallback', () => {
  describe('Basic Debounce Behavior', () => {
    it('calls the callback after the specified delay', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      // Call the debounced callback
      act(() => {
        result.current.debouncedCallback();
      });

      // Callback should not be called immediately
      expect(callback).not.toHaveBeenCalled();

      // Advance time by the delay
      act(() => {
        vi.advanceTimersByTime(delay);
      });

      // Now callback should be called
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('does not call callback before delay has passed', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      act(() => {
        result.current.debouncedCallback();
      });

      // Advance time but not enough
      act(() => {
        vi.advanceTimersByTime(delay - 100);
      });

      // Callback should not be called yet
      expect(callback).not.toHaveBeenCalled();
    });

    it('passes arguments to the callback', () => {
      const callback = vi.fn();
      const delay = 300;

      const { result } = renderHook(() =>
        useDebouncedCallback(callback, delay)
      );

      act(() => {
        result.current.debouncedCallback('arg1', 'arg2', 123);
      });

      act(() => {
        vi.advanceTimersByTime(delay);
      });

      expect(callback).toHaveBeenCalledWith('arg1', 'arg2', 123);
    });
  });

  describe('Rapid Successive Calls', () => {
    it('only executes once when called multiple times in quick succession', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      // Make several rapid calls
      act(() => {
        result.current.debouncedCallback('call1');
        vi.advanceTimersByTime(100);
        result.current.debouncedCallback('call2');
        vi.advanceTimersByTime(100);
        result.current.debouncedCallback('call3');
      });

      // Callback should not be called yet
      expect(callback).not.toHaveBeenCalled();

      // Wait for the full delay after the last call
      act(() => {
        vi.advanceTimersByTime(delay);
      });

      // Should only be called once with the last arguments
      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith('call3');
    });

    it('resets the timer on each call', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      act(() => {
        result.current.debouncedCallback();
      });

      // Advance time partially
      act(() => {
        vi.advanceTimersByTime(400);
      });

      // Call again - this should reset the timer
      act(() => {
        result.current.debouncedCallback();
      });

      // After original 500ms, callback should NOT have been called
      // because timer was reset
      act(() => {
        vi.advanceTimersByTime(100);
      });
      expect(callback).not.toHaveBeenCalled();

      // After another 400ms (500ms from the second call), it should be called
      act(() => {
        vi.advanceTimersByTime(400);
      });
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  describe('Cancel Function', () => {
    it('prevents pending execution when cancel is called', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      act(() => {
        result.current.debouncedCallback();
      });

      // Cancel before the delay expires
      act(() => {
        vi.advanceTimersByTime(200);
        result.current.cancel();
      });

      // Wait for the full delay
      act(() => {
        vi.advanceTimersByTime(delay);
      });

      // Callback should never have been called
      expect(callback).not.toHaveBeenCalled();
    });

    it('can be called multiple times safely', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      act(() => {
        result.current.debouncedCallback();
      });

      // Cancel multiple times
      act(() => {
        result.current.cancel();
        result.current.cancel();
        result.current.cancel();
      });

      act(() => {
        vi.advanceTimersByTime(delay);
      });

      // Should not throw and callback should not be called
      expect(callback).not.toHaveBeenCalled();
    });

    it('allows new calls after cancellation', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      // First call
      act(() => {
        result.current.debouncedCallback('first');
      });

      // Cancel it
      act(() => {
        result.current.cancel();
      });

      // New call
      act(() => {
        result.current.debouncedCallback('second');
      });

      act(() => {
        vi.advanceTimersByTime(delay);
      });

      // Only the second call should have executed
      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith('second');
    });
  });

  describe('Cleanup on Unmount', () => {
    it('cancels pending execution when component unmounts', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result, unmount } = renderHook(() =>
        useDebouncedCallback(callback, delay)
      );

      act(() => {
        result.current.debouncedCallback();
      });

      // Unmount before the delay expires
      act(() => {
        vi.advanceTimersByTime(200);
        unmount();
      });

      // Wait for what would have been the full delay
      act(() => {
        vi.advanceTimersByTime(delay);
      });

      // Callback should never have been called
      expect(callback).not.toHaveBeenCalled();
    });

    it('handles multiple calls before unmount', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result, unmount } = renderHook(() =>
        useDebouncedCallback(callback, delay)
      );

      act(() => {
        result.current.debouncedCallback('first');
        vi.advanceTimersByTime(100);
        result.current.debouncedCallback('second');
        vi.advanceTimersByTime(100);
        result.current.debouncedCallback('third');
      });

      // Unmount
      unmount();

      // Wait for delay
      act(() => {
        vi.advanceTimersByTime(delay);
      });

      // None of the callbacks should have been called
      expect(callback).not.toHaveBeenCalled();
    });
  });

  describe('Callback Reference Updates', () => {
    it('uses the latest callback when executed', () => {
      const callback1 = vi.fn();
      const callback2 = vi.fn();
      const delay = 500;

      const { result, rerender } = renderHook(
        ({ callback }) => useDebouncedCallback(callback, delay),
        { initialProps: { callback: callback1 } }
      );

      // Call with initial callback
      act(() => {
        result.current.debouncedCallback();
      });

      // Update the callback before the delay expires
      act(() => {
        vi.advanceTimersByTime(200);
      });

      rerender({ callback: callback2 });

      // Wait for the delay to finish
      act(() => {
        vi.advanceTimersByTime(300);
      });

      // The new callback should be called, not the old one
      expect(callback1).not.toHaveBeenCalled();
      expect(callback2).toHaveBeenCalledTimes(1);
    });
  });

  describe('Different Delay Values', () => {
    it('works with very short delays', () => {
      const callback = vi.fn();
      const delay = 10;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      act(() => {
        result.current.debouncedCallback();
      });

      act(() => {
        vi.advanceTimersByTime(delay);
      });

      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('works with long delays (like 2000ms for search history)', () => {
      const callback = vi.fn();
      const delay = 2000;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      act(() => {
        result.current.debouncedCallback();
      });

      // Should not be called after 1 second
      act(() => {
        vi.advanceTimersByTime(1000);
      });
      expect(callback).not.toHaveBeenCalled();

      // Should not be called after 1.9 seconds
      act(() => {
        vi.advanceTimersByTime(900);
      });
      expect(callback).not.toHaveBeenCalled();

      // Should be called after 2 seconds
      act(() => {
        vi.advanceTimersByTime(100);
      });
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('respects delay changes between calls', () => {
      const callback = vi.fn();

      const { result, rerender } = renderHook(
        ({ delay }) => useDebouncedCallback(callback, delay),
        { initialProps: { delay: 500 } }
      );

      // Make a call with 500ms delay
      act(() => {
        result.current.debouncedCallback();
      });

      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(callback).toHaveBeenCalledTimes(1);

      // Rerender with new delay
      rerender({ delay: 1000 });

      // Make another call
      act(() => {
        result.current.debouncedCallback();
      });

      // Should not be called after 500ms
      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(callback).toHaveBeenCalledTimes(1);

      // Should be called after 1000ms total
      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(callback).toHaveBeenCalledTimes(2);
    });
  });

  describe('Typed Arguments', () => {
    it('maintains type safety for arguments', () => {
      const callback = vi.fn((name: string, age: number) => {
        return `${name} is ${age} years old`;
      });
      const delay = 300;

      const { result } = renderHook(() =>
        useDebouncedCallback(callback, delay)
      );

      act(() => {
        result.current.debouncedCallback('Alice', 30);
      });

      act(() => {
        vi.advanceTimersByTime(delay);
      });

      expect(callback).toHaveBeenCalledWith('Alice', 30);
    });

    it('works with no arguments', () => {
      const callback = vi.fn(() => 'no args');
      const delay = 300;

      const { result } = renderHook(() =>
        useDebouncedCallback(callback, delay)
      );

      act(() => {
        result.current.debouncedCallback();
      });

      act(() => {
        vi.advanceTimersByTime(delay);
      });

      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  describe('Edge Cases', () => {
    it('handles zero delay', () => {
      const callback = vi.fn();
      const delay = 0;

      const { result } = renderHook(() => useDebouncedCallback(callback, delay));

      act(() => {
        result.current.debouncedCallback();
      });

      // Even with 0 delay, should be async (via setTimeout)
      expect(callback).not.toHaveBeenCalled();

      act(() => {
        vi.advanceTimersByTime(0);
      });

      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('returned functions maintain referential stability', () => {
      const callback = vi.fn();
      const delay = 500;

      const { result, rerender } = renderHook(() =>
        useDebouncedCallback(callback, delay)
      );

      const firstDebouncedCallback = result.current.debouncedCallback;
      const firstCancel = result.current.cancel;

      // Rerender (simulating a parent component re-render)
      rerender();

      // The returned functions should be the same references
      expect(result.current.debouncedCallback).toBe(firstDebouncedCallback);
      expect(result.current.cancel).toBe(firstCancel);
    });
  });
});
