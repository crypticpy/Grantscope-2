/**
 * KanbanColumn Component
 *
 * A droppable column for the workstream kanban board.
 * Uses @dnd-kit for drop target functionality with sortable cards.
 *
 * Features:
 * - Droppable area for card placement
 * - Column header with title, description, and count
 * - Visual feedback when dragging over
 * - Scrollable card list with max height
 * - Empty state placeholder
 * - Dark mode support
 */

import React, { memo, useMemo } from "react";
import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import {
  Inbox,
  Search,
  FlaskConical,
  FileText,
  Eye,
  Archive,
  Presentation,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { Tooltip } from "../ui/Tooltip";
import { KanbanCard } from "./KanbanCard";
import {
  KANBAN_COLUMNS,
  type KanbanStatus,
  type WorkstreamCard,
  type OnCardClickCallback,
  type CardActionCallbacks,
} from "./types";

// =============================================================================
// Types
// =============================================================================

export interface KanbanColumnProps {
  /** Unique column identifier */
  id: KanbanStatus;
  /** Column display title */
  title: string;
  /** Column description for the header */
  description: string;
  /** Cards in this column */
  cards: WorkstreamCard[];
  /** The parent workstream ID */
  workstreamId?: string;
  /** Optional callback when a card is clicked */
  onCardClick?: OnCardClickCallback;
  /** Optional card action callbacks */
  cardActions?: CardActionCallbacks;
  /** Optional callback for bulk export (Brief column only) */
  onBulkExport?: () => void;
}

// =============================================================================
// Constants
// =============================================================================

/**
 * Icon mapping for each column status.
 * Provides visual context for the workflow stage.
 */
const COLUMN_ICONS: Record<KanbanStatus, LucideIcon> = {
  inbox: Inbox,
  screening: Search,
  research: FlaskConical,
  brief: FileText,
  watching: Eye,
  archived: Archive,
};

/**
 * Color accent mapping for column headers.
 * Subtle visual differentiation between stages.
 */
const COLUMN_COLORS: Record<
  KanbanStatus,
  { bg: string; text: string; border: string }
> = {
  inbox: {
    bg: "bg-blue-50 dark:bg-blue-900/20",
    text: "text-blue-600 dark:text-blue-400",
    border: "border-blue-200 dark:border-blue-800",
  },
  screening: {
    bg: "bg-amber-50 dark:bg-amber-900/20",
    text: "text-amber-600 dark:text-amber-400",
    border: "border-amber-200 dark:border-amber-800",
  },
  research: {
    bg: "bg-purple-50 dark:bg-purple-900/20",
    text: "text-purple-600 dark:text-purple-400",
    border: "border-purple-200 dark:border-purple-800",
  },
  brief: {
    bg: "bg-green-50 dark:bg-green-900/20",
    text: "text-green-600 dark:text-green-400",
    border: "border-green-200 dark:border-green-800",
  },
  watching: {
    bg: "bg-cyan-50 dark:bg-cyan-900/20",
    text: "text-cyan-600 dark:text-cyan-400",
    border: "border-cyan-200 dark:border-cyan-800",
  },
  archived: {
    bg: "bg-gray-50 dark:bg-gray-800/50",
    text: "text-gray-500 dark:text-gray-400",
    border: "border-gray-200 dark:border-gray-700",
  },
};

// =============================================================================
// Sub-components
// =============================================================================

interface EmptyColumnStateProps {
  columnId: KanbanStatus;
  hint?: string;
}

/**
 * Empty state component for columns with no cards.
 * Displays a column-specific hint when available.
 */
function EmptyColumnState({ columnId, hint }: EmptyColumnStateProps) {
  const colors = COLUMN_COLORS[columnId];

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-8 px-4",
        "border-2 border-dashed rounded-lg",
        "text-center",
        colors.border,
      )}
    >
      <p className="text-sm text-gray-500 dark:text-gray-400">
        No signals in this column
      </p>
      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
        {hint || "Drag cards here to move them"}
      </p>
    </div>
  );
}

// =============================================================================
// Component
// =============================================================================

/**
 * KanbanColumn - A droppable column containing sortable cards.
 *
 * Provides the drop zone for cards and manages the sortable context
 * for cards within this column.
 */
export const KanbanColumn = memo(function KanbanColumn({
  id,
  title,
  description,
  cards,
  workstreamId,
  onCardClick,
  cardActions,
  onBulkExport,
}: KanbanColumnProps) {
  // Configure droppable behavior
  const { setNodeRef, isOver } = useDroppable({
    id,
    data: {
      type: "column",
      columnId: id,
    },
  });

  // Get column definition for actions and hints
  const columnDef = useMemo(
    () => KANBAN_COLUMNS.find((col) => col.id === id),
    [id],
  );

  // Extract card IDs for sortable context
  const cardIds = useMemo(() => cards.map((card) => card.id), [cards]);

  // Get column styling
  const colors = COLUMN_COLORS[id];
  const Icon = COLUMN_ICONS[id];

  return (
    <div
      ref={setNodeRef}
      className={cn(
        // Base column styles
        "flex flex-col",
        "w-72 min-w-72 flex-shrink-0",
        "bg-gray-50 dark:bg-[#1a1d40]",
        "rounded-xl",
        "border border-gray-200 dark:border-gray-800",
        // Transition for hover/over states
        "transition-all duration-200",
        // Drop target highlight - applied to entire column
        isOver && "ring-2 ring-brand-blue/50 border-brand-blue/50",
      )}
    >
      {/* Column Header */}
      <div
        className={cn(
          "px-4 py-3 rounded-t-xl",
          "border-b",
          colors.bg,
          colors.border,
        )}
      >
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <Icon className={cn("h-4 w-4", colors.text)} />
            <h3 className="font-semibold text-gray-900 dark:text-white text-sm">
              {title}
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {/* Bulk Export Button - Brief column only */}
            {id === "brief" && onBulkExport && cards.length > 0 && (
              <Tooltip
                content={
                  <div className="max-w-[200px]">
                    <p className="font-medium">Export Portfolio</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Combine all briefs into a single presentation
                    </p>
                  </div>
                }
                side="bottom"
              >
                <button
                  onClick={onBulkExport}
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-1",
                    "text-xs font-medium rounded-md",
                    "bg-[#44499C]/10 text-[#44499C]",
                    "hover:bg-[#44499C]/20",
                    "dark:bg-[#44499C]/20 dark:text-[#9b9edb]",
                    "dark:hover:bg-[#44499C]/30",
                    "transition-colors",
                  )}
                  aria-label="Export all briefs as portfolio"
                >
                  <Presentation className="h-3.5 w-3.5" />
                  <span>Export All</span>
                </button>
              </Tooltip>
            )}
            {/* Primary Action Indicator - shows available action for this column */}
            {columnDef?.primaryAction && (
              <Tooltip
                content={
                  <div className="max-w-[200px]">
                    <p className="font-medium">
                      {columnDef.primaryAction.label}
                    </p>
                    {columnDef.primaryAction.description && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        {columnDef.primaryAction.description}
                      </p>
                    )}
                    <p className="text-xs text-gray-500 mt-1 italic">
                      Use signal menu to trigger
                    </p>
                  </div>
                }
                side="bottom"
              >
                <div
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-1",
                    "text-xs rounded-md",
                    colors.text,
                    "opacity-60",
                  )}
                  aria-label={`${columnDef.primaryAction.label} available in signal menu`}
                >
                  <columnDef.primaryAction.icon className="h-3.5 w-3.5" />
                </div>
              </Tooltip>
            )}
            {/* Card Count Badge */}
            <span
              className={cn(
                "inline-flex items-center justify-center",
                "min-w-5 h-5 px-1.5",
                "text-xs font-medium rounded-full",
                cards.length > 0
                  ? cn(colors.bg, colors.text, "border", colors.border)
                  : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
              )}
            >
              {cards.length}
            </span>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
          {description}
        </p>
      </div>

      {/* Card List - Scrollable Area */}
      <div
        className={cn(
          "flex-1 p-3 overflow-y-auto",
          "min-h-32 max-h-[calc(100vh-280px)]",
          "transition-all duration-150",
        )}
      >
        <SortableContext items={cardIds} strategy={verticalListSortingStrategy}>
          {cards.length > 0 ? (
            <div className="space-y-3">
              {cards.map((card) => (
                <KanbanCard
                  key={card.id}
                  card={card}
                  workstreamId={workstreamId}
                  columnId={id}
                  onCardClick={onCardClick}
                  cardActions={cardActions}
                />
              ))}
            </div>
          ) : (
            <EmptyColumnState columnId={id} hint={columnDef?.emptyStateHint} />
          )}
        </SortableContext>
      </div>
    </div>
  );
});

export default KanbanColumn;
