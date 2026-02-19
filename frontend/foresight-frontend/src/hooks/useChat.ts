/**
 * useChat Hook
 *
 * Manages chat state including messages, streaming responses, conversation
 * lifecycle, and suggested questions. Designed for use with the ChatPanel
 * component across global, signal, and workstream scopes.
 *
 * @module hooks/useChat
 */

import { useState, useRef, useCallback, useEffect } from "react";
import {
  sendChatMessage,
  parseSSEStream,
  fetchConversation,
  fetchConversations,
  fetchSuggestions,
  fetchChatStats,
  type ChatMessage,
  type ChatMention,
  type Citation,
} from "../lib/chat-api";

// ============================================================================
// Types
// ============================================================================

export interface UseChatOptions {
  /** The scope context for this chat session */
  scope: "signal" | "workstream" | "global" | "wizard" | "grant_assistant";
  /** ID of the scoped entity (card_id or workstream_id), if not global */
  scopeId?: string;
  /** Resume an existing conversation by ID */
  initialConversationId?: string;
  /** Skip auto-restoring the most recent conversation (e.g., user clicked "New Chat") */
  forceNew?: boolean;
}

export interface UseChatReturn {
  /** Committed messages in the conversation */
  messages: ChatMessage[];
  /** Whether the assistant is currently streaming a response */
  isStreaming: boolean;
  /** Accumulated text content being streamed */
  streamingContent: string;
  /** Citations received during the current stream */
  streamingCitations: Citation[];
  /** The active conversation ID, or null for a new conversation */
  conversationId: string | null;
  /** Title of the active conversation, if loaded */
  conversationTitle: string | null;
  /** ISO 8601 timestamp when the active conversation was last updated */
  conversationUpdatedAt: string | null;
  /** Contextual question suggestions */
  suggestedQuestions: string[];
  /** Current error message, if any */
  error: string | null;
  /** Send a user message and begin streaming the assistant response */
  sendMessage: (message: string, mentions?: ChatMention[]) => Promise<void>;
  /** Abort the current streaming response */
  stopGenerating: () => void;
  /** Load an existing conversation by ID */
  loadConversation: (conversationId: string) => Promise<void>;
  /** Clear messages and start a fresh conversation */
  startNewConversation: () => void;
  /** Fetch fresh suggested questions for the current scope */
  loadSuggestions: () => Promise<void>;
  /** Retry the last failed message */
  retryLastMessage: () => void;
  /** Current streaming progress step */
  progressStep: { step: string; detail: string } | null;
  /** Metadata about the last response (source counts, etc.) */
  responseMetadata: Record<string, unknown> | null;
  /** A rotating fun fact about the user's data */
  funFact: string | null;
}

// ============================================================================
// Default Suggested Questions
// ============================================================================

/**
 * Returns grant-focused default suggested questions based on chat scope.
 * Used as a fallback when the server doesn't return suggestions.
 */
function getDefaultSuggestedQuestions(scope: string): string[] {
  switch (scope) {
    case "global":
      return [
        "What grants are approaching their deadlines?",
        "Which programs have the highest alignment scores?",
        "Summarize the latest federal grant opportunities",
        "What's the total value of my grant pipeline?",
      ];
    case "workstream":
      return [
        "What are the top opportunities in this program?",
        "Which grants here have the nearest deadlines?",
        "Summarize the funding landscape for this program",
        "What eligibility requirements should I focus on?",
      ];
    case "signal":
      return [
        "What are the key eligibility requirements?",
        "How does this opportunity align with our strategic goals?",
        "What similar grants have been awarded recently?",
        "Summarize the application timeline and process",
      ];
    default:
      return [
        "What grants are approaching their deadlines?",
        "Which programs have the highest alignment scores?",
        "Summarize the latest federal grant opportunities",
        "What's the total value of my grant pipeline?",
      ];
  }
}

// ============================================================================
// Session Storage Helpers
// ============================================================================

function storageKey(scope: string, scopeId?: string): string {
  return `grantscope:chat:${scope}:${scopeId || "global"}`;
}

function persistConversationId(
  scope: string,
  scopeId: string | undefined,
  convId: string | null,
): void {
  const key = storageKey(scope, scopeId);
  try {
    if (convId) {
      sessionStorage.setItem(key, convId);
    } else {
      sessionStorage.removeItem(key);
    }
  } catch {
    // sessionStorage unavailable (SSR, private browsing quota)
  }
}

function restoreConversationId(scope: string, scopeId?: string): string | null {
  try {
    return sessionStorage.getItem(storageKey(scope, scopeId));
  } catch {
    return null;
  }
}

// ============================================================================
// Hook
// ============================================================================

export function useChat(options: UseChatOptions): UseChatReturn {
  const { scope, scopeId, initialConversationId, forceNew } = options;

  // Resolve starting conversation: explicit prop > sessionStorage > null
  // When forceNew is true, skip restoration entirely
  const resolvedInitialId = forceNew
    ? null
    : (initialConversationId ?? restoreConversationId(scope, scopeId));

  // Message state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);

  // Conversation state
  const [conversationId, setConversationId] = useState<string | null>(
    resolvedInitialId,
  );
  const [conversationTitle, setConversationTitle] = useState<string | null>(
    null,
  );
  const [conversationUpdatedAt, setConversationUpdatedAt] = useState<
    string | null
  >(null);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Fun fact for empty state
  const [funFact, setFunFact] = useState<string | null>(null);

  // Progress & metadata state
  const [progressStep, setProgressStep] = useState<{
    step: string;
    detail: string;
  } | null>(null);
  const [responseMetadata, setResponseMetadata] = useState<Record<
    string,
    unknown
  > | null>(null);

  // Refs for cleanup and abort
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);
  const lastFailedMessageRef = useRef<string | null>(null);

  // Track mount/unmount for safe state updates
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      // Abort any in-flight stream on unmount
      abortControllerRef.current?.abort();
    };
  }, []);

  // ============================================================================
  // Send Message
  // ============================================================================

  const sendMessage = useCallback(
    async (message: string, mentions?: ChatMention[]) => {
      if (!message.trim() || isStreaming) return;

      lastFailedMessageRef.current = message.trim();
      setError(null);
      setProgressStep(null);
      setResponseMetadata(null);

      // Add user message to the list immediately
      const userMessage: ChatMessage = {
        id: `temp-user-${Date.now()}`,
        role: "user",
        content: message.trim(),
        citations: [],
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsStreaming(true);
      setStreamingContent("");
      setStreamingCitations([]);
      setSuggestedQuestions([]);

      // Create a new abort controller for this request
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        const response = await sendChatMessage(
          {
            scope,
            scope_id: scopeId,
            message: message.trim(),
            conversation_id: conversationId ?? undefined,
            mentions: mentions?.length ? mentions : undefined,
          },
          abortController.signal,
        );

        // Accumulate tokens using a local variable for performance
        let accumulatedContent = "";
        const accumulatedCitations: Citation[] = [];

        await parseSSEStream(response, {
          onToken: (content) => {
            if (!isMountedRef.current) return;
            accumulatedContent += content;
            setStreamingContent(accumulatedContent);
          },

          onCitation: (citation) => {
            if (!isMountedRef.current) return;
            accumulatedCitations.push(citation);
            setStreamingCitations([...accumulatedCitations]);
          },

          onSuggestions: (suggestions) => {
            if (!isMountedRef.current) return;
            setSuggestedQuestions(suggestions);
          },

          onProgress: (data) => {
            if (!isMountedRef.current) return;
            setProgressStep(data);
          },

          onMetadata: (data) => {
            if (!isMountedRef.current) return;
            setResponseMetadata(data);
          },

          onDone: (data) => {
            if (!isMountedRef.current) return;

            lastFailedMessageRef.current = null;
            setProgressStep(null);

            // Set the conversation ID from the server response and persist
            if (data.conversation_id) {
              setConversationId(data.conversation_id);
              persistConversationId(scope, scopeId, data.conversation_id);
            }

            // Move streaming content into a committed assistant message
            const assistantMessage: ChatMessage = {
              id: data.message_id || `temp-assistant-${Date.now()}`,
              role: "assistant",
              content: accumulatedContent,
              citations: accumulatedCitations,
              created_at: new Date().toISOString(),
            };

            setMessages((prev) => [...prev, assistantMessage]);
            setStreamingContent("");
            setStreamingCitations([]);
            setIsStreaming(false);
          },

          onError: (errorMsg) => {
            if (!isMountedRef.current) return;
            setError(errorMsg);
            setProgressStep(null);
            setIsStreaming(false);
            setStreamingContent("");
            setStreamingCitations([]);
          },
        });
      } catch (err) {
        if (!isMountedRef.current) return;

        // Ignore abort errors (user cancelled)
        if (err instanceof DOMException && err.name === "AbortError") {
          // If there's partial content, commit it as an incomplete message
          setIsStreaming(false);
          return;
        }

        setError(err instanceof Error ? err.message : "Failed to send message");
        setProgressStep(null);
        setIsStreaming(false);
        setStreamingContent("");
        setStreamingCitations([]);
      } finally {
        if (abortControllerRef.current === abortController) {
          abortControllerRef.current = null;
        }
      }
    },
    [scope, scopeId, conversationId, isStreaming],
  );

  // ============================================================================
  // Stop Generating
  // ============================================================================

  const stopGenerating = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    // If we have partial streaming content, commit it as an incomplete message
    setStreamingContent((currentContent) => {
      if (currentContent) {
        setStreamingCitations((currentCitations) => {
          const partialMessage: ChatMessage = {
            id: `temp-partial-${Date.now()}`,
            role: "assistant",
            content: currentContent,
            citations: currentCitations,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, partialMessage]);
          return [];
        });
      }
      return "";
    });

    setIsStreaming(false);
  }, []);

  // ============================================================================
  // Load Conversation
  // ============================================================================

  const loadConversation = useCallback(
    async (convId: string) => {
      setError(null);

      try {
        const data = await fetchConversation(convId);
        if (!isMountedRef.current) return;

        setConversationId(data.conversation.id);
        setConversationTitle(data.conversation.title ?? null);
        setConversationUpdatedAt(data.conversation.updated_at ?? null);
        setMessages(data.messages);
        setSuggestedQuestions([]);
        persistConversationId(scope, scopeId, data.conversation.id);
      } catch {
        if (!isMountedRef.current) return;
        // If the stored conversation was deleted, clear it and start fresh
        persistConversationId(scope, scopeId, null);
        setConversationId(null);
        setError(null);
      }
    },
    [scope, scopeId],
  );

  // ============================================================================
  // Start New Conversation
  // ============================================================================

  const startNewConversation = useCallback(() => {
    // Abort any active stream
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    setMessages([]);
    setConversationId(null);
    setConversationTitle(null);
    setConversationUpdatedAt(null);
    setStreamingContent("");
    setStreamingCitations([]);
    setIsStreaming(false);
    setError(null);
    setSuggestedQuestions([]);
    persistConversationId(scope, scopeId, null);
  }, [scope, scopeId]);

  // ============================================================================
  // Load Suggestions
  // ============================================================================

  const loadSuggestions = useCallback(async () => {
    try {
      const suggestions = await fetchSuggestions(scope, scopeId);
      if (!isMountedRef.current) return;
      setSuggestedQuestions(
        suggestions.length > 0
          ? suggestions
          : getDefaultSuggestedQuestions(scope),
      );
    } catch {
      // Suggestions are non-critical — fall back to defaults
      if (isMountedRef.current) {
        setSuggestedQuestions(getDefaultSuggestedQuestions(scope));
      }
    }
  }, [scope, scopeId]);

  // ============================================================================
  // Retry Last Message
  // ============================================================================

  const retryLastMessage = useCallback(() => {
    if (!lastFailedMessageRef.current) return;
    const msg = lastFailedMessageRef.current;
    // Remove the failed user message from the list (last user message)
    setMessages((prev) => {
      let lastUserIdx = -1;
      for (let j = prev.length - 1; j >= 0; j--) {
        if (prev[j]?.role === "user") {
          lastUserIdx = j;
          break;
        }
      }
      if (lastUserIdx >= 0) {
        return prev.slice(0, lastUserIdx);
      }
      return prev;
    });
    setError(null);
    // Re-send
    sendMessage(msg);
  }, [sendMessage]);

  // ============================================================================
  // Effects
  // ============================================================================

  // On mount: restore conversation from prop → sessionStorage → backend (most recent)
  // When forceNew is set, skip restoration and show blank chat with suggestions.
  useEffect(() => {
    let cancelled = false;

    async function restore() {
      // User explicitly requested a fresh chat
      if (forceNew) {
        setSuggestedQuestions(getDefaultSuggestedQuestions(scope));
        loadSuggestions();
        fetchChatStats()
          .then((data) => {
            if (data.facts.length > 0) {
              setFunFact(
                data.facts[Math.floor(Math.random() * data.facts.length)] ??
                  null,
              );
            }
          })
          .catch(() => {});
        return;
      }

      if (resolvedInitialId) {
        // Fast path: we already have a conversation ID (prop or sessionStorage)
        await loadConversation(resolvedInitialId);
        return;
      }

      // Slow path: query the backend for the most recent conversation in this scope
      try {
        const conversations = await fetchConversations({
          scope,
          scope_id: scopeId,
          limit: 1,
        });
        if (cancelled || !isMountedRef.current) return;

        if (conversations.length > 0 && conversations[0]) {
          await loadConversation(conversations[0].id);
        } else {
          // No prior conversations — show suggestions
          setSuggestedQuestions(getDefaultSuggestedQuestions(scope));
          loadSuggestions();
          fetchChatStats()
            .then((data) => {
              if (data.facts.length > 0) {
                setFunFact(
                  data.facts[Math.floor(Math.random() * data.facts.length)] ??
                    null,
                );
              }
            })
            .catch(() => {});
        }
      } catch {
        // Failed to fetch — fall back to empty state with suggestions
        if (!cancelled && isMountedRef.current) {
          setSuggestedQuestions(getDefaultSuggestedQuestions(scope));
          loadSuggestions();
          fetchChatStats()
            .then((data) => {
              if (data.facts.length > 0) {
                setFunFact(
                  data.facts[Math.floor(Math.random() * data.facts.length)] ??
                    null,
                );
              }
            })
            .catch(() => {});
        }
      }
    }

    restore();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
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
    loadSuggestions,
    retryLastMessage,
    progressStep,
    responseMetadata,
    funFact,
  };
}
