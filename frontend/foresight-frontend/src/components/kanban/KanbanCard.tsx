/**
 * KanbanCard Component
 *
 * A draggable card component for the workstream kanban board.
 * Uses @dnd-kit/sortable for drag-and-drop functionality.
 *
 * Features:
 * - Draggable with smooth visual feedback
 * - Displays card metadata with badge components
 * - Notes and reminder indicators
 * - Click navigation to card detail view
 * - Dark mode support
 */

import React, { memo, useCallback } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useNavigate } from 'react-router-dom';
import { StickyNote, Bell, GripVertical, Sparkles, UserPlus, Heart, Check, X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { PillarBadge } from '../PillarBadge';
import { HorizonBadge } from '../HorizonBadge';
import { StageBadge } from '../StageBadge';
import { Top25Badge } from '../Top25Badge';
import { Tooltip } from '../ui/Tooltip';
import { CardActions } from './CardActions';
import { getPillarByCode } from '../../data/taxonomy';
import type {
  WorkstreamCard as WorkstreamCardType,
  CardActionCallbacks,
  KanbanStatus,
} from './types';

// =============================================================================
// Types
// =============================================================================

export interface KanbanCardProps {
  /** The workstream card data to display */
  card: WorkstreamCardType;
  /** The parent workstream ID (for CardActions) */
  workstreamId?: string;
  /** The column ID this card is in (for column-specific actions) */
  columnId?: KanbanStatus;
  /** Whether the card is currently being dragged (for overlay) */
  isDragOverlay?: boolean;
  /** Optional callback when card is clicked */
  onCardClick?: (card: WorkstreamCardType) => void;
  /** Optional card action callbacks */
  cardActions?: CardActionCallbacks;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get color class for the card's left border accent.
 * Based on the card's horizon for visual grouping.
 */
function getAccentBorderClass(horizon: 'H1' | 'H2' | 'H3'): string {
  const accentMap: Record<string, string> = {
    H1: 'border-l-green-500',
    H2: 'border-l-amber-500',
    H3: 'border-l-purple-500',
  };
  return accentMap[horizon] || 'border-l-gray-400';
}

/**
 * Parse stage number from stage_id if needed.
 * Handles both number and string formats (e.g., "1_concept" -> 1).
 */
function parseStageNumber(stageId: number | string): number | null {
  if (typeof stageId === 'number') {
    return stageId;
  }
  const match = String(stageId).match(/^(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}

/**
 * AddedFromTooltipContent - Explains why the card was added to the workstream
 */
function AddedFromTooltipContent({
  addedFrom,
  card,
}: {
  addedFrom: 'auto' | 'manual' | 'follow';
  card: WorkstreamCardType['card'];
}) {
  const pillar = getPillarByCode(card.pillar_id);

  if (addedFrom === 'auto') {
    return (
      <div className="space-y-2 min-w-[180px] max-w-[240px]">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-blue-500" />
          <span className="font-medium text-gray-900 dark:text-gray-100">Auto-matched</span>
        </div>
        <p className="text-xs text-gray-600 dark:text-gray-400">
          This card was automatically added because it matched your workstream filters:
        </p>
        <div className="space-y-1 text-xs">
          {pillar && (
            <div className="flex items-center gap-1.5">
              <span className="text-gray-500 dark:text-gray-400">Pillar:</span>
              <span className="text-gray-700 dark:text-gray-300">{pillar.name}</span>
            </div>
          )}
          {card.horizon && (
            <div className="flex items-center gap-1.5">
              <span className="text-gray-500 dark:text-gray-400">Horizon:</span>
              <span className="text-gray-700 dark:text-gray-300">{card.horizon}</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (addedFrom === 'manual') {
    return (
      <div className="space-y-2 min-w-[140px]">
        <div className="flex items-center gap-2">
          <UserPlus className="h-4 w-4 text-gray-500" />
          <span className="font-medium text-gray-900 dark:text-gray-100">Manually added</span>
        </div>
        <p className="text-xs text-gray-600 dark:text-gray-400">
          You added this card to your workstream.
        </p>
      </div>
    );
  }

  // 'follow'
  return (
    <div className="space-y-2 min-w-[140px]">
      <div className="flex items-center gap-2">
        <Heart className="h-4 w-4 text-pink-500" />
        <span className="font-medium text-gray-900 dark:text-gray-100">From followed card</span>
      </div>
      <p className="text-xs text-gray-600 dark:text-gray-400">
        Added because you followed this card.
      </p>
    </div>
  );
}

// =============================================================================
// Component
// =============================================================================

/**
 * KanbanCard - A draggable card for the kanban board.
 *
 * Renders a compact card with key metadata badges and indicators.
 * Supports drag-and-drop reordering via @dnd-kit.
 */
export const KanbanCard = memo(function KanbanCard({
  card,
  workstreamId,
  columnId,
  isDragOverlay = false,
  onCardClick,
  cardActions,
}: KanbanCardProps) {
  const navigate = useNavigate();

  // Configure sortable behavior
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: card.id,
    data: {
      type: 'card',
      card,
    },
  });

  // Apply transform styles for drag animation
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  // Extract card data
  const { card: embeddedCard } = card;
  const stageNumber = parseStageNumber(embeddedCard.stage_id);
  const hasNotes = card.notes && card.notes.trim().length > 0;
  const hasReminder = card.reminder_at !== null;

  /**
   * Handle card click navigation.
   * Prevents navigation during drag operations.
   */
  const handleClick = (e: React.MouseEvent) => {
    // Don't navigate if dragging
    if (isDragging) {
      e.preventDefault();
      return;
    }

    if (onCardClick) {
      onCardClick(card);
    } else {
      navigate(`/cards/${embeddedCard.slug}`);
    }
  };

  /**
   * Handle keyboard navigation for accessibility.
   */
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (onCardClick) {
        onCardClick(card);
      } else {
        navigate(`/cards/${embeddedCard.slug}`);
      }
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        // Base card styles
        'group relative bg-white dark:bg-[#2d3166] rounded-lg shadow-sm',
        'border border-gray-200 dark:border-gray-700',
        'border-l-4',
        getAccentBorderClass(embeddedCard.horizon),
        // Hover and interaction states
        'transition-all duration-200',
        'hover:shadow-md hover:border-gray-300 dark:hover:border-gray-600',
        // Drag states
        isDragging && 'opacity-50 shadow-lg ring-2 ring-brand-blue/50',
        isDragOverlay && 'shadow-xl scale-105 rotate-2 cursor-grabbing',
        // Touch optimization
        'touch-none'
      )}
    >
      {/* Top-right actions: Drag Handle + Card Actions */}
      <div
        className={cn(
          'absolute top-2 right-2 flex items-center gap-0.5',
          'opacity-0 group-hover:opacity-100 transition-opacity',
          isDragOverlay && 'opacity-100'
        )}
      >
        {/* Card Actions Menu */}
        {cardActions && workstreamId && columnId && !isDragOverlay && (
          <CardActions
            card={card}
            workstreamId={workstreamId}
            columnId={columnId}
            onNotesUpdate={cardActions.onNotesUpdate}
            onDeepDive={cardActions.onDeepDive}
            onRemove={cardActions.onRemove}
            onMoveToColumn={cardActions.onMoveToColumn}
            onQuickUpdate={cardActions.onQuickUpdate}
            onExport={cardActions.onExport}
            onExportBrief={cardActions.onExportBrief}
            onCheckUpdates={cardActions.onCheckUpdates}
            onGenerateBrief={cardActions.onGenerateBrief}
          />
        )}

        {/* Drag Handle */}
        <div
          {...attributes}
          {...listeners}
          className={cn(
            'p-1 rounded',
            'text-gray-400 dark:text-gray-500',
            'hover:bg-gray-100 dark:hover:bg-gray-700',
            'cursor-grab active:cursor-grabbing'
          )}
          aria-label="Drag to reorder"
        >
          <GripVertical className="h-4 w-4" />
        </div>
      </div>

      {/* Card Content - Clickable Area */}
      <div
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        className="p-3 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-inset rounded-lg"
      >
        {/* Card Title */}
        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2 pr-6 line-clamp-2">
          {embeddedCard.name}
        </h4>

        {/* Badge Row */}
        <div className="flex items-center gap-1.5 flex-wrap mb-2">
          <PillarBadge
            pillarId={embeddedCard.pillar_id}
            size="sm"
            showIcon={false}
            disableTooltip={isDragOverlay}
          />
          <HorizonBadge
            horizon={embeddedCard.horizon}
            size="sm"
            disableTooltip={isDragOverlay}
          />
          {stageNumber !== null && (
            <StageBadge
              stage={stageNumber}
              size="sm"
              variant="minimal"
              disableTooltip={isDragOverlay}
            />
          )}
        </div>

        {/* Top 25 Badge - if applicable */}
        {embeddedCard.top25_relevance && embeddedCard.top25_relevance.length > 0 && (
          <div className="mb-2">
            <Top25Badge
              priorities={embeddedCard.top25_relevance}
              size="sm"
              showCount
            />
          </div>
        )}

        {/* Indicators Row */}
        <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
          {/* Notes Indicator */}
          {hasNotes && (
            <div
              className="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400"
              title="Has notes"
            >
              <StickyNote className="h-3 w-3" />
              <span className="sr-only">Has notes</span>
            </div>
          )}

          {/* Reminder Indicator */}
          {hasReminder && (
            <div
              className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400"
              title="Reminder set"
            >
              <Bell className="h-3 w-3" />
              <span className="sr-only">Reminder set</span>
            </div>
          )}

          {/* Added From Badge - with tooltip explaining why */}
          <Tooltip
            content={
              <AddedFromTooltipContent
                addedFrom={card.added_from as 'auto' | 'manual' | 'follow'}
                card={embeddedCard}
              />
            }
            side="top"
            align="end"
            contentClassName="p-2"
            disabled={isDragOverlay}
          >
            <span
              className={cn(
                'ml-auto text-[10px] uppercase tracking-wide font-medium px-1.5 py-0.5 rounded cursor-help',
                card.added_from === 'auto' && 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
                card.added_from === 'manual' && 'bg-gray-50 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
                card.added_from === 'follow' && 'bg-pink-50 text-pink-600 dark:bg-pink-900/30 dark:text-pink-400'
              )}
            >
              {card.added_from}
            </span>
          </Tooltip>
        </div>

        {/* Quick Actions for Inbox Cards */}
        {columnId === 'inbox' && cardActions?.onMoveToColumn && !isDragOverlay && (
          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
            <button
              onClick={(e) => {
                e.stopPropagation();
                cardActions.onMoveToColumn?.(card.id, 'screening');
              }}
              className="flex-1 inline-flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-medium text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/40 rounded-md transition-colors"
              title="Move to Screening"
            >
              <Check className="h-3.5 w-3.5" />
              Accept
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                cardActions.onMoveToColumn?.(card.id, 'archived');
              }}
              className="flex-1 inline-flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-medium text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 rounded-md transition-colors"
              title="Move to Archived"
            >
              <X className="h-3.5 w-3.5" />
              Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  );
});

export default KanbanCard;
