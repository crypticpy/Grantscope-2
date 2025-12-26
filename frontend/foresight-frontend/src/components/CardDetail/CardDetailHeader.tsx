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

import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

// Badge Components
import { PillarBadge } from '../PillarBadge';
import { HorizonBadge } from '../HorizonBadge';
import { StageBadge } from '../StageBadge';
import { AnchorBadge } from '../AnchorBadge';
import { Top25Badge } from '../Top25Badge';

// Types
import type { Card } from './types';

// Utilities
import { parseStageNumber } from './utils';

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
  backLink = '/discover',
  backLinkText = 'Back to Discover',
  children,
}) => {
  // Parse stage number from stage_id string
  const stageNumber = parseStageNumber(card.stage_id);

  return (
    <div className="mb-8">
      {/* Back Navigation Link */}
      <Link
        to={backLink}
        className="inline-flex items-center text-sm text-gray-500 dark:text-gray-400 hover:text-brand-blue mb-4 transition-colors"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        {backLinkText}
      </Link>

      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Title and Primary Badges */}
          <div className="flex flex-col sm:flex-row sm:items-center flex-wrap gap-3 mb-4">
            <h1 className="text-2xl sm:text-3xl font-bold text-brand-dark-blue dark:text-white break-words">
              {card.name}
            </h1>
            <div className="flex items-center gap-2 flex-wrap">
              <PillarBadge
                pillarId={card.pillar_id}
                goalId={card.goal_id}
                showIcon
                size="md"
              />
              <HorizonBadge
                horizon={card.horizon}
                showIcon
                size="md"
              />
              {card.top25_relevance && card.top25_relevance.length > 0 && (
                <Top25Badge
                  priorities={card.top25_relevance}
                  showCount
                  size="md"
                />
              )}
            </div>
          </div>

          {/* Summary */}
          <p className="text-base sm:text-lg text-gray-600 dark:text-gray-300 mb-4 break-words">
            {card.summary}
          </p>

          {/* Quick Info Row */}
          <div className="flex items-center flex-wrap gap-2 sm:gap-4 text-sm">
            {stageNumber && (
              <StageBadge
                stage={stageNumber}
                variant="badge"
                showName
                size="sm"
              />
            )}
            {card.anchor_id && (
              <AnchorBadge
                anchor={card.anchor_id}
                size="sm"
                abbreviated
              />
            )}
            <span className="text-gray-500">
              Created: {new Date(card.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>

        {/* Action Buttons Area - receives children (e.g., CardActionButtons) */}
        {children && (
          <div className="flex items-center gap-2 sm:gap-3 overflow-x-auto pb-2 lg:pb-0 lg:overflow-visible lg:flex-wrap lg:justify-end -mx-4 px-4 sm:mx-0 sm:px-0">
            {children}
          </div>
        )}
      </div>
    </div>
  );
};

export default CardDetailHeader;
