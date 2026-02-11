/**
 * PersonalizedQueue Component
 *
 * Displays a personalized discovery queue of intelligence cards ranked
 * by multi-factor scoring (novelty, workstream relevance, pillar alignment,
 * followed card context).
 *
 * Features:
 * - Cards ranked by discovery_score
 * - Score indicator with breakdown tooltip
 * - Dismiss functionality to remove cards
 * - Loading and empty states
 * - Infinite scroll pagination support
 */

import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Eye,
  Heart,
  X,
  Sparkles,
  TrendingUp,
  Target,
  Users,
  Clock,
  RefreshCw,
} from "lucide-react";
import { useAuthContext } from "../hooks/useAuthContext";
import { supabase } from "../App";
import { PillarBadge } from "./PillarBadge";
import { HorizonBadge } from "./HorizonBadge";
import { StageBadge } from "./StageBadge";
import { Top25Badge } from "./Top25Badge";
import { Tooltip } from "./ui/Tooltip";
import { cn } from "../lib/utils";
import { parseStageNumber } from "../lib/stage-utils";
import {
  fetchPersonalizedDiscoveryQueue,
  dismissCard,
  type PersonalizedCard,
  type ScoreBreakdown,
} from "../lib/discovery-api";

export interface PersonalizedQueueProps {
  /** Number of cards to load per page */
  pageSize?: number;
  /** Additional className for container */
  className?: string;
  /** Whether to show the header section */
  showHeader?: boolean;
}

/**
 * Get color and label for discovery score level
 */
function getScoreLevel(score: number): {
  level: "high" | "medium" | "low";
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
} {
  if (score >= 0.7) {
    return {
      level: "high",
      label: "Highly Relevant",
      color: "text-green-600 dark:text-green-400",
      bgColor: "bg-green-100 dark:bg-green-900/30",
      borderColor: "border-green-300 dark:border-green-700",
    };
  }
  if (score >= 0.4) {
    return {
      level: "medium",
      label: "Moderately Relevant",
      color: "text-amber-600 dark:text-amber-400",
      bgColor: "bg-amber-100 dark:bg-amber-900/30",
      borderColor: "border-amber-300 dark:border-amber-700",
    };
  }
  return {
    level: "low",
    label: "Explore",
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-100 dark:bg-blue-900/30",
    borderColor: "border-blue-300 dark:border-blue-700",
  };
}

/**
 * Score breakdown tooltip content
 */
function ScoreBreakdownTooltip({
  score,
  breakdown,
}: {
  score: number;
  breakdown?: ScoreBreakdown;
}) {
  const scoreInfo = getScoreLevel(score);

  const factors = breakdown
    ? [
        {
          label: "Novelty",
          value: breakdown.novelty,
          icon: Clock,
          weight: "25%",
        },
        {
          label: "Workstream Match",
          value: breakdown.workstream_relevance,
          icon: Target,
          weight: "40%",
        },
        {
          label: "Pillar Alignment",
          value: breakdown.pillar_alignment,
          icon: TrendingUp,
          weight: "20%",
        },
        {
          label: "Followed Context",
          value: breakdown.followed_context,
          icon: Users,
          weight: "15%",
        },
      ]
    : null;

  return (
    <div className="space-y-3 min-w-[220px] max-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className={cn("p-1.5 rounded-md", scoreInfo.bgColor)}>
          <Sparkles className={cn("h-4 w-4", scoreInfo.color)} />
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {scoreInfo.label}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Discovery Score: {Math.round(score * 100)}%
          </div>
        </div>
      </div>

      {/* Score bar */}
      <div>
        <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              scoreInfo.level === "high" && "bg-green-500 dark:bg-green-400",
              scoreInfo.level === "medium" && "bg-amber-500 dark:bg-amber-400",
              scoreInfo.level === "low" && "bg-blue-500 dark:bg-blue-400",
            )}
            style={{ width: `${score * 100}%` }}
          />
        </div>
      </div>

      {/* Factor breakdown */}
      {factors && (
        <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
            Score Breakdown
          </div>
          <div className="space-y-1.5">
            {factors.map((factor) => (
              <div
                key={factor.label}
                className="flex items-center gap-2 text-xs"
              >
                <factor.icon className="h-3 w-3 text-gray-400 shrink-0" />
                <span className="text-gray-600 dark:text-gray-300 flex-1">
                  {factor.label}
                </span>
                <span className="text-gray-400 dark:text-gray-500">
                  {factor.weight}
                </span>
                <span
                  className={cn(
                    "font-medium w-8 text-right",
                    factor.value >= 0.7
                      ? "text-green-600 dark:text-green-400"
                      : factor.value >= 0.4
                        ? "text-amber-600 dark:text-amber-400"
                        : "text-gray-500 dark:text-gray-400",
                  )}
                >
                  {Math.round(factor.value * 100)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Explanation */}
      <p className="text-[10px] text-gray-400 dark:text-gray-500 pt-1">
        Based on your workstreams, followed cards, and card novelty
      </p>
    </div>
  );
}

/**
 * Discovery score indicator badge
 */
function DiscoveryScoreIndicator({
  score,
  breakdown,
  size = "md",
}: {
  score: number;
  breakdown?: ScoreBreakdown;
  size?: "sm" | "md";
}) {
  const scoreInfo = getScoreLevel(score);

  const sizeClasses =
    size === "sm" ? "px-1.5 py-0.5 text-xs gap-1" : "px-2 py-1 text-sm gap-1.5";

  const iconSize = size === "sm" ? 12 : 14;

  return (
    <Tooltip
      content={<ScoreBreakdownTooltip score={score} breakdown={breakdown} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      <span
        className={cn(
          "inline-flex items-center rounded-full font-medium border cursor-pointer",
          scoreInfo.bgColor,
          scoreInfo.color,
          scoreInfo.borderColor,
          sizeClasses,
        )}
        role="status"
        aria-label={`Discovery score: ${Math.round(score * 100)}%`}
      >
        <Sparkles className="shrink-0" size={iconSize} />
        <span>{Math.round(score * 100)}</span>
      </span>
    </Tooltip>
  );
}

/**
 * PersonalizedQueue component
 */
export function PersonalizedQueue({
  pageSize = 20,
  className,
  showHeader = true,
}: PersonalizedQueueProps) {
  const { user } = useAuthContext();
  const [cards, setCards] = useState<PersonalizedCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [followedCardIds, setFollowedCardIds] = useState<Set<string>>(
    new Set(),
  );
  const [dismissingCardId, setDismissingCardId] = useState<string | null>(null);

  // Load followed cards for the heart icon state
  const loadFollowedCards = useCallback(async () => {
    if (!user?.id) return;
    try {
      const { data } = await supabase
        .from("card_follows")
        .select("card_id")
        .eq("user_id", user.id);

      if (data) {
        setFollowedCardIds(new Set(data.map((f) => f.card_id)));
      }
    } catch (_err) {
      // Silent fail for followed cards - non-critical
    }
  }, [user?.id]);

  // Load personalized queue
  const loadQueue = useCallback(
    async (isLoadMore = false) => {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        setError("Please sign in to view your personalized queue");
        setLoading(false);
        return;
      }

      try {
        if (isLoadMore) {
          setLoadingMore(true);
        } else {
          setLoading(true);
          setError(null);
        }

        const currentOffset = isLoadMore ? offset : 0;
        const data = await fetchPersonalizedDiscoveryQueue(
          session.access_token,
          pageSize,
          currentOffset,
        );

        if (isLoadMore) {
          setCards((prev) => [...prev, ...data]);
        } else {
          setCards(data);
        }

        setHasMore(data.length === pageSize);
        setOffset(currentOffset + data.length);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load personalized queue",
        );
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [offset, pageSize],
  );

  // Initial load
  useEffect(() => {
    loadQueue();
    loadFollowedCards();
  }, [user?.id]);

  // Handle refresh
  const handleRefresh = () => {
    setOffset(0);
    loadQueue(false);
  };

  // Handle load more
  const handleLoadMore = () => {
    if (!loadingMore && hasMore) {
      loadQueue(true);
    }
  };

  // Handle card dismissal
  const handleDismiss = async (cardId: string) => {
    if (dismissingCardId) return;

    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) return;

    setDismissingCardId(cardId);

    // Optimistic update - remove card immediately
    setCards((prev) => prev.filter((c) => c.id !== cardId));

    try {
      await dismissCard(session.access_token, cardId, "irrelevant");
    } catch (_err) {
      // Revert on error by reloading
      setOffset(0);
      loadQueue(false);
    } finally {
      setDismissingCardId(null);
    }
  };

  // Toggle follow card
  const toggleFollowCard = async (cardId: string) => {
    if (!user?.id) return;

    const isFollowing = followedCardIds.has(cardId);

    // Optimistic update
    setFollowedCardIds((prev) => {
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
        await supabase
          .from("card_follows")
          .delete()
          .eq("user_id", user.id)
          .eq("card_id", cardId);
      } else {
        await supabase.from("card_follows").insert({
          user_id: user.id,
          card_id: cardId,
          priority: "medium",
        });
      }
    } catch (_err) {
      // Revert optimistic update on error
      setFollowedCardIds((prev) => {
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

  // Loading state
  if (loading) {
    return (
      <div className={cn("", className)}>
        {showHeader && (
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-brand-blue" />
              For You
            </h2>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Personalized intelligence based on your workstreams and interests
            </p>
          </div>
        )}
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue"></div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={cn("", className)}>
        {showHeader && (
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-brand-blue" />
              For You
            </h2>
          </div>
        )}
        <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-lg shadow">
          <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-blue text-white rounded-lg hover:bg-brand-dark-blue transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (cards.length === 0) {
    return (
      <div className={cn("", className)}>
        {showHeader && (
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-brand-blue" />
              For You
            </h2>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Personalized intelligence based on your workstreams and interests
            </p>
          </div>
        )}
        <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-lg shadow">
          <Sparkles className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
            All caught up!
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 max-w-sm mx-auto">
            You've reviewed all personalized recommendations. Check back later
            for new discoveries, or explore all cards to find more.
          </p>
          <div className="mt-6">
            <Link
              to="/discover"
              className="inline-flex items-center gap-2 px-4 py-2 bg-brand-blue text-white rounded-lg hover:bg-brand-dark-blue transition-colors"
            >
              <Eye className="h-4 w-4" />
              Explore All Cards
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("", className)}>
      {/* Header */}
      {showHeader && (
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-brand-blue" />
              For You
            </h2>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              {cards.length} personalized recommendation
              {cards.length !== 1 ? "s" : ""} based on your interests
            </p>
          </div>
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-brand-blue dark:hover:text-brand-blue transition-colors"
            title="Refresh recommendations"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>
      )}

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {cards.map((card) => {
          const stageNumber = parseStageNumber(card.stage_id);

          return (
            <div
              key={card.id}
              className="bg-white dark:bg-dark-surface rounded-lg shadow p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue relative group"
            >
              {/* Dismiss button */}
              <button
                onClick={() => handleDismiss(card.id)}
                disabled={dismissingCardId === card.id}
                className="absolute top-2 right-2 p-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                title="Dismiss this signal"
                aria-label="Dismiss signal"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="flex items-start justify-between mb-4">
                <div className="flex-1 pr-6">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                    <Link
                      to={`/signals/${card.slug}`}
                      className="hover:text-brand-blue transition-colors"
                    >
                      {card.name}
                    </Link>
                  </h3>
                  <div className="flex items-center gap-2 flex-wrap mb-3">
                    <DiscoveryScoreIndicator
                      score={card.discovery_score}
                      breakdown={card.score_breakdown}
                      size="sm"
                    />
                    <PillarBadge pillarId={card.pillar_id} showIcon size="sm" />
                    <HorizonBadge horizon={card.horizon} size="sm" />
                    {stageNumber !== null && (
                      <StageBadge
                        stage={stageNumber}
                        size="sm"
                        variant="minimal"
                      />
                    )}
                    {card.top25_relevance &&
                      card.top25_relevance.length > 0 && (
                        <Top25Badge
                          priorities={card.top25_relevance}
                          size="sm"
                          showCount
                        />
                      )}
                  </div>
                </div>
                <button
                  onClick={() => toggleFollowCard(card.id)}
                  className={cn(
                    "flex-shrink-0 p-2 transition-colors",
                    followedCardIds.has(card.id)
                      ? "text-red-500 hover:text-red-600"
                      : "text-gray-400 hover:text-red-500",
                  )}
                  title={
                    followedCardIds.has(card.id)
                      ? "Unfollow signal"
                      : "Follow signal"
                  }
                  aria-pressed={followedCardIds.has(card.id)}
                >
                  <Heart
                    className="h-5 w-5"
                    fill={
                      followedCardIds.has(card.id) ? "currentColor" : "none"
                    }
                  />
                </button>
              </div>

              <p className="text-gray-600 dark:text-gray-400 mb-4 line-clamp-3">
                {card.summary}
              </p>

              <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                <Link
                  to={`/signals/${card.slug}`}
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

      {/* Load more button */}
      {hasMore && (
        <div className="mt-8 text-center">
          <button
            onClick={handleLoadMore}
            disabled={loadingMore}
            className="inline-flex items-center gap-2 px-6 py-2 bg-white dark:bg-dark-surface text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
          >
            {loadingMore ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600 dark:border-gray-300"></div>
                Loading...
              </>
            ) : (
              <>Load More</>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

export default PersonalizedQueue;
