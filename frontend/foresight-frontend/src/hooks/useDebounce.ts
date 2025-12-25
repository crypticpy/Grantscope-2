import { useState, useEffect, useRef } from 'react';

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

    // Check if value has actually changed
    const hasChanged = JSON.stringify(value) !== JSON.stringify(debouncedValue);

    if (hasChanged) {
      setIsPending(true);
    }

    const handler = setTimeout(() => {
      setDebouncedValue(value);
      setIsPending(false);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return { debouncedValue, isPending };
}
