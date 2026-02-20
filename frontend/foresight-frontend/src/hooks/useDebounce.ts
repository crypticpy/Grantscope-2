import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Hook that debounces a value by a specified delay.
 * Returns the debounced value which only updates after the delay has passed
 * since the last change.
 *
 * @param value - The value to debounce
 * @param delay - The debounce delay in milliseconds
 * @returns The debounced value
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Hook that debounces a value and also tracks whether a debounce is in progress.
 * Useful for showing loading indicators during debounce.
 *
 * @param value - The value to debounce
 * @param delay - The debounce delay in milliseconds
 * @returns Object with debouncedValue and isPending flag
 */
export function useDebouncedValue<T>(
  value: T,
  delay: number
): { debouncedValue: T; isPending: boolean } {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  const [isPending, setIsPending] = useState(false);
  const isFirstRender = useRef(true);

  useEffect(() => {
    // Skip pending state on first render
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    // Check if value has actually changed. Fallback avoids crashes on
    // non-serializable values (e.g., circular structures).
    const hasChanged = (() => {
      try {
        return JSON.stringify(value) !== JSON.stringify(debouncedValue);
      } catch {
        return !Object.is(value, debouncedValue);
      }
    })();

    if (!hasChanged) {
      setIsPending(false);
      return;
    }

    setIsPending(true);

    const handler = setTimeout(() => {
      setDebouncedValue(value);
      setIsPending(false);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay, debouncedValue]);

  return { debouncedValue, isPending };
}

/**
 * Hook that debounces a callback function by a specified delay.
 * Unlike useDebounce which debounces a value, this debounces the actual function call.
 * Useful for debouncing API calls or other side effects independently from state updates.
 *
 * @param callback - The callback function to debounce
 * @param delay - The debounce delay in milliseconds
 * @returns Object with debouncedCallback and cancel function
 */
export function useDebouncedCallback<T extends (...args: Parameters<T>) => ReturnType<T>>(
  callback: T,
  delay: number
): { debouncedCallback: (...args: Parameters<T>) => void; cancel: () => void } {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const callbackRef = useRef(callback);

  // Keep callback ref up to date
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const cancel = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const debouncedCallback = useCallback(
    (...args: Parameters<T>) => {
      // Cancel any pending execution
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      // Schedule new execution
      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args);
        timeoutRef.current = null;
      }, delay);
    },
    [delay]
  );

  return { debouncedCallback, cancel };
}
