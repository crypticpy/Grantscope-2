/**
 * DiscoverCard Component
 *
 * A memoized card component for the Discover page.
 * Displays a card with badges, scores, follow button, and compare mode support.
 * Supports both grid and list display modes for virtualized rendering.
 *
 * Features:
 * - Memoized with React.memo to prevent unnecessary re-renders
 * - Support for grid and list view modes
 * - Compare mode selection
 * - Follow/unfollow functionality
 * - Search term highlighting
 * - Responsive design
 */

import { memo } from "react";
import { Link } from "react-router-dom";
import {
  Eye,
  Heart,
  Sparkles,
  Calendar,
  ArrowLeftRight,
  Check,
} from "lucide-react";
import { format, formatDistanceToNow } from "date-fns";
import { PillarBadge } from "./PillarBadge";
import { HorizonBadge } from "./HorizonBadge";
import { StageBadge } from "./StageBadge";
import { Top25Badge } from "./Top25Badge";
import { highlightText } from "../lib/highlight-utils";
import { cn } from "../lib/utils";

/**
 * Card data interface
 */
export interface DiscoverCardData {
  id: string;
  name: string;
  slug: string;
  summary: string;
  pillar_id: string;
  stage_id: string;
  horizon: "H1" | "H2" | "H3";
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
  search_relevance?: number;
}

/**
 * Parse stage number from stage_id string
 * e.g., "1_concept" -> 1, "2_emerging" -> 2
 */
const parseStageNumber = (stageId: string): number | null => {
  const match = stageId.match(/^(\d+)/);
  return match?.[1] ? parseInt(match[1], 10) : null;
};

/**
 * Get color classes for score values
 */
const getScoreColorClasses = (score: number): string => {
  if (score >= 80) return "text-green-600 dark:text-green-400";
  if (score >= 60) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
};

/**
 * Format card date for display
 * Shows relative time for recent updates, absolute date for creation
 */
const formatCardDate = (
  createdAt: string,
  updatedAt?: string,
): { label: string; text: string } => {
  try {
    const created = new Date(createdAt);
    const updated = updatedAt ? new Date(updatedAt) : null;

    // If updated_at exists and is different from created_at (more than 1 minute difference)
    if (updated && Math.abs(updated.getTime() - created.getTime()) > 60000) {
      return {
        label: "Updated",
        text: formatDistanceToNow(updated, { addSuffix: true }),
      };
    }

    // Fall back to created_at with absolute date format
    return {
      label: "Created",
      text: format(created, "MMM d, yyyy"),
    };
  } catch {
    // Handle invalid dates gracefully
    return {
      label: "Created",
      text: "Unknown",
    };
  }
};

/**
 * Props for the DiscoverCard component
 */
export interface DiscoverCardProps {
  /** The card data */
  card: DiscoverCardData;
  /** Whether the card is being followed by the user */
  isFollowing: boolean;
  /** Whether compare mode is active */
  compareMode: boolean;
  /** Whether this card is selected for comparison */
  isSelectedForCompare: boolean;
  /** Current search term for highlighting */
  searchTerm: string;
  /** Display mode - grid or list */
  viewMode: "grid" | "list";
  /** Callback when follow button is clicked */
  onFollowToggle: () => void;
  /** Callback when card is selected for comparison */
  onCompareToggle: () => void;
}

/**
 * DiscoverCard Component
 *
 * A memoized card component for displaying cards in the Discover page.
 * Optimized for virtualized rendering with proper memoization.
 */
export const DiscoverCard = memo(function DiscoverCard({
  card,
  isFollowing,
  compareMode,
  isSelectedForCompare,
  searchTerm,
  viewMode: _viewMode,
  onFollowToggle,
  onCompareToggle,
}: DiscoverCardProps) {
  const stageNumber = parseStageNumber(card.stage_id);

  return (
    <div
      onClick={compareMode ? onCompareToggle : undefined}
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg shadow p-6 border-l-4 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg relative",
        compareMode
          ? isSelectedForCompare
            ? "border-l-extended-purple ring-2 ring-extended-purple/50 cursor-pointer"
            : "border-transparent hover:border-l-extended-purple/50 cursor-pointer"
          : "border-transparent hover:border-l-brand-blue",
      )}
    >
      {/* Compare Mode Selection Indicator */}
      {compareMode && (
        <div
          className={cn(
            "absolute top-3 right-3 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all duration-200",
            isSelectedForCompare
              ? "bg-extended-purple border-extended-purple text-white"
              : "border-gray-300 dark:border-gray-600 bg-white dark:bg-dark-surface",
          )}
        >
          {isSelectedForCompare && <Check className="h-4 w-4" />}
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
                to={`/signals/${card.slug}`}
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
              <Top25Badge
                priorities={card.top25_relevance}
                size="sm"
                showCount
              />
            )}
          </div>
        </div>
        {!compareMode && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onFollowToggle();
            }}
            className={cn(
              "flex-shrink-0 p-2 transition-colors",
              isFollowing
                ? "text-red-500 hover:text-red-600"
                : "text-gray-400 hover:text-red-500",
            )}
            title={isFollowing ? "Unfollow opportunity" : "Follow opportunity"}
            aria-pressed={isFollowing}
          >
            <Heart
              className="h-5 w-5"
              fill={isFollowing ? "currentColor" : "none"}
            />
          </button>
        )}
      </div>

      <p className="text-gray-600 dark:text-gray-400 mb-4 line-clamp-3">
        {searchTerm ? highlightText(card.summary, searchTerm) : card.summary}
      </p>

      {/* Scores */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div
          className="flex justify-between"
          title="How much this could affect Austin's operations or residents"
        >
          <span className="text-gray-500 dark:text-gray-400">Impact:</span>
          <span className={getScoreColorClasses(card.impact_score)}>
            {card.impact_score}
          </span>
        </div>
        <div
          className="flex justify-between"
          title="How closely this aligns with Austin's strategic priorities"
        >
          <span className="text-gray-500 dark:text-gray-400">Relevance:</span>
          <span className={getScoreColorClasses(card.relevance_score)}>
            {card.relevance_score}
          </span>
        </div>
        <div
          className="flex justify-between"
          title="How quickly this technology or trend is evolving"
        >
          <span className="text-gray-500 dark:text-gray-400">Velocity:</span>
          <span className={getScoreColorClasses(card.velocity_score)}>
            {card.velocity_score}
          </span>
        </div>
        <div
          className="flex justify-between"
          title="How new or emerging this is in the market"
        >
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
            {isSelectedForCompare ? "Selected" : "Click to select"}
          </span>
        ) : (
          <Link
            to={`/signals/${card.slug}`}
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
});

export default DiscoverCard;
