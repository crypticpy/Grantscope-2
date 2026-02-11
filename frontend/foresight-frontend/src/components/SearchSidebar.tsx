/**
 * SearchSidebar Component
 *
 * A collapsible sidebar that displays saved searches and search history.
 * Allows users to quickly re-run saved searches and manage their search library.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Bookmark,
  Trash2,
  Play,
  Loader2,
  AlertCircle,
  ChevronRight,
  ChevronLeft,
  Sparkles,
  Filter,
  Search as SearchIcon,
} from 'lucide-react';
import { cn } from '../lib/utils';
import {
  listSavedSearches,
  deleteSavedSearch,
  SavedSearch,
  SavedSearchQueryConfig,
} from '../lib/discovery-api';
import { supabase } from '../App';

// ============================================================================
// Types
// ============================================================================

export interface SearchSidebarProps {
  /** Whether the sidebar is open */
  isOpen: boolean;
  /** Called when sidebar should toggle */
  onToggle: () => void;
  /** Called when a saved search is selected */
  onSelectSearch: (queryConfig: SavedSearchQueryConfig) => void;
  /** Key to trigger refresh (increment to force reload) */
  refreshKey?: number;
}

// ============================================================================
// Main Component
// ============================================================================

export function SearchSidebar({
  isOpen,
  onToggle,
  onSelectSearch,
  refreshKey = 0,
}: SearchSidebarProps) {
  // State
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Get auth token helper
  const getAuthToken = useCallback(async (): Promise<string | null> => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || null;
  }, []);

  // Load saved searches
  const loadSavedSearches = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = await getAuthToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      const response = await listSavedSearches(token);
      setSavedSearches(response.saved_searches);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to load saved searches'
      );
    } finally {
      setIsLoading(false);
    }
  }, [getAuthToken]);

  // Load on mount and when refreshKey changes
  useEffect(() => {
    loadSavedSearches();
  }, [loadSavedSearches, refreshKey]);

  // Handle delete
  const handleDelete = async (searchId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Don't trigger selection

    setDeletingId(searchId);
    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      await deleteSavedSearch(token, searchId);
      setSavedSearches((prev) => prev.filter((s) => s.id !== searchId));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to delete search'
      );
      // Clear error after 3 seconds
      setTimeout(() => setError(null), 3000);
    } finally {
      setDeletingId(null);
    }
  };

  // Handle selection
  const handleSelect = (search: SavedSearch) => {
    onSelectSearch(search.query_config);
  };

  // Build description for saved search
  const getSearchDescription = (config: SavedSearchQueryConfig): string => {
    const parts: string[] = [];

    if (config.query) {
      parts.push(`"${config.query}"`);
    }

    if (config.filters) {
      const { pillar_ids, stage_ids, horizon, date_range, score_thresholds } = config.filters;

      if (pillar_ids && pillar_ids.length > 0) {
        parts.push(`${pillar_ids.length} pillar(s)`);
      }
      if (stage_ids && stage_ids.length > 0) {
        parts.push(`${stage_ids.length} stage(s)`);
      }
      if (horizon && horizon !== 'ALL') {
        parts.push(`Horizon ${horizon}`);
      }
      if (date_range && (date_range.start || date_range.end)) {
        parts.push('date filter');
      }
      if (score_thresholds && Object.keys(score_thresholds).length > 0) {
        parts.push('score thresholds');
      }
    }

    if (config.use_vector_search) {
      parts.push('semantic');
    }

    return parts.length > 0 ? parts.join(' • ') : 'No filters';
  };

  // Format relative time
  const formatRelativeTime = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return date.toLocaleDateString();
  };

  return (
    <>
      {/* Toggle Button (visible when sidebar is closed) */}
      {!isOpen && (
        <button
          onClick={onToggle}
          className="fixed left-0 top-1/2 -translate-y-1/2 z-40 bg-white dark:bg-dark-surface shadow-lg rounded-r-lg px-2 py-4 hover:bg-gray-50 dark:hover:bg-[#3d4176] transition-colors border-r border-t border-b border-gray-200 dark:border-gray-600"
          aria-label="Open saved searches sidebar"
          title="Saved Searches"
        >
          <div className="flex flex-col items-center gap-2">
            <Bookmark className="h-5 w-5 text-brand-blue" />
            <ChevronRight className="h-4 w-4 text-gray-400" />
          </div>
        </button>
      )}

      {/* Sidebar Panel */}
      <div
        className={cn(
          'fixed left-0 top-16 bottom-0 z-40 bg-white dark:bg-dark-surface shadow-xl border-r border-gray-200 dark:border-gray-600 transition-transform duration-300 ease-in-out w-80',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-600">
          <div className="flex items-center gap-2">
            <Bookmark className="h-5 w-5 text-brand-blue" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Saved Searches
            </h2>
          </div>
          <button
            onClick={onToggle}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-md hover:bg-gray-100 dark:hover:bg-[#3d4176] transition-colors"
            aria-label="Close sidebar"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-col h-[calc(100%-56px)] overflow-hidden">
          {/* Error Message */}
          {error && (
            <div className="mx-4 mt-4 flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-md">
              <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400 shrink-0" />
              <p className="text-sm text-red-800 dark:text-red-300">{error}</p>
            </div>
          )}

          {/* Loading State */}
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 text-brand-blue animate-spin" />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Loading saved searches...
                </p>
              </div>
            </div>
          ) : savedSearches.length === 0 ? (
            /* Empty State */
            <div className="flex-1 flex items-center justify-center px-6">
              <div className="text-center">
                <SearchIcon className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
                <h3 className="mt-3 text-sm font-medium text-gray-900 dark:text-white">
                  No saved searches
                </h3>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Save your search filters to quickly access them later.
                </p>
              </div>
            </div>
          ) : (
            /* Saved Searches List */
            <div className="flex-1 overflow-y-auto py-2">
              {savedSearches.map((search) => (
                <div
                  key={search.id}
                  onClick={() => handleSelect(search)}
                  className="group mx-2 mb-2 p-3 rounded-lg border border-gray-200 dark:border-gray-600 hover:border-brand-blue hover:bg-brand-light-blue/50 dark:hover:bg-brand-blue/10 cursor-pointer transition-all"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSelect(search);
                    }
                  }}
                >
                  {/* Title Row */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-gray-900 dark:text-white truncate">
                        {search.name}
                      </h3>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {/* Run Button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelect(search);
                        }}
                        className="p-1.5 text-gray-400 hover:text-brand-blue rounded opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Run this search"
                        aria-label={`Run search: ${search.name}`}
                      >
                        <Play className="h-4 w-4" />
                      </button>
                      {/* Delete Button */}
                      <button
                        onClick={(e) => handleDelete(search.id, e)}
                        disabled={deletingId === search.id}
                        className="p-1.5 text-gray-400 hover:text-red-500 rounded opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50"
                        title="Delete this search"
                        aria-label={`Delete search: ${search.name}`}
                      >
                        {deletingId === search.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Description */}
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 truncate">
                    {getSearchDescription(search.query_config)}
                  </p>

                  {/* Metadata Row */}
                  <div className="mt-2 flex items-center gap-2">
                    {/* Semantic Search Badge */}
                    {search.query_config.use_vector_search && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-extended-purple/10 text-extended-purple">
                        <Sparkles className="h-3 w-3" />
                        Semantic
                      </span>
                    )}
                    {/* Filter Badge */}
                    {search.query_config.filters && Object.keys(search.query_config.filters).length > 0 && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                        <Filter className="h-3 w-3" />
                        Filters
                      </span>
                    )}
                    {/* Last Used */}
                    <span className="text-xs text-gray-400 ml-auto">
                      {formatRelativeTime(search.last_used_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Backdrop (mobile) */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/20 md:hidden"
          onClick={onToggle}
          aria-hidden="true"
        />
      )}
    </>
  );
}

export default SearchSidebar;
