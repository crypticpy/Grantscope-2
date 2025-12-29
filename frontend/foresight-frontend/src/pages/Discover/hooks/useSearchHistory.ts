/**
 * useSearchHistory Hook
 *
 * Manages search history state and operations for the Discover page.
 */

import { useState, useCallback, useEffect } from 'react';
import { supabase } from '../../../App';
import { useDebouncedCallback } from '../../../hooks/useDebounce';
import {
  getSearchHistory,
  recordSearchHistory,
  deleteSearchHistoryEntry,
  clearSearchHistory,
  type SearchHistoryEntry,
  type SearchHistoryCreate,
  type SavedSearchQueryConfig,
} from '../../../lib/discovery-api';

export interface UseSearchHistoryReturn {
  /** Search history entries */
  searchHistory: SearchHistoryEntry[];
  /** Whether history is being loaded */
  historyLoading: boolean;
  /** Whether history section is expanded */
  isHistoryExpanded: boolean;
  /** Toggle history expansion */
  toggleHistoryExpanded: () => void;
  /** ID of entry being deleted (for loading state) */
  deletingHistoryId: string | null;
  /** Load search history from server */
  loadSearchHistory: () => Promise<void>;
  /** Record a search to history (debounced) */
  recordSearch: (queryConfig: SavedSearchQueryConfig, resultCount: number) => void;
  /** Delete a single history entry */
  deleteHistoryEntry: (entryId: string, e: React.MouseEvent) => Promise<void>;
  /** Clear all history */
  clearHistory: () => Promise<void>;
}

/**
 * Hook for managing search history
 *
 * @param userId - Current user ID (or undefined if not authenticated)
 * @returns Search history state and handlers
 */
export function useSearchHistory(userId: string | undefined): UseSearchHistoryReturn {
  const [searchHistory, setSearchHistory] = useState<SearchHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [isHistoryExpanded, setIsHistoryExpanded] = useState(false);
  const [deletingHistoryId, setDeletingHistoryId] = useState<string | null>(null);

  const toggleHistoryExpanded = useCallback(() => {
    setIsHistoryExpanded((prev) => !prev);
  }, []);

  /**
   * Load search history from server
   */
  const loadSearchHistory = useCallback(async () => {
    if (!userId) return;

    setHistoryLoading(true);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;

      if (token) {
        const response = await getSearchHistory(token, 20);
        setSearchHistory(response.history);
      }
    } catch {
      // Silently fail - history is not critical
    } finally {
      setHistoryLoading(false);
    }
  }, [userId]);

  /**
   * Record search to history
   */
  const recordSearchToHistory = useCallback(
    async (queryConfig: SavedSearchQueryConfig, resultCount: number) => {
      if (!userId) return;

      // Skip recording if no search criteria are set (default empty state)
      const hasQuery = queryConfig.query && queryConfig.query.trim().length > 0;
      const hasFilters = queryConfig.filters && Object.keys(queryConfig.filters).length > 0;
      if (!hasQuery && !hasFilters) return;

      try {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData?.session?.access_token;

        if (token) {
          const entry: SearchHistoryCreate = {
            query_config: queryConfig,
            result_count: resultCount,
          };

          const newEntry = await recordSearchHistory(token, entry);

          // Update local history state - prepend new entry and limit to 50
          setSearchHistory((prev) => {
            const updated = [newEntry, ...prev.filter((h) => h.id !== newEntry.id)];
            return updated.slice(0, 50);
          });
        }
      } catch {
        // Silently fail - history recording is not critical
      }
    },
    [userId]
  );

  /**
   * Debounced version of recordSearchToHistory (2000ms delay)
   * Allows users time to settle on their final search before recording
   */
  const { debouncedCallback: recordSearch } = useDebouncedCallback(recordSearchToHistory, 2000);

  /**
   * Delete a single history entry
   */
  const deleteHistoryEntry = useCallback(async (entryId: string, e: React.MouseEvent) => {
    e.stopPropagation();

    setDeletingHistoryId(entryId);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;

      if (token) {
        await deleteSearchHistoryEntry(token, entryId);
        setSearchHistory((prev) => prev.filter((h) => h.id !== entryId));
      }
    } catch {
      // Silently fail
    } finally {
      setDeletingHistoryId(null);
    }
  }, []);

  /**
   * Clear all history
   */
  const clearHistory = useCallback(async () => {
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;

      if (token) {
        await clearSearchHistory(token);
        setSearchHistory([]);
      }
    } catch {
      // Silently fail
    }
  }, []);

  // Load search history on mount and when user changes
  useEffect(() => {
    loadSearchHistory();
  }, [loadSearchHistory]);

  return {
    searchHistory,
    historyLoading,
    isHistoryExpanded,
    toggleHistoryExpanded,
    deletingHistoryId,
    loadSearchHistory,
    recordSearch,
    deleteHistoryEntry,
    clearHistory,
  };
}

export default useSearchHistory;
