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
  fetchSuggestions,
  type ChatMessage,
  type Citation,
} from "../lib/chat-api";

// ============================================================================
// Types
// ============================================================================

export interface UseChatOptions {
  /** The scope context for this chat session */
  scope: "signal" | "workstream" | "global";
  /** ID of the scoped entity (card_id or workstream_id), if not global */
  scopeId?: string;
  /** Resume an existing conversation by ID */
  initialConversationId?: string;
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
  /** Contextual question suggestions */
  suggestedQuestions: string[];
  /** Current error message, if any */
  error: string | null;
  /** Send a user message and begin streaming the assistant response */
  sendMessage: (message: string) => Promise<void>;
  /** Abort the current streaming response */
  stopGenerating: () => void;
  /** Load an existing conversation by ID */
  loadConversation: (conversationId: string) => Promise<void>;
  /** Clear messages and start a fresh conversation */
  startNewConversation: () => void;
  /** Fetch fresh suggested questions for the current scope */
  loadSuggestions: () => Promise<void>;
}

// ============================================================================
// Hook
// ============================================================================

export function useChat(options: UseChatOptions): UseChatReturn {
  const { scope, scopeId, initialConversationId } = options;

  // Message state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);

  // Conversation state
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversationId ?? null,
  );
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Refs for cleanup and abort
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);

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
    async (message: string) => {
      if (!message.trim() || isStreaming) return;

      setError(null);

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

          onDone: (data) => {
            if (!isMountedRef.current) return;

            // Set the conversation ID from the server response
            if (data.conversation_id) {
              setConversationId(data.conversation_id);
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

  const loadConversation = useCallback(async (convId: string) => {
    setError(null);

    try {
      const data = await fetchConversation(convId);
      if (!isMountedRef.current) return;

      setConversationId(data.conversation.id);
      setMessages(data.messages);
      setSuggestedQuestions([]);
    } catch (err) {
      if (!isMountedRef.current) return;
      setError(
        err instanceof Error ? err.message : "Failed to load conversation",
      );
    }
  }, []);

  // ============================================================================
  // Start New Conversation
  // ============================================================================

  const startNewConversation = useCallback(() => {
    // Abort any active stream
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    setMessages([]);
    setConversationId(null);
    setStreamingContent("");
    setStreamingCitations([]);
    setIsStreaming(false);
    setError(null);
    setSuggestedQuestions([]);
  }, []);

  // ============================================================================
  // Load Suggestions
  // ============================================================================

  const loadSuggestions = useCallback(async () => {
    try {
      const suggestions = await fetchSuggestions(scope, scopeId);
      if (!isMountedRef.current) return;
      setSuggestedQuestions(suggestions);
    } catch {
      // Suggestions are non-critical, fail silently
    }
  }, [scope, scopeId]);

  // ============================================================================
  // Effects
  // ============================================================================

  // Auto-load suggestions on mount if no messages exist
  useEffect(() => {
    if (messages.length === 0 && !initialConversationId) {
      loadSuggestions();
    }
  }, [messages.length, initialConversationId, loadSuggestions]);

  // Load initial conversation if provided
  useEffect(() => {
    if (initialConversationId) {
      loadConversation(initialConversationId);
    }
  }, [initialConversationId, loadConversation]);

  return {
    messages,
    isStreaming,
    streamingContent,
    streamingCitations,
    conversationId,
    suggestedQuestions,
    error,
    sendMessage,
    stopGenerating,
    loadConversation,
    startNewConversation,
    loadSuggestions,
  };
}
