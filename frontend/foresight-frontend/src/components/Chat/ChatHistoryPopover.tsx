/**
 * ChatHistoryPopover Component
 *
 * A dropdown popover that shows recent chat conversations for the current scope.
 * Triggered by a clock/history icon button. Allows switching between conversations
 * or starting a new one.
 *
 * @module components/Chat/ChatHistoryPopover
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Clock, Plus, Loader2, MessageSquare } from "lucide-react";
import { cn } from "../../lib/utils";
import { fetchConversations, type Conversation } from "../../lib/chat-api";

// ============================================================================
// Types
// ============================================================================

export interface ChatHistoryPopoverProps {
  /** The scope context for fetching conversations */
  scope: "signal" | "workstream" | "global" | "wizard" | "grant_assistant";
  /** ID of the scoped entity (card_id or workstream_id), if not global */
  scopeId?: string;
  /** Currently active conversation ID, used to highlight the active item */
  activeConversationId?: string | null;
  /** Called when the user selects a conversation from the list */
  onSelect: (conversationId: string) => void;
  /** Called when the user clicks "New Chat" */
  onNewChat: () => void;
}

// ============================================================================
// Helpers
// ============================================================================

/**
 * Formats an ISO timestamp into a human-friendly relative time string.
 * Examples: "just now", "5m ago", "2h ago", "3d ago"
 */
function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return "just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return "";
  }
}

/**
 * Truncates a string to the specified max length, appending an ellipsis if needed.
 */
function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trimEnd() + "\u2026";
}

// ============================================================================
// Component
// ============================================================================

export function ChatHistoryPopover({
  scope,
  scopeId,
  activeConversationId,
  onSelect,
  onNewChat,
}: ChatHistoryPopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // --------------------------------------------------------------------------
  // Fetch conversations when opened
  // --------------------------------------------------------------------------

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    try {
      const data = await fetchConversations({
        scope,
        scope_id: scopeId,
        limit: 10,
      });
      setConversations(data);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, [scope, scopeId]);

  useEffect(() => {
    if (isOpen) {
      loadHistory();
    }
  }, [isOpen, loadHistory]);

  // --------------------------------------------------------------------------
  // Close on click outside or Escape
  // --------------------------------------------------------------------------

  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(e: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setIsOpen(false);
        buttonRef.current?.focus();
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  // --------------------------------------------------------------------------
  // Handlers
  // --------------------------------------------------------------------------

  const handleToggle = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  const handleSelect = useCallback(
    (conversationId: string) => {
      onSelect(conversationId);
      setIsOpen(false);
    },
    [onSelect],
  );

  const handleNewChat = useCallback(() => {
    onNewChat();
    setIsOpen(false);
  }, [onNewChat]);

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="relative">
      {/* Trigger button */}
      <button
        ref={buttonRef}
        type="button"
        onClick={handleToggle}
        className={cn(
          "inline-flex items-center justify-center",
          "w-7 h-7 rounded-md",
          "text-gray-500 dark:text-gray-400",
          "hover:bg-gray-100 dark:hover:bg-dark-surface-hover",
          "focus:outline-none focus:ring-2 focus:ring-brand-blue",
          "transition-colors duration-200",
          isOpen && "bg-gray-100 dark:bg-dark-surface-hover",
        )}
        aria-label="Chat history"
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
      </button>

      {/* Popover dropdown */}
      {isOpen && (
        <div
          ref={popoverRef}
          className={cn(
            "absolute right-0 top-full mt-1 z-50",
            "w-72 max-h-80",
            "bg-white dark:bg-dark-surface-elevated",
            "border border-gray-200 dark:border-gray-700",
            "rounded-lg shadow-lg",
            "flex flex-col",
            "animate-in fade-in-0 zoom-in-95 duration-150",
          )}
          role="menu"
          aria-label="Recent conversations"
        >
          {/* Header with New Chat */}
          <div
            className={cn(
              "flex items-center justify-between px-3 py-2",
              "border-b border-gray-100 dark:border-gray-700",
            )}
          >
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Recent Chats
            </span>
            <button
              type="button"
              onClick={handleNewChat}
              className={cn(
                "inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md",
                "text-brand-blue",
                "hover:bg-brand-blue/10 dark:hover:bg-brand-blue/20",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue",
                "transition-colors duration-200",
              )}
              role="menuitem"
            >
              <Plus className="h-3 w-3" aria-hidden="true" />
              New Chat
            </button>
          </div>

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto py-1">
            {isLoading && (
              <div className="flex items-center justify-center py-6">
                <Loader2
                  className="h-4 w-4 animate-spin text-gray-400 dark:text-gray-500"
                  aria-hidden="true"
                />
                <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">
                  Loading...
                </span>
              </div>
            )}

            {loadError && !isLoading && (
              <div className="px-3 py-4 text-center">
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  Failed to load conversations.
                </p>
                <button
                  type="button"
                  onClick={loadHistory}
                  className="mt-1 text-xs text-brand-blue hover:underline focus:outline-none"
                >
                  Retry
                </button>
              </div>
            )}

            {!isLoading && !loadError && conversations.length === 0 && (
              <div className="px-3 py-6 text-center">
                <MessageSquare
                  className="h-5 w-5 mx-auto text-gray-300 dark:text-gray-600 mb-1.5"
                  aria-hidden="true"
                />
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  No conversations yet.
                </p>
              </div>
            )}

            {!isLoading &&
              !loadError &&
              conversations.map((conv) => {
                const isActive = conv.id === activeConversationId;
                const title = conv.title
                  ? truncate(conv.title, 45)
                  : "Untitled conversation";
                const timeAgo = formatRelativeTime(conv.updated_at);

                return (
                  <button
                    key={conv.id}
                    type="button"
                    onClick={() => handleSelect(conv.id)}
                    className={cn(
                      "w-full text-left px-3 py-2 flex items-start gap-2",
                      "hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                      "focus:outline-none focus:bg-gray-50 dark:focus:bg-dark-surface-hover",
                      "transition-colors duration-150",
                      isActive &&
                        "bg-brand-blue/5 dark:bg-brand-blue/10 border-l-2 border-brand-blue",
                    )}
                    role="menuitem"
                    aria-current={isActive ? "true" : undefined}
                  >
                    <MessageSquare
                      className={cn(
                        "h-3.5 w-3.5 mt-0.5 shrink-0",
                        isActive
                          ? "text-brand-blue"
                          : "text-gray-400 dark:text-gray-500",
                      )}
                      aria-hidden="true"
                    />
                    <div className="flex-1 min-w-0">
                      <p
                        className={cn(
                          "text-sm leading-snug truncate",
                          isActive
                            ? "font-medium text-brand-blue dark:text-blue-400"
                            : "text-gray-700 dark:text-gray-300",
                        )}
                      >
                        {title}
                      </p>
                      <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                        {timeAgo}
                      </p>
                    </div>
                  </button>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatHistoryPopover;
