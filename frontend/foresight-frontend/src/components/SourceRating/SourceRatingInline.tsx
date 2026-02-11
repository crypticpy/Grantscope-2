/**
 * SourceRatingInline Component
 *
 * A composite inline widget that combines StarRating, RelevanceSelector,
 * an optional comment input, and aggregate team rating stats. Handles
 * loading ratings on mount, submitting changes with optimistic UI, and
 * displaying a divergence indicator when AI and human scores disagree.
 *
 * Features:
 * - Fetches current user's rating and aggregate stats on mount
 * - Optimistic UI: immediately reflects user changes before API confirmation
 * - Debounced comment submission to avoid excessive API calls
 * - Shows aggregate team stats via RatingAggregate
 * - Divergence indicator when AI score and human average differ by >30 points
 * - Loading and error states
 * - Dark mode support
 *
 * @module SourceRating/SourceRatingInline
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { cn } from "../../lib/utils";
import { StarRating } from "./StarRating";
import { RelevanceSelector } from "./RelevanceSelector";
import { RatingAggregate } from "./RatingAggregate";
import {
  rateSource,
  getSourceRatings,
  type SourceRatingAggregate,
} from "../../lib/source-rating-api";

/**
 * Props for the SourceRatingInline component
 */
export interface SourceRatingInlineProps {
  /** The ID of the source to rate */
  sourceId: string;
  /** Bearer token for authenticated API calls */
  token: string;
  /**
   * Optional AI-assigned relevance score (0-100) for this source.
   * When provided, the component will show a divergence indicator
   * if the human average differs from the AI score by more than 30 points.
   */
  aiRelevanceScore?: number;
  /** Optional additional CSS classes for the container */
  className?: string;
}

/** Debounce delay for comment submissions (ms) */
const COMMENT_DEBOUNCE_MS = 800;

/**
 * SourceRatingInline provides a complete inline rating experience for a source.
 *
 * On mount, it fetches the aggregate ratings and the current user's existing
 * rating (if any). The user can set a quality star rating, select a relevance
 * level, and optionally add a text comment. All changes are submitted
 * optimistically -- the UI updates immediately and the API call runs
 * in the background.
 *
 * If an `aiRelevanceScore` is provided, the component compares it against the
 * human average quality (scaled to 0-100). When the difference exceeds 30
 * points, a divergence indicator appears to flag the discrepancy for review.
 *
 * @example
 * ```tsx
 * <SourceRatingInline
 *   sourceId="src_abc123"
 *   token={authToken}
 *   aiRelevanceScore={85}
 * />
 * ```
 */
export const SourceRatingInline: React.FC<SourceRatingInlineProps> = ({
  sourceId,
  token,
  aiRelevanceScore,
  className,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [qualityRating, setQualityRating] = useState<number>(0);
  const [relevanceRating, setRelevanceRating] = useState<string>("medium");
  const [comment, setComment] = useState<string>("");

  const [aggregate, setAggregate] = useState<SourceRatingAggregate | null>(
    null,
  );

  const commentTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (commentTimerRef.current) {
        clearTimeout(commentTimerRef.current);
      }
    };
  }, []);

  /**
   * Fetch aggregate ratings and the current user's rating on mount.
   */
  useEffect(() => {
    let cancelled = false;

    async function fetchRatings() {
      try {
        setLoading(true);
        setError(null);
        const data = await getSourceRatings(sourceId, token);

        if (cancelled) return;

        setAggregate(data);

        // Populate form with existing user rating if present
        if (data.current_user_rating) {
          setQualityRating(data.current_user_rating.quality_rating);
          setRelevanceRating(data.current_user_rating.relevance_rating);
          setComment(data.current_user_rating.comment || "");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load ratings",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchRatings();
    return () => {
      cancelled = true;
    };
  }, [sourceId, token]);

  /**
   * Submit a rating to the API. Updates the aggregate optimistically.
   */
  const submitRating = useCallback(
    async (quality: number, relevance: string, commentText: string) => {
      if (quality === 0) return; // Don't submit if no quality rating set

      setSubmitting(true);
      try {
        await rateSource(
          sourceId,
          {
            quality_rating: quality,
            relevance_rating: relevance,
            comment: commentText || undefined,
          },
          token,
        );

        // Re-fetch aggregate to get updated stats
        if (mountedRef.current) {
          const updated = await getSourceRatings(sourceId, token);
          if (mountedRef.current) {
            setAggregate(updated);
          }
        }
      } catch (err) {
        if (mountedRef.current) {
          setError(
            err instanceof Error ? err.message : "Failed to submit rating",
          );
        }
      } finally {
        if (mountedRef.current) {
          setSubmitting(false);
        }
      }
    },
    [sourceId, token],
  );

  /**
   * Handle quality star rating change with optimistic UI.
   */
  const handleQualityChange = useCallback(
    (value: number) => {
      setQualityRating(value);
      // Optimistically update aggregate
      setAggregate((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          avg_quality:
            prev.total_ratings > 0
              ? (prev.avg_quality * prev.total_ratings -
                  (prev.current_user_rating?.quality_rating || 0) +
                  value) /
                Math.max(prev.total_ratings, 1)
              : value,
          total_ratings: prev.current_user_rating
            ? prev.total_ratings
            : prev.total_ratings + 1,
        };
      });
      submitRating(value, relevanceRating, comment);
    },
    [relevanceRating, comment, submitRating],
  );

  /**
   * Handle relevance selector change with optimistic UI.
   */
  const handleRelevanceChange = useCallback(
    (value: string) => {
      setRelevanceRating(value);
      if (qualityRating > 0) {
        submitRating(qualityRating, value, comment);
      }
    },
    [qualityRating, comment, submitRating],
  );

  /**
   * Handle comment input change with debounced submission.
   */
  const handleCommentChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newComment = e.target.value;
      setComment(newComment);

      // Debounce comment submission
      if (commentTimerRef.current) {
        clearTimeout(commentTimerRef.current);
      }

      if (qualityRating > 0) {
        commentTimerRef.current = setTimeout(() => {
          submitRating(qualityRating, relevanceRating, newComment);
        }, COMMENT_DEBOUNCE_MS);
      }
    },
    [qualityRating, relevanceRating, submitRating],
  );

  /**
   * Calculate whether there is a divergence between AI and human scores.
   * AI score is 0-100; human avg quality is 1-5, scaled to 0-100 as (avg/5)*100.
   */
  const divergenceInfo = React.useMemo(() => {
    if (
      aiRelevanceScore == null ||
      !aggregate ||
      aggregate.total_ratings === 0
    ) {
      return null;
    }

    const humanScaled = (aggregate.avg_quality / 5) * 100;
    const diff = Math.abs(aiRelevanceScore - humanScaled);

    if (diff > 30) {
      return {
        aiScore: aiRelevanceScore,
        humanScore: Math.round(humanScaled),
        difference: Math.round(diff),
      };
    }
    return null;
  }, [aiRelevanceScore, aggregate]);

  // Loading state
  if (loading) {
    return (
      <div className={cn("animate-pulse space-y-2 py-3", className)}>
        <div className="h-5 w-28 bg-gray-200 dark:bg-gray-700 rounded" />
        <div className="h-6 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
      </div>
    );
  }

  // Error state
  if (error && !aggregate) {
    return (
      <div
        className={cn("text-sm text-red-600 dark:text-red-400 py-2", className)}
      >
        {error}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "space-y-3 py-3 border-t border-gray-100 dark:border-gray-700",
        className,
      )}
    >
      {/* User rating controls */}
      <div className="space-y-2">
        <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          Your Rating
        </div>

        {/* Star rating row */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500 dark:text-gray-400 w-14 shrink-0">
            Quality
          </span>
          <StarRating
            value={qualityRating}
            onChange={handleQualityChange}
            size="sm"
          />
          {submitting && (
            <span className="text-xs text-gray-400 dark:text-gray-500 animate-pulse">
              Saving...
            </span>
          )}
        </div>

        {/* Relevance selector row */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500 dark:text-gray-400 w-14 shrink-0">
            Relevance
          </span>
          <RelevanceSelector
            value={relevanceRating}
            onChange={handleRelevanceChange}
          />
        </div>

        {/* Comment input */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500 dark:text-gray-400 w-14 shrink-0">
            Comment
          </span>
          <input
            type="text"
            value={comment}
            onChange={handleCommentChange}
            placeholder="Optional comment..."
            className={cn(
              "flex-1 text-sm px-2 py-1 rounded border transition-colors",
              "border-gray-200 bg-white text-gray-700 placeholder-gray-400",
              "dark:border-gray-600 dark:bg-dark-surface dark:text-gray-200 dark:placeholder-gray-500",
              "focus:outline-none focus:ring-1 focus:ring-blue-400 focus:border-blue-400",
              "disabled:opacity-50",
            )}
            maxLength={500}
            disabled={qualityRating === 0}
            aria-label="Rating comment"
          />
        </div>
      </div>

      {/* Divergence indicator */}
      {divergenceInfo && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-yellow-50 border border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800">
          <span className="text-yellow-600 dark:text-yellow-400 text-sm font-medium">
            Score Divergence
          </span>
          <span className="text-xs text-yellow-700 dark:text-yellow-300">
            AI: {divergenceInfo.aiScore} vs Team: {divergenceInfo.humanScore} (
            {divergenceInfo.difference}pt gap)
          </span>
        </div>
      )}

      {/* Error message for submission failures */}
      {error && aggregate && (
        <div className="text-xs text-red-500 dark:text-red-400">{error}</div>
      )}

      {/* Aggregate stats */}
      {aggregate && <RatingAggregate aggregate={aggregate} />}
    </div>
  );
};

export default SourceRatingInline;
