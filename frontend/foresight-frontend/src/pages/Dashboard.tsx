import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Calendar, TrendingUp, Eye, Plus, Filter } from 'lucide-react';
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
  created_at: string;
  top25_relevance?: string[];
}

interface FollowingCard {
  id: string;
  priority: string;
  cards: Card;
}

const Dashboard: React.FC = () => {
  const { user } = useAuthContext();
  const [recentCards, setRecentCards] = useState<Card[]>([]);
  const [followingCards, setFollowingCards] = useState<FollowingCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalCards: 0,
    newThisWeek: 0,
    following: 0,
    workstreams: 0
  });

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      // Load recent cards
      const { data: recentData } = await supabase
        .from('cards')
        .select('*')
        .eq('status', 'active')
        .order('created_at', { ascending: false })
        .limit(6);

      // Load following cards
      const { data: followingData } = await supabase
        .from('card_follows')
        .select(`
          id,
          priority,
          cards (*)
        `)
        .eq('user_id', user?.id);

      // Load stats - use count properly from Supabase response
      const { count: totalCardsCount } = await supabase
        .from('cards')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'active');

      const { count: workstreamCountNum } = await supabase
        .from('workstreams')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', user?.id);

      const oneWeekAgo = new Date();
      oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);

      const { count: newThisWeekCount } = await supabase
        .from('cards')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'active')
        .gte('created_at', oneWeekAgo.toISOString());

      setRecentCards(recentData || []);
      setFollowingCards(followingData || []);
      setStats({
        totalCards: totalCardsCount || 0,
        newThisWeek: newThisWeekCount || 0,
        following: followingData?.length || 0,
        workstreams: workstreamCountNum || 0
      });
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      'high': 'bg-red-100 text-red-800',
      'medium': 'bg-yellow-100 text-yellow-800',
      'low': 'bg-green-100 text-green-800'
    };
    return colors[priority] || 'bg-gray-100 text-gray-800';
  };

  // Helper to parse stage_id to number
  const parseStageNumber = (stageId: string): number | null => {
    const num = parseInt(stageId, 10);
    return isNaN(num) ? null : num;
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

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Eye className="h-8 w-8 text-brand-blue" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Cards</p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.totalCards}</p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <TrendingUp className="h-8 w-8 text-brand-green" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">New This Week</p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.newThisWeek}</p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Calendar className="h-8 w-8 text-extended-purple" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Following</p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.following}</p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Filter className="h-8 w-8 text-extended-orange" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Workstreams</p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.workstreams}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Following Cards */}
      {followingCards.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Your Followed Cards
          </h2>
          <div className="grid gap-4">
            {followingCards.slice(0, 3).map((following) => {
              const stageNum = parseStageNumber(following.cards.stage_id);
              return (
                <div key={following.id} className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
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
                        <span>Impact: {following.cards.impact_score}/100</span>
                        <span>Relevance: {following.cards.relevance_score}/100</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

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
