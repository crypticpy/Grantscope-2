import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Search, Filter, Grid, List, Eye, Heart, Clock, Star, Inbox, History } from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { PillarBadge } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge } from '../components/StageBadge';
import { Top25Badge } from '../components/Top25Badge';

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
  const [sortOption, setSortOption] = useState<SortOption>('newest');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [followedCardIds, setFollowedCardIds] = useState<Set<string>>(new Set());

  // Quick filter from URL params (new, following)
  const quickFilter = searchParams.get('filter') || '';

  useEffect(() => {
    loadDiscoverData();
    loadFollowedCards();
  }, [user?.id]);

  useEffect(() => {
    loadCards();
  }, [searchTerm, selectedPillar, selectedStage, selectedHorizon, sortOption, quickFilter, followedCardIds]);

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
                placeholder="Search cards..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
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

        {/* View Controls */}
        <div className="mt-4 flex items-center justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Showing {cards.length} cards
          </p>
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

                <p className="text-gray-600 dark:text-gray-400 mb-4 line-clamp-3">{card.summary}</p>

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
    </div>
  );
};

export default Discover;
