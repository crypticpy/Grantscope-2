/**
 * Chat API Client
 *
 * API functions for the Foresight chat system with SSE streaming support.
 * Handles sending messages, parsing server-sent events, managing conversations,
 * and fetching suggested questions.
 *
 * @module lib/chat-api
 */

import { supabase } from "../App";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ============================================================================
// Types
// ============================================================================

/**
 * A single chat message in a conversation.
 */
export interface ChatMessage {
  /** Unique message identifier (UUID) */
  id: string;
  /** Whether the message is from the user or the assistant */
  role: "user" | "assistant";
  /** The text content of the message */
  content: string;
  /** Citations referenced in the message */
  citations: Citation[];
  /** ISO 8601 timestamp when the message was created */
  created_at: string;
}

/**
 * A citation reference within an assistant message.
 * Links to either a card (signal) or an external source.
 */
export interface Citation {
  /** Display index for inline references like [1], [2] */
  index: number;
  /** UUID of the referenced card, if applicable */
  card_id?: string;
  /** Slug of the referenced card for URL-friendly navigation */
  card_slug?: string;
  /** UUID of the referenced source, if applicable */
  source_id?: string;
  /** Display title of the cited resource */
  title: string;
  /** URL to the external source, if applicable */
  url?: string;
  /** Brief excerpt from the cited content */
  excerpt?: string;
  /** ISO date string when the source was published */
  published_date?: string;
}

/**
 * A conversation session containing one or more message exchanges.
 */
export interface Conversation {
  /** Unique conversation identifier (UUID) */
  id: string;
  /** The scope context of this conversation */
  scope: "signal" | "workstream" | "global";
  /** ID of the scoped entity (card_id or workstream_id), if not global */
  scope_id?: string;
  /** Auto-generated or user-set title for the conversation */
  title?: string;
  /** ISO 8601 timestamp when the conversation was created */
  created_at: string;
  /** ISO 8601 timestamp when the conversation was last updated */
  updated_at: string;
}

/**
 * A server-sent event from the chat streaming endpoint.
 */
export interface SSEEvent {
  /** The type of event */
  type:
    | "token"
    | "citation"
    | "suggestions"
    | "done"
    | "error"
    | "progress"
    | "metadata";
  /** Text content for token events */
  content?: string;
  /** Structured data for citation, suggestions, done, and error events */
  data?: unknown;
}

// ============================================================================
// Auth Helper
// ============================================================================

/**
 * Retrieves the current auth token from Supabase session.
 *
 * @returns The access token string, or null if not authenticated
 */
async function getAuthToken(): Promise<string | null> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

// ============================================================================
// Streaming API
// ============================================================================

/**
 * Sends a chat message to the streaming endpoint.
 *
 * Returns the raw Response so the caller can read the SSE stream
 * via parseSSEStream(). The response body is a ReadableStream
 * of server-sent events.
 *
 * @param params - Message parameters including scope, message text, and optional conversation ID
 * @param signal - Optional AbortSignal to cancel the request
 * @returns The raw fetch Response for stream reading
 * @throws Error if authentication fails or the request errors
 */
export async function sendChatMessage(
  params: {
    scope: string;
    scope_id?: string;
    message: string;
    conversation_id?: string;
  },
  signal?: AbortSignal,
): Promise<Response> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required. Please sign in.");
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      scope: params.scope,
      scope_id: params.scope_id,
      message: params.message,
      conversation_id: params.conversation_id,
    }),
    signal,
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ message: "Chat request failed" }));
    throw new Error(
      error.message || error.detail || `Chat error: ${response.status}`,
    );
  }

  return response;
}

/**
 * Parses a Server-Sent Events stream from a fetch Response.
 *
 * Handles:
 * - Buffering partial lines when data arrives in chunks mid-line
 * - Empty lines between SSE events
 * - The "data: " prefix on each event line
 * - JSON parsing of event payloads
 * - Graceful handling of stream disconnects
 *
 * @param response - The fetch Response with a readable SSE body
 * @param callbacks - Event-specific callback handlers
 */
export async function parseSSEStream(
  response: Response,
  callbacks: {
    onToken: (content: string) => void;
    onCitation: (citation: Citation) => void;
    onSuggestions: (suggestions: string[]) => void;
    onDone: (data: { conversation_id: string; message_id: string }) => void;
    onError: (error: string) => void;
    /** Called when the backend reports a processing progress step */
    onProgress?: (data: { step: string; detail: string }) => void;
    /** Called when the backend sends response metadata (source counts, etc.) */
    onMetadata?: (data: Record<string, unknown>) => void;
  },
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError("Response body is not readable");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        // Process any remaining buffered data
        if (buffer.trim()) {
          processSSELine(buffer, callbacks);
        }
        break;
      }

      // Decode the chunk and add to buffer
      buffer += decoder.decode(value, { stream: true });

      // Process complete lines from the buffer
      const lines = buffer.split("\n");
      // Keep the last element as it may be an incomplete line
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        // Skip empty lines (SSE event separator)
        if (!trimmed) continue;
        processSSELine(trimmed, callbacks);
      }
    }
  } catch (err) {
    // AbortError is expected when user cancels
    if (err instanceof DOMException && err.name === "AbortError") {
      return;
    }
    callbacks.onError(
      err instanceof Error ? err.message : "Stream reading failed",
    );
  } finally {
    reader.releaseLock();
  }
}

/**
 * Processes a single SSE line and dispatches to the appropriate callback.
 *
 * @param line - A single line from the SSE stream
 * @param callbacks - Event-specific callback handlers
 */
function processSSELine(
  line: string,
  callbacks: {
    onToken: (content: string) => void;
    onCitation: (citation: Citation) => void;
    onSuggestions: (suggestions: string[]) => void;
    onDone: (data: { conversation_id: string; message_id: string }) => void;
    onError: (error: string) => void;
    onProgress?: (data: { step: string; detail: string }) => void;
    onMetadata?: (data: Record<string, unknown>) => void;
  },
): void {
  // SSE lines have the format: "data: {json}"
  if (!line.startsWith("data: ")) return;

  const jsonStr = line.slice(6); // Remove "data: " prefix

  // Handle "[DONE]" sentinel if used
  if (jsonStr === "[DONE]") return;

  try {
    const event: SSEEvent = JSON.parse(jsonStr);

    switch (event.type) {
      case "token":
        if (event.content !== undefined) {
          callbacks.onToken(event.content);
        }
        break;

      case "citation":
        if (event.data) {
          callbacks.onCitation(event.data as Citation);
        }
        break;

      case "suggestions":
        if (event.data && Array.isArray(event.data)) {
          callbacks.onSuggestions(event.data as string[]);
        }
        break;

      case "done":
        if (event.data) {
          callbacks.onDone(
            event.data as { conversation_id: string; message_id: string },
          );
        }
        break;

      case "error":
        callbacks.onError(
          (event.data as string) || event.content || "Unknown streaming error",
        );
        break;

      case "progress":
        if (callbacks.onProgress && event.data) {
          callbacks.onProgress(event.data as { step: string; detail: string });
        }
        break;

      case "metadata":
        if (callbacks.onMetadata && event.data) {
          callbacks.onMetadata(event.data as Record<string, unknown>);
        }
        break;

      default:
        // Unknown event type - ignore gracefully
        break;
    }
  } catch {
    // Malformed JSON - skip this line silently
  }
}

// ============================================================================
// REST API Functions
// ============================================================================

/**
 * Generic API request helper with authentication.
 *
 * @param endpoint - API endpoint path (without base URL)
 * @param options - Fetch options (method, body, headers, etc.)
 * @returns Typed response from the API
 * @throws Error with message from API response or generic error
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Authentication required. Please sign in.");
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ message: "Request failed" }));
    throw new Error(
      error.message || error.detail || `API error: ${response.status}`,
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * Lists conversations for the current user with optional filtering.
 *
 * @param params - Optional pagination and scope filter parameters
 * @returns Array of conversation records
 */
export async function fetchConversations(params?: {
  limit?: number;
  offset?: number;
  scope?: string;
  scope_id?: string;
}): Promise<Conversation[]> {
  const searchParams = new URLSearchParams();
  if (params?.limit !== undefined)
    searchParams.append("limit", String(params.limit));
  if (params?.offset !== undefined)
    searchParams.append("offset", String(params.offset));
  if (params?.scope) searchParams.append("scope", params.scope);
  if (params?.scope_id) searchParams.append("scope_id", params.scope_id);

  const queryString = searchParams.toString();
  const endpoint = `/api/v1/chat/conversations${queryString ? `?${queryString}` : ""}`;

  return apiRequest<Conversation[]>(endpoint);
}

/**
 * Fetches a single conversation with its full message history.
 *
 * @param conversationId - UUID of the conversation
 * @returns The conversation record and its messages
 */
export async function fetchConversation(conversationId: string): Promise<{
  conversation: Conversation;
  messages: ChatMessage[];
}> {
  return apiRequest<{
    conversation: Conversation;
    messages: ChatMessage[];
  }>(`/api/v1/chat/conversations/${conversationId}`);
}

/**
 * Deletes a conversation and all its messages.
 *
 * @param conversationId - UUID of the conversation to delete
 */
export async function deleteConversation(
  conversationId: string,
): Promise<void> {
  return apiRequest<void>(`/api/v1/chat/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

/**
 * Renames a conversation by updating its title.
 *
 * @param conversationId - UUID of the conversation to rename
 * @param title - The new title for the conversation
 * @returns The updated conversation record
 */
export async function renameConversation(
  conversationId: string,
  title: string,
): Promise<Conversation> {
  return apiRequest<Conversation>(
    `/api/v1/chat/conversations/${conversationId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ title }),
    },
  );
}

/** Search conversations by title and message content. */
export async function searchConversations(
  query: string,
  limit?: number,
): Promise<Conversation[]> {
  const searchParams = new URLSearchParams();
  searchParams.append("q", query);
  if (limit !== undefined) searchParams.append("limit", String(limit));
  return apiRequest<Conversation[]>(
    `/api/v1/chat/conversations/search?${searchParams.toString()}`,
  );
}

/**
 * Fetches suggested questions for a given scope.
 *
 * Returns contextually relevant questions based on the scope
 * (e.g., questions about a specific signal or workstream).
 *
 * @param scope - The chat scope ("signal", "workstream", or "global")
 * @param scopeId - Optional ID of the scoped entity
 * @returns Array of suggested question strings
 */
export async function fetchSuggestions(
  scope: string,
  scopeId?: string,
): Promise<string[]> {
  const searchParams = new URLSearchParams();
  searchParams.append("scope", scope);
  if (scopeId) searchParams.append("scope_id", scopeId);

  const queryString = searchParams.toString();
  return apiRequest<string[]>(`/api/v1/chat/suggestions?${queryString}`);
}

// ============================================================================
// Pin / Save Messages
// ============================================================================

/** Pin a chat message for quick reference. */
export async function pinMessage(
  messageId: string,
  note?: string,
): Promise<unknown> {
  return apiRequest(`/api/v1/chat/messages/${messageId}/pin`, {
    method: "POST",
    body: JSON.stringify(note ? { note } : {}),
  });
}

/** Unpin a previously pinned chat message. */
export async function unpinMessage(messageId: string): Promise<void> {
  return apiRequest<void>(`/api/v1/chat/messages/${messageId}/pin`, {
    method: "DELETE",
  });
}

/** Pinned message with its conversation context. */
export interface PinnedMessage {
  id: string;
  message_id: string;
  conversation_id: string;
  note: string | null;
  created_at: string;
  chat_messages: {
    id: string;
    content: string;
    role: string;
    citations: Citation[];
    created_at: string;
  };
  chat_conversations: {
    id: string;
    title: string | null;
    scope: string;
  };
}

/** Fetch the current user's pinned messages. */
export async function fetchPinnedMessages(params?: {
  limit?: number;
  offset?: number;
}): Promise<PinnedMessage[]> {
  const searchParams = new URLSearchParams();
  if (params?.limit !== undefined)
    searchParams.append("limit", String(params.limit));
  if (params?.offset !== undefined)
    searchParams.append("offset", String(params.offset));
  const qs = searchParams.toString();
  return apiRequest<PinnedMessage[]>(`/api/v1/chat/pins${qs ? `?${qs}` : ""}`);
}
