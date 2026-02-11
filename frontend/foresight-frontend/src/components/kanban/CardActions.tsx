/**
 * CardActions Component
 *
 * A dropdown menu providing contextual actions for workstream kanban cards.
 * Includes navigation, notes editing, deep dive requests, column moves, and removal.
 *
 * Features:
 * - View card details navigation
 * - Add/edit notes with modal dialog
 * - Request deep dive analysis
 * - Move card to different kanban columns
 * - Remove card from workstream
 * - Dark mode support
 * - Keyboard navigation and accessibility
 */

import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  memo,
  useMemo,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  MoreVertical,
  Eye,
  StickyNote,
  ArrowRight,
  Trash2,
  X,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { cn } from "../../lib/utils";
import {
  KANBAN_COLUMNS,
  type KanbanStatus,
  type WorkstreamCard,
  type ColumnAction,
} from "./types";

// =============================================================================
// Types
// =============================================================================

export interface CardActionsProps {
  /** The workstream card to show actions for */
  card: WorkstreamCard;
  /** The parent workstream ID (for context) */
  workstreamId: string;
  /** Current column the card is in - determines available actions */
  columnId: KanbanStatus;
  /** Callback when notes are updated */
  onNotesUpdate: (cardId: string, notes: string) => void;
  /** Callback when deep dive is requested */
  onDeepDive: (cardId: string) => void;
  /** Callback when card is removed from workstream */
  onRemove: (cardId: string) => void;
  /** Callback when card is moved to a different column */
  onMoveToColumn: (cardId: string, status: KanbanStatus) => void;
  /** Callback for quick update action (screening column) */
  onQuickUpdate?: (cardId: string) => Promise<void>;
  /** Callback for export action (card export) */
  onExport?: (cardId: string, format: "pdf" | "pptx") => Promise<void>;
  /** Callback for exporting executive brief (brief column) */
  onExportBrief?: (cardId: string, format: "pdf" | "pptx") => Promise<void>;
  /** Callback for check updates action (watching column) */
  onCheckUpdates?: (cardId: string) => Promise<void>;
  /** Callback for generating an executive brief (brief column) */
  onGenerateBrief?: (workstreamCardId: string, cardId: string) => void;
}

// =============================================================================
// Notes Modal Component
// =============================================================================

interface NotesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (notes: string) => void;
  initialNotes: string;
  cardName: string;
  isSaving?: boolean;
}

/**
 * NotesModal - Modal dialog for adding/editing card notes.
 *
 * Provides a textarea for notes input with save/cancel actions.
 */
const NotesModal = memo(function NotesModal({
  isOpen,
  onClose,
  onSave,
  initialNotes,
  cardName,
  isSaving = false,
}: NotesModalProps) {
  const [notes, setNotes] = useState(initialNotes);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const saveButtonRef = useRef<HTMLButtonElement>(null);

  // Reset notes when modal opens with new initial value
  useEffect(() => {
    if (isOpen) {
      setNotes(initialNotes);
      // Focus textarea after brief delay for animation
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [isOpen, initialNotes]);

  // Focus trap - keep focus within modal
  useEffect(() => {
    if (!isOpen) return;

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;

      const focusableElements = modalRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );

      if (!focusableElements || focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    };

    document.addEventListener("keydown", handleTabKey);
    return () => document.removeEventListener("keydown", handleTabKey);
  }, [isOpen]);

  // Handle escape key to close
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isSaving) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, isSaving, onClose]);

  // Handle save
  const handleSave = useCallback(() => {
    onSave(notes.trim());
  }, [notes, onSave]);

  // Handle keyboard shortcut (Cmd/Ctrl + Enter to save)
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !isSaving) {
        e.preventDefault();
        handleSave();
      }
    },
    [handleSave, isSaving],
  );

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="notes-modal-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={isSaving ? undefined : onClose}
        aria-hidden="true"
      />

      {/* Modal Content */}
      <div
        ref={modalRef}
        className="relative bg-white dark:bg-[#2d3166] rounded-lg shadow-xl w-full max-w-lg transform transition-all"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-600">
          <div className="flex items-center gap-2 min-w-0">
            <StickyNote className="h-5 w-5 text-amber-500 shrink-0" />
            <h2
              id="notes-modal-title"
              className="text-lg font-semibold text-gray-900 dark:text-white truncate"
            >
              {initialNotes ? "Edit Notes" : "Add Notes"}
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-md transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Card Name Reference */}
          <div className="text-sm text-gray-600 dark:text-gray-400">
            <span className="font-medium">Signal:</span>{" "}
            <span className="text-gray-900 dark:text-white">{cardName}</span>
          </div>

          {/* Notes Textarea */}
          <div>
            <label
              htmlFor="card-notes"
              className="block text-sm font-medium text-gray-900 dark:text-white mb-2"
            >
              Notes
            </label>
            <textarea
              ref={textareaRef}
              id="card-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Add your notes about this signal..."
              disabled={isSaving}
              rows={6}
              className={cn(
                "w-full px-3 py-2 border rounded-md shadow-sm text-sm resize-none",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue",
                "dark:bg-[#3d4176] dark:text-white dark:placeholder-gray-400",
                "border-gray-300 bg-white dark:border-gray-600",
                "disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            />
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Press Cmd/Ctrl + Enter to save
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-600">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-[#3d4176] border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            ref={saveButtonRef}
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className={cn(
              "inline-flex items-center px-4 py-2 text-sm font-medium text-white rounded-md",
              "focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166]",
              "transition-colors",
              isSaving
                ? "bg-brand-blue/60 cursor-not-allowed"
                : "bg-brand-blue hover:bg-brand-dark-blue",
            )}
            aria-busy={isSaving}
          >
            {isSaving && (
              <Loader2
                className="h-4 w-4 mr-2 animate-spin"
                aria-hidden="true"
              />
            )}
            {isSaving ? "Saving..." : "Save Notes"}
          </button>
        </div>
      </div>
    </div>
  );
});

// =============================================================================
// Move Submenu Component
// =============================================================================

interface MoveSubmenuProps {
  currentStatus: KanbanStatus;
  onMove: (status: KanbanStatus) => void;
}

/**
 * MoveSubmenu - Submenu showing available columns to move card to.
 */
const MoveSubmenu = memo(function MoveSubmenu({
  currentStatus,
  onMove,
}: MoveSubmenuProps) {
  return (
    <div className="py-1">
      {KANBAN_COLUMNS.map((column) => {
        const isCurrentColumn = column.id === currentStatus;

        return (
          <button
            key={column.id}
            onClick={() => {
              if (!isCurrentColumn) {
                onMove(column.id);
              }
            }}
            disabled={isCurrentColumn}
            className={cn(
              "w-full flex items-center gap-2 px-4 py-2 text-sm text-left transition-colors",
              isCurrentColumn
                ? "text-gray-400 dark:text-gray-500 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50"
                : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700",
            )}
          >
            <span className="flex-1">{column.title}</span>
            {isCurrentColumn && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                (current)
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
});

// =============================================================================
// Main Component
// =============================================================================

/**
 * CardActions - Dropdown menu with contextual actions for a kanban card.
 *
 * Provides a three-dot menu button that opens a dropdown with various
 * card management actions including navigation, notes, moves, and removal.
 * Shows column-specific actions based on which column the card is in.
 */
export const CardActions = memo(function CardActions({
  card,
  workstreamId: _workstreamId,
  columnId,
  onNotesUpdate,
  onDeepDive,
  onRemove,
  onMoveToColumn,
  onQuickUpdate,
  onExport,
  onExportBrief,
  onCheckUpdates,
  onGenerateBrief,
}: CardActionsProps) {
  const navigate = useNavigate();

  // Dropdown state
  const [isOpen, setIsOpen] = useState(false);
  const [showMoveSubmenu, setShowMoveSubmenu] = useState(false);
  const [_focusedIndex, setFocusedIndex] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuItemsRef = useRef<(HTMLButtonElement | null)[]>([]);

  // Notes modal state
  const [isNotesModalOpen, setIsNotesModalOpen] = useState(false);
  const [isSavingNotes, setIsSavingNotes] = useState(false);

  // Loading states for column-specific actions
  const [isQuickUpdating, setIsQuickUpdating] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isCheckingUpdates, setIsCheckingUpdates] = useState(false);

  // Screen reader announcement for loading states
  const [srAnnouncement, setSrAnnouncement] = useState("");

  // Get column-specific actions
  const columnDefinition = useMemo(
    () => KANBAN_COLUMNS.find((col) => col.id === columnId),
    [columnId],
  );

  const columnActions = useMemo<ColumnAction[]>(() => {
    const actions: ColumnAction[] = [];
    if (columnDefinition?.primaryAction) {
      actions.push(columnDefinition.primaryAction);
    }
    if (columnDefinition?.secondaryActions) {
      actions.push(...columnDefinition.secondaryActions);
    }
    return actions;
  }, [columnDefinition]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setShowMoveSubmenu(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      switch (e.key) {
        case "Escape":
          setIsOpen(false);
          setShowMoveSubmenu(false);
          setFocusedIndex(-1);
          buttonRef.current?.focus();
          break;
        case "ArrowDown":
          e.preventDefault();
          setFocusedIndex((prev) => {
            const menuItems = menuItemsRef.current.filter(Boolean);
            const next = prev < menuItems.length - 1 ? prev + 1 : 0;
            menuItems[next]?.focus();
            return next;
          });
          break;
        case "ArrowUp":
          e.preventDefault();
          setFocusedIndex((prev) => {
            const menuItems = menuItemsRef.current.filter(Boolean);
            const next = prev > 0 ? prev - 1 : menuItems.length - 1;
            menuItems[next]?.focus();
            return next;
          });
          break;
        case "Home":
          e.preventDefault();
          setFocusedIndex(0);
          menuItemsRef.current[0]?.focus();
          break;
        case "End": {
          e.preventDefault();
          const menuItems = menuItemsRef.current.filter(Boolean);
          setFocusedIndex(menuItems.length - 1);
          menuItems[menuItems.length - 1]?.focus();
          break;
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Toggle dropdown
  const toggleDropdown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setIsOpen((prev) => !prev);
    setShowMoveSubmenu(false);
    setFocusedIndex(-1);
    menuItemsRef.current = [];
  }, []);

  // Handle view details
  const handleViewDetails = useCallback(() => {
    setIsOpen(false);
    navigate(`/signals/${card.card.slug}`);
  }, [navigate, card.card.slug]);

  // Handle notes action
  const handleNotesClick = useCallback(() => {
    setIsOpen(false);
    setIsNotesModalOpen(true);
  }, []);

  // Handle save notes
  const handleSaveNotes = useCallback(
    async (notes: string) => {
      setIsSavingNotes(true);
      try {
        await onNotesUpdate(card.id, notes);
        setIsNotesModalOpen(false);
      } finally {
        setIsSavingNotes(false);
      }
    },
    [card.id, onNotesUpdate],
  );

  // Handle deep dive
  const handleDeepDive = useCallback(() => {
    setIsOpen(false);
    onDeepDive(card.id);
  }, [card.id, onDeepDive]);

  // Handle quick update (screening column)
  const handleQuickUpdate = useCallback(async () => {
    if (!onQuickUpdate) return;
    setIsOpen(false);
    setIsQuickUpdating(true);
    setSrAnnouncement("Starting quick update...");
    try {
      await onQuickUpdate(card.id);
      setSrAnnouncement("Quick update completed");
    } catch {
      setSrAnnouncement("Quick update failed");
    } finally {
      setIsQuickUpdating(false);
    }
  }, [card.id, onQuickUpdate]);

  // Handle export
  // NOTE: Export requires the actual card UUID (card.card.id), not the junction table ID (card.id)
  // In the Brief column, use onExportBrief to export the executive brief content
  // In other columns, use onExport to export the original card
  const handleExport = useCallback(
    async (format: "pdf" | "pptx") => {
      // In Brief column, export the brief; otherwise export the card
      const exportFn = columnId === "brief" ? onExportBrief : onExport;
      if (!exportFn) return;

      setIsOpen(false);
      setIsExporting(true);
      const exportType = columnId === "brief" ? "Brief" : "";
      setSrAnnouncement(
        `Exporting ${exportType} as ${format.toUpperCase()}...`,
      );
      try {
        await exportFn(card.card.id, format);
        setSrAnnouncement(
          `${exportType} ${format.toUpperCase()} export completed`,
        );
      } catch {
        setSrAnnouncement(
          `${exportType} ${format.toUpperCase()} export failed`,
        );
      } finally {
        setIsExporting(false);
      }
    },
    [card.card.id, columnId, onExport, onExportBrief],
  );

  // Handle check updates (watching column)
  const handleCheckUpdates = useCallback(async () => {
    if (!onCheckUpdates) return;
    setIsOpen(false);
    setIsCheckingUpdates(true);
    setSrAnnouncement("Checking for updates...");
    try {
      await onCheckUpdates(card.id);
      setSrAnnouncement("Update check completed");
    } catch {
      setSrAnnouncement("Update check failed");
    } finally {
      setIsCheckingUpdates(false);
    }
  }, [card.id, onCheckUpdates]);

  // Handle generate brief (brief column)
  const handleGenerateBrief = useCallback(() => {
    if (!onGenerateBrief) return;
    setIsOpen(false);
    onGenerateBrief(card.id, card.card.id);
  }, [card.id, card.card.id, onGenerateBrief]);

  // Handle move to column
  const handleMoveToColumn = useCallback(
    (status: KanbanStatus) => {
      setIsOpen(false);
      setShowMoveSubmenu(false);
      onMoveToColumn(card.id, status);
    },
    [card.id, onMoveToColumn],
  );

  // Handle remove (must be defined before handleColumnAction which references it)
  const handleRemove = useCallback(() => {
    setIsOpen(false);
    onRemove(card.id);
  }, [card.id, onRemove]);

  // Generic action handler that routes to the correct function
  const handleColumnAction = useCallback(
    async (action: ColumnAction) => {
      switch (action.handler) {
        case "quickUpdate":
          await handleQuickUpdate();
          break;
        case "deepDive":
          handleDeepDive();
          break;
        case "exportPdf":
          await handleExport("pdf");
          break;
        case "exportPptx":
          await handleExport("pptx");
          break;
        case "checkUpdates":
          await handleCheckUpdates();
          break;
        case "viewDetails":
          handleViewDetails();
          break;
        case "addNotes":
          handleNotesClick();
          break;
        case "remove":
          handleRemove();
          break;
        case "generateBrief":
          handleGenerateBrief();
          break;
      }
    },
    [
      handleQuickUpdate,
      handleDeepDive,
      handleExport,
      handleCheckUpdates,
      handleViewDetails,
      handleNotesClick,
      handleRemove,
      handleGenerateBrief,
    ],
  );

  // Check if any column action is loading
  const isColumnActionLoading =
    isQuickUpdating || isExporting || isCheckingUpdates;

  // Toggle move submenu
  const toggleMoveSubmenu = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMoveSubmenu((prev) => !prev);
  }, []);

  const hasExistingNotes = card.notes && card.notes.trim().length > 0;

  return (
    <>
      {/* Dropdown Container */}
      <div className="relative" ref={dropdownRef}>
        {/* Trigger Button */}
        <button
          ref={buttonRef}
          onClick={toggleDropdown}
          className={cn(
            "p-1.5 rounded-md transition-colors",
            "text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300",
            "hover:bg-gray-100 dark:hover:bg-gray-700",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-1 dark:focus:ring-offset-gray-800",
            isOpen &&
              "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300",
          )}
          aria-label="Signal actions"
          aria-haspopup="true"
          aria-expanded={isOpen}
        >
          <MoreVertical className="h-4 w-4" />
        </button>

        {/* Dropdown Menu */}
        {isOpen && (
          <div
            className={cn(
              "absolute right-0 mt-1 w-52 z-50",
              "bg-white dark:bg-gray-800 rounded-lg shadow-lg",
              "border border-gray-200 dark:border-gray-700",
              "py-1 overflow-hidden",
            )}
            role="menu"
            aria-orientation="vertical"
          >
            {/* Column-Specific Actions (shown first if available) */}
            {columnActions.length > 0 && (
              <>
                {columnActions.map((action) => {
                  const Icon = action.icon;
                  const isLoading =
                    (action.handler === "quickUpdate" && isQuickUpdating) ||
                    (action.handler === "exportPdf" && isExporting) ||
                    (action.handler === "exportPptx" && isExporting) ||
                    (action.handler === "checkUpdates" && isCheckingUpdates);

                  return (
                    <button
                      key={action.id}
                      onClick={() => handleColumnAction(action)}
                      disabled={isColumnActionLoading}
                      className={cn(
                        "w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors",
                        "text-brand-blue dark:text-brand-light-blue",
                        "hover:bg-blue-50 dark:hover:bg-blue-900/20",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                      )}
                      role="menuitem"
                      title={action.description}
                    >
                      {isLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Icon className="h-4 w-4" />
                      )}
                      <span className="flex-1 text-left">{action.label}</span>
                      {action.description && (
                        <span className="text-xs text-gray-400 dark:text-gray-500 truncate max-w-[80px]">
                          {action.handler === "quickUpdate" && "5 sources"}
                          {action.handler === "deepDive" && "15 sources"}
                        </span>
                      )}
                    </button>
                  );
                })}
                {/* Divider after column-specific actions */}
                <div className="my-1 border-t border-gray-200 dark:border-gray-700" />
              </>
            )}

            {/* Universal Actions */}
            {/* View Details */}
            <button
              onClick={handleViewDetails}
              className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              role="menuitem"
            >
              <Eye className="h-4 w-4 text-gray-400 dark:text-gray-500" />
              View Details
            </button>

            {/* Add/Edit Notes */}
            <button
              onClick={handleNotesClick}
              className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              role="menuitem"
            >
              <StickyNote className="h-4 w-4 text-amber-500" />
              {hasExistingNotes ? "Edit Notes" : "Add Notes"}
            </button>

            {/* Divider */}
            <div className="my-1 border-t border-gray-200 dark:border-gray-700" />

            {/* Move to... */}
            <div className="relative">
              <button
                onClick={toggleMoveSubmenu}
                className="w-full flex items-center justify-between gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                role="menuitem"
                aria-haspopup="true"
                aria-expanded={showMoveSubmenu}
              >
                <span className="flex items-center gap-3">
                  <ArrowRight className="h-4 w-4 text-gray-400 dark:text-gray-500" />
                  Move to...
                </span>
                <ChevronRight
                  className={cn(
                    "h-4 w-4 text-gray-400 transition-transform",
                    showMoveSubmenu && "rotate-90",
                  )}
                />
              </button>

              {/* Move Submenu */}
              {showMoveSubmenu && (
                <div
                  className={cn(
                    "absolute left-full top-0 ml-1 w-44",
                    "bg-white dark:bg-gray-800 rounded-lg shadow-lg",
                    "border border-gray-200 dark:border-gray-700",
                    "overflow-hidden",
                  )}
                >
                  <MoveSubmenu
                    currentStatus={card.status}
                    onMove={handleMoveToColumn}
                  />
                </div>
              )}
            </div>

            {/* Divider */}
            <div className="my-1 border-t border-gray-200 dark:border-gray-700" />

            {/* Remove from Workstream */}
            <button
              onClick={handleRemove}
              className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
              role="menuitem"
            >
              <Trash2 className="h-4 w-4" />
              Remove from Workstream
            </button>
          </div>
        )}
      </div>

      {/* Notes Modal */}
      <NotesModal
        isOpen={isNotesModalOpen}
        onClose={() => setIsNotesModalOpen(false)}
        onSave={handleSaveNotes}
        initialNotes={card.notes || ""}
        cardName={card.card.name}
        isSaving={isSavingNotes}
      />

      {/* Screen reader announcements for loading states */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {srAnnouncement}
      </div>
    </>
  );
});

export default CardActions;
