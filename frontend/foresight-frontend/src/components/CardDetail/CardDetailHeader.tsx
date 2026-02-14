/**
 * CardDetailHeader Component
 *
 * Displays the header section of a card detail page including:
 * - Back navigation link
 * - Card title with primary badges (Pillar, Horizon, Top25)
 * - Card summary
 * - Quick info row (Stage, Anchor, Created date)
 *
 * This component is responsive and handles dark mode styling.
 */

import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

// Badge Components
import { PillarBadge } from "../PillarBadge";
import { HorizonBadge } from "../HorizonBadge";
import { StageBadge } from "../StageBadge";
import { AnchorBadge } from "../AnchorBadge";
import { Top25Badge } from "../Top25Badge";
import { TrendBadge, type TrendDirection } from "../TrendBadge";

// Types
import type { Card } from "./types";

// Utilities
import { parseStageNumber } from "./utils";

/**
 * Props for the CardDetailHeader component
 */
export interface CardDetailHeaderProps {
  /** The card data to display */
  card: Card;
  /** Optional custom back link URL (defaults to /discover) */
  backLink?: string;
  /** Optional custom back link text (defaults to "Back to Discover") */
  backLinkText?: string;
  /** Optional children to render in the action buttons area */
  children?: React.ReactNode;
}

/**
 * CardDetailHeader displays the header section of a card detail page.
 *
 * Features:
 * - Responsive layout with flex wrapping on mobile
 * - Primary badges (Pillar, Horizon, Top25) next to title
 * - Summary text with proper line wrapping
 * - Quick info row with stage, anchor, and created date
 * - Dark mode support
 *
 * @example
 * ```tsx
 * <CardDetailHeader card={card}>
 *   <CardActionButtons card={card} />
 * </CardDetailHeader>
 * ```
 */
export const CardDetailHeader: React.FC<CardDetailHeaderProps> = ({
  card,
  backLink = "/discover",
  backLinkText = "Back to Discover",
  children,
}) => {
  // Parse stage number from stage_id string
  const stageNumber = parseStageNumber(card.stage_id);

  return (
    <div className="mb-8">
      {/* Back Navigation Link */}
      <Link
        to={backLink}
        className="inline-flex items-center text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-brand-blue dark:hover:text-brand-blue mb-6 transition-colors"
      >
        <ArrowLeft className="h-4 w-4 mr-1.5" />
        {backLinkText}
      </Link>

      {/* Hero Section Container - optimized for quick scanning */}
      <div className="bg-white dark:bg-dark-surface/90 rounded-2xl border border-gray-200 dark:border-gray-700/70 shadow-sm overflow-hidden mb-6">
        {/* Gradient Header Bar - Austin brand colors */}
        <div className="bg-gradient-to-r from-brand-blue to-brand-green h-1.5" />

        {/* Action Buttons Row - Top with separator */}
        {children && (
          <div className="px-5 sm:px-6 lg:px-8 pt-4 pb-3 border-b border-gray-200 dark:border-gray-700/50">
            <div className="flex items-center justify-end gap-2 sm:gap-3 flex-wrap">
              {children}
            </div>
          </div>
        )}

        {/* Main Content Area */}
        <div className="p-5 sm:p-6 lg:p-8">
          {/* Primary Classification Badges - TOP for quick scanning */}
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap mb-4">
            <div className="transition-transform hover:scale-105">
              <PillarBadge
                pillarId={card.pillar_id}
                goalId={card.goal_id}
                showIcon
                size="lg"
              />
            </div>
            <div className="transition-transform hover:scale-105">
              <HorizonBadge horizon={card.horizon} showIcon size="lg" />
            </div>
            {card.top25_relevance && card.top25_relevance.length > 0 && (
              <div className="transition-transform hover:scale-105">
                <Top25Badge
                  priorities={card.top25_relevance}
                  showCount
                  size="lg"
                />
              </div>
            )}
          </div>

          {/* Title - prominent for quick identification, full width */}
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-gray-900 dark:text-white break-words mb-4 leading-tight tracking-tight">
            {card.name}
          </h1>

          {/* Summary - the "elevator pitch", full width for better readability */}
          <p className="text-base sm:text-lg text-gray-700 dark:text-gray-200 mb-5 break-words leading-relaxed">
            {card.summary}
          </p>

          {/* Secondary Info Row - Stage, Anchor, Created Date */}
          <div className="flex items-center flex-wrap gap-3 sm:gap-4 pt-3 border-t border-gray-200/60 dark:border-gray-700/50">
            {stageNumber && (
              <div className="transition-transform hover:scale-105">
                <StageBadge
                  stage={stageNumber}
                  variant="badge"
                  showName
                  size="md"
                />
              </div>
            )}
            {card.anchor_id && (
              <div className="transition-transform hover:scale-105">
                <AnchorBadge anchor={card.anchor_id} size="md" abbreviated />
              </div>
            )}
            {card.trend_direction && card.trend_direction !== "unknown" && (
              <TrendBadge direction={card.trend_direction as TrendDirection} />
            )}
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Created: {new Date(card.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CardDetailHeader;
