/**
 * KanbanBoard Component
 *
 * The main kanban board component for workstream card management.
 * Orchestrates drag-and-drop interactions across multiple columns.
 *
 * Features:
 * - Full DnD context with pointer and keyboard sensors
 * - Horizontal scrolling container for 6 columns
 * - Drag overlay for smooth drag preview
 * - Cross-column card movement
 * - Within-column card reordering
 * - Responsive design with mobile stacking
 * - Dark mode support
 */

import React, { useState, useMemo, useCallback } from "react";
import {
  DndContext,
  DragOverlay,
  pointerWithin,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type DragOverEvent,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { cn } from "../../lib/utils";
import { KanbanColumn } from "./KanbanColumn";
import { KanbanCard } from "./KanbanCard";
import {
  KANBAN_COLUMNS,
  type KanbanStatus,
  type WorkstreamCard,
  type OnCardMoveCallback,
  type OnCardClickCallback,
  type CardActionCallbacks,
} from "./types";

// =============================================================================
// Types
// =============================================================================

export interface KanbanBoardProps {
  /** Cards organized by status */
  cards: Record<KanbanStatus, WorkstreamCard[]>;
  /** The workstream ID */
  workstreamId: string;
  /** Callback when a card is moved */
  onCardMove: OnCardMoveCallback;
  /** Optional callback when a card is clicked */
  onCardClick?: OnCardClickCallback;
  /** Optional card action callbacks */
  cardActions?: CardActionCallbacks;
  /** Optional callback for bulk export (passed to Brief column) */
  onBulkExport?: () => void;
  /** Optional additional class names */
  className?: string;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Find which column a card belongs to based on its ID.
 */
function findColumnForCard(
  cardId: string,
  cards: Record<KanbanStatus, WorkstreamCard[]>,
): KanbanStatus | null {
  for (const [status, columnCards] of Object.entries(cards)) {
    if (columnCards.some((card) => card.id === cardId)) {
      return status as KanbanStatus;
    }
  }
  return null;
}

/**
 * Find a card by its ID across all columns.
 */
function findCard(
  cardId: string,
  cards: Record<KanbanStatus, WorkstreamCard[]>,
): WorkstreamCard | null {
  for (const columnCards of Object.values(cards)) {
    const card = columnCards.find((c) => c.id === cardId);
    if (card) return card;
  }
  return null;
}

// =============================================================================
// Component
// =============================================================================

/**
 * KanbanBoard - The main board orchestrating drag-and-drop.
 *
 * Manages the DnD context, sensors, and coordinates card movements
 * between and within columns.
 */
export function KanbanBoard({
  cards,
  workstreamId,
  onCardMove,
  onCardClick,
  cardActions,
  onBulkExport,
  className,
}: KanbanBoardProps) {
  // Track the currently dragged card for the overlay
  const [activeCard, setActiveCard] = useState<WorkstreamCard | null>(null);

  // Configure DnD sensors
  // Pointer sensor for mouse/touch with activation constraint
  // Keyboard sensor for accessibility
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        // Require 8px movement before starting drag
        // Prevents accidental drags on click
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  /**
   * Handle drag start - capture the active card for overlay.
   */
  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const { active } = event;
      const card = findCard(String(active.id), cards);
      if (card) {
        setActiveCard(card);
      }
    },
    [cards],
  );

  /**
   * Handle drag over - could be used for real-time updates.
   * Currently a no-op but kept for potential future use.
   */
  const handleDragOver = useCallback((_event: DragOverEvent) => {
    // Reserved for real-time column highlighting or card reordering
    // during drag if needed in the future
  }, []);

  /**
   * Handle drag end - calculate new position and trigger callback.
   */
  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      // Clear the active card
      setActiveCard(null);

      // If no drop target, do nothing
      if (!over) return;

      const activeId = String(active.id);
      const overId = String(over.id);

      // Find source column
      const sourceColumn = findColumnForCard(activeId, cards);
      if (!sourceColumn) return;

      // Determine target column
      // Could be dropping on a card (overId is card.id) or column (overId is column.id)
      let targetColumn: KanbanStatus;
      let targetIndex: number;

      // Check if over is a column
      if (KANBAN_COLUMNS.some((col) => col.id === overId)) {
        targetColumn = overId as KanbanStatus;
        // Dropping on empty column - append at end
        targetIndex = cards[targetColumn].length;
      } else {
        // Dropping on a card - find its column
        const overColumn = findColumnForCard(overId, cards);
        if (!overColumn) return;
        targetColumn = overColumn;

        // Find the index of the card we're dropping over
        const overIndex = cards[targetColumn].findIndex((c) => c.id === overId);
        if (overIndex === -1) return;

        // If same column, use arrayMove logic
        if (sourceColumn === targetColumn) {
          const activeIndex = cards[sourceColumn].findIndex(
            (c) => c.id === activeId,
          );
          if (activeIndex === overIndex) return; // Same position
          targetIndex = overIndex;
        } else {
          // Different column - insert at the over position
          targetIndex = overIndex;
        }
      }

      // Trigger the callback with the new position
      onCardMove(activeId, targetColumn, targetIndex);
    },
    [cards, onCardMove],
  );

  /**
   * Handle drag cancel - clear active state.
   */
  const handleDragCancel = useCallback(() => {
    setActiveCard(null);
  }, []);

  /**
   * Build column data with cards for rendering.
   */
  const columnsWithCards = useMemo(() => {
    return KANBAN_COLUMNS.map((columnDef) => ({
      ...columnDef,
      cards: cards[columnDef.id] || [],
    }));
  }, [cards]);

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={pointerWithin}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      {/* Horizontal Scroll Container */}
      <div
        className={cn(
          // Desktop: horizontal scroll
          "flex gap-4 overflow-x-auto pb-4",
          // Add padding for scroll shadow effect
          "px-1",
          // Thin scrollbar on desktop
          "scrollbar-thin",
          // Mobile: stack vertically
          "max-md:flex-col max-md:overflow-x-visible",
          className,
        )}
      >
        {columnsWithCards.map((column) => (
          <KanbanColumn
            key={column.id}
            id={column.id}
            title={column.title}
            description={column.description}
            cards={column.cards}
            workstreamId={workstreamId}
            onCardClick={onCardClick}
            cardActions={cardActions}
            onBulkExport={column.id === "brief" ? onBulkExport : undefined}
          />
        ))}
      </div>

      {/* Drag Overlay - Rendered outside columns for smooth animation */}
      <DragOverlay dropAnimation={null}>
        {activeCard ? <KanbanCard card={activeCard} isDragOverlay /> : null}
      </DragOverlay>
    </DndContext>
  );
}

export default KanbanBoard;
