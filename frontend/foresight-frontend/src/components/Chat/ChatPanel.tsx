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
  Download,
  Check,
  GitFork,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useChat } from "../../hooks/useChat";
import { useChatKeyboard } from "../../hooks/useChatKeyboard";
import { useSpeechToText } from "../../hooks/useSpeechToText";
import { ChatMessage as ChatMessageComponent } from "./ChatMessage";
import { ChatSuggestionChips } from "./ChatSuggestionChips";
import { ChatHistoryPopover } from "./ChatHistoryPopover";
import { ChatMentionAutocomplete } from "./ChatMentionAutocomplete";
import type {
  ChatMention,
  Citation,
  SmartSuggestion,
  MentionResult,
} from "../../lib/chat-api";
import { fetchSmartSuggestions } from "../../lib/chat-api";

// ============================================================================
// Smart Suggestion Category Config
// ============================================================================

const CATEGORY_CONFIG: Record<
  string,
  { icon: string; borderColor: string; hoverBorder: string }
> = {
  deeper: {
    icon: "\u2315",
    borderColor: "border-l-blue-500",
    hoverBorder: "hover:border-blue-400 dark:hover:border-blue-500",
  },
  compare: {
    icon: "\u2194",
    borderColor: "border-l-purple-500",
    hoverBorder: "hover:border-purple-400 dark:hover:border-purple-500",
  },
  action: {
    icon: "\u2192",
    borderColor: "border-l-amber-500",
    hoverBorder: "hover:border-amber-400 dark:hover:border-amber-500",
  },
  explore: {
    icon: "\u25C8",
    borderColor: "border-l-teal-500",
    hoverBorder: "hover:border-teal-400 dark:hover:border-teal-500",
  },
};

// ============================================================================
// Types
// ============================================================================

export interface ChatPanelProps {
  /** The scope context for this chat session */
  scope: "signal" | "workstream" | "global" | "wizard" | "grant_assistant";
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
  /** Called when the active conversation changes (created or loaded) */
  onConversationChange?: (conversationId: string | null) => void;
  /** Skip auto-restoring the most recent conversation (user clicked "New Chat") */
  forceNew?: boolean;
  /** Default suggested questions shown in empty state when backend returns none */
  defaultSuggestedQuestions?: string[];
}

// ============================================================================
// Helpers
// ============================================================================

/**
 * Formats an ISO timestamp into a relative time string for the banner.
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

function scopeDisplayLabel(
  scope: "signal" | "workstream" | "global" | "wizard" | "grant_assistant",
): string {
  switch (scope) {
    case "signal":
      return "Signal";
    case "workstream":
      return "Workstream";
    case "wizard":
      return "Wizard";
    case "grant_assistant":
      return "Grant Search";
    case "global":
    default:
      return "Global";
  }
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
  placeholder = "Ask GrantScope about grants, funding opportunities, and deadlines...",
  emptyStateTitle = "Ask GrantScope",
  emptyStateDescription = "Ask questions about grants, funding opportunities, eligibility requirements, and more. GrantScope uses AI to synthesize intelligence from your data.",
  onCitationClick,
  initialConversationId,
  onConversationChange,
  forceNew,
  defaultSuggestedQuestions = [],
}: ChatPanelProps) {
  const {
    messages,
    isStreaming,
    streamingContent,
    streamingCitations,
    conversationId,
    conversationTitle,
    conversationUpdatedAt,
    suggestedQuestions,
    error,
    sendMessage,
    stopGenerating,
    loadConversation,
    startNewConversation,
    retryLastMessage,
    progressStep,
  } = useChat({ scope, scopeId, initialConversationId, forceNew });

  // Notify parent when conversationId changes
  useEffect(() => {
    onConversationChange?.(conversationId);
  }, [conversationId, onConversationChange]);

  // Input state
  const [inputValue, setInputValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const initialQuerySentRef = useRef(false);

  // Error dismiss
  const [errorDismissed, setErrorDismissed] = useState(false);

  // Smart suggestions state
  const [smartSuggestions, setSmartSuggestions] = useState<SmartSuggestion[]>(
    [],
  );
  const [smartSuggestionsLoading, setSmartSuggestionsLoading] = useState(false);
  const prevIsStreamingRef = useRef(false);

  // @mention autocomplete state
  const [mentionActive, setMentionActive] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionStartIndex, setMentionStartIndex] = useState(-1);
  const [mentionPosition, setMentionPosition] = useState({ top: 0, left: 0 });
  const inputWrapperRef = useRef<HTMLDivElement>(null);

  // Accumulated structured mention data for the current message draft
  const [activeMentions, setActiveMentions] = useState<ChatMention[]>([]);

  // "Continuing conversation" banner state
  const userHasSentMessage = useRef(false);
  const [showContinueBanner, setShowContinueBanner] = useState(false);
  const bannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [showForkNotice, setShowForkNotice] = useState(false);
  const forkTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [exported, setExported] = useState(false);
  const exportTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
  // "Continuing conversation" banner
  // ============================================================================

  // Show banner when conversation is auto-restored (messages exist on mount)
  // and user hasn't sent anything yet.
  useEffect(() => {
    if (
      messages.length > 0 &&
      !userHasSentMessage.current &&
      conversationTitle &&
      conversationUpdatedAt
    ) {
      setShowContinueBanner(true);

      // Auto-dismiss after 5 seconds
      bannerTimerRef.current = setTimeout(() => {
        setShowContinueBanner(false);
      }, 5000);
    }

    return () => {
      if (bannerTimerRef.current) {
        clearTimeout(bannerTimerRef.current);
        bannerTimerRef.current = null;
      }
    };
    // Only trigger on initial load — when conversationTitle/updatedAt become available
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationTitle, conversationUpdatedAt]);

  // ============================================================================
  // Smart Suggestions — fetch when streaming completes
  // ============================================================================

  useEffect(() => {
    const wasStreaming = prevIsStreamingRef.current;
    prevIsStreamingRef.current = isStreaming;

    // Detect transition: streaming just ended
    if (wasStreaming && !isStreaming && conversationId && messages.length > 0) {
      let cancelled = false;
      setSmartSuggestionsLoading(true);

      fetchSmartSuggestions(scope, scopeId, conversationId)
        .then((results) => {
          if (!cancelled && results.length > 0) {
            setSmartSuggestions(results);
          }
        })
        .catch(() => {
          // Silently fail — we fall back to regular suggestedQuestions
        })
        .finally(() => {
          if (!cancelled) setSmartSuggestionsLoading(false);
        });

      return () => {
        cancelled = true;
      };
    }
    return undefined;
  }, [isStreaming, conversationId, messages.length, scope, scopeId]);

  // Clear smart suggestions and active mentions when starting a new conversation
  useEffect(() => {
    if (messages.length === 0) {
      setSmartSuggestions([]);
      setActiveMentions([]);
    }
  }, [messages.length]);

  // ============================================================================
  // Handlers
  // ============================================================================

  const handleSubmit = useCallback(() => {
    if (!inputValue.trim() || isStreaming) return;
    sendMessage(
      inputValue.trim(),
      activeMentions.length > 0 ? activeMentions : undefined,
    );
    setInputValue("");
    setActiveMentions([]);
    setMentionActive(false);
    setShowForkNotice(false);

    // Mark that user has sent a message and dismiss the banner
    userHasSentMessage.current = true;
    setShowContinueBanner(false);
    if (bannerTimerRef.current) {
      clearTimeout(bannerTimerRef.current);
      bannerTimerRef.current = null;
    }

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [inputValue, isStreaming, sendMessage, activeMentions]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // When mention autocomplete is active, let it handle navigation keys
      if (mentionActive) {
        if (
          e.key === "ArrowDown" ||
          e.key === "ArrowUp" ||
          e.key === "Enter" ||
          e.key === "Tab" ||
          e.key === "Escape"
        ) {
          // These are handled by ChatMentionAutocomplete's document keydown listener
          return;
        }
      }

      // Enter to send (Shift+Enter for newline)
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit, mentionActive],
  );

  // --------------------------------------------------------------------------
  // @mention detection in input
  // --------------------------------------------------------------------------

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      const cursorPos = e.target.selectionStart ?? value.length;
      setInputValue(value);

      // Look backwards from cursor for an unmatched @ trigger
      const textBeforeCursor = value.slice(0, cursorPos);
      const lastAtIndex = textBeforeCursor.lastIndexOf("@");

      if (lastAtIndex >= 0) {
        const textAfterAt = textBeforeCursor.slice(lastAtIndex + 1);

        // Check that the @ is at the start or preceded by a space (not mid-word)
        const charBefore = lastAtIndex > 0 ? value[lastAtIndex - 1] : " ";
        const isValidTrigger =
          charBefore === " " || charBefore === "\n" || lastAtIndex === 0;

        // Check that there are no spaces that would indicate the user has
        // moved past the mention query, unless it looks like a multi-word search
        // Allow multi-word queries (up to ~60 chars)
        const isReasonableLength = textAfterAt.length <= 60;

        // If the text after @ contains a closing bracket, the mention is already completed
        const isAlreadyCompleted = textAfterAt.includes("]");

        if (isValidTrigger && isReasonableLength && !isAlreadyCompleted) {
          setMentionActive(true);
          setMentionQuery(textAfterAt);
          setMentionStartIndex(lastAtIndex);

          // Calculate position for the dropdown (above the input)
          if (inputWrapperRef.current) {
            const wrapperRect = inputWrapperRef.current.getBoundingClientRect();
            // Position at bottom-left of the input wrapper, dropdown appears above
            setMentionPosition({
              top: 4, // small gap above the input area
              left: Math.min(lastAtIndex * 8, wrapperRect.width - 288), // rough char width estimate
            });
          }
          return;
        }
      }

      // No active mention trigger
      if (mentionActive) {
        setMentionActive(false);
      }
    },
    [mentionActive],
  );

  const handleMentionSelect = useCallback(
    (mention: MentionResult) => {
      // Replace @query with @[Title] in the input
      const before = inputValue.slice(0, mentionStartIndex);
      const after = inputValue.slice(
        mentionStartIndex + 1 + mentionQuery.length,
      );
      const mentionText = `@[${mention.title}]`;
      const newValue = before + mentionText + (after || " ");

      setInputValue(newValue);
      setMentionActive(false);
      setMentionQuery("");
      setMentionStartIndex(-1);

      // Track the structured mention data for the API payload
      setActiveMentions((prev) => {
        // Avoid duplicates (same entity mentioned twice)
        if (prev.some((m) => m.id === mention.id)) return prev;
        return [
          ...prev,
          { id: mention.id, type: mention.type, title: mention.title },
        ];
      });

      // Refocus the textarea and position cursor after the mention
      requestAnimationFrame(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          const newCursorPos = before.length + mentionText.length + 1;
          textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
        }
      });
    },
    [inputValue, mentionStartIndex, mentionQuery],
  );

  const handleMentionClose = useCallback(() => {
    setMentionActive(false);
    setMentionQuery("");
    setMentionStartIndex(-1);
  }, []);

  const handleSuggestionSelect = useCallback(
    (question: string) => {
      sendMessage(question);
      setShowForkNotice(false);
    },
    [sendMessage],
  );

  const handleEditResend = useCallback(
    ({
      originalMessageId,
      editedContent,
    }: {
      originalMessageId?: string;
      editedContent: string;
    }): boolean => {
      // Intentional behavior: edited text is sent as a new correction message.
      // We do not mutate or truncate prior conversation history from originalMessageId.
      void originalMessageId;
      const trimmed = editedContent.trim();
      if (!trimmed || isStreaming) return false;
      sendMessage(trimmed);
      setShowForkNotice(false);
      userHasSentMessage.current = true;
      setShowContinueBanner(false);
      if (bannerTimerRef.current) {
        clearTimeout(bannerTimerRef.current);
        bannerTimerRef.current = null;
      }
      return true;
    },
    [isStreaming, sendMessage],
  );

  const handleForkConversation = useCallback(
    (assistantContent: string) => {
      const trimmed = assistantContent.trim();
      if (!trimmed) return;

      const prefix = "Branch context from previous reply:\n\n";
      const maxContentLength = 3600;
      const truncated = trimmed.slice(0, maxContentLength);

      startNewConversation();
      setActiveMentions([]);
      setMentionActive(false);
      setInputValue(`${prefix}${truncated}\n\n`);
      setShowForkNotice(true);

      if (forkTimerRef.current) {
        clearTimeout(forkTimerRef.current);
      }
      forkTimerRef.current = setTimeout(() => {
        setShowForkNotice(false);
      }, 5000);

      requestAnimationFrame(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          const end = textareaRef.current.value.length;
          textareaRef.current.setSelectionRange(end, end);
        }
      });
    },
    [startNewConversation],
  );

  const handleExportConversation = useCallback(() => {
    if (messages.length === 0) return;

    const title = conversationTitle?.trim() || "GrantScope Chat Transcript";
    const timestamp = new Date().toLocaleString();
    const lines: string[] = [
      `# ${title}`,
      "",
      `- Exported: ${timestamp}`,
      `- Scope: ${scopeDisplayLabel(scope)}`,
    ];

    if (scopeId) {
      lines.push(`- Scope ID: ${scopeId}`);
    }

    lines.push("");

    messages.forEach((message) => {
      const role = message.role === "assistant" ? "Assistant" : "User";
      const createdAt = message.created_at
        ? new Date(message.created_at).toLocaleString()
        : null;
      lines.push(
        `## ${role}${createdAt ? ` (${createdAt})` : ""}`,
        "",
        message.content || "_(empty message)_",
      );

      if (message.role === "assistant" && message.citations.length > 0) {
        lines.push("", "Sources:");
        message.citations.forEach((citation) => {
          const suffix = citation.url ? ` - ${citation.url}` : "";
          lines.push(`- [${citation.index}] ${citation.title}${suffix}`);
        });
      }

      lines.push("", "---", "");
    });

    const safeTitle = title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 48);
    const dateStamp = new Date().toISOString().slice(0, 10);
    const filename = `${safeTitle || "chat-transcript"}-${dateStamp}.md`;

    const blob = new Blob([lines.join("\n")], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    setExported(true);
    if (exportTimerRef.current) {
      clearTimeout(exportTimerRef.current);
    }
    exportTimerRef.current = setTimeout(() => {
      setExported(false);
    }, 2000);
  }, [messages, conversationTitle, scope, scopeId]);

  // ============================================================================
  // Keyboard Shortcuts
  // ============================================================================

  const handleCopyLastResponse = useCallback(() => {
    const lastAssistant = [...messages]
      .reverse()
      .find((m) => m.role === "assistant");
    if (lastAssistant) {
      navigator.clipboard.writeText(lastAssistant.content).catch(() => {});
    }
  }, [messages]);

  useChatKeyboard({
    onFocusInput: () => textareaRef.current?.focus(),
    onNewConversation: startNewConversation,
    onCopyLastResponse: handleCopyLastResponse,
    onStopGenerating: stopGenerating,
    isStreaming,
  });

  // ============================================================================
  // Voice Input (Speech-to-Text)
  // ============================================================================

  const {
    isListening,
    isSupported: isSpeechSupported,
    transcript,
    startListening,
    stopListening,
  } = useSpeechToText();

  // Append transcript to input when speech recognition produces a result
  useEffect(() => {
    if (transcript) {
      setInputValue((prev) => {
        const separator = prev && !prev.endsWith(" ") ? " " : "";
        return prev + separator + transcript;
      });
      // Auto-focus input so user can continue typing
      textareaRef.current?.focus();
    }
  }, [transcript]);

  const handleMicToggle = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const showEmptyState = messages.length === 0 && !isStreaming;
  const showError = error && !errorDismissed;

  // ============================================================================
  // Conversation switch crossfade
  // ============================================================================

  const [fadeIn, setFadeIn] = useState(true);
  const prevConversationIdRef = useRef(conversationId);

  useEffect(() => {
    const prevId = prevConversationIdRef.current;
    prevConversationIdRef.current = conversationId;

    // Only crossfade on actual conversation switches (both sides non-null),
    // not on the null→UUID transition that occurs when a new conversation
    // is auto-created by the streaming done event.
    if (prevId && conversationId && prevId !== conversationId) {
      setFadeIn(false);
      const timer = requestAnimationFrame(() => {
        setFadeIn(true);
      });
      return () => cancelAnimationFrame(timer);
    }
    return undefined;
  }, [conversationId]);

  useEffect(() => {
    return () => {
      if (forkTimerRef.current) {
        clearTimeout(forkTimerRef.current);
      }
      if (exportTimerRef.current) {
        clearTimeout(exportTimerRef.current);
      }
    };
  }, []);

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
            "relative z-40 flex items-center justify-between px-4 py-2",
            "border-b border-gray-200 dark:border-gray-700",
            "bg-white/80 dark:bg-dark-surface-deep/80 backdrop-blur-sm",
          )}
        >
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            Chat
          </span>
          <div className="flex items-center gap-1">
            <ChatHistoryPopover
              scope={scope}
              scopeId={scopeId}
              activeConversationId={conversationId}
              onSelect={loadConversation}
              onNewChat={startNewConversation}
            />
            <button
              type="button"
              onClick={handleExportConversation}
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md",
                "text-gray-600 dark:text-gray-400",
                "hover:bg-gray-100 dark:hover:bg-dark-surface-hover",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue",
                "transition-colors duration-200",
              )}
              aria-label={
                exported ? "Conversation exported" : "Export conversation"
              }
              title="Export full chat"
            >
              {exported ? (
                <Check className="h-3.5 w-3.5 text-brand-green" />
              ) : (
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              Export
            </button>
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
        </div>
      )}

      {/* Forked conversation notice */}
      {showForkNotice && (
        <div
          className={cn(
            "flex items-center gap-1.5 px-4 py-1.5",
            "bg-emerald-50/80 dark:bg-emerald-900/20",
            "border-b border-emerald-100 dark:border-emerald-800/30",
            "text-xs text-emerald-700 dark:text-emerald-300",
            "animate-in fade-in-0 slide-in-from-top-1 duration-200",
          )}
        >
          <GitFork className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>
            Forked from the selected reply. Edit the branch context and send.
          </span>
        </div>
      )}

      {/* "Continuing conversation" banner */}
      {showContinueBanner && conversationTitle && conversationUpdatedAt && (
        <div
          className={cn(
            "flex items-center justify-between px-4 py-1.5",
            "bg-blue-50/80 dark:bg-blue-900/15",
            "border-b border-blue-100 dark:border-blue-800/30",
            "animate-in fade-in-0 slide-in-from-top-1 duration-200",
          )}
        >
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
            <span>Continuing from </span>
            <span className="text-gray-600 dark:text-gray-300">
              {formatRelativeTime(conversationUpdatedAt)}
            </span>
            <span className="mx-1">&middot;</span>
            <span className="text-gray-600 dark:text-gray-300 font-medium">
              {conversationTitle.length > 40
                ? conversationTitle.slice(0, 40).trimEnd() + "\u2026"
                : conversationTitle}
            </span>
          </p>
          <button
            type="button"
            onClick={() => {
              setShowContinueBanner(false);
              if (bannerTimerRef.current) {
                clearTimeout(bannerTimerRef.current);
                bannerTimerRef.current = null;
              }
              startNewConversation();
            }}
            className={cn(
              "shrink-0 ml-2 text-xs font-medium",
              "text-brand-blue hover:text-brand-dark-blue",
              "dark:text-blue-400 dark:hover:text-blue-300",
              "hover:underline focus:outline-none focus:underline",
              "transition-colors duration-150",
            )}
          >
            Start new
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
          "transition-opacity duration-200",
          fadeIn ? "opacity-100" : "opacity-0",
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
            {(suggestedQuestions.length > 0 ||
              defaultSuggestedQuestions.length > 0) && (
              <div className="mt-6 w-full max-w-lg">
                <ChatSuggestionChips
                  suggestions={
                    suggestedQuestions.length > 0
                      ? suggestedQuestions
                      : defaultSuggestedQuestions
                  }
                  onSelect={handleSuggestionSelect}
                />
              </div>
            )}

            {/* Keyboard shortcut hint */}
            <p className="mt-4 text-[10px] text-gray-300 dark:text-gray-600">
              Press{" "}
              <kbd className="px-1 py-0.5 rounded bg-gray-100 dark:bg-dark-surface text-gray-500 dark:text-gray-400 font-mono">
                /
              </kbd>{" "}
              to focus
            </p>
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
              onEditResend={handleEditResend}
              onForkConversation={handleForkConversation}
              isConversationStreaming={isStreaming}
            />
          </div>
        ))}

        {/* Interrupted response note */}
        {messages.length > 0 &&
          messages[messages.length - 1]?.id?.startsWith("temp-partial-") &&
          !isStreaming && (
            <div className="mt-2 ml-10 text-xs text-gray-400 dark:text-gray-500 italic">
              Response was interrupted.{" "}
              <button
                type="button"
                onClick={retryLastMessage}
                className="text-brand-blue hover:underline focus:outline-none"
              >
                Retry
              </button>
            </div>
          )}

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

        {/* Progress / Thinking indicator */}
        {isStreaming && !streamingContent && (
          <div className="mt-4 flex items-start gap-2 text-sm text-gray-500 dark:text-gray-400">
            <div
              className={cn(
                "flex items-center justify-center w-6 h-6 rounded-full shrink-0",
                "bg-brand-blue/10 dark:bg-brand-blue/20",
              )}
            >
              <Sparkles
                className="h-3.5 w-3.5 text-brand-blue"
                aria-hidden="true"
              />
            </div>
            <div className="flex flex-col gap-1">
              {progressStep ? (
                <div className="flex items-center gap-1.5">
                  <Loader2
                    className="h-3.5 w-3.5 animate-spin text-brand-blue"
                    aria-hidden="true"
                  />
                  <span className="text-sm">{progressStep.detail}</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  <Loader2
                    className="h-3.5 w-3.5 animate-spin text-brand-blue"
                    aria-hidden="true"
                  />
                  <span>GrantScope is thinking...</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Progress during streaming (show step above content) */}
        {isStreaming &&
          streamingContent &&
          progressStep &&
          progressStep.step === "citing" && (
            <div className="mt-2 mb-1 flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
              <span>{progressStep.detail}</span>
            </div>
          )}

        {/* Post-response suggestions: smart categorized chips or inline fallback.
            Priority: smart suggestions (if loaded) > inline SSE suggestions > skeleton (only if no inline available) */}
        {!isStreaming && messages.length > 0 && (
          <div className="mt-4">
            {smartSuggestions.length > 0 ? (
              <div
                className="flex flex-wrap gap-2"
                role="list"
                aria-label="Smart follow-up suggestions"
              >
                {smartSuggestions.map((suggestion, index) => {
                  const defaultConfig = {
                    icon: "\u2315",
                    borderColor: "border-l-blue-500",
                    hoverBorder:
                      "hover:border-blue-400 dark:hover:border-blue-500",
                  };
                  const config =
                    CATEGORY_CONFIG[suggestion.category] ?? defaultConfig;
                  return (
                    <button
                      key={`${suggestion.category}-${suggestion.text}`}
                      type="button"
                      role="listitem"
                      onClick={() => handleSuggestionSelect(suggestion.text)}
                      className={cn(
                        "inline-flex items-center gap-1.5",
                        "px-3.5 py-2 rounded-lg",
                        "text-sm text-gray-700 dark:text-gray-300",
                        "border border-gray-200 dark:border-gray-600",
                        "border-l-[3px]",
                        config.borderColor,
                        "bg-white dark:bg-dark-surface",
                        "hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                        config.hoverBorder,
                        "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-1",
                        "transition-all duration-200",
                        "animate-in fade-in-0 slide-in-from-bottom-1 duration-300",
                        "cursor-pointer",
                      )}
                      style={{
                        animationDelay: `${index * 60}ms`,
                        animationFillMode: "both",
                      }}
                    >
                      <span
                        className="text-xs font-medium text-gray-400 dark:text-gray-500 shrink-0 w-4 text-center"
                        aria-hidden="true"
                      >
                        {config.icon}
                      </span>
                      <span className="text-left">{suggestion.text}</span>
                    </button>
                  );
                })}
              </div>
            ) : suggestedQuestions.length > 0 ? (
              /* Show inline SSE suggestions immediately — don't wait for smart suggestions */
              <ChatSuggestionChips
                suggestions={suggestedQuestions}
                onSelect={handleSuggestionSelect}
              />
            ) : smartSuggestionsLoading ? (
              /* Only show skeleton when NO inline suggestions are available */
              <div
                className="flex flex-wrap gap-2"
                aria-label="Loading suggestions"
              >
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className={cn(
                      "h-9 rounded-lg animate-pulse",
                      "bg-gray-200 dark:bg-dark-surface-elevated",
                      i === 1 ? "w-52" : i === 2 ? "w-60" : "w-44",
                    )}
                    aria-hidden="true"
                  />
                ))}
              </div>
            ) : null}
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
          <div className="flex-1">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => {
                retryLastMessage();
                setErrorDismissed(true);
              }}
              className={cn(
                "ml-2 text-xs font-medium",
                "text-brand-blue hover:text-brand-dark-blue dark:text-blue-400 dark:hover:text-blue-300",
                "hover:underline focus:outline-none focus:underline",
              )}
            >
              Retry
            </button>
          </div>
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
          ref={inputWrapperRef}
          className={cn(
            "relative",
            "flex items-end gap-2",
            "bg-gray-50 dark:bg-dark-surface",
            "border border-gray-200 dark:border-gray-600",
            "rounded-xl",
            "focus-within:ring-2 focus-within:ring-brand-blue focus-within:border-transparent",
            "transition-all duration-200",
            compact ? "px-3 py-2" : "px-4 py-3",
          )}
        >
          {/* @mention autocomplete dropdown */}
          {mentionActive && mentionQuery.length > 0 && (
            <ChatMentionAutocomplete
              query={mentionQuery}
              position={mentionPosition}
              onSelect={handleMentionSelect}
              onClose={handleMentionClose}
            />
          )}

          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleInputChange}
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
            aria-label="Chat message input. Type @ to mention opportunities or workstreams."
          />

          <div className="flex items-center gap-1.5 shrink-0">
            {/* Voice input button */}
            {isSpeechSupported && !isStreaming && (
              <button
                type="button"
                onClick={handleMicToggle}
                className={cn(
                  "inline-flex items-center justify-center",
                  "w-8 h-8 rounded-lg",
                  "focus:outline-none focus:ring-2 focus:ring-offset-1",
                  "transition-colors duration-200",
                  isListening
                    ? [
                        "bg-red-500 text-white",
                        "hover:bg-red-600",
                        "focus:ring-red-400",
                        "animate-pulse",
                      ]
                    : [
                        "text-gray-400 dark:text-gray-500",
                        "hover:text-gray-600 dark:hover:text-gray-300",
                        "hover:bg-gray-200/60 dark:hover:bg-gray-700/60",
                        "focus:ring-brand-blue",
                      ],
                )}
                aria-label={
                  isListening ? "Stop voice input" : "Start voice input"
                }
                title={isListening ? "Stop voice input" : "Voice input"}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                  aria-hidden="true"
                >
                  <rect x="9" y="1" width="6" height="12" rx="3" />
                  <path d="M5 10a7 7 0 0 0 14 0" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                </svg>
              </button>
            )}

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
