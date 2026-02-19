/**
 * ChatCitation Component
 *
 * Renders a citation reference as a compact pill badge with the citation
 * number and source title. Shows a hover card with details after a short
 * delay, and supports click navigation to cards or external URLs.
 *
 * @module components/Chat/ChatCitation
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { cn } from "../../lib/utils";
import type { Citation } from "../../lib/chat-api";
import { ChatCitationCard } from "./ChatCitationCard";

// ============================================================================
// Types
// ============================================================================

export interface ChatCitationProps {
  /** The citation data to render */
  citation: Citation;
  /** Optional click handler override. If not provided, default navigation is used. */
  onClick?: (citation: Citation) => void;
}

// ============================================================================
// Component
// ============================================================================

export function ChatCitation({ citation, onClick }: ChatCitationProps) {
  const navigate = useNavigate();
  const [showCard, setShowCard] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const cardEnterTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cardLeaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (cardEnterTimerRef.current) clearTimeout(cardEnterTimerRef.current);
      if (cardLeaveTimerRef.current) clearTimeout(cardLeaveTimerRef.current);
    };
  }, []);

  const handleClick = () => {
    if (onClick) {
      onClick(citation);
      return;
    }

    // Default navigation: prefer in-app card navigation, fall back to external URL
    if (citation.card_slug) {
      navigate(`/signals/${citation.card_slug}`);
    } else if (citation.card_id) {
      navigate(`/signals/${citation.card_id}`);
    } else if (citation.url) {
      window.open(citation.url, "_blank", "noopener,noreferrer");
    }
  };

  const handleMouseEnter = () => {
    // Clear any pending leave timer
    if (cardLeaveTimerRef.current) {
      clearTimeout(cardLeaveTimerRef.current);
      cardLeaveTimerRef.current = null;
    }
    // Show hover card after 250ms delay
    cardEnterTimerRef.current = setTimeout(() => {
      setShowCard(true);
    }, 250);
  };

  const handleMouseLeave = () => {
    // Clear pending enter timer
    if (cardEnterTimerRef.current) {
      clearTimeout(cardEnterTimerRef.current);
      cardEnterTimerRef.current = null;
    }
    // Hide hover card after 150ms grace period
    cardLeaveTimerRef.current = setTimeout(() => {
      setShowCard(false);
    }, 150);
  };

  // Called when the mouse enters the hover card, so we cancel the
  // parent leave timer and keep the card visible.
  const handleCardMouseEnter = useCallback(() => {
    if (cardLeaveTimerRef.current) {
      clearTimeout(cardLeaveTimerRef.current);
      cardLeaveTimerRef.current = null;
    }
  }, []);

  const handleCardClose = useCallback(() => {
    setShowCard(false);
  }, []);

  return (
    <div className="relative inline-block">
      <button
        ref={triggerRef}
        type="button"
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onBlur={() => {
          setShowCard(false);
        }}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full",
          "text-xs font-medium",
          "bg-brand-blue/10 text-brand-blue",
          "hover:bg-brand-blue/20",
          "dark:bg-brand-blue/20 dark:text-blue-300 dark:hover:bg-brand-blue/30",
          "border border-brand-blue/20 dark:border-brand-blue/30",
          "cursor-pointer transition-colors duration-150",
          "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-1",
          "max-w-[220px]",
        )}
        aria-label={`Source ${citation.index}: ${citation.title}`}
      >
        {/* Number badge */}
        <span
          className={cn(
            "inline-flex items-center justify-center",
            "min-w-[1.125rem] h-[1.125rem] rounded-full",
            "bg-brand-blue text-white",
            "text-[10px] font-bold leading-none",
          )}
        >
          {citation.index}
        </span>

        {/* Title (truncated) */}
        <span className="truncate">{citation.title}</span>
      </button>

      {/* Hover card (shown after 250ms delay) */}
      {showCard && triggerRef.current && (
        <ChatCitationCard
          citation={citation}
          anchor={triggerRef.current}
          onClose={handleCardClose}
          onMouseEnterCard={handleCardMouseEnter}
        />
      )}
    </div>
  );
}

export default ChatCitation;
