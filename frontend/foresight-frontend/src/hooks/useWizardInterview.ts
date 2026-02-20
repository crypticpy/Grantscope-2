/**
 * useWizardInterview Hook
 *
 * Wraps the useChat hook with wizard-specific topic tracking for the
 * grant application interview step. Monitors assistant messages for
 * topic completion markers and exposes interview progress state.
 *
 * @module hooks/useWizardInterview
 */

import { useState, useEffect, useRef, useMemo } from "react";
import { useChat, type UseChatReturn } from "./useChat";

// ============================================================================
// Types
// ============================================================================

export interface UseWizardInterviewOptions {
  /** Wizard session UUID */
  sessionId: string;
  /** Existing conversation to resume, or null for a new interview */
  conversationId: string | null;
  /** Grant context for context-aware greeting (optional) */
  grantName?: string;
}

export interface UseWizardInterviewReturn extends Omit<
  UseChatReturn,
  "messages" | "streamingContent"
> {
  /** Messages with topic markers stripped from content */
  messages: UseChatReturn["messages"];
  /** Streaming content with topic markers stripped */
  streamingContent: string;
  /** Set of completed topic identifiers */
  completedTopics: Set<string>;
  /** Number of topics completed (0-7) */
  topicProgress: number;
  /** True when at least 4 core topics are complete */
  isInterviewComplete: boolean;
}

// ============================================================================
// Constants
// ============================================================================

/** All valid interview topics in display order */
const VALID_TOPICS = [
  "program_overview",
  "staffing",
  "budget",
  "timeline",
  "deliverables",
  "evaluation",
  "capacity",
] as const;

/** The 4 core topics required for interview completion */
const CORE_TOPICS = [
  "program_overview",
  "staffing",
  "budget",
  "timeline",
] as const;

/** Pattern source for topic completion markers in message content */
const TOPIC_MARKER_PATTERN = /<!--\s*TOPIC_COMPLETE:\s*(\w+)\s*-->/;

// ============================================================================
// Helpers
// ============================================================================

/**
 * Extracts all topic names from TOPIC_COMPLETE markers in a string.
 */
function extractTopics(content: string): string[] {
  const topics: string[] = [];
  const regex = new RegExp(TOPIC_MARKER_PATTERN.source, "g");
  let match: RegExpExecArray | null;
  while ((match = regex.exec(content)) !== null) {
    const topic = match[1];
    if (topic && (VALID_TOPICS as readonly string[]).includes(topic)) {
      topics.push(topic);
    }
  }
  return topics;
}

/**
 * Strips TOPIC_COMPLETE markers from a string.
 */
function stripTopicMarkers(content: string): string {
  return content
    .replace(new RegExp(TOPIC_MARKER_PATTERN.source, "g"), "")
    .trim();
}

// ============================================================================
// Hook
// ============================================================================

export function useWizardInterview(
  options: UseWizardInterviewOptions,
): UseWizardInterviewReturn {
  const { sessionId, conversationId, grantName } = options;

  // Wrap useChat with wizard scope + session-specific scopeId
  const chat = useChat({
    scope: "wizard",
    scopeId: sessionId,
    initialConversationId: conversationId ?? undefined,
    forceNew: !conversationId,
  });

  // Track completed topics
  const [completedTopics, setCompletedTopics] = useState<Set<string>>(
    new Set(),
  );

  // Track whether the initial greeting has been sent
  const greetingSentRef = useRef(false);
  const initialLoadCheckedRef = useRef(false);

  // Stable ref for sendMessage to avoid redundant resets from unstable memoized function
  const sendMessageRef = useRef(chat.sendMessage);
  useEffect(() => {
    sendMessageRef.current = chat.sendMessage;
  }, [chat.sendMessage]);

  // ---------------------------------------------------------------------------
  // Scan all messages for topic markers whenever messages change
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const topics = new Set<string>();
    for (const msg of chat.messages) {
      for (const topic of extractTopics(msg.content)) {
        topics.add(topic);
      }
    }
    // Also scan current streaming content
    if (chat.streamingContent) {
      for (const topic of extractTopics(chat.streamingContent)) {
        topics.add(topic);
      }
    }
    setCompletedTopics(topics);
  }, [chat.messages, chat.streamingContent]);

  // ---------------------------------------------------------------------------
  // Auto-send greeting on first mount for new conversations
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (initialLoadCheckedRef.current) return;

    // Wait until chat has finished its initial load attempt.
    // useChat sets messages to [] and isStreaming to false when ready.
    // We use a small delay to let the restore cycle complete.
    const timer = setTimeout(() => {
      initialLoadCheckedRef.current = true;

      // If we have an existing conversation (resuming), skip greeting
      if (conversationId) {
        greetingSentRef.current = true;
        return;
      }

      if (
        !greetingSentRef.current &&
        chat.messages.length === 0 &&
        !chat.isStreaming
      ) {
        greetingSentRef.current = true;
        const greeting = grantName
          ? `Hello, I need help preparing a grant application for "${grantName}". I've already gathered research and details about this opportunity — please use that context to guide our interview.`
          : "Hello, I need help preparing a grant application.";
        sendMessageRef.current(greeting);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [chat.messages.length, chat.isStreaming, grantName, conversationId]);

  // ---------------------------------------------------------------------------
  // Strip topic markers from messages for display
  // ---------------------------------------------------------------------------

  const cleanedMessages = useMemo(
    () =>
      chat.messages.map((msg) => ({
        ...msg,
        content: stripTopicMarkers(msg.content),
      })),
    [chat.messages],
  );

  const cleanedStreamingContent = useMemo(
    () => stripTopicMarkers(chat.streamingContent),
    [chat.streamingContent],
  );

  // ---------------------------------------------------------------------------
  // Derived state
  // ---------------------------------------------------------------------------

  const topicProgress = completedTopics.size;

  const isInterviewComplete = useMemo(() => {
    let coreCompleted = 0;
    for (const topic of CORE_TOPICS) {
      if (completedTopics.has(topic)) {
        coreCompleted++;
      }
    }
    return coreCompleted >= 4;
  }, [completedTopics]);

  // Forward the hook-provided sendMessage to avoid wrapping indirection.
  const sendMessage = chat.sendMessage;

  return {
    // Overridden returns with markers stripped
    messages: cleanedMessages,
    streamingContent: cleanedStreamingContent,

    // Pass through all other useChat returns
    isStreaming: chat.isStreaming,
    streamingCitations: chat.streamingCitations,
    conversationId: chat.conversationId,
    conversationTitle: chat.conversationTitle,
    conversationUpdatedAt: chat.conversationUpdatedAt,
    suggestedQuestions: chat.suggestedQuestions,
    error: chat.error,
    sendMessage,
    stopGenerating: chat.stopGenerating,
    loadConversation: chat.loadConversation,
    startNewConversation: chat.startNewConversation,
    loadSuggestions: chat.loadSuggestions,
    retryLastMessage: chat.retryLastMessage,
    progressStep: chat.progressStep,
    responseMetadata: chat.responseMetadata,
    funFact: chat.funFact,

    // Wizard-specific returns
    completedTopics,
    topicProgress,
    isInterviewComplete,
  };
}
