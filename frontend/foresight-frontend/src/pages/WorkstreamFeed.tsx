/**
 * WorkstreamFeed Page
 *
 * Displays filtered cards based on a workstream's criteria including:
 * - Workstream header with name, description, and status
 * - Filter display showing selected pillars, horizon, stages, and keywords
 * - Cards grid with matching intelligence cards
 * - Empty state when no cards match filters
 */

import React, { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Edit,
  Eye,
  Heart,
  HeartOff,
  Filter,
  Loader2,
  Tag,
  RefreshCw,
} from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { cn } from '../lib/utils';
import { PillarBadge, PillarBadgeGroup } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge } from '../components/StageBadge';
import { Top25Badge } from '../components/Top25Badge';
import { getStageByNumber, getPillarByCode } from '../data/taxonomy';

// ============================================================================
// Types
// ============================================================================

interface Workstream {
  id: string;
  name: string;
  description: string;
  pillar_ids: string[];
  goal_ids: string[];
  stage_ids: string[];
  horizon: string;
  keywords: string[];
  is_active: boolean;
  auto_add: boolean;
  created_at: string;
  user_id: string;
}

interface Card {
  id: string;
  name: string;
  slug: string;
  summary: string;
  pillar_id: string;
  stage_id: number;
  horizon: 'H1' | 'H2' | 'H3';
  novelty_score: number;
  maturity_score: number;
  impact_score: number;
  relevance_score: number;
  velocity_score: number;
  risk_score: number;
  opportunity_score: number;
  top25_priorities?: string[];
  created_at: string;
}

interface CardFollow {
  card_id: string;
  priority: 'low' | 'medium' | 'high';
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Status badge for active/inactive workstream
 */
function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        isActive
          ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400 border border-green-300 dark:border-green-700'
          : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300 border border-gray-300 dark:border-gray-600'
      )}
    >
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

/**
 * Keyword tag display
 */
function KeywordTag({ keyword }: { keyword: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-brand-light-blue dark:bg-brand-blue/20 text-brand-dark-blue dark:text-brand-light-blue border border-brand-blue/30 dark:border-brand-blue/40">
      <Tag className="h-3 w-3" />
      {keyword}
    </span>
  );
}

/**
 * Stage range display for multiple stages
 */
function StageRangeDisplay({ stageIds }: { stageIds: string[] }) {
  if (stageIds.length === 0) return null;

  // Parse stage numbers
  const stageNumbers = stageIds
    .map((id) => parseInt(id, 10))
    .filter((n) => !isNaN(n))
    .sort((a, b) => a - b);

  if (stageNumbers.length === 0) return null;

  // If single stage or non-consecutive, show individual badges
  if (stageNumbers.length <= 2) {
    return (
      <div className="flex items-center gap-1 flex-wrap">
        {stageNumbers.map((stage) => (
          <StageBadge key={stage} stage={stage} size="sm" showName={false} variant="minimal" />
        ))}
      </div>
    );
  }

  // Check if consecutive
  const isConsecutive = stageNumbers.every(
    (n, i) => i === 0 || n === stageNumbers[i - 1] + 1
  );

  if (isConsecutive) {
    const min = stageNumbers[0];
    const max = stageNumbers[stageNumbers.length - 1];
    return (
      <span className="text-sm text-gray-600 dark:text-gray-400">
        Stages {min} - {max}
      </span>
    );
  }

  // Show individual badges for non-consecutive
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {stageNumbers.map((stage) => (
        <StageBadge key={stage} stage={stage} size="sm" showName={false} variant="minimal" />
      ))}
    </div>
  );
}

/**
 * Card component for displaying a single intelligence card
 */
function CardItem({
  card,
  isFollowed,
  onToggleFollow,
}: {
  card: Card;
  isFollowed: boolean;
  onToggleFollow: (cardId: string, isFollowed: boolean) => void;
}) {
  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2 truncate">
            <Link to={`/cards/${card.slug}`} className="hover:text-brand-blue transition-colors">
              {card.name}
            </Link>
          </h3>
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <PillarBadge pillarId={card.pillar_id} size="sm" />
            <HorizonBadge horizon={card.horizon} size="sm" />
            <StageBadge stage={card.stage_id} size="sm" showName={false} variant="minimal" />
            {card.top25_priorities && card.top25_priorities.length > 0 && (
              <Top25Badge priorities={card.top25_priorities} size="sm" showCount />
            )}
          </div>
        </div>
        <button
          onClick={() => onToggleFollow(card.id, isFollowed)}
          className={cn(
            'flex-shrink-0 p-2 transition-colors rounded-full',
            isFollowed
              ? 'text-red-500 hover:text-red-600 hover:bg-red-50'
              : 'text-gray-400 hover:text-red-500 hover:bg-gray-50'
          )}
          title={isFollowed ? 'Unfollow card' : 'Follow card'}
          aria-label={isFollowed ? 'Unfollow card' : 'Follow card'}
        >
          {isFollowed ? (
            <Heart className="h-5 w-5 fill-current" />
          ) : (
            <Heart className="h-5 w-5" />
          )}
        </button>
      </div>

      <p className="text-gray-600 dark:text-gray-400 mb-4 line-clamp-3">{card.summary}</p>

      {/* Scores */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Impact:</span>
          <span className={getScoreColor(card.impact_score)}>{card.impact_score}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Relevance:</span>
          <span className={getScoreColor(card.relevance_score)}>{card.relevance_score}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Velocity:</span>
          <span className={getScoreColor(card.velocity_score)}>{card.velocity_score}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Novelty:</span>
          <span className={getScoreColor(card.novelty_score)}>{card.novelty_score}</span>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
        <Link
          to={`/cards/${card.slug}`}
          className="inline-flex items-center text-sm text-brand-blue hover:text-brand-dark-blue dark:hover:text-brand-light-blue transition-colors"
        >
          <Eye className="h-4 w-4 mr-1" />
          View Details
        </Link>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

const WorkstreamFeed: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuthContext();

  // State
  const [workstream, setWorkstream] = useState<Workstream | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [followedCardIds, setFollowedCardIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [cardsLoading, setCardsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load workstream data
  useEffect(() => {
    if (id) {
      loadWorkstream();
    }
  }, [id]);

  // Load cards when workstream changes
  useEffect(() => {
    if (workstream) {
      loadWorkstreamFeed();
      loadFollowedCards();
    }
  }, [workstream]);

  /**
   * Load workstream details
   */
  const loadWorkstream = async () => {
    try {
      setLoading(true);
      setError(null);

      const { data, error: fetchError } = await supabase
        .from('workstreams')
        .select('*')
        .eq('id', id)
        .single();

      if (fetchError) {
        console.error('Error loading workstream:', fetchError);
        setError('Failed to load workstream. It may not exist or you may not have access.');
        return;
      }

      // Verify ownership
      if (data.user_id !== user?.id) {
        setError('You do not have access to this workstream.');
        return;
      }

      setWorkstream(data);
    } catch (err) {
      console.error('Error loading workstream:', err);
      setError('An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Load cards matching workstream filters
   *
   * This queries cards based on the workstream's filter criteria.
   * In a production environment, this would ideally call an API endpoint
   * like GET /api/v1/me/workstreams/{id}/feed that handles the filtering server-side.
   */
  const loadWorkstreamFeed = async () => {
    if (!workstream) return;

    try {
      setCardsLoading(true);

      let query = supabase
        .from('cards')
        .select('*')
        .eq('status', 'active');

      // Apply pillar filter
      if (workstream.pillar_ids && workstream.pillar_ids.length > 0) {
        query = query.in('pillar_id', workstream.pillar_ids);
      }

      // Apply horizon filter
      if (workstream.horizon && workstream.horizon !== 'ALL') {
        query = query.eq('horizon', workstream.horizon);
      }

      // Apply stage filter
      if (workstream.stage_ids && workstream.stage_ids.length > 0) {
        const stageNumbers = workstream.stage_ids
          .map((s) => parseInt(s, 10))
          .filter((n) => !isNaN(n));
        if (stageNumbers.length > 0) {
          query = query.in('stage_id', stageNumbers);
        }
      }

      // Note: Keyword filtering would ideally be done server-side with full-text search
      // For now, we'll filter client-side if needed
      const { data, error: fetchError } = await query.order('created_at', { ascending: false });

      if (fetchError) {
        console.error('Error loading feed:', fetchError);
        return;
      }

      let filteredCards = data || [];

      // Client-side keyword filtering (if keywords exist)
      if (workstream.keywords && workstream.keywords.length > 0) {
        const lowercaseKeywords = workstream.keywords.map((k) => k.toLowerCase());
        filteredCards = filteredCards.filter((card) => {
          const cardText = `${card.name} ${card.summary}`.toLowerCase();
          return lowercaseKeywords.some((keyword) => cardText.includes(keyword));
        });
      }

      setCards(filteredCards);
    } catch (err) {
      console.error('Error loading feed:', err);
    } finally {
      setCardsLoading(false);
    }
  };

  /**
   * Load user's followed cards
   */
  const loadFollowedCards = async () => {
    if (!user) return;

    try {
      const { data } = await supabase
        .from('card_follows')
        .select('card_id')
        .eq('user_id', user.id);

      if (data) {
        setFollowedCardIds(new Set(data.map((f) => f.card_id)));
      }
    } catch (err) {
      console.error('Error loading followed cards:', err);
    }
  };

  /**
   * Toggle card follow status
   */
  const handleToggleFollow = async (cardId: string, isCurrentlyFollowed: boolean) => {
    if (!user) return;

    try {
      if (isCurrentlyFollowed) {
        // Unfollow
        await supabase
          .from('card_follows')
          .delete()
          .eq('user_id', user.id)
          .eq('card_id', cardId);

        setFollowedCardIds((prev) => {
          const next = new Set(prev);
          next.delete(cardId);
          return next;
        });
      } else {
        // Follow
        await supabase.from('card_follows').insert({
          user_id: user.id,
          card_id: cardId,
          priority: 'medium',
        });

        setFollowedCardIds((prev) => new Set([...prev, cardId]));
      }
    } catch (err) {
      console.error('Error toggling follow:', err);
    }
  };

  /**
   * Refresh feed
   */
  const handleRefresh = () => {
    if (workstream) {
      loadWorkstreamFeed();
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-brand-blue" />
          <p className="text-gray-600 dark:text-gray-400">Loading workstream...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <div className="text-red-500 dark:text-red-400 mb-4">
            <Filter className="mx-auto h-12 w-12" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">Error</h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">{error}</p>
          <Link
            to="/workstreams"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Workstreams
          </Link>
        </div>
      </div>
    );
  }

  // No workstream found
  if (!workstream) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <Filter className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
          <h3 className="mt-2 text-lg font-medium text-gray-900 dark:text-white">Workstream not found</h3>
          <p className="mt-1 text-gray-600 dark:text-gray-400">
            The workstream you're looking for doesn't exist or has been deleted.
          </p>
          <div className="mt-6">
            <Link
              to="/workstreams"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Workstreams
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header Section */}
      <div className="mb-8">
        {/* Back button */}
        <Link
          to="/workstreams"
          className="inline-flex items-center text-sm text-gray-600 dark:text-gray-400 hover:text-brand-blue transition-colors mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Workstreams
        </Link>

        {/* Title and actions */}
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">{workstream.name}</h1>
              <StatusBadge isActive={workstream.is_active} />
            </div>
            {workstream.description && (
              <p className="text-gray-600 dark:text-gray-400 max-w-3xl">{workstream.description}</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-[#3d4176] hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] transition-colors"
              title="Refresh feed"
            >
              <RefreshCw className={cn('h-4 w-4', cardsLoading && 'animate-spin')} />
            </button>
            <Link
              to={`/workstreams/${id}/edit`}
              className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-[#3d4176] hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] transition-colors"
            >
              <Edit className="h-4 w-4 mr-2" />
              Edit
            </Link>
          </div>
        </div>
      </div>

      {/* Filter Display Section */}
      <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 mb-6">
        <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
          Active Filters
        </h2>

        <div className="space-y-4">
          {/* Pillars */}
          {workstream.pillar_ids && workstream.pillar_ids.length > 0 && (
            <div className="flex items-start gap-3">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-20 shrink-0 pt-0.5">
                Pillars:
              </span>
              <PillarBadgeGroup
                pillarIds={workstream.pillar_ids}
                size="sm"
                maxVisible={6}
              />
            </div>
          )}

          {/* Horizon */}
          {workstream.horizon && workstream.horizon !== 'ALL' && (
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-20 shrink-0">
                Horizon:
              </span>
              <HorizonBadge
                horizon={workstream.horizon as 'H1' | 'H2' | 'H3'}
                size="sm"
              />
            </div>
          )}

          {/* Stages */}
          {workstream.stage_ids && workstream.stage_ids.length > 0 && (
            <div className="flex items-start gap-3">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-20 shrink-0 pt-0.5">
                Stages:
              </span>
              <StageRangeDisplay stageIds={workstream.stage_ids} />
            </div>
          )}

          {/* Keywords */}
          {workstream.keywords && workstream.keywords.length > 0 && (
            <div className="flex items-start gap-3">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-20 shrink-0 pt-0.5">
                Keywords:
              </span>
              <div className="flex items-center gap-1.5 flex-wrap">
                {workstream.keywords.map((keyword) => (
                  <KeywordTag key={keyword} keyword={keyword} />
                ))}
              </div>
            </div>
          )}

          {/* No filters */}
          {(!workstream.pillar_ids || workstream.pillar_ids.length === 0) &&
            (!workstream.horizon || workstream.horizon === 'ALL') &&
            (!workstream.stage_ids || workstream.stage_ids.length === 0) &&
            (!workstream.keywords || workstream.keywords.length === 0) && (
              <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                No filters configured. Showing all cards.
              </p>
            )}
        </div>
      </div>

      {/* Cards Grid */}
      {cardsLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-brand-blue" />
            <p className="text-gray-600 dark:text-gray-400">Loading cards...</p>
          </div>
        </div>
      ) : cards.length === 0 ? (
        /* Empty State */
        <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <Filter className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
          <h3 className="mt-2 text-lg font-medium text-gray-900 dark:text-white">No matching cards</h3>
          <p className="mt-1 text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            No intelligence cards currently match this workstream's filters. Try adjusting
            the filter criteria to broaden your results.
          </p>
          <div className="mt-6">
            <Link
              to={`/workstreams/${id}/edit`}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] transition-colors"
            >
              <Edit className="h-4 w-4 mr-2" />
              Adjust Filters
            </Link>
          </div>
        </div>
      ) : (
        <>
          {/* Results count */}
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Showing {cards.length} {cards.length === 1 ? 'card' : 'cards'}
            </p>
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {cards.map((card) => (
              <CardItem
                key={card.id}
                card={card}
                isFollowed={followedCardIds.has(card.id)}
                onToggleFollow={handleToggleFollow}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default WorkstreamFeed;
