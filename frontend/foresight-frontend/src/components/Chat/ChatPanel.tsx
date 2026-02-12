/**
 * ChatPanel Component
 *
 * The main reusable chat interface used across the /ask page, signal detail,
 * and workstream pages. Provides a complete chat experience with streaming
 * responses, suggested questions, and error handling.
 *
 * @module components/Chat/ChatPanel
 */

import React, { useRef, useEffect, useState, useCallback } from "react";
import {
  Send,
  StopCircle,
  Plus,
  AlertCircle,
  X,
  Sparkles,
  Loader2,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useChat } from "../../hooks/useChat";
import { ChatMessage as ChatMessageComponent } from "./ChatMessage";
import { ChatSuggestionChips } from "./ChatSuggestionChips";
import type { Citation } from "../../lib/chat-api";

// ============================================================================
// Types
// ============================================================================

export interface ChatPanelProps {
  /** The scope context for this chat session */
  scope: "signal" | "workstream" | "global";
  /** ID of the scoped entity (card_id or workstream_id), if not global */
  scopeId?: string;
  /** Additional CSS classes to apply to the root element */
  className?: string;
  /** Compact mode for slide-out panels */
  compact?: boolean;
  /** Pre-fill and auto-send this query on mount */
  initialQuery?: string;
  /** Custom placeholder for the input */
  placeholder?: string;
  /** Title shown in the empty state */
  emptyStateTitle?: string;
  /** Description shown below the empty state title */
  emptyStateDescription?: string;
  /** Callback when a citation is clicked */
  onCitationClick?: (citation: Citation) => void;
  /** Resume an existing conversation by ID */
  initialConversationId?: string;
}

// ============================================================================
// Component
// ============================================================================

export function ChatPanel({
  scope,
  scopeId,
  className,
  compact = false,
  initialQuery,
  placeholder = "Ask Foresight about signals, trends, and strategy...",
  emptyStateTitle = "Ask Foresight",
  emptyStateDescription = "Ask questions about signals, emerging trends, strategic priorities, and more. Foresight uses AI to synthesize intelligence from your data.",
  onCitationClick,
  initialConversationId,
}: ChatPanelProps) {
  const {
    messages,
    isStreaming,
    streamingContent,
    streamingCitations,
    suggestedQuestions,
    error,
    sendMessage,
    stopGenerating,
    startNewConversation,
  } = useChat({ scope, scopeId, initialConversationId });

  // Input state
  const [inputValue, setInputValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const initialQuerySentRef = useRef(false);

  // Error dismiss
  const [errorDismissed, setErrorDismissed] = useState(false);

  // ============================================================================
  // Auto-scroll
  // ============================================================================

  const scrollToBottom = useCallback((smooth = true) => {
    messagesEndRef.current?.scrollIntoView({
      behavior: smooth ? "smooth" : "auto",
    });
  }, []);

  // Scroll to bottom on new committed messages (smooth)
  useEffect(() => {
    scrollToBottom(true);
  }, [messages, scrollToBottom]);

  // Scroll to bottom during streaming (instant, throttled)
  useEffect(() => {
    if (!streamingContent) return;
    const id = requestAnimationFrame(() => scrollToBottom(false));
    return () => cancelAnimationFrame(id);
  }, [streamingContent, scrollToBottom]);

  // ============================================================================
  // Auto-grow textarea
  // ============================================================================

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Reset height to auto to measure scrollHeight correctly
    textarea.style.height = "auto";
    // Set to scrollHeight, capped at a max height
    const maxHeight = compact ? 120 : 160;
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
  }, [inputValue, compact]);

  // ============================================================================
  // Auto-send initial query
  // ============================================================================

  useEffect(() => {
    if (initialQuery && !initialQuerySentRef.current) {
      initialQuerySentRef.current = true;
      sendMessage(initialQuery);
    }
  }, [initialQuery, sendMessage]);

  // ============================================================================
  // Reset error dismissed when error changes
  // ============================================================================

  useEffect(() => {
    if (error) {
      setErrorDismissed(false);
    }
  }, [error]);

  // ============================================================================
  // Handlers
  // ============================================================================

  const handleSubmit = useCallback(() => {
    if (!inputValue.trim() || isStreaming) return;
    sendMessage(inputValue.trim());
    setInputValue("");

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [inputValue, isStreaming, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter to send (Shift+Enter for newline)
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const handleSuggestionSelect = useCallback(
    (question: string) => {
      sendMessage(question);
    },
    [sendMessage],
  );

  const showEmptyState = messages.length === 0 && !isStreaming;
  const showError = error && !errorDismissed;

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div
      className={cn(
        "flex flex-col h-full",
        "bg-white dark:bg-dark-surface-deep",
        className,
      )}
    >
      {/* Header bar for new conversation */}
      {messages.length > 0 && (
        <div
          className={cn(
            "flex items-center justify-between px-4 py-2",
            "border-b border-gray-200 dark:border-gray-700",
            "bg-white/80 dark:bg-dark-surface-deep/80 backdrop-blur-sm",
          )}
        >
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            Chat
          </span>
          <button
            type="button"
            onClick={startNewConversation}
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md",
              "text-gray-600 dark:text-gray-400",
              "hover:bg-gray-100 dark:hover:bg-dark-surface-hover",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue",
              "transition-colors duration-200",
            )}
            aria-label="Start new conversation"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            New Chat
          </button>
        </div>
      )}

      {/* Messages area */}
      <div
        ref={messagesContainerRef}
        className={cn(
          "flex-1 overflow-y-auto",
          compact ? "px-3 py-3" : "px-4 py-4 sm:px-6",
          "scroll-smooth",
        )}
      >
        {/* Empty state */}
        {showEmptyState && (
          <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-center">
            <div
              className={cn(
                "flex items-center justify-center w-12 h-12 rounded-full mb-4",
                "bg-brand-blue/10 dark:bg-brand-blue/20",
              )}
            >
              <Sparkles
                className="h-6 w-6 text-brand-blue"
                aria-hidden="true"
              />
            </div>
            <h3
              className={cn(
                "font-semibold text-gray-900 dark:text-gray-100",
                compact ? "text-base" : "text-lg",
              )}
            >
              {emptyStateTitle}
            </h3>
            <p
              className={cn(
                "mt-2 text-gray-500 dark:text-gray-400 max-w-md",
                compact ? "text-xs" : "text-sm",
              )}
            >
              {emptyStateDescription}
            </p>

            {/* Suggestion chips in empty state */}
            {suggestedQuestions.length > 0 && (
              <div className="mt-6 w-full max-w-lg">
                <ChatSuggestionChips
                  suggestions={suggestedQuestions}
                  onSelect={handleSuggestionSelect}
                />
              </div>
            )}
          </div>
        )}

        {/* Message list */}
        {messages.map((message, index) => (
          <div
            key={message.id}
            className={cn(
              "animate-in fade-in-0 slide-in-from-bottom-2 duration-300",
              index > 0 && "mt-4",
            )}
            style={{ animationDelay: `${Math.min(index * 50, 200)}ms` }}
          >
            <ChatMessageComponent
              message={message}
              onCitationClick={onCitationClick}
            />
          </div>
        ))}

        {/* Streaming response */}
        {isStreaming && streamingContent && (
          <div className="mt-4 animate-in fade-in-0 duration-200">
            <ChatMessageComponent
              message={{
                role: "assistant",
                content: streamingContent,
                citations: streamingCitations,
              }}
              isStreaming
              onCitationClick={onCitationClick}
            />
          </div>
        )}

        {/* Thinking indicator */}
        {isStreaming && !streamingContent && (
          <div className="mt-4 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <div className="flex items-center gap-1.5">
              <div
                className={cn(
                  "flex items-center justify-center w-6 h-6 rounded-full",
                  "bg-brand-blue/10 dark:bg-brand-blue/20",
                )}
              >
                <Sparkles
                  className="h-3.5 w-3.5 text-brand-blue"
                  aria-hidden="true"
                />
              </div>
              <Loader2
                className="h-4 w-4 animate-spin text-brand-blue"
                aria-hidden="true"
              />
              <span>Foresight is thinking...</span>
            </div>
          </div>
        )}

        {/* Post-response suggestions */}
        {!isStreaming &&
          messages.length > 0 &&
          suggestedQuestions.length > 0 && (
            <div className="mt-4">
              <ChatSuggestionChips
                suggestions={suggestedQuestions}
                onSelect={handleSuggestionSelect}
              />
            </div>
          )}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Error banner */}
      {showError && (
        <div
          className={cn(
            "mx-4 mb-2 flex items-start gap-2 px-3 py-2.5 rounded-lg",
            "bg-red-50 dark:bg-red-900/20",
            "border border-red-200 dark:border-red-800",
            "text-sm text-red-700 dark:text-red-400",
          )}
          role="alert"
        >
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span className="flex-1">{error}</span>
          <button
            type="button"
            onClick={() => setErrorDismissed(true)}
            className={cn(
              "p-0.5 rounded",
              "text-red-400 hover:text-red-600 dark:hover:text-red-300",
              "hover:bg-red-100 dark:hover:bg-red-800/30",
              "focus:outline-none focus:ring-1 focus:ring-red-400",
              "transition-colors duration-200",
            )}
            aria-label="Dismiss error"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Input area */}
      <div
        className={cn(
          "border-t border-gray-200 dark:border-gray-700",
          "bg-white dark:bg-dark-surface-deep",
          compact ? "px-3 py-3" : "px-4 py-3 sm:px-6",
        )}
      >
        <div
          className={cn(
            "flex items-end gap-2",
            "bg-gray-50 dark:bg-dark-surface",
            "border border-gray-200 dark:border-gray-600",
            "rounded-xl",
            "focus-within:ring-2 focus-within:ring-brand-blue focus-within:border-transparent",
            "transition-all duration-200",
            compact ? "px-3 py-2" : "px-4 py-3",
          )}
        >
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            maxLength={4000}
            disabled={isStreaming}
            className={cn(
              "flex-1 resize-none bg-transparent",
              "text-sm text-gray-900 dark:text-gray-100",
              "placeholder-gray-400 dark:placeholder-gray-500",
              "focus:outline-none",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
            aria-label="Chat message input"
          />

          <div className="flex items-center gap-1.5 shrink-0">
            {/* Keyboard shortcut hint */}
            <span
              className={cn(
                "hidden sm:inline text-[10px] text-gray-400 dark:text-gray-500",
                "whitespace-nowrap",
              )}
            >
              Enter to send
            </span>

            {/* Send / Stop button */}
            {isStreaming ? (
              <button
                type="button"
                onClick={stopGenerating}
                className={cn(
                  "inline-flex items-center justify-center",
                  "w-8 h-8 rounded-lg",
                  "bg-red-500 text-white",
                  "hover:bg-red-600",
                  "focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-1",
                  "transition-colors duration-200",
                )}
                aria-label="Stop generating"
              >
                <StopCircle className="h-4 w-4" aria-hidden="true" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!inputValue.trim()}
                className={cn(
                  "inline-flex items-center justify-center",
                  "w-8 h-8 rounded-lg",
                  "bg-brand-blue text-white",
                  "hover:bg-brand-dark-blue",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-1",
                  "disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-brand-blue",
                  "transition-colors duration-200",
                )}
                aria-label="Send message"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatPanel;
