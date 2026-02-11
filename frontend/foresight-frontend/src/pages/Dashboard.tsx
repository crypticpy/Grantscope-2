import React, { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import {
  Calendar,
  TrendingUp,
  Eye,
  Plus,
  Filter,
  Star,
  Sparkles,
  ArrowRight,
  RefreshCw,
  BookOpen,
} from "lucide-react";
import { supabase } from "../App";
import { useAuthContext } from "../hooks/useAuthContext";
import { PillarBadge } from "../components/PillarBadge";
import { HorizonBadge } from "../components/HorizonBadge";
import { StageBadge } from "../components/StageBadge";
import { Top25Badge } from "../components/Top25Badge";
import { QualityBadge } from "../components/QualityBadge";
import { fetchPendingCount } from "../lib/discovery-api";
import { parseStageNumber } from "../lib/stage-utils";
import { logger } from "../lib/logger";
import type { BaseCard } from "../types/card";

type Card = BaseCard;

interface FollowingCard {
  id: string;
  priority: string;
  cards: Card;
}

/**
 * Explicit type for rows returned by the Supabase join query
 * `card_follows.select("id, priority, cards (*)")`.
 *
 * `cards` may be `null` when the related card has been deleted or the
 * join yields no match, so consumers must guard before accessing fields.
 */
interface SupabaseFollowRow {
  id: string;
  priority: string;
  cards: Card | null;
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

/** Extract a numeric count from a Supabase head-only response, defaulting to 0 on error. */
function safeCount(r: { error: unknown; count: number | null }): number {
  return r.error ? 0 : (r.count ?? 0);
}

/**
 * Animates a number from 0 to the target value over the given duration (ms)
 * using requestAnimationFrame for smooth 60fps rendering.
 */
function useCountUp(target: number, duration = 500): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    if (target === 0) {
      setValue(0);
      return;
    }
    const start = performance.now();
    const animate = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      // Use ease-out curve for a more natural feel
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration]);

  return value;
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
    workstreams: 0,
    updatedThisWeek: 0,
  });
  const [qualityDistribution, setQualityDistribution] = useState({
    high: 0,
    moderate: 0,
    low: 0,
  });

  // Animated stat card values
  const animatedTotalCards = useCountUp(stats.totalCards);
  const animatedNewThisWeek = useCountUp(stats.newThisWeek);
  const animatedFollowing = useCountUp(stats.following);
  const animatedWorkstreams = useCountUp(stats.workstreams);
  const animatedUpdatedThisWeek = useCountUp(stats.updatedThisWeek);

  useEffect(() => {
    loadDashboardData();
    loadPendingCount();
  }, []);

  const loadPendingCount = async () => {
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session?.access_token) {
        const count = await fetchPendingCount(session.access_token);
        setPendingReviewCount(count);
      }
    } catch (err) {
      // Silently fail - non-critical
      logger.debug("Could not fetch pending count:", err);
    }
  };

  const loadDashboardData = async () => {
    try {
      const oneWeekAgo = new Date();
      oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);

      const [
        recentCardsResult,
        followingCardsResult,
        statsResult,
        updatedResult,
        qualityHighResult,
        qualityModResult,
        qualityLowResult,
      ] = await Promise.all([
        // Recent cards
        supabase
          .from("cards")
          .select("*")
          .eq("status", "active")
          .order("created_at", { ascending: false })
          .limit(6),

        // Following cards (join)
        supabase
          .from("card_follows")
          .select(`id, priority, cards (*)`)
          .eq("user_id", user?.id),

        // Dashboard stats via RPC
        supabase.rpc("get_dashboard_stats", { p_user_id: user?.id }),

        // Updated this week
        supabase
          .from("cards")
          .select("id", { count: "exact", head: true })
          .eq("status", "active")
          .gte("updated_at", oneWeekAgo.toISOString()),

        // Quality distribution buckets (high ≥75 / moderate 50-74 / low <50)
        supabase
          .from("cards")
          .select("id", { count: "exact", head: true })
          .eq("status", "active")
          .gte("signal_quality_score", 75),
        supabase
          .from("cards")
          .select("id", { count: "exact", head: true })
          .eq("status", "active")
          .gte("signal_quality_score", 50)
          .lt("signal_quality_score", 75),
        supabase
          .from("cards")
          .select("id", { count: "exact", head: true })
          .eq("status", "active")
          .or("signal_quality_score.lt.50,signal_quality_score.is.null"),
      ]);

      // Log errors for debugging (non-blocking)
      if (recentCardsResult.error) {
        console.error("Error loading recent cards:", recentCardsResult.error);
      }
      if (followingCardsResult.error) {
        console.error(
          "Error loading following cards:",
          followingCardsResult.error,
        );
      }
      if (statsResult.error) {
        console.error("Error loading dashboard stats:", statsResult.error);
      }

      // --- Recent cards ---
      setRecentCards(
        recentCardsResult.error ? [] : (recentCardsResult.data ?? []),
      );

      // --- Following cards ---
      // Supabase infers `cards (*)` as `any[]`, but the actual runtime shape
      // is a single Card object (or null when the join has no match).
      // We cast through `unknown` to our explicit SupabaseFollowRow type,
      // then filter out rows where the related card was deleted.
      const rawFollowing: SupabaseFollowRow[] = followingCardsResult.error
        ? []
        : ((followingCardsResult.data ?? []) as unknown as SupabaseFollowRow[]);

      const transformedFollowing: FollowingCard[] = rawFollowing
        .filter(
          (row): row is SupabaseFollowRow & { cards: Card } =>
            row.cards !== null,
        )
        .map((row) => ({
          id: row.id,
          priority: row.priority,
          cards: row.cards,
        }));
      setFollowingCards(transformedFollowing);

      // --- Stats ---
      const statsData: DashboardStatsResponse | null = statsResult.error
        ? null
        : statsResult.data;

      setStats({
        totalCards: statsData?.total_cards ?? 0,
        newThisWeek: statsData?.new_this_week ?? 0,
        following: statsData?.following ?? 0,
        workstreams: statsData?.workstreams ?? 0,
        updatedThisWeek: safeCount(updatedResult),
      });

      // --- Quality distribution ---
      setQualityDistribution({
        high: safeCount(qualityHighResult),
        moderate: safeCount(qualityModResult),
        low: safeCount(qualityLowResult),
      });
    } catch (error) {
      console.error("Error loading dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      high: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
      medium:
        "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
      low: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
    };
    return (
      colors[priority] ||
      "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
    );
  };

  const getPriorityBorder = (priority: string) => {
    const borders: Record<string, string> = {
      high: "border-l-red-500",
      medium: "border-l-amber-500",
      low: "border-l-emerald-500",
    };
    return borders[priority] || "border-l-gray-300";
  };

  const getPriorityGradient = (priority: string) => {
    const gradients: Record<string, string> = {
      high: "from-red-50 dark:from-red-900/10",
      medium: "from-amber-50 dark:from-amber-900/10",
      low: "from-emerald-50 dark:from-emerald-900/10",
    };
    return gradients[priority] || "from-gray-50 dark:from-gray-800/50";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue mx-auto"></div>
          <p className="mt-4 text-gray-500 dark:text-gray-400">
            Loading dashboard...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">
          Welcome back, {user?.email?.split("@")[0]}
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
                    {pendingReviewCount} New Discovery
                    {pendingReviewCount !== 1 ? "ies" : ""} Pending Review
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    AI has found new intelligence signals. Review and approve
                    them to add to your library.
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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
        <Link
          to="/discover"
          aria-label={`Total Signals: ${stats.totalCards}`}
          className="bg-white dark:bg-dark-surface rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Eye className="h-8 w-8 text-brand-blue group-hover:scale-110 transition-transform" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                Total Signals
              </p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                {animatedTotalCards}
              </p>
            </div>
          </div>
        </Link>

        <Link
          to="/discover?filter=new"
          aria-label={`New This Week: ${stats.newThisWeek}`}
          className="bg-white dark:bg-dark-surface rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <TrendingUp className="h-8 w-8 text-brand-green group-hover:scale-110 transition-transform" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                New This Week
              </p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                {animatedNewThisWeek}
              </p>
            </div>
          </div>
        </Link>

        <Link
          to="/discover?filter=following"
          aria-label={`Following: ${stats.following}`}
          className="bg-white dark:bg-dark-surface rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Calendar className="h-8 w-8 text-extended-purple group-hover:scale-110 transition-transform" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                Following
              </p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                {animatedFollowing}
              </p>
            </div>
          </div>
        </Link>

        <Link
          to="/workstreams"
          aria-label={`Workstreams: ${stats.workstreams}`}
          className="bg-white dark:bg-dark-surface rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Filter className="h-8 w-8 text-extended-orange group-hover:scale-110 transition-transform" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                Workstreams
              </p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                {animatedWorkstreams}
              </p>
            </div>
          </div>
        </Link>

        <Link
          to="/discover?filter=updated"
          aria-label={`Updated This Week: ${stats.updatedThisWeek}`}
          className="bg-white dark:bg-dark-surface rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <RefreshCw className="h-8 w-8 text-amber-500 group-hover:scale-110 transition-transform" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                Updated This Week
              </p>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                {animatedUpdatedThisWeek}
              </p>
            </div>
          </div>
        </Link>
      </div>

      {/* Quality Distribution & Methodology Link */}
      <div className="flex items-center justify-between mb-8">
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400"
        >
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            {qualityDistribution.high} High
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
            {qualityDistribution.moderate} Moderate
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500"></span>
            {qualityDistribution.low} Needs Verification
          </span>
        </div>
        <Link
          to="/methodology"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-brand-blue dark:hover:text-brand-blue transition-colors"
        >
          <BookOpen className="h-4 w-4" />
          How does Foresight work?
        </Link>
      </div>

      {/* Following Cards */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Your Followed Signals
          </h2>
        </div>
        {followingCards.length > 0 ? (
          <div className="grid gap-4">
            {followingCards.slice(0, 3).map((following, index) => {
              const stageNum = parseStageNumber(following.cards.stage_id);
              return (
                <div
                  key={following.id}
                  style={{
                    animationDelay: `${Math.min(index, 5) * 50}ms`,
                    animationFillMode: "both",
                  }}
                  className={`animate-in fade-in slide-in-from-bottom-2 duration-300 bg-gradient-to-r ${getPriorityGradient(following.priority)} to-white dark:to-[#2d3166] rounded-lg shadow p-6 border-l-4 ${getPriorityBorder(following.priority)} transition-all duration-200 hover:-translate-y-1 hover:shadow-lg`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <Star className="h-4 w-4 text-amber-500 fill-amber-500 flex-shrink-0" />
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                          <Link
                            to={`/signals/${following.cards.slug}`}
                            state={{ from: "/" }}
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
                        {following.cards.top25_relevance &&
                          following.cards.top25_relevance.length > 0 && (
                            <Top25Badge
                              priorities={following.cards.top25_relevance}
                              size="sm"
                              showCount={true}
                            />
                          )}
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getPriorityColor(following.priority)}`}
                        >
                          {following.priority}
                        </span>
                      </div>
                      <p className="text-gray-600 dark:text-gray-300 mb-3">
                        {following.cards.summary}
                      </p>
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
          <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-lg shadow">
            <Star className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
              Start Following Signals
            </h3>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
              Follow signals to build your personalized intelligence feed.
              <br />
              <span className="text-gray-400">
                Browse the Discover page and click the heart icon on any signal
                to start following it.
              </span>
            </p>
            <div className="mt-6">
              <Link
                to="/discover"
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
              >
                <Eye className="h-4 w-4 mr-2" />
                Explore Signals
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
          {recentCards.map((card, index) => {
            const stageNum = parseStageNumber(card.stage_id);
            return (
              <div
                key={card.id}
                style={{
                  animationDelay: `${Math.min(index, 5) * 50}ms`,
                  animationFillMode: "both",
                }}
                className="animate-in fade-in slide-in-from-bottom-2 duration-300 bg-white dark:bg-dark-surface rounded-lg shadow p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                        <Link
                          to={`/signals/${card.slug}`}
                          state={{ from: "/" }}
                          className="hover:text-brand-blue transition-colors"
                        >
                          {card.name}
                        </Link>
                      </h3>
                      <QualityBadge
                        score={card.signal_quality_score}
                        size="sm"
                      />
                      <PillarBadge
                        pillarId={card.pillar_id}
                        showIcon={true}
                        size="sm"
                      />
                      <HorizonBadge horizon={card.horizon} size="sm" />
                      {stageNum && (
                        <StageBadge
                          stage={stageNum}
                          size="sm"
                          showName={false}
                          variant="minimal"
                        />
                      )}
                      {card.top25_relevance &&
                        card.top25_relevance.length > 0 && (
                          <Top25Badge
                            priorities={card.top25_relevance}
                            size="sm"
                            showCount={true}
                          />
                        )}
                    </div>
                    <p className="text-gray-600 dark:text-gray-300 mb-3">
                      {card.summary}
                    </p>
                    <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                      <span>Impact: {card.impact_score}/100</span>
                      <span>Relevance: {card.relevance_score}/100</span>
                      <span>Velocity: {card.velocity_score}/100</span>
                    </div>
                  </div>
                  <div className="ml-4 flex-shrink-0">
                    <Link
                      to={`/signals/${card.slug}`}
                      state={{ from: "/" }}
                      className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 dark:text-gray-200 bg-white dark:bg-dark-surface-elevated hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue transition-colors"
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
