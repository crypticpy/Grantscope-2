/**
 * CreateSignalModal Component
 *
 * A modal dialog for creating new intelligence signals. Provides two
 * creation modes via tabbed navigation:
 *
 * - **Quick Create**: Enter a topic phrase and let AI generate the full card.
 * - **Manual Create**: Fill out all fields manually with full control.
 *
 * Uses a custom overlay-based modal (no Radix Dialog dependency required).
 * Includes keyboard accessibility (Escape to close, focus trapping).
 *
 * @example
 * ```tsx
 * const [isOpen, setIsOpen] = useState(false);
 *
 * <CreateSignalModal
 *   isOpen={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   workstreamId="ws-abc-123"
 * />
 * ```
 *
 * @module CreateSignal/CreateSignalModal
 */

import React, { useState, useCallback, useEffect, useRef } from "react";
import { X, Zap, PenTool } from "lucide-react";
import { cn } from "../../lib/utils";
import { QuickCreateTab } from "./QuickCreateTab";
import { ManualCreateTab } from "./ManualCreateTab";

// =============================================================================
// Types
// =============================================================================

export interface CreateSignalModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Optional pre-selected workstream ID (passed to QuickCreateTab) */
  workstreamId?: string;
}

/** Tab identifiers */
type TabId = "quick" | "manual";

/** Tab configuration */
interface TabConfig {
  id: TabId;
  label: string;
  icon: React.ElementType;
  description: string;
}

// =============================================================================
// Constants
// =============================================================================

const TABS: TabConfig[] = [
  {
    id: "quick",
    label: "Quick Create",
    icon: Zap,
    description: "Enter a topic and let AI do the rest",
  },
  {
    id: "manual",
    label: "Manual Create",
    icon: PenTool,
    description: "Full control over all signal fields",
  },
];

// =============================================================================
// Component
// =============================================================================

/**
 * CreateSignalModal provides a modal dialog with two tabs for creating
 * new intelligence signals. Handles overlay behavior, keyboard events,
 * and clean state reset on close.
 */
export function CreateSignalModal({
  isOpen,
  onClose,
  workstreamId,
}: CreateSignalModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>("quick");
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  /**
   * Reset tab to default when modal opens.
   */
  useEffect(() => {
    if (isOpen) {
      setActiveTab("quick");
      // Focus the close button on open for keyboard accessibility
      requestAnimationFrame(() => {
        closeButtonRef.current?.focus();
      });
    }
  }, [isOpen]);

  /**
   * Handle keyboard events: Escape to close, Tab trapping.
   */
  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }

      // Simple focus trap
      if (e.key === "Tab" && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  /**
   * Prevent body scroll when modal is open.
   */
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  /**
   * Handle overlay click to close (only when clicking the backdrop).
   */
  const handleOverlayClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [onClose],
  );

  if (!isOpen) return null;

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-start justify-center",
        "bg-black/50 dark:bg-black/70",
        "backdrop-blur-sm",
        "overflow-y-auto py-8 sm:py-16",
      )}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-signal-title"
    >
      <div
        ref={modalRef}
        className={cn(
          "relative w-full max-w-lg mx-4",
          "bg-white dark:bg-[#1e2158]",
          "rounded-xl shadow-2xl",
          "border border-gray-200 dark:border-gray-700",
          "animate-in fade-in-0 zoom-in-95 duration-200",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2
            id="create-signal-title"
            className="text-lg font-semibold text-gray-900 dark:text-gray-100"
          >
            Create Signal
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className={cn(
              "p-1.5 rounded-md",
              "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
              "hover:bg-gray-100 dark:hover:bg-gray-700",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue",
              "transition-colors duration-150",
            )}
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="px-6 pt-4">
          <div
            className="flex rounded-lg bg-gray-100 dark:bg-[#2d3166] p-1"
            role="tablist"
            aria-label="Signal creation method"
          >
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  aria-controls={`tabpanel-${tab.id}`}
                  id={`tab-${tab.id}`}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md",
                    "transition-all duration-150",
                    "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-inset",
                    isActive
                      ? "bg-white dark:bg-[#3d4176] text-gray-900 dark:text-gray-100 shadow-sm"
                      : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300",
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Tab description */}
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 text-center">
            {TABS.find((t) => t.id === activeTab)?.description}
          </p>
        </div>

        {/* Tab Content */}
        <div className="px-6 py-5">
          {/* Quick Create Panel */}
          <div
            id="tabpanel-quick"
            role="tabpanel"
            aria-labelledby="tab-quick"
            hidden={activeTab !== "quick"}
          >
            {activeTab === "quick" && (
              <QuickCreateTab workstreamId={workstreamId} />
            )}
          </div>

          {/* Manual Create Panel */}
          <div
            id="tabpanel-manual"
            role="tabpanel"
            aria-labelledby="tab-manual"
            hidden={activeTab !== "manual"}
          >
            {activeTab === "manual" && <ManualCreateTab />}
          </div>
        </div>
      </div>
    </div>
  );
}

export default CreateSignalModal;
