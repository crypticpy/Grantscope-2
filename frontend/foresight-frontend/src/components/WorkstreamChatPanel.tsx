/**
 * WorkstreamChatPanel Component
 *
 * A slide-out panel that renders a ChatPanel scoped to a specific workstream.
 * Provides an AI chat interface for asking questions about the signals, trends,
 * and strategic themes in a research stream.
 *
 * Features:
 * - Slide-out animation from the right edge of the screen
 * - Mobile backdrop overlay with click-to-close
 * - Escape key to close
 * - Dark mode support
 * - Responsive width (full on mobile, 420px on larger screens)
 *
 * @module components/WorkstreamChatPanel
 */

import React, { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "../lib/utils";
import { ChatPanel } from "./Chat/ChatPanel";

/**
 * Props for the WorkstreamChatPanel component
 */
export interface WorkstreamChatPanelProps {
  /** UUID of the workstream to scope the chat to */
  workstreamId: string;
  /** Display name of the workstream for header and placeholder */
  workstreamName: string;
  /** Whether the panel is currently open */
  isOpen: boolean;
  /** Callback when the panel should be closed */
  onClose: () => void;
}

/**
 * WorkstreamChatPanel renders a slide-out chat panel for workstream-scoped AI chat.
 *
 * @example
 * ```tsx
 * const [chatOpen, setChatOpen] = useState(false);
 *
 * <WorkstreamChatPanel
 *   workstreamId={workstream.id}
 *   workstreamName={workstream.name}
 *   isOpen={chatOpen}
 *   onClose={() => setChatOpen(false)}
 * />
 * ```
 */
export function WorkstreamChatPanel({
  workstreamId,
  workstreamName,
  isOpen,
  onClose,
}: WorkstreamChatPanelProps) {
  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={cn(
          "fixed top-0 right-0 h-full z-50 bg-white dark:bg-dark-surface-deep",
          "border-l border-gray-200 dark:border-gray-700",
          "shadow-2xl transition-transform duration-300 ease-in-out",
          "w-full sm:w-[420px]",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <div>
            <h3 className="font-semibold text-sm text-gray-900 dark:text-white">
              Chat with Workstream
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[300px]">
              {workstreamName}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-dark-surface-hover transition-colors"
            aria-label="Close chat panel"
          >
            <X className="h-4 w-4 text-gray-500" />
          </button>
        </div>

        {/* Chat content */}
        <div className="h-[calc(100%-3.5rem)]">
          <ChatPanel
            scope="workstream"
            scopeId={workstreamId}
            compact
            placeholder={`Ask about ${workstreamName}...`}
            emptyStateTitle="Chat with this workstream"
            emptyStateDescription="Ask questions about the signals, trends, and strategic themes in this research stream."
          />
        </div>
      </div>
    </>
  );
}

export default WorkstreamChatPanel;
