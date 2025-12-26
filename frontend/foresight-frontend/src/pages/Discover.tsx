import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { Search, Filter, Grid, List, Eye, Heart, Clock, Star, Inbox, History, Calendar, Sparkles, Bookmark, ChevronDown, ChevronUp, Loader2, X, AlertTriangle, RefreshCw, ArrowLeftRight, Check } from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { useDebouncedValue } from '../hooks/useDebounce';
import { PillarBadge } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge } from '../components/StageBadge';
import { Top25Badge } from '../components/Top25Badge';
import { SaveSearchModal } from '../components/SaveSearchModal';
import { SearchSidebar } from '../components/SearchSidebar';
import { advancedSearch, AdvancedSearchRequest, SavedSearchQueryConfig, getSearchHistory, SearchHistoryEntry, deleteSearchHistoryEntry, clearSearchHistory, recordSearchHistory, SearchHistoryCreate } from '../lib/discovery-api';
import { highlightText } from '../lib/highlight-utils';

interface Card {
  id: string;
  name: string;
  slug: string;
  summary: string;
  pillar_id: string;
  stage_id: string;
  horizon: 'H1' | 'H2' | 'H3';
  novelty_score: number;
  maturity_score: number;
  impact_score: number;
  relevance_score: number;
  velocity_score: number;
  risk_score: number;
  opportunity_score: number;
  created_at: string;
  updated_at?: string;
  anchor_id?: string;
  top25_relevance?: string[];
  // Search-specific fields (populated when semantic search is used)
  search_relevance?: number; // Vector similarity score (0-1)
}

interface Pillar {
  id: string;
  name: string;
  color: string;
}

interface Stage {
  id: string;
  name: string;
  sort_order: number;
}

type SortOption = 'newest' | 'oldest' | 'recently_updated' | 'least_recently_updated';

/**
 * Parse stage number from stage_id string
 * e.g., "1_concept" -> 1, "2_emerging" -> 2
 */
const parseStageNumber = (stageId: string): number | null => {
  const match = stageId.match(/^(\d+)/);
  return match ? parseInt(match[1], 10) : null;
};

/**
 * Get color classes for score values
 */
const getScoreColorClasses = (score: number): string => {
  if (score >= 80) return 'text-green-600 dark:text-green-400';
  if (score >= 60) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
};

/**
 * Get sort configuration based on selected sort option
 */
const getSortConfig = (option: SortOption): { column: string; ascending: boolean } => {
  switch (option) {
    case 'oldest':
      return { column: 'created_at', ascending: true };
    case 'recently_updated':
      return { column: 'updated_at', ascending: false };
    case 'least_recently_updated':
      return { column: 'updated_at', ascending: true };
    case 'newest':
    default:
      return { column: 'created_at', ascending: false };
  }
};

/**
 * Format card date for display
 * Shows relative time for recent updates, absolute date for creation
 */
const formatCardDate = (createdAt: string, updatedAt?: string): { label: string; text: string } => {
  try {
    const created = new Date(createdAt);
    const updated = updatedAt ? new Date(updatedAt) : null;

    // If updated_at exists and is different from created_at (more than 1 minute difference)
    if (updated && Math.abs(updated.getTime() - created.getTime()) > 60000) {
      return {
        label: 'Updated',
        text: formatDistanceToNow(updated, { addSuffix: true })
      };
    }

    // Fall back to created_at with absolute date format
    return {
      label: 'Created',
      text: format(created, 'MMM d, yyyy')
    };
  } catch {
    // Handle invalid dates gracefully
    return {
      label: 'Created',
      text: 'Unknown'
    };
  }
};

const Discover: React.FC = () => {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [cards, setCards] = useState<Card[]>([]);
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPillar, setSelectedPillar] = useState('');
  const [selectedStage, setSelectedStage] = useState('');
  const [selectedHorizon, setSelectedHorizon] = useState('');
  const [sortOption, setSortOption] = useState<SortOption>('newest');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [followedCardIds, setFollowedCardIds] = useState<Set<string>>(new Set());

  // Comparison mode state
  const [compareMode, setCompareMode] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState<Array<{ id: string; name: string }>>([]);

  // Score threshold filters (minimum values, 0-100)
  const [impactMin, setImpactMin] = useState<number>(0);
  const [relevanceMin, setRelevanceMin] = useState<number>(0);
  const [noveltyMin, setNoveltyMin] = useState<number>(0);

  // Date range filters (YYYY-MM-DD format)
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  // Semantic search toggle - uses vector search API when enabled
  const [useSemanticSearch, setUseSemanticSearch] = useState<boolean>(false);

  // Debounce filter values that change rapidly (300ms delay)
  // This reduces API calls when users type in search or drag sliders
  const filterState = useMemo(() => ({
    searchTerm,
    impactMin,
    relevanceMin,
    noveltyMin,
  }), [searchTerm, impactMin, relevanceMin, noveltyMin]);

  const { debouncedValue: debouncedFilters, isPending: isFilterPending } = useDebouncedValue(filterState, 300);

  // Save search modal state
  const [showSaveSearchModal, setShowSaveSearchModal] = useState(false);

  // Saved searches sidebar state
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);

  // Search history state
  const [searchHistory, setSearchHistory] = useState<SearchHistoryEntry[]>([]);
  const [isHistoryExpanded, setIsHistoryExpanded] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [deletingHistoryId, setDeletingHistoryId] = useState<string | null>(null);

  // Quick filter from URL params (new, following)
  const quickFilter = searchParams.get('filter') || '';

  // Build current search query config for saving
  const currentQueryConfig = useMemo<SavedSearchQueryConfig>(() => {
    const config: SavedSearchQueryConfig = {
      use_vector_search: useSemanticSearch,
    };

    if (searchTerm.trim()) {
      config.query = searchTerm.trim();
    }

    // Build filters object
    const filters: SavedSearchQueryConfig['filters'] = {};

    if (selectedPillar) {
      filters.pillar_ids = [selectedPillar];
    }
    if (selectedStage) {
      filters.stage_ids = [selectedStage];
    }
    if (selectedHorizon && selectedHorizon !== '') {
      filters.horizon = selectedHorizon as 'H1' | 'H2' | 'H3';
    }
    if (dateFrom || dateTo) {
      filters.date_range = {
        ...(dateFrom && { start: dateFrom }),
        ...(dateTo && { end: dateTo }),
      };
    }
    if (impactMin > 0 || relevanceMin > 0 || noveltyMin > 0) {
      filters.score_thresholds = {
        ...(impactMin > 0 && { impact_score: { min: impactMin } }),
        ...(relevanceMin > 0 && { relevance_score: { min: relevanceMin } }),
        ...(noveltyMin > 0 && { novelty_score: { min: noveltyMin } }),
      };
    }

    // Only add filters if there's at least one filter set
    if (Object.keys(filters).length > 0) {
      config.filters = filters;
    }

    return config;
  }, [searchTerm, selectedPillar, selectedStage, selectedHorizon, dateFrom, dateTo, impactMin, relevanceMin, noveltyMin, useSemanticSearch]);

  useEffect(() => {
    loadDiscoverData();
    loadFollowedCards();
  }, [user?.id]);

  // Use debounced values for frequently-changing filters to reduce API calls
  useEffect(() => {
    loadCards();
  }, [debouncedFilters, selectedPillar, selectedStage, selectedHorizon, quickFilter, followedCardIds, dateFrom, dateTo, useSemanticSearch, sortOption]);

  const loadDiscoverData = async () => {
    try {
      // Load pillars
      const { data: pillarsData } = await supabase
        .from('pillars')
        .select('*')
        .order('name');

      // Load stages
      const { data: stagesData } = await supabase
        .from('stages')
        .select('*')
        .order('sort_order');

      setPillars(pillarsData || []);
      setStages(stagesData || []);
    } catch (error) {
      console.error('Error loading discover data:', error);
    }
  };

  const loadFollowedCards = async () => {
    if (!user?.id) return;
    try {
      const { data } = await supabase
        .from('card_follows')
        .select('card_id')
        .eq('user_id', user.id);

      if (data) {
        setFollowedCardIds(new Set(data.map(f => f.card_id)));
      }
    } catch (error) {
      console.error('Error loading followed cards:', error);
    }
  };

  const loadCards = async () => {
    setLoading(true);
    setError(null);
    try {
      // Handle "following" filter - need to filter client-side since we have the IDs
      if (quickFilter === 'following') {
        if (followedCardIds.size === 0) {
          setCards([]);
          setLoading(false);
          return;
        }

        let query = supabase
          .from('cards')
          .select('*')
          .eq('status', 'active')
          .in('id', Array.from(followedCardIds));

        if (debouncedFilters.searchTerm) {
          query = query.or(`name.ilike.%${debouncedFilters.searchTerm}%,summary.ilike.%${debouncedFilters.searchTerm}%`);
        }

        const sortConfig = getSortConfig(sortOption);
        const { data } = await query.order(sortConfig.column, { ascending: sortConfig.ascending });
        setCards(data || []);
        setLoading(false);
        return;
      }

      // Use advanced search API when semantic search is enabled and there's a search term
      if (useSemanticSearch && debouncedFilters.searchTerm.trim()) {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData?.session?.access_token;

        if (token) {
          // Build advanced search request with all current filters (using debounced values)
          const searchRequest: AdvancedSearchRequest = {
            query: debouncedFilters.searchTerm,
            use_vector_search: true,
            filters: {
              ...(selectedPillar && { pillar_ids: [selectedPillar] }),
              ...(selectedStage && { stage_ids: [selectedStage] }),
              ...(selectedHorizon && selectedHorizon !== '' && { horizon: selectedHorizon as 'H1' | 'H2' | 'H3' }),
              ...((dateFrom || dateTo) && {
                date_range: {
                  ...(dateFrom && { start: dateFrom }),
                  ...(dateTo && { end: dateTo }),
                },
              }),
              ...((debouncedFilters.impactMin > 0 || debouncedFilters.relevanceMin > 0 || debouncedFilters.noveltyMin > 0) && {
                score_thresholds: {
                  ...(debouncedFilters.impactMin > 0 && { impact_score: { min: debouncedFilters.impactMin } }),
                  ...(debouncedFilters.relevanceMin > 0 && { relevance_score: { min: debouncedFilters.relevanceMin } }),
                  ...(debouncedFilters.noveltyMin > 0 && { novelty_score: { min: debouncedFilters.noveltyMin } }),
                },
              }),
            },
            limit: 100,
          };

          const response = await advancedSearch(token, searchRequest);

          // Map search results to Card interface
          const mappedCards: Card[] = response.results.map((result) => ({
            id: result.id,
            name: result.name,
            slug: result.slug,
            summary: result.summary || result.description || '',
            pillar_id: result.pillar_id || '',
            stage_id: result.stage_id || '',
            horizon: (result.horizon as 'H1' | 'H2' | 'H3') || 'H1',
            novelty_score: result.novelty_score || 0,
            maturity_score: result.maturity_score || 0,
            impact_score: result.impact_score || 0,
            relevance_score: result.relevance_score || 0,
            velocity_score: result.velocity_score || 0,
            risk_score: result.risk_score || 0,
            opportunity_score: result.opportunity_score || 0,
            created_at: result.created_at || '',
            anchor_id: result.anchor_id,
            // Include search relevance score from vector search (0-1 similarity)
            search_relevance: result.search_relevance,
          }));

          setCards(mappedCards);

          // Record search to history (async, non-blocking)
          recordSearchToHistory(currentQueryConfig, mappedCards.length);

          setLoading(false);
          return;
        }
      }

      // Standard Supabase query for text search
      let query = supabase
        .from('cards')
        .select('*')
        .eq('status', 'active');

      // Handle "new" filter - cards from the last week
      if (quickFilter === 'new') {
        const oneWeekAgo = new Date();
        oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
        query = query.gte('created_at', oneWeekAgo.toISOString());
      }

      if (selectedPillar) {
        query = query.eq('pillar_id', selectedPillar);
      }
      if (selectedStage) {
        query = query.eq('stage_id', selectedStage);
      }
      if (selectedHorizon) {
        query = query.eq('horizon', selectedHorizon);
      }

      if (debouncedFilters.searchTerm) {
        query = query.or(`name.ilike.%${debouncedFilters.searchTerm}%,summary.ilike.%${debouncedFilters.searchTerm}%`);
      }

      // Apply score threshold filters (using debounced values)
      if (debouncedFilters.impactMin > 0) {
        query = query.gte('impact_score', debouncedFilters.impactMin);
      }
      if (debouncedFilters.relevanceMin > 0) {
        query = query.gte('relevance_score', debouncedFilters.relevanceMin);
      }
      if (debouncedFilters.noveltyMin > 0) {
        query = query.gte('novelty_score', debouncedFilters.noveltyMin);
      }

      // Apply date range filters
      if (dateFrom) {
        query = query.gte('created_at', dateFrom);
      }
      if (dateTo) {
        query = query.lte('created_at', dateTo);
      }

      const sortConfig = getSortConfig(sortOption);
      const { data } = await query.order(sortConfig.column, { ascending: sortConfig.ascending });

      setCards(data || []);

      // Record search to history (skip quick filters since they're preset, not user searches)
      if (!quickFilter) {
        recordSearchToHistory(currentQueryConfig, (data || []).length);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';

      // Check for network-specific errors
      if (err instanceof TypeError && err.message.includes('fetch')) {
        setError('Network error: Unable to connect to the server. Please check your connection and try again.');
      } else if (errorMessage.includes('401') || errorMessage.includes('Unauthorized')) {
        setError('Authentication error: Please sign in to use advanced search features.');
      } else if (errorMessage.includes('500') || errorMessage.includes('Internal Server Error')) {
        setError('Server error: The search service is temporarily unavailable. Please try again in a few moments.');
      } else if (errorMessage.includes('timeout') || errorMessage.includes('Timeout')) {
        setError('Request timeout: The search took too long. Try narrowing your filters or search term.');
      } else {
        setError(`Failed to load cards: ${errorMessage}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const toggleFollowCard = async (cardId: string) => {
    if (!user?.id) return;

    const isFollowing = followedCardIds.has(cardId);

    // Optimistic update
    setFollowedCardIds(prev => {
      const newSet = new Set(prev);
      if (isFollowing) {
        newSet.delete(cardId);
      } else {
        newSet.add(cardId);
      }
      return newSet;
    });

    try {
      if (isFollowing) {
        // Unfollow
        await supabase
          .from('card_follows')
          .delete()
          .eq('user_id', user.id)
          .eq('card_id', cardId);
      } else {
        // Follow
        await supabase
          .from('card_follows')
          .insert({
            user_id: user.id,
            card_id: cardId,
            priority: 'medium'
          });
      }
    } catch (error) {
      console.error('Error toggling card follow:', error);
      // Revert optimistic update on error
      setFollowedCardIds(prev => {
        const newSet = new Set(prev);
        if (isFollowing) {
          newSet.add(cardId);
        } else {
          newSet.delete(cardId);
        }
        return newSet;
      });
    }
  };

  // Apply saved search configuration
  const handleSelectSavedSearch = useCallback((config: SavedSearchQueryConfig) => {
    // Apply query
    if (config.query !== undefined) {
      setSearchTerm(config.query);
    } else {
      setSearchTerm('');
    }

    // Apply semantic search toggle
    setUseSemanticSearch(config.use_vector_search ?? false);

    // Apply filters
    const filters = config.filters ?? {};

    // Pillar (take first if array)
    setSelectedPillar(filters.pillar_ids?.[0] ?? '');

    // Stage (take first if array)
    setSelectedStage(filters.stage_ids?.[0] ?? '');

    // Horizon
    setSelectedHorizon(filters.horizon && filters.horizon !== 'ALL' ? filters.horizon : '');

    // Date range
    setDateFrom(filters.date_range?.start ?? '');
    setDateTo(filters.date_range?.end ?? '');

    // Score thresholds
    setImpactMin(filters.score_thresholds?.impact_score?.min ?? 0);
    setRelevanceMin(filters.score_thresholds?.relevance_score?.min ?? 0);
    setNoveltyMin(filters.score_thresholds?.novelty_score?.min ?? 0);

    // Clear quick filter when applying saved search
    setSearchParams({});

    // Close sidebar after selection
    setIsSidebarOpen(false);
  }, [setSearchParams]);

  // Handle save search success - refresh sidebar
  const handleSaveSearchSuccess = useCallback(() => {
    setShowSaveSearchModal(false);
    setSidebarRefreshKey((prev) => prev + 1);
  }, []);

  // Record search to history after execution
  const recordSearchToHistory = useCallback(async (queryConfig: SavedSearchQueryConfig, resultCount: number) => {
    if (!user?.id) return;

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
    } catch (_error) {
      // Silently fail - history recording is not critical
    }
  }, [user?.id]);

  // Load search history
  const loadSearchHistory = useCallback(async () => {
    if (!user?.id) return;

    setHistoryLoading(true);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;

      if (token) {
        const response = await getSearchHistory(token, 20);
        setSearchHistory(response.history);
      }
    } catch (_error) {
      // Silently fail - history is not critical
    } finally {
      setHistoryLoading(false);
    }
  }, [user?.id]);

  // Load search history on mount and when user changes
  useEffect(() => {
    loadSearchHistory();
  }, [loadSearchHistory]);

  // Initialize comparison mode from URL params or sessionStorage
  useEffect(() => {
    const isCompareMode = searchParams.get('compare') === 'true';
    if (isCompareMode) {
      setCompareMode(true);

      // Check if there's a card stored from CardDetail
      const storedCard = sessionStorage.getItem('compareCard');
      if (storedCard) {
        try {
          const cardData = JSON.parse(storedCard);
          if (cardData.id && cardData.name) {
            setSelectedForCompare([cardData]);
          }
        } catch {
          // Invalid data, ignore
        }
        // Clear the stored card after using it
        sessionStorage.removeItem('compareCard');
      }
    }
  }, [searchParams]);

  // Toggle card selection for comparison
  const toggleCardForCompare = useCallback((card: { id: string; name: string }) => {
    setSelectedForCompare((prev) => {
      const isSelected = prev.some((c) => c.id === card.id);
      if (isSelected) {
        return prev.filter((c) => c.id !== card.id);
      }
      // Limit to 2 cards
      if (prev.length >= 2) {
        // Replace the oldest selection
        return [prev[1], card];
      }
      return [...prev, card];
    });
  }, []);

  // Navigate to comparison view
  const navigateToCompare = useCallback(() => {
    if (selectedForCompare.length === 2) {
      const ids = selectedForCompare.map((c) => c.id).join(',');
      navigate(`/compare?card_ids=${ids}`);
    }
  }, [selectedForCompare, navigate]);

  // Exit comparison mode
  const exitCompareMode = useCallback(() => {
    setCompareMode(false);
    setSelectedForCompare([]);
    // Remove compare param from URL
    const newParams = new URLSearchParams(searchParams);
    newParams.delete('compare');
    setSearchParams(newParams);
  }, [searchParams, setSearchParams]);

  // Handle clicking a history item to re-run the search
  const handleHistoryClick = useCallback((entry: SearchHistoryEntry) => {
    handleSelectSavedSearch(entry.query_config);
  }, [handleSelectSavedSearch]);

  // Delete a single history entry
  const handleDeleteHistoryEntry = useCallback(async (entryId: string, e: React.MouseEvent) => {
    e.stopPropagation();

    setDeletingHistoryId(entryId);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;

      if (token) {
        await deleteSearchHistoryEntry(token, entryId);
        setSearchHistory((prev) => prev.filter((h) => h.id !== entryId));
      }
    } catch (_error) {
      // Silently fail
    } finally {
      setDeletingHistoryId(null);
    }
  }, []);

  // Clear all history
  const handleClearHistory = useCallback(async () => {
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;

      if (token) {
        await clearSearchHistory(token);
        setSearchHistory([]);
      }
    } catch (_error) {
      // Silently fail
    }
  }, []);

  // Format relative time for history entries
  const formatHistoryTime = useCallback((dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  }, []);

  // Build a short description of a query config
  const getHistoryDescription = useCallback((config: SavedSearchQueryConfig): string => {
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
        parts.push(`${horizon}`);
      }
      if (date_range && (date_range.start || date_range.end)) {
        parts.push('date filter');
      }
      if (score_thresholds && Object.keys(score_thresholds).length > 0) {
        parts.push('score filters');
      }
    }

    if (parts.length === 0 && !config.use_vector_search) {
      return 'All cards';
    }

    return parts.join(' • ') || (config.use_vector_search ? 'Semantic search' : 'All cards');
  }, []);

  return (
    <>
      {/* Saved Searches Sidebar */}
      <SearchSidebar
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        onSelectSearch={handleSelectSavedSearch}
        refreshKey={sidebarRefreshKey}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">Discover Intelligence</h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Explore emerging trends and technologies relevant to Austin's strategic priorities.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (compareMode) {
                  exitCompareMode();
                } else {
                  setCompareMode(true);
                }
              }}
              className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                compareMode
                  ? 'text-white bg-extended-purple border border-extended-purple'
                  : 'text-extended-purple bg-extended-purple/10 border border-extended-purple/30 hover:bg-extended-purple hover:text-white'
              }`}
              aria-pressed={compareMode}
              title={compareMode ? 'Exit compare mode' : 'Select cards to compare'}
            >
              <ArrowLeftRight className="w-4 h-4" />
              {compareMode ? 'Exit Compare' : 'Compare'}
            </button>
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                isSidebarOpen
                  ? 'text-brand-blue bg-brand-light-blue dark:bg-brand-blue/20 border border-brand-blue/30'
                  : 'text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
              aria-pressed={isSidebarOpen}
              title="Toggle saved searches sidebar"
            >
              <Bookmark className="w-4 h-4" />
              Saved Searches
            </button>
            <Link
              to="/discover/queue"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <Inbox className="w-4 h-4" />
              Review Queue
            </Link>
            <Link
              to="/discover/history"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <History className="w-4 h-4" />
              Run History
            </Link>
          </div>
        </div>
      </div>

      {/* Quick Filter Chips */}
      <div className="flex items-center gap-3 mb-6">
        <span className="text-sm font-medium text-gray-500 dark:text-gray-400">Quick filters:</span>
        <button
          onClick={() => setSearchParams({})}
          className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            !quickFilter
              ? 'bg-brand-blue text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
        >
          <Eye className="h-4 w-4 mr-1.5" />
          All Cards
        </button>
        <button
          onClick={() => setSearchParams({ filter: 'new' })}
          className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            quickFilter === 'new'
              ? 'bg-brand-green text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
        >
          <Clock className="h-4 w-4 mr-1.5" />
          New This Week
        </button>
        <button
          onClick={() => setSearchParams({ filter: 'following' })}
          className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            quickFilter === 'following'
              ? 'bg-extended-purple text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
        >
          <Star className="h-4 w-4 mr-1.5" />
          Following
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          {/* Search */}
          <div className="lg:col-span-2">
            <label htmlFor="search" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <input
                type="text"
                id="search"
                className="pl-10 block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                placeholder={useSemanticSearch ? "Semantic search (finds related concepts)..." : "Search cards..."}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            {/* Semantic Search Toggle */}
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                role="switch"
                aria-checked={useSemanticSearch}
                onClick={() => setUseSemanticSearch(!useSemanticSearch)}
                className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 ${
                  useSemanticSearch ? 'bg-extended-purple' : 'bg-gray-200 dark:bg-gray-600'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    useSemanticSearch ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </button>
              <label
                className={`flex items-center gap-1.5 text-sm cursor-pointer ${
                  useSemanticSearch
                    ? 'text-extended-purple font-medium'
                    : 'text-gray-600 dark:text-gray-400'
                }`}
                onClick={() => setUseSemanticSearch(!useSemanticSearch)}
              >
                <Sparkles className={`h-4 w-4 ${useSemanticSearch ? 'text-extended-purple' : 'text-gray-400'}`} />
                Semantic Search
              </label>
              {useSemanticSearch && (
                <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">
                  (finds conceptually related cards)
                </span>
              )}
            </div>
          </div>

          {/* Pillar Filter */}
          <div>
            <label htmlFor="pillar" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Strategic Pillar
            </label>
            <select
              id="pillar"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={selectedPillar}
              onChange={(e) => setSelectedPillar(e.target.value)}
            >
              <option value="">All Pillars</option>
              {pillars.map((pillar) => (
                <option key={pillar.id} value={pillar.id}>
                  {pillar.name}
                </option>
              ))}
            </select>
          </div>

          {/* Stage Filter */}
          <div>
            <label htmlFor="stage" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Maturity Stage
            </label>
            <select
              id="stage"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={selectedStage}
              onChange={(e) => setSelectedStage(e.target.value)}
            >
              <option value="">All Stages</option>
              {stages.map((stage) => (
                <option key={stage.id} value={stage.id}>
                  {stage.name}
                </option>
              ))}
            </select>
          </div>

          {/* Horizon Filter */}
          <div>
            <label htmlFor="horizon" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Horizon
            </label>
            <select
              id="horizon"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={selectedHorizon}
              onChange={(e) => setSelectedHorizon(e.target.value)}
            >
              <option value="">All Horizons</option>
              <option value="H1">H1 (0-2 years)</option>
              <option value="H2">H2 (2-5 years)</option>
              <option value="H3">H3 (5+ years)</option>
            </select>
          </div>

          {/* Sort */}
          <div>
            <label htmlFor="sort" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Sort By
            </label>
            <select
              id="sort"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={sortOption}
              onChange={(e) => setSortOption(e.target.value as SortOption)}
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="recently_updated">Recently Updated</option>
              <option value="least_recently_updated">Least Recently Updated</option>
            </select>
          </div>
        </div>

        {/* Date Range Filters */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <div className="lg:col-span-2 flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-400 flex-shrink-0" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Date Range:</span>
          </div>
          <div>
            <label htmlFor="dateFrom" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Created After
            </label>
            <input
              type="date"
              id="dateFrom"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="dateTo" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Created Before
            </label>
            <input
              type="date"
              id="dateTo"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
        </div>

        {/* Score Threshold Sliders */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Minimum Score Thresholds
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Impact Score Slider */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label htmlFor="impactMin" className="text-sm text-gray-600 dark:text-gray-400">
                  Impact
                </label>
                <span className={`text-sm font-medium ${impactMin > 0 ? getScoreColorClasses(impactMin) : 'text-gray-500 dark:text-gray-400'}`}>
                  {impactMin > 0 ? `≥ ${impactMin}` : 'Any'}
                </span>
              </div>
              <input
                type="range"
                id="impactMin"
                min="0"
                max="100"
                step="5"
                value={impactMin}
                onChange={(e) => setImpactMin(Number(e.target.value))}
                className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-brand-blue"
                title={`Minimum impact score: ${impactMin}`}
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>0</span>
                <span>50</span>
                <span>100</span>
              </div>
            </div>

            {/* Relevance Score Slider */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label htmlFor="relevanceMin" className="text-sm text-gray-600 dark:text-gray-400">
                  Relevance
                </label>
                <span className={`text-sm font-medium ${relevanceMin > 0 ? getScoreColorClasses(relevanceMin) : 'text-gray-500 dark:text-gray-400'}`}>
                  {relevanceMin > 0 ? `≥ ${relevanceMin}` : 'Any'}
                </span>
              </div>
              <input
                type="range"
                id="relevanceMin"
                min="0"
                max="100"
                step="5"
                value={relevanceMin}
                onChange={(e) => setRelevanceMin(Number(e.target.value))}
                className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-brand-blue"
                title={`Minimum relevance score: ${relevanceMin}`}
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>0</span>
                <span>50</span>
                <span>100</span>
              </div>
            </div>

            {/* Novelty Score Slider */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label htmlFor="noveltyMin" className="text-sm text-gray-600 dark:text-gray-400">
                  Novelty
                </label>
                <span className={`text-sm font-medium ${noveltyMin > 0 ? getScoreColorClasses(noveltyMin) : 'text-gray-500 dark:text-gray-400'}`}>
                  {noveltyMin > 0 ? `≥ ${noveltyMin}` : 'Any'}
                </span>
              </div>
              <input
                type="range"
                id="noveltyMin"
                min="0"
                max="100"
                step="5"
                value={noveltyMin}
                onChange={(e) => setNoveltyMin(Number(e.target.value))}
                className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-brand-blue"
                title={`Minimum novelty score: ${noveltyMin}`}
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>0</span>
                <span>50</span>
                <span>100</span>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Search History */}
        {user?.id && searchHistory.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
            <button
              onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
              className="w-full flex items-center justify-between text-left"
            >
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-gray-400" />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Recent Searches ({searchHistory.length})
                </span>
              </div>
              <div className="flex items-center gap-2">
                {historyLoading && (
                  <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />
                )}
                {isHistoryExpanded ? (
                  <ChevronUp className="h-4 w-4 text-gray-400" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-gray-400" />
                )}
              </div>
            </button>

            {isHistoryExpanded && (
              <div className="mt-3 space-y-2 max-h-64 overflow-y-auto">
                {/* Clear All Button */}
                <div className="flex justify-end mb-2">
                  <button
                    onClick={handleClearHistory}
                    className="text-xs text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                    title="Clear all search history"
                  >
                    Clear all
                  </button>
                </div>

                {searchHistory.map((entry) => (
                  <div
                    key={entry.id}
                    onClick={() => handleHistoryClick(entry)}
                    className="group flex items-start justify-between gap-2 p-2 rounded-md border border-gray-200 dark:border-gray-600 hover:border-brand-blue hover:bg-brand-light-blue/50 dark:hover:bg-brand-blue/10 cursor-pointer transition-all"
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleHistoryClick(entry);
                      }
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Semantic search badge */}
                        {entry.query_config.use_vector_search && (
                          <span className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded text-[10px] font-medium bg-extended-purple/10 text-extended-purple">
                            <Sparkles className="h-2.5 w-2.5" />
                            AI
                          </span>
                        )}
                        {/* Query/description */}
                        <span className="text-sm text-gray-900 dark:text-white truncate">
                          {getHistoryDescription(entry.query_config)}
                        </span>
                      </div>
                      {/* Metadata row */}
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-400">
                          {formatHistoryTime(entry.executed_at)}
                        </span>
                        <span className="text-xs text-gray-400">•</span>
                        <span className="text-xs text-gray-400">
                          {entry.result_count} result{entry.result_count !== 1 ? 's' : ''}
                        </span>
                      </div>
                    </div>

                    {/* Delete button */}
                    <button
                      onClick={(e) => handleDeleteHistoryEntry(entry.id, e)}
                      disabled={deletingHistoryId === entry.id}
                      className="p-1 text-gray-400 hover:text-red-500 rounded opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50 shrink-0"
                      title="Remove from history"
                      aria-label="Remove from history"
                    >
                      {deletingHistoryId === entry.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <X className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* View Controls and Save Search */}
        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Showing {cards.length} cards
            </p>
            {isFilterPending && (
              <span className="inline-flex items-center gap-1 text-xs text-brand-blue">
                <Loader2 className="h-3 w-3 animate-spin" />
                Updating...
              </span>
            )}
          </div>
          <div className="flex items-center space-x-3">
            {/* Save Search Button */}
            <button
              onClick={() => setShowSaveSearchModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-blue bg-brand-light-blue dark:bg-brand-blue/20 border border-brand-blue/30 rounded-md hover:bg-brand-blue hover:text-white dark:hover:bg-brand-blue transition-colors"
              title="Save current search filters"
            >
              <Bookmark className="h-4 w-4" />
              Save Search
            </button>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 rounded-md transition-colors ${
                  viewMode === 'grid'
                    ? 'bg-brand-light-blue text-brand-blue dark:bg-brand-blue/20 dark:text-brand-blue'
                    : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
                }`}
                aria-label="Grid view"
                aria-pressed={viewMode === 'grid'}
              >
                <Grid className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 rounded-md transition-colors ${
                  viewMode === 'list'
                    ? 'bg-brand-light-blue text-brand-blue dark:bg-brand-blue/20 dark:text-brand-blue'
                    : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
                }`}
                aria-label="List view"
                aria-pressed={viewMode === 'list'}
              >
                <List className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Compare Mode Banner */}
      {compareMode && (
        <div className="mb-6 p-4 bg-extended-purple/10 border border-extended-purple/30 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ArrowLeftRight className="h-5 w-5 text-extended-purple" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">
                  Compare Mode Active
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-300">
                  {selectedForCompare.length === 0
                    ? 'Click on cards to select them for comparison (max 2)'
                    : selectedForCompare.length === 1
                    ? `Selected: ${selectedForCompare[0].name} — Click another card to compare`
                    : `Ready to compare: ${selectedForCompare[0].name} vs ${selectedForCompare[1].name}`}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {selectedForCompare.length > 0 && (
                <button
                  onClick={() => setSelectedForCompare([])}
                  className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
                >
                  Clear Selection
                </button>
              )}
              <button
                onClick={navigateToCompare}
                disabled={selectedForCompare.length !== 2}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-extended-purple text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-extended-purple/90 transition-colors"
              >
                <ArrowLeftRight className="h-4 w-4" />
                Compare Cards
              </button>
              <button
                onClick={exitCompareMode}
                className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                title="Exit compare mode"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Selected Cards Pills */}
          {selectedForCompare.length > 0 && (
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              {selectedForCompare.map((card, index) => (
                <span
                  key={card.id}
                  className="inline-flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-gray-800 rounded-full text-sm border border-extended-purple/30"
                >
                  <span className="font-medium text-extended-purple">
                    {index + 1}.
                  </span>
                  <span className="text-gray-700 dark:text-gray-200 truncate max-w-[200px]">
                    {card.name}
                  </span>
                  <button
                    onClick={() => toggleCardForCompare(card)}
                    className="text-gray-400 hover:text-red-500 transition-colors"
                    title="Remove from comparison"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium text-red-700 dark:text-red-300">{error}</p>
              <button
                onClick={() => {
                  setError(null);
                  loadCards();
                }}
                className="mt-2 inline-flex items-center gap-1.5 text-sm text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 transition-colors"
              >
                <RefreshCw className="h-4 w-4" />
                Try again
              </button>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
              aria-label="Dismiss error"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      {/* Cards Grid/List */}
      {loading || isFilterPending ? (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue"></div>
          {isFilterPending && !loading && (
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
              Updating search...
            </p>
          )}
        </div>
      ) : cards.length === 0 && !error ? (
        <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
          {/* Icon based on context */}
          {quickFilter === 'following' ? (
            <Star className="mx-auto h-12 w-12 text-gray-400" />
          ) : useSemanticSearch && searchTerm ? (
            <Sparkles className="mx-auto h-12 w-12 text-gray-400" />
          ) : searchTerm || selectedPillar || selectedStage || selectedHorizon || dateFrom || dateTo || impactMin > 0 || relevanceMin > 0 || noveltyMin > 0 ? (
            <Filter className="mx-auto h-12 w-12 text-gray-400" />
          ) : (
            <Inbox className="mx-auto h-12 w-12 text-gray-400" />
          )}

          {/* Heading based on context */}
          <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
            {quickFilter === 'following'
              ? "You're Not Following Any Cards"
              : quickFilter === 'new'
              ? 'No New Cards This Week'
              : useSemanticSearch && searchTerm
              ? 'No Semantic Matches Found'
              : searchTerm || selectedPillar || selectedStage || selectedHorizon || dateFrom || dateTo || impactMin > 0 || relevanceMin > 0 || noveltyMin > 0
              ? 'No Cards Match Your Filters'
              : 'No Cards Available'}
          </h3>

          {/* Helpful message based on context */}
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            {quickFilter === 'following' ? (
              <>
                Start following cards to build your personalized feed.
                <br />
                <span className="text-gray-400">Click the heart icon on any card to follow it.</span>
              </>
            ) : quickFilter === 'new' ? (
              'Check back soon for newly discovered intelligence cards.'
            ) : useSemanticSearch && searchTerm ? (
              <>
                No cards matched your semantic search for "<strong className="text-gray-700 dark:text-gray-300">{searchTerm}</strong>".
                <br />
                <span className="text-gray-400">Try different keywords, or switch to standard text search.</span>
              </>
            ) : searchTerm ? (
              <>
                No cards matched your search for "<strong className="text-gray-700 dark:text-gray-300">{searchTerm}</strong>".
                <br />
                <span className="text-gray-400">Try different keywords or enable semantic search for broader matches.</span>
              </>
            ) : selectedPillar || selectedStage || selectedHorizon || dateFrom || dateTo || impactMin > 0 || relevanceMin > 0 || noveltyMin > 0 ? (
              <>
                Your current filter combination returned no results.
                <br />
                <span className="text-gray-400">Try removing some filters or adjusting score thresholds.</span>
              </>
            ) : (
              'The intelligence library is empty. Cards will appear here as they are discovered.'
            )}
          </p>

          {/* Action buttons based on context */}
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            {quickFilter === 'following' && (
              <Link
                to="/discover"
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
              >
                <Eye className="h-4 w-4 mr-2" />
                Browse All Cards
              </Link>
            )}
            {(searchTerm || selectedPillar || selectedStage || selectedHorizon || dateFrom || dateTo || impactMin > 0 || relevanceMin > 0 || noveltyMin > 0) && !quickFilter && (
              <button
                onClick={() => {
                  setSearchTerm('');
                  setSelectedPillar('');
                  setSelectedStage('');
                  setSelectedHorizon('');
                  setDateFrom('');
                  setDateTo('');
                  setImpactMin(0);
                  setRelevanceMin(0);
                  setNoveltyMin(0);
                  setUseSemanticSearch(false);
                }}
                className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <X className="h-4 w-4 mr-2" />
                Clear All Filters
              </button>
            )}
            {useSemanticSearch && searchTerm && (
              <button
                onClick={() => setUseSemanticSearch(false)}
                className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <Search className="h-4 w-4 mr-2" />
                Try Standard Search
              </button>
            )}
          </div>
        </div>
      ) : cards.length > 0 ? (
        <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6' : 'space-y-4'}>
          {cards.map((card) => {
            const stageNumber = parseStageNumber(card.stage_id);
            const isSelectedForCompare = selectedForCompare.some((c) => c.id === card.id);

            return (
              <div
                key={card.id}
                onClick={compareMode ? () => toggleCardForCompare({ id: card.id, name: card.name }) : undefined}
                className={`bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 border-l-4 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg relative ${
                  compareMode
                    ? isSelectedForCompare
                      ? 'border-l-extended-purple ring-2 ring-extended-purple/50 cursor-pointer'
                      : 'border-transparent hover:border-l-extended-purple/50 cursor-pointer'
                    : 'border-transparent hover:border-l-brand-blue'
                }`}
              >
                {/* Compare Mode Selection Indicator */}
                {compareMode && (
                  <div
                    className={`absolute top-3 right-3 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                      isSelectedForCompare
                        ? 'bg-extended-purple border-extended-purple text-white'
                        : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800'
                    }`}
                  >
                    {isSelectedForCompare && (
                      <Check className="h-4 w-4" />
                    )}
                  </div>
                )}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                      {compareMode ? (
                        <span className="hover:text-extended-purple transition-colors cursor-pointer">
                          {card.name}
                        </span>
                      ) : (
                        <Link
                          to={`/cards/${card.slug}`}
                          className="hover:text-brand-blue transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {card.name}
                        </Link>
                      )}
                    </h3>
                    <div className="flex items-center gap-2 flex-wrap mb-3">
                      {/* Search Relevance Badge - shown when semantic search is used */}
                      {card.search_relevance !== undefined && (
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-extended-purple/10 text-extended-purple border border-extended-purple/30"
                          title={`Search match: ${Math.round(card.search_relevance * 100)}% similarity to your query`}
                        >
                          <Sparkles className="h-3 w-3" />
                          {Math.round(card.search_relevance * 100)}% match
                        </span>
                      )}
                      <PillarBadge pillarId={card.pillar_id} showIcon size="sm" />
                      <HorizonBadge horizon={card.horizon} size="sm" />
                      {stageNumber !== null && (
                        <StageBadge stage={stageNumber} size="sm" variant="minimal" />
                      )}
                      {card.top25_relevance && card.top25_relevance.length > 0 && (
                        <Top25Badge priorities={card.top25_relevance} size="sm" showCount />
                      )}
                    </div>
                  </div>
                  {!compareMode && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleFollowCard(card.id);
                      }}
                      className={`flex-shrink-0 p-2 transition-colors ${
                        followedCardIds.has(card.id)
                          ? 'text-red-500 hover:text-red-600'
                          : 'text-gray-400 hover:text-red-500'
                      }`}
                      title={followedCardIds.has(card.id) ? 'Unfollow card' : 'Follow card'}
                      aria-pressed={followedCardIds.has(card.id)}
                    >
                      <Heart
                        className="h-5 w-5"
                        fill={followedCardIds.has(card.id) ? 'currentColor' : 'none'}
                      />
                    </button>
                  )}
                </div>

                <p className="text-gray-600 dark:text-gray-400 mb-4 line-clamp-3">
                  {searchTerm ? highlightText(card.summary, searchTerm) : card.summary}
                </p>

                {/* Scores */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex justify-between" title="How much this could affect Austin's operations or residents">
                    <span className="text-gray-500 dark:text-gray-400">Impact:</span>
                    <span className={getScoreColorClasses(card.impact_score)}>
                      {card.impact_score}
                    </span>
                  </div>
                  <div className="flex justify-between" title="How closely this aligns with Austin's strategic priorities">
                    <span className="text-gray-500 dark:text-gray-400">Relevance:</span>
                    <span className={getScoreColorClasses(card.relevance_score)}>
                      {card.relevance_score}
                    </span>
                  </div>
                  <div className="flex justify-between" title="How quickly this technology or trend is evolving">
                    <span className="text-gray-500 dark:text-gray-400">Velocity:</span>
                    <span className={getScoreColorClasses(card.velocity_score)}>
                      {card.velocity_score}
                    </span>
                  </div>
                  <div className="flex justify-between" title="How new or emerging this is in the market">
                    <span className="text-gray-500 dark:text-gray-400">Novelty:</span>
                    <span className={getScoreColorClasses(card.novelty_score)}>
                      {card.novelty_score}
                    </span>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600 flex items-center justify-between">
                  {compareMode ? (
                    <span className="inline-flex items-center text-sm text-extended-purple">
                      <ArrowLeftRight className="h-4 w-4 mr-1" />
                      {isSelectedForCompare ? 'Selected' : 'Click to select'}
                    </span>
                  ) : (
                    <Link
                      to={`/cards/${card.slug}`}
                      className="inline-flex items-center text-sm text-brand-blue hover:text-brand-dark-blue dark:text-brand-blue dark:hover:text-brand-light-blue transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Eye className="h-4 w-4 mr-1" />
                      View Details
                    </Link>
                  )}
                  {/* Date display */}
                  <span className="inline-flex items-center text-xs text-gray-500 dark:text-gray-400">
                    <Calendar className="h-3 w-3 mr-1" />
                    {(() => {
                      const dateInfo = formatCardDate(card.created_at, card.updated_at);
                      return `${dateInfo.label} ${dateInfo.text}`;
                    })()}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}

        {/* Save Search Modal */}
        <SaveSearchModal
          isOpen={showSaveSearchModal}
          onClose={() => setShowSaveSearchModal(false)}
          onSuccess={handleSaveSearchSuccess}
          queryConfig={currentQueryConfig}
        />
      </div>
    </>
  );
};

export default Discover;
