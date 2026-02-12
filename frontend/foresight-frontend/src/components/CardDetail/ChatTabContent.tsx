/**
 * ChatTabContent Component
 *
 * A wrapper that renders ChatPanel with signal scope for the CardDetail page.
 * Provides a chat interface scoped to a specific signal/card, allowing users
 * to ask questions about the signal's sources, implications, and strategic relevance.
 *
 * @module CardDetail
 */

import React from "react";
import { ChatPanel } from "../Chat/ChatPanel";

/**
 * Props for the ChatTabContent component
 */
export interface ChatTabContentProps {
  /** UUID of the card to scope the chat to */
  cardId: string;
  /** Display name of the card for placeholder and empty state */
  cardName: string;
  /** Primary pillar ID for additional context */
  primaryPillar?: string;
}

/**
 * ChatTabContent renders a ChatPanel scoped to a specific signal.
 *
 * Used as a tab within the CardDetail component to provide an AI chat
 * interface that can answer questions about the signal, its sources,
 * strategic implications, and related trends.
 *
 * @example
 * ```tsx
 * <ChatTabContent
 *   cardId={card.id}
 *   cardName={card.name}
 *   primaryPillar={card.pillar_id}
 * />
 * ```
 */
export function ChatTabContent({
  cardId,
  cardName,
  primaryPillar: _primaryPillar,
}: ChatTabContentProps) {
  return (
    <ChatPanel
      scope="signal"
      scopeId={cardId}
      compact
      placeholder={`Ask about ${cardName}...`}
      emptyStateTitle={`Chat about ${cardName}`}
      emptyStateDescription="Ask questions about this signal's sources, implications, and strategic relevance."
      className="h-[calc(100vh-20rem)]"
    />
  );
}

export default ChatTabContent;
