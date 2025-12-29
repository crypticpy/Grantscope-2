import { useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Storage key prefix for scroll positions
 */
const SCROLL_STORAGE_PREFIX = 'scroll_position_';

/**
 * Default scroll position getter - defined at module level for stable reference
 */
const defaultGetScrollPosition = () => window.scrollY;

/**
 * Default scroll position setter - defined at module level for stable reference
 */
const defaultSetScrollPosition = (position: number) =>
  window.scrollTo({ top: position, behavior: 'instant' });

/**
 * Configuration options for scroll restoration
 */
export interface UseScrollRestorationOptions {
  /**
   * Custom storage key. If not provided, uses the current pathname.
   */
  storageKey?: string;
  /**
   * Whether to clear the stored position after restoration.
   * Set to false if you want to persist across refreshes.
   * Default: true
   */
  clearAfterRestore?: boolean;
  /**
   * Delay in ms before restoring scroll position.
   * Allows time for content to render.
   * Default: 50
   */
  restoreDelay?: number;
  /**
   * Whether to debounce scroll saves to avoid excessive writes.
   * Default: true
   */
  debounce?: boolean;
  /**
   * Debounce delay in ms.
   * Default: 100
   */
  debounceDelay?: number;
  /**
   * Custom scroll getter function. Use this for virtualized lists
   * that have their own scroll container.
   * Default: () => window.scrollY
   */
  getScrollPosition?: () => number;
  /**
   * Custom scroll setter function. Use this for virtualized lists
   * that have their own scroll container.
   * Default: (position) => window.scrollTo(0, position)
   */
  setScrollPosition?: (position: number) => void;
  /**
   * Whether scroll restoration is enabled.
   * Default: true
   */
  enabled?: boolean;
  /**
   * Whether to persist scroll position across full page reloads.
   * When false, scroll is still saved/restored for in-app navigation (unmount/mount),
   * but won't be saved on refresh/close tab.
   * Default: true
   */
  saveOnBeforeUnload?: boolean;
}

/**
 * Return type for the useScrollRestoration hook
 */
export interface UseScrollRestorationReturn {
  /**
   * Manually save the current scroll position
   */
  saveScrollPosition: () => void;
  /**
   * Manually restore the saved scroll position
   */
  restoreScrollPosition: () => void;
  /**
   * Clear the saved scroll position
   */
  clearScrollPosition: () => void;
  /**
   * Get the currently saved scroll position (or null if none)
   */
  getSavedScrollPosition: () => number | null;
}

/**
 * Hook for saving and restoring scroll position across navigation.
 *
 * Features:
 * - Automatically saves scroll position when navigating away
 * - Automatically restores scroll position when returning
 * - Works with browser back/forward navigation
 * - Supports custom scroll containers (for virtualized lists)
 * - Debounced scroll saves for performance
 *
 * @example
 * // Basic usage with window scroll
 * useScrollRestoration();
 *
 * @example
 * // With virtualized list
 * const listRef = useRef<VirtualizedListHandle>(null);
 * useScrollRestoration({
 *   getScrollPosition: () => listRef.current?.getScrollOffset() ?? 0,
 *   setScrollPosition: (pos) => listRef.current?.setScrollOffset(pos),
 * });
 *
 * @example
 * // With custom scroll container
 * const containerRef = useRef<HTMLDivElement>(null);
 * useScrollRestoration({
 *   getScrollPosition: () => containerRef.current?.scrollTop ?? 0,
 *   setScrollPosition: (pos) => {
 *     if (containerRef.current) containerRef.current.scrollTop = pos;
 *   },
 * });
 */
export function useScrollRestoration(
  options: UseScrollRestorationOptions = {}
): UseScrollRestorationReturn {
  const {
    storageKey: customKey,
    clearAfterRestore = true,
    restoreDelay = 50,
    debounce = true,
    debounceDelay = 100,
    getScrollPosition = defaultGetScrollPosition,
    setScrollPosition = defaultSetScrollPosition,
    enabled = true,
    saveOnBeforeUnload = true,
  } = options;

  const location = useLocation();
  const storageKey = `${SCROLL_STORAGE_PREFIX}${customKey ?? location.pathname}`;

  // Refs to track state without causing re-renders
  const hasRestoredRef = useRef(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isNavigatingAwayRef = useRef(false);

  /**
   * Save scroll position to sessionStorage
   */
  const saveScrollPosition = useCallback(() => {
    if (!enabled) return;

    try {
      const position = getScrollPosition();
      // Only save if we have a meaningful scroll position
      if (position > 0) {
        sessionStorage.setItem(storageKey, position.toString());
      }
    } catch {
      // Ignore storage errors (e.g., quota exceeded, private browsing)
    }
  }, [enabled, getScrollPosition, storageKey]);

  /**
   * Debounced save function
   */
  const debouncedSave = useCallback(() => {
    if (!enabled || !debounce) {
      saveScrollPosition();
      return;
    }

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      saveScrollPosition();
    }, debounceDelay);
  }, [enabled, debounce, debounceDelay, saveScrollPosition]);

  /**
   * Get saved scroll position from sessionStorage
   */
  const getSavedScrollPosition = useCallback((): number | null => {
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) {
        const position = parseInt(saved, 10);
        return isNaN(position) ? null : position;
      }
    } catch {
      // Ignore storage errors
    }
    return null;
  }, [storageKey]);

  /**
   * Clear saved scroll position from sessionStorage
   */
  const clearScrollPosition = useCallback(() => {
    try {
      sessionStorage.removeItem(storageKey);
    } catch {
      // Ignore storage errors
    }
  }, [storageKey]);

  /**
   * Restore scroll position from sessionStorage
   */
  const restoreScrollPosition = useCallback(() => {
    if (!enabled || hasRestoredRef.current) return;

    const savedPosition = getSavedScrollPosition();
    if (savedPosition !== null && savedPosition > 0) {
      // Use requestAnimationFrame to ensure DOM is ready
      requestAnimationFrame(() => {
        setTimeout(() => {
          setScrollPosition(savedPosition);
          hasRestoredRef.current = true;

          if (clearAfterRestore) {
            clearScrollPosition();
          }
        }, restoreDelay);
      });
    } else {
      hasRestoredRef.current = true;
    }
  }, [
    enabled,
    getSavedScrollPosition,
    setScrollPosition,
    clearAfterRestore,
    clearScrollPosition,
    restoreDelay,
  ]);

  // Restore scroll position on mount
  useEffect(() => {
    if (!enabled) return;

    // Reset restored flag when location changes
    hasRestoredRef.current = false;

    // Attempt to restore scroll position
    restoreScrollPosition();
  }, [enabled, restoreScrollPosition, location.key]);

  // Save scroll position on scroll
  useEffect(() => {
    if (!enabled) return;

    const handleScroll = () => {
      // Don't save during restoration or when navigating away
      if (!hasRestoredRef.current || isNavigatingAwayRef.current) return;
      debouncedSave();
    };

    window.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      window.removeEventListener('scroll', handleScroll);

      // Clear any pending debounce
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [enabled, debouncedSave]);

  // Save scroll position before page unload (refresh, close tab, navigate away)
  useEffect(() => {
    if (!enabled || !saveOnBeforeUnload) return;

    const handleBeforeUnload = () => {
      isNavigatingAwayRef.current = true;
      saveScrollPosition();
    };

    // Also save when visibility changes (e.g., switching tabs on mobile)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        saveScrollPosition();
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [enabled, saveOnBeforeUnload, saveScrollPosition]);

  // Save scroll position when component unmounts (navigation)
  useEffect(() => {
    if (!enabled) return;

    return () => {
      // Clear debounce timer
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      // Save current position on unmount
      saveScrollPosition();
    };
  }, [enabled, saveScrollPosition]);

  return {
    saveScrollPosition,
    restoreScrollPosition,
    clearScrollPosition,
    getSavedScrollPosition,
  };
}

export default useScrollRestoration;
