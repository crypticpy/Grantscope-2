/**
 * DiscoverCard Component
 *
 * Renders a single card in the Discover page grid/list view.
 * Supports comparison mode and follow functionality.
 */

import React from "react";
import { Link } from "react-router-dom";
import {
  Eye,
  Heart,
  Calendar,
  Sparkles,
  ArrowLeftRight,
  Check,
  AlertTriangle,
  User,
  Scan,
} from "lucide-react";
import { PillarBadge } from "../../../components/PillarBadge";
import { HorizonBadge } from "../../../components/HorizonBadge";
import { StageBadge } from "../../../components/StageBadge";
import { Top25Badge } from "../../../components/Top25Badge";
import { QualityBadge } from "../../../components/QualityBadge";
import {
  VelocityBadge,
  type VelocityTrend,
} from "../../../components/VelocityBadge";
import { highlightText } from "../../../lib/highlight-utils";
import { parseStageNumber } from "../../../lib/stage-utils";
import type { Card } from "../types";
import { getScoreColorClasses, formatCardDate } from "../utils";

export interface DiscoverCardProps {
  card: Card;
  /** Whether comparison mode is active */
  compareMode: boolean;
  /** Whether this card is selected for comparison */
  isSelectedForCompare: boolean;
  /** Whether this card is followed by the user */
  isFollowed: boolean;
  /** Current search term for highlighting */
  searchTerm: string;
  /** Callback when card is toggled for comparison */
  onToggleCompare: (card: { id: string; name: string }) => void;
  /** Callback when card follow is toggled */
  onToggleFollow: (cardId: string) => void;
}

/**
 * DiscoverCard - Memoized card component for virtualized lists
 */
export const DiscoverCard = React.memo(function DiscoverCard({
  card,
  compareMode,
  isSelectedForCompare,
  isFollowed,
  searchTerm,
  onToggleCompare,
  onToggleFollow,
}: DiscoverCardProps) {
  const stageNumber = parseStageNumber(card.stage_id);

  return (
    <div
      onClick={
        compareMode
          ? () => onToggleCompare({ id: card.id, name: card.name })
          : undefined
      }
      className={`bg-white dark:bg-dark-surface rounded-lg shadow-sm p-5 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg relative overflow-hidden ${
        compareMode
          ? isSelectedForCompare
            ? "ring-2 ring-extended-purple/50 cursor-pointer"
            : "hover:ring-1 hover:ring-extended-purple/30 cursor-pointer"
          : ""
      }`}
    >
      {/* Top gradient accent bar */}
      <div className="absolute top-0 left-0 right-0 h-1 rounded-t-lg bg-gradient-to-r from-brand-blue to-brand-green" />

      {/* Compare Mode Selection Indicator */}
      {compareMode && (
        <div
          className={`absolute top-3 right-3 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all duration-200 ${
            isSelectedForCompare
              ? "bg-extended-purple border-extended-purple text-white"
              : "border-gray-300 dark:border-gray-600 bg-white dark:bg-dark-surface"
          }`}
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
            {/* Quality Badge */}
            <QualityBadge score={card.signal_quality_score ?? null} size="sm" />
            <VelocityBadge
              trend={card.velocity_trend as VelocityTrend}
              score={card.velocity_score}
            />
            {/* Provenance indicator */}
            {card.origin === "user_created" && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700">
                <User className="h-2.5 w-2.5" />
                User Created
              </span>
            )}
            {card.origin === "workstream_scan" && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-700">
                <Scan className="h-2.5 w-2.5" />
                Via Workstream
              </span>
            )}
            {card.origin === "manual" && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-700">
                <User className="h-2.5 w-2.5" />
                Manual Import
              </span>
            )}
            {/* Scores Unverified indicator */}
            {card.discovery_metadata?.scores_are_defaults === true && (
              <span
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-yellow-50 text-yellow-800 border border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-300 dark:border-yellow-700"
                title="Scores are defaults and have not been verified by analysis"
              >
                <AlertTriangle className="h-2.5 w-2.5" />
                Scores Unverified
              </span>
            )}
          </div>
        </div>
        {!compareMode && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleFollow(card.id);
            }}
            className={`flex-shrink-0 p-2 transition-all duration-200 active:scale-75 ${
              isFollowed
                ? "text-red-500 hover:text-red-600"
                : "text-gray-400 hover:text-red-500"
            }`}
            title={isFollowed ? "Unfollow signal" : "Follow signal"}
            aria-pressed={isFollowed}
          >
            <Heart
              className="h-5 w-5"
              fill={isFollowed ? "currentColor" : "none"}
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
