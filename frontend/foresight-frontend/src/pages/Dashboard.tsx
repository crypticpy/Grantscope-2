import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Calendar, TrendingUp, Eye, Plus, Filter, Star, Sparkles, ArrowRight } from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { PillarBadge } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge } from '../components/StageBadge';
import { Top25Badge } from '../components/Top25Badge';
import { fetchPendingCount } from '../lib/discovery-api';
import { parseStageNumber } from '../lib/stage-utils';
import { logger } from '../lib/logger';

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
  created_at: string;
  top25_relevance?: string[];
}

interface FollowingCard {
  id: string;
  priority: string;
  cards: Card;
}

/**
 * TypeScript interface for the get_dashboard_stats RPC response.
 * This interface ensures type safety when calling the Supabase RPC function
 * that consolidates dashboard statistics into a single database call.
 */
interface DashboardStatsResponse {
  total_cards: number;
  new_this_week: number;
  following: number;
  workstreams: number;
}

const Dashboard: React.FC = () => {
  const { user } = useAuthContext();
  const [recentCards, setRecentCards] = useState<Card[]>([]);
  const [followingCards, setFollowingCards] = useState<FollowingCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingReviewCount, setPendingReviewCount] = useState(0);
  const [stats, setStats] = useState({
    totalCards: 0,
    newThisWeek: 0,
    following: 0,
    workstreams: 0
  });

  useEffect(() => {
    loadDashboardData();
    loadPendingCount();
  }, []);

  const loadPendingCount = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        const count = await fetchPendingCount(session.access_token);
        setPendingReviewCount(count);
      }
    } catch (err) {
      // Silently fail - non-critical
      logger.debug('Could not fetch pending count:', err);
    }
  };

  const loadDashboardData = async () => {
    try {
      // Parallelize all dashboard queries using Promise.all
      // This reduces 5 sequential network calls to 3 parallel calls
      const [recentCardsResult, followingCardsResult, statsResult] = await Promise.all([
        // Query 1: Load recent cards
        supabase
          .from('cards')
          .select('*')
          .eq('status', 'active')
          .order('created_at', { ascending: false })
          .limit(6),

        // Query 2: Load following cards
        supabase
          .from('card_follows')
          .select(`
            id,
            priority,
            cards (*)
          `)
          .eq('user_id', user?.id),

        // Query 3: Load dashboard stats via RPC (replaces 4 separate count queries)
        supabase.rpc('get_dashboard_stats', { p_user_id: user?.id })
      ]);

      // Extract data from results, handling potential errors for each query
      const recentData = recentCardsResult.error
        ? []
        : recentCardsResult.data;

      const followingData = followingCardsResult.error
        ? []
        : followingCardsResult.data;

      // Type the stats response and handle potential errors
      const statsData: DashboardStatsResponse | null = statsResult.error
        ? null
        : statsResult.data;

      // Log any errors for debugging (non-blocking)
      if (recentCardsResult.error) {
        console.error('Error loading recent cards:', recentCardsResult.error);
      }
      if (followingCardsResult.error) {
        console.error('Error loading following cards:', followingCardsResult.error);
      }
      if (statsResult.error) {
        console.error('Error loading dashboard stats:', statsResult.error);
      }

      setRecentCards(recentData || []);
      // Transform Supabase nested response to match our interface
      interface SupabaseFollowRow {
        id: string;
        priority: string;
        cards: Card;
      }
      const transformedFollowing = (followingData || []).map((item: SupabaseFollowRow) => ({
        id: item.id,
        priority: item.priority,
        cards: item.cards
      }));
      setFollowingCards(transformedFollowing);

      // Set stats from RPC response or use fallback values
      setStats({
        totalCards: statsData?.total_cards ?? 0,
        newThisWeek: statsData?.new_this_week ?? 0,
        following: statsData?.following ?? 0,
        workstreams: statsData?.workstreams ?? 0
      });
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      'high': 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
      'medium': 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
      'low': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300'
    };
    return colors[priority] || 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
  };

  const getPriorityBorder = (priority: string) => {
    const borders: Record<string, string> = {
      'high': 'border-l-red-500',
      'medium': 'border-l-amber-500',
      'low': 'border-l-emerald-500'
    };
    return borders[priority] || 'border-l-gray-300';
  };

  const getPriorityGradient = (priority: string) => {
    const gradients: Record<string, string> = {
      'high': 'from-red-50 dark:from-red-900/10',
      'medium': 'from-amber-50 dark:from-amber-900/10',
      'low': 'from-emerald-50 dark:from-emerald-900/10'
    };
    return gradients[priority] || 'from-gray-50 dark:from-gray-800/50';
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-brand-blue"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">
          Welcome back, {user?.email?.split('@')[0]}
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Here's what's happening in your strategic intelligence feed.
        </p>
      </div>

      {/* Pending Review Alert */}
      {pendingReviewCount > 0 && (
        <div className="mb-8">
          <Link
            to="/discover/queue"
            className="block bg-gradient-to-r from-brand-blue/10 to-brand-green/10 dark:from-brand-blue/20 dark:to-brand-green/20 border border-brand-blue/20 dark:border-brand-blue/30 rounded-lg p-4 hover:from-brand-blue/15 hover:to-brand-green/15 dark:hover:from-brand-blue/25 dark:hover:to-brand-green/25 transition-all group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 p-2 bg-brand-blue/20 dark:bg-brand-blue/30 rounded-full">
                  <Sparkles className="h-5 w-5 text-brand-blue" />
                </div>
                <div>
                  <h3 className="font-semibold text-brand-dark-blue dark:text-white">
                    {pendingReviewCount} New Discovery{pendingReviewCount !== 1 ? 'ies' : ''} Pending Review
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    AI has found new intelligence cards. Review and approve them to add to your library.
                  </p>
                </div>
              </div>
              <div className="flex-shrink-0 flex items-center gap-1 text-brand-blue group-hover:translate-x-1 transition-transform">
                <span className="text-sm font-medium">Review Now</span>
                <ArrowRight className="h-4 w-4" />
              </div>
            </div>
          </Link>
        </div>
      )}

      {/* Stats Cards - Clickable KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <Link
          to="/discover"
          className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg cursor-pointer group"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Eye className="h-8 w-8 text-brand-blue group-hover:scale-110 transition-transform" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Cards</p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.totalCards}</p>
            </div>
          </div>
        </Link>

        <Link
          to="/discover?filter=new"
          className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg cursor-pointer group"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <TrendingUp className="h-8 w-8 text-brand-green group-hover:scale-110 transition-transform" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">New This Week</p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.newThisWeek}</p>
            </div>
          </div>
        </Link>

        <Link
          to="/discover?filter=following"
          className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg cursor-pointer group"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Calendar className="h-8 w-8 text-extended-purple group-hover:scale-110 transition-transform" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Following</p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.following}</p>
            </div>
          </div>
        </Link>

        <Link
          to="/workstreams"
          className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg cursor-pointer group"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Filter className="h-8 w-8 text-extended-orange group-hover:scale-110 transition-transform" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Workstreams</p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.workstreams}</p>
            </div>
          </div>
        </Link>
      </div>

      {/* Following Cards */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Your Followed Cards
          </h2>
        </div>
        {followingCards.length > 0 ? (
          <div className="grid gap-4">
            {followingCards.slice(0, 3).map((following) => {
              const stageNum = parseStageNumber(following.cards.stage_id);
              return (
                <div
                  key={following.id}
                  className={`bg-gradient-to-r ${getPriorityGradient(following.priority)} to-white dark:to-[#2d3166] rounded-lg shadow p-6 border-l-4 ${getPriorityBorder(following.priority)} transition-all duration-200 hover:-translate-y-1 hover:shadow-lg`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <Star className="h-4 w-4 text-amber-500 fill-amber-500 flex-shrink-0" />
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                          <Link
                            to={`/cards/${following.cards.slug}`}
                            className="hover:text-brand-blue transition-colors"
                          >
                            {following.cards.name}
                          </Link>
                        </h3>
                        <PillarBadge
                          pillarId={following.cards.pillar_id}
                          showIcon={true}
                          size="sm"
                        />
                        <HorizonBadge
                          horizon={following.cards.horizon}
                          size="sm"
                        />
                        {stageNum && (
                          <StageBadge
                            stage={stageNum}
                            size="sm"
                            showName={false}
                            variant="minimal"
                          />
                        )}
                        {following.cards.top25_relevance && following.cards.top25_relevance.length > 0 && (
                          <Top25Badge
                            priorities={following.cards.top25_relevance}
                            size="sm"
                            showCount={true}
                          />
                        )}
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getPriorityColor(following.priority)}`}>
                          {following.priority}
                        </span>
                      </div>
                      <p className="text-gray-600 dark:text-gray-300 mb-3">{following.cards.summary}</p>
                      <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-brand-blue"></span>
                          Impact: {following.cards.impact_score}/100
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-extended-purple"></span>
                          Relevance: {following.cards.relevance_score}/100
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
            <Star className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
              Start Following Cards
            </h3>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
              Follow cards to build your personalized intelligence feed.
              <br />
              <span className="text-gray-400">Browse the Discover page and click the heart icon on any card to start following it.</span>
            </p>
            <div className="mt-6">
              <Link
                to="/discover"
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
              >
                <Eye className="h-4 w-4 mr-2" />
                Explore Cards
                <ArrowRight className="h-4 w-4 ml-2" />
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* Recent Cards */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Recent Intelligence
          </h2>
          <Link
            to="/discover"
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-brand-blue bg-brand-light-blue hover:bg-brand-blue hover:text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue transition-colors"
          >
            <Plus className="h-4 w-4 mr-1" />
            View All
          </Link>
        </div>
        <div className="grid gap-4">
          {recentCards.map((card) => {
            const stageNum = parseStageNumber(card.stage_id);
            return (
              <div key={card.id} className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                        <Link
                          to={`/cards/${card.slug}`}
                          className="hover:text-brand-blue transition-colors"
                        >
                          {card.name}
                        </Link>
                      </h3>
                      <PillarBadge
                        pillarId={card.pillar_id}
                        showIcon={true}
                        size="sm"
                      />
                      <HorizonBadge
                        horizon={card.horizon}
                        size="sm"
                      />
                      {stageNum && (
                        <StageBadge
                          stage={stageNum}
                          size="sm"
                          showName={false}
                          variant="minimal"
                        />
                      )}
                      {card.top25_relevance && card.top25_relevance.length > 0 && (
                        <Top25Badge
                          priorities={card.top25_relevance}
                          size="sm"
                          showCount={true}
                        />
                      )}
                    </div>
                    <p className="text-gray-600 dark:text-gray-300 mb-3">{card.summary}</p>
                    <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                      <span>Impact: {card.impact_score}/100</span>
                      <span>Relevance: {card.relevance_score}/100</span>
                      <span>Velocity: {card.velocity_score}/100</span>
                    </div>
                  </div>
                  <div className="ml-4 flex-shrink-0">
                    <Link
                      to={`/cards/${card.slug}`}
                      className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 dark:text-gray-200 bg-white dark:bg-[#3d4176] hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue transition-colors"
                    >
                      View Details
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
