/**
 * Kanban Types and Column Definitions
 *
 * Core type definitions for the workstream kanban board feature.
 * These types map to the backend API responses for workstream cards
 * and define the structure of the kanban workflow columns.
 */

import type { LucideIcon } from "lucide-react";
import { RefreshCw, Search, FileDown, Presentation, Bell } from "lucide-react";
import type { EmbeddedCard } from "../../types/card";

export type { EmbeddedCard };

// =============================================================================
// Status and Column Types
// =============================================================================

/**
 * Valid status values for kanban cards.
 * Maps to the workflow stages a research card can progress through.
 */
export type KanbanStatus =
  | "inbox"
  | "screening"
  | "research"
  | "brief"
  | "watching"
  | "archived";

/**
 * Describes how a card was added to a workstream.
 */
export type AddedFrom = "manual" | "auto" | "follow";

/**
 * Research status for a card in the workstream.
 * Tracks active or recently completed research tasks.
 */
export interface CardResearchStatus {
  /** Current research task status (queued, processing, completed, failed) */
  status: "queued" | "processing" | "completed" | "failed" | null;
  /** Task type (quick_update, deep_research) */
  task_type?: "quick_update" | "deep_research";
  /** ID of the research task for polling */
  task_id?: string;
  /** When research started */
  started_at?: string;
  /** When research completed */
  completed_at?: string;
}

/**
 * A card within a workstream kanban board.
 * Represents the junction between a workstream and a research card,
 * including workflow-specific metadata like status and position.
 */
export interface WorkstreamCard {
  /** Unique workstream-card junction identifier */
  id: string;
  /** Reference to the underlying card */
  card_id: string;
  /** Reference to the parent workstream */
  workstream_id: string;
  /** Current kanban column/status */
  status: KanbanStatus;
  /** Position within the column for ordering */
  position: number;
  /** User notes attached to this card in this workstream */
  notes: string | null;
  /** Optional reminder timestamp */
  reminder_at: string | null;
  /** How the card was added to the workstream */
  added_from: AddedFrom;
  /** Active research status for this card (populated from separate tracking) */
  research_status?: CardResearchStatus;
  /** Review status for content quality review workflow */
  review_status?: "pending_review" | "approved" | "rejected" | null;
  /** When the card was added to the workstream */
  added_at: string;
  /** Last update timestamp */
  updated_at: string;
  /** The embedded research card data */
  card: EmbeddedCard;
}

// =============================================================================
// Column Configuration
// =============================================================================

/**
 * Handler identifiers for column-specific actions.
 * Maps to actual handler functions in the component.
 */
export type ActionHandler =
  | "quickUpdate"
  | "deepDive"
  | "exportPdf"
  | "exportPptx"
  | "checkUpdates"
  | "viewDetails"
  | "addNotes"
  | "remove"
  | "generateBrief";

/**
 * Defines an action available on cards within a specific column.
 * Actions can be either always available or column-specific.
 */
export interface ColumnAction {
  /** Unique identifier for the action */
  id: string;
  /** Display label for the action button/menu item */
  label: string;
  /** Lucide icon component to display */
  icon: LucideIcon;
  /** Optional description for tooltips or expanded UI */
  description?: string;
  /** Handler identifier - maps to actual function */
  handler: ActionHandler;
  /** Whether this action is always available or column-specific */
  availability: "always" | "column-specific";
}

/**
 * Configuration for a kanban column.
 * Defines the column metadata and contains the cards within it.
 */
export interface KanbanColumn {
  /** Column identifier matching KanbanStatus */
  id: KanbanStatus;
  /** Display title for the column header */
  title: string;
  /** Description explaining the column's purpose */
  description: string;
  /** Cards currently in this column */
  cards: WorkstreamCard[];
}

/**
 * Column definition without cards.
 * Used for static column configuration.
 */
export interface KanbanColumnDefinition {
  /** Column identifier matching KanbanStatus */
  id: KanbanStatus;
  /** Display title for the column header */
  title: string;
  /** Description explaining the column's purpose */
  description: string;
  /** Primary action for this column (shown prominently) */
  primaryAction?: ColumnAction;
  /** Additional column-specific actions */
  secondaryActions?: ColumnAction[];
  /** Hint text shown in empty state */
  emptyStateHint?: string;
}

/**
 * Static column definitions for the kanban board.
 * Defines the workflow stages in their display order.
 * Each column can have primary and secondary actions specific to that workflow stage.
 */
export const KANBAN_COLUMNS: KanbanColumnDefinition[] = [
  {
    id: "inbox",
    title: "Inbox",
    description: "New signals matching your filters",
    emptyStateHint:
      "Signals matching your filters will appear here automatically",
    // No primary action - inbox is for triage
  },
  {
    id: "screening",
    title: "Screening",
    description: "Quick triage - is this relevant?",
    primaryAction: {
      id: "quick-update",
      label: "Quick Update",
      icon: RefreshCw,
      description: "Run a quick 5-source research update",
      handler: "quickUpdate",
      availability: "column-specific",
    },
    emptyStateHint: "Drag signals here to evaluate their relevance",
  },
  {
    id: "research",
    title: "Research",
    description: "Deep investigation in progress",
    primaryAction: {
      id: "deep-dive",
      label: "Deep Dive",
      icon: Search,
      description: "Run comprehensive 15-source research",
      handler: "deepDive",
      availability: "column-specific",
    },
    emptyStateHint: "Signals here are being actively researched",
  },
  {
    id: "brief",
    title: "Brief",
    description: "Ready to present to leadership",
    primaryAction: {
      id: "generate-brief",
      label: "Generate Brief",
      icon: FileDown,
      description: "Generate executive brief for this card",
      handler: "generateBrief",
      availability: "column-specific",
    },
    secondaryActions: [
      {
        id: "export-pdf",
        label: "Export Brief PDF",
        icon: FileDown,
        description: "Export brief as PDF document",
        handler: "exportPdf",
        availability: "column-specific",
      },
      {
        id: "export-pptx",
        label: "Export Brief PPTX",
        icon: Presentation,
        description: "Export brief as PowerPoint presentation",
        handler: "exportPptx",
        availability: "column-specific",
      },
    ],
    emptyStateHint: "Signals ready for leadership briefings",
  },
  {
    id: "watching",
    title: "Watching",
    description: "Monitoring for updates",
    primaryAction: {
      id: "check-updates",
      label: "Check for Updates",
      icon: Bell,
      description: "Search for recent developments",
      handler: "checkUpdates",
      availability: "column-specific",
    },
    emptyStateHint: "Signals here will be monitored for new developments",
  },
  {
    id: "archived",
    title: "Archived",
    description: "No longer active",
    emptyStateHint: "Completed or dismissed signals",
    // No primary action - archived cards are dormant
  },
];

// =============================================================================
// Callback Types
// =============================================================================

/**
 * Callback signature for when a card is moved between columns or reordered.
 *
 * @param cardId - The ID of the card being moved
 * @param newStatus - The target column status
 * @param newPosition - The new position index within the column
 */
export type OnCardMoveCallback = (
  cardId: string,
  newStatus: KanbanStatus,
  newPosition: number,
) => void;

/**
 * Callback signature for when a card is clicked.
 *
 * @param card - The workstream card that was clicked
 */
export type OnCardClickCallback = (card: WorkstreamCard) => void;

/**
 * Callback signature for when a card's notes are updated.
 *
 * @param cardId - The ID of the card
 * @param notes - The new notes content
 */
export type OnNotesUpdateCallback = (cardId: string, notes: string) => void;

/**
 * Callback signature for when a deep dive is requested.
 *
 * @param cardId - The ID of the card to request deep dive for
 */
export type OnDeepDiveCallback = (cardId: string) => void;

/**
 * Callback signature for when a card is removed from the workstream.
 *
 * @param cardId - The ID of the card to remove
 */
export type OnRemoveCardCallback = (cardId: string) => void;

/**
 * Callback signature for when a card is moved to a different column via menu.
 *
 * @param cardId - The ID of the card
 * @param status - The target column status
 */
export type OnMoveToColumnCallback = (
  cardId: string,
  status: KanbanStatus,
) => void;

/**
 * Callback signature for column-specific actions (Quick Update, Check Updates).
 *
 * @param cardId - The ID of the card
 */
export type OnQuickUpdateCallback = (cardId: string) => Promise<void>;

/**
 * Callback signature for exporting a card.
 *
 * @param cardId - The ID of the card
 * @param format - Export format (pdf or pptx)
 */
export type OnExportCallback = (
  cardId: string,
  format: "pdf" | "pptx",
) => Promise<void>;

/**
 * Callback signature for checking for updates on a card.
 *
 * @param cardId - The ID of the card
 */
export type OnCheckUpdatesCallback = (cardId: string) => Promise<void>;

/**
 * Callback signature for generating an executive brief.
 *
 * @param workstreamCardId - The ID of the workstream card (junction table ID)
 * @param cardId - The ID of the underlying research card
 */
export type OnGenerateBriefCallback = (
  workstreamCardId: string,
  cardId: string,
) => void;

/**
 * Combined card action callbacks for the kanban board.
 *
 * IMPORTANT: All `cardId` parameters in these callbacks refer to the
 * WorkstreamCard.id (the junction table ID), NOT the underlying card's UUID.
 * This is consistent with the workstream API endpoints which use the junction ID.
 */
export interface CardActionCallbacks {
  /** Callback when notes are updated */
  onNotesUpdate: OnNotesUpdateCallback;
  /** Callback when deep dive is requested */
  onDeepDive: OnDeepDiveCallback;
  /** Callback when card is removed from workstream */
  onRemove: OnRemoveCardCallback;
  /** Callback when card is moved to a different column */
  onMoveToColumn: OnMoveToColumnCallback;
  /** Callback for quick update action (screening column) */
  onQuickUpdate?: OnQuickUpdateCallback;
  /** Callback for export action (card export) */
  onExport?: OnExportCallback;
  /** Callback for exporting executive brief (brief column) */
  onExportBrief?: OnExportCallback;
  /** Callback for check updates action (watching column) */
  onCheckUpdates?: OnCheckUpdatesCallback;
  /** Callback for generating an executive brief (brief column) */
  onGenerateBrief?: OnGenerateBriefCallback;
  /** Callback for approving a card's review status */
  onApproveReview?: (cardId: string) => void;
}
