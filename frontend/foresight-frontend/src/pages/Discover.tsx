import React, { useState, useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Search, Filter, Grid, List, Eye, Heart, Clock, Star, Inbox, History, Calendar, Sparkles, Bookmark } from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { PillarBadge } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge } from '../components/StageBadge';
import { Top25Badge } from '../components/Top25Badge';
import { SaveSearchModal } from '../components/SaveSearchModal';
import { advancedSearch, AdvancedSearchRequest, SavedSearchQueryConfig } from '../lib/discovery-api';
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

const Discover: React.FC = () => {
  const { user } = useAuthContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const [cards, setCards] = useState<Card[]>([]);
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPillar, setSelectedPillar] = useState('');
  const [selectedStage, setSelectedStage] = useState('');
  const [selectedHorizon, setSelectedHorizon] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [followedCardIds, setFollowedCardIds] = useState<Set<string>>(new Set());

  // Score threshold filters (minimum values, 0-100)
  const [impactMin, setImpactMin] = useState<number>(0);
  const [relevanceMin, setRelevanceMin] = useState<number>(0);
  const [noveltyMin, setNoveltyMin] = useState<number>(0);

  // Date range filters (YYYY-MM-DD format)
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  // Semantic search toggle - uses vector search API when enabled
  const [useSemanticSearch, setUseSemanticSearch] = useState<boolean>(false);

  // Save search modal state
  const [showSaveSearchModal, setShowSaveSearchModal] = useState(false);

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

  useEffect(() => {
    loadCards();
  }, [searchTerm, selectedPillar, selectedStage, selectedHorizon, quickFilter, followedCardIds, impactMin, relevanceMin, noveltyMin, dateFrom, dateTo, useSemanticSearch]);

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

        if (searchTerm) {
          query = query.or(`name.ilike.%${searchTerm}%,summary.ilike.%${searchTerm}%`);
        }

        const { data } = await query.order('created_at', { ascending: false });
        setCards(data || []);
        setLoading(false);
        return;
      }

      // Use advanced search API when semantic search is enabled and there's a search term
      if (useSemanticSearch && searchTerm.trim()) {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData?.session?.access_token;

        if (token) {
          // Build advanced search request with all current filters
          const searchRequest: AdvancedSearchRequest = {
            query: searchTerm,
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
              ...((impactMin > 0 || relevanceMin > 0 || noveltyMin > 0) && {
                score_thresholds: {
                  ...(impactMin > 0 && { impact_score: { min: impactMin } }),
                  ...(relevanceMin > 0 && { relevance_score: { min: relevanceMin } }),
                  ...(noveltyMin > 0 && { novelty_score: { min: noveltyMin } }),
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

      if (searchTerm) {
        query = query.or(`name.ilike.%${searchTerm}%,summary.ilike.%${searchTerm}%`);
      }

      // Apply score threshold filters
      if (impactMin > 0) {
        query = query.gte('impact_score', impactMin);
      }
      if (relevanceMin > 0) {
        query = query.gte('relevance_score', relevanceMin);
      }
      if (noveltyMin > 0) {
        query = query.gte('novelty_score', noveltyMin);
      }

      // Apply date range filters
      if (dateFrom) {
        query = query.gte('created_at', dateFrom);
      }
      if (dateTo) {
        query = query.lte('created_at', dateTo);
      }

      const { data } = await query.order('created_at', { ascending: false });

      setCards(data || []);
    } catch (error) {
      console.error('Error loading cards:', error);
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

  return (
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
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

        {/* View Controls and Save Search */}
        <div className="mt-4 flex items-center justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Showing {cards.length} cards
          </p>
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

      {/* Cards Grid/List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue"></div>
        </div>
      ) : cards.length === 0 ? (
        <div className="text-center py-12">
          <Filter className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No cards found</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Try adjusting your filters or search terms.
          </p>
        </div>
      ) : (
        <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6' : 'space-y-4'}>
          {cards.map((card) => {
            const stageNumber = parseStageNumber(card.stage_id);

            return (
              <div
                key={card.id}
                className={`bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                      <Link
                        to={`/cards/${card.slug}`}
                        className="hover:text-brand-blue transition-colors"
                      >
                        {card.name}
                      </Link>
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
                  <button
                    onClick={() => toggleFollowCard(card.id)}
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

                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                  <Link
                    to={`/cards/${card.slug}`}
                    className="inline-flex items-center text-sm text-brand-blue hover:text-brand-dark-blue dark:text-brand-blue dark:hover:text-brand-light-blue transition-colors"
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    View Details
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Save Search Modal */}
      <SaveSearchModal
        isOpen={showSaveSearchModal}
        onClose={() => setShowSaveSearchModal(false)}
        onSuccess={() => setShowSaveSearchModal(false)}
        queryConfig={currentQueryConfig}
      />
    </div>
  );
};

export default Discover;
