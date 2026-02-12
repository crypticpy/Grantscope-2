/**
 * ChatCitationCard Component
 *
 * A floating hover card that shows citation details when the user hovers
 * over a citation pill. Displays the source title (linked), excerpt,
 * published date, and a signal link when available.
 *
 * @module components/Chat/ChatCitationCard
 */

import { useEffect, useRef, useState } from "react";
import { ExternalLink, Calendar, FileText } from "lucide-react";
import { cn } from "../../lib/utils";
import type { Citation } from "../../lib/chat-api";

// ============================================================================
// Types
// ============================================================================

export interface ChatCitationCardProps {
  /** The citation data to display */
  citation: Citation;
  /** The element to position relative to */
  anchor: HTMLElement;
  /** Called when the card should be closed */
  onClose: () => void;
  /** Called when the mouse enters the card, so the parent can cancel its leave timer */
  onMouseEnterCard?: () => void;
}

// ============================================================================
// Component
// ============================================================================

export function ChatCitationCard({
  citation,
  anchor,
  onClose,
  onMouseEnterCard,
}: ChatCitationCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{
    top: number;
    left: number;
    placement: "above" | "below";
  }>({ top: 0, left: 0, placement: "above" });

  // Compute position relative to the anchor element
  useEffect(() => {
    const rect = anchor.getBoundingClientRect();
    const cardHeight = 200; // Estimated max height
    const spaceAbove = rect.top;
    const spaceBelow = window.innerHeight - rect.bottom;

    let top: number;
    let placement: "above" | "below";

    if (spaceAbove >= cardHeight || spaceAbove > spaceBelow) {
      // Position above
      top = rect.top - 8;
      placement = "above";
    } else {
      // Position below
      top = rect.bottom + 8;
      placement = "below";
    }

    let left = rect.left;
    // Ensure card doesn't overflow right edge
    const cardWidth = 384; // max-w-sm = 24rem = 384px
    if (left + cardWidth > window.innerWidth - 16) {
      left = window.innerWidth - cardWidth - 16;
    }
    // Ensure card doesn't overflow left edge
    if (left < 16) {
      left = 16;
    }

    setPosition({ top, left, placement });
  }, [anchor]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Close on mouse leave with 150ms grace period
  const leaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseEnter = () => {
    if (leaveTimerRef.current) {
      clearTimeout(leaveTimerRef.current);
      leaveTimerRef.current = null;
    }
    // Also cancel the parent's leave timer so the card stays open
    onMouseEnterCard?.();
  };

  const handleMouseLeave = () => {
    leaveTimerRef.current = setTimeout(() => {
      onClose();
    }, 150);
  };

  useEffect(() => {
    return () => {
      if (leaveTimerRef.current) {
        clearTimeout(leaveTimerRef.current);
      }
    };
  }, []);

  // Truncate excerpt to 200 characters
  const truncatedExcerpt = citation.excerpt
    ? citation.excerpt.length > 200
      ? citation.excerpt.slice(0, 200) + "\u2026"
      : citation.excerpt
    : null;

  // Format published date
  const formattedDate = citation.published_date
    ? (() => {
        try {
          return new Date(citation.published_date).toLocaleDateString(
            undefined,
            {
              year: "numeric",
              month: "short",
              day: "numeric",
            },
          );
        } catch {
          return null;
        }
      })()
    : null;

  return (
    <div
      ref={cardRef}
      role="tooltip"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={cn(
        "fixed z-[100] max-w-sm w-80",
        "bg-white dark:bg-dark-surface-elevated",
        "border border-gray-200 dark:border-gray-600",
        "rounded-lg shadow-lg",
        "p-3",
        "animate-in fade-in-0 zoom-in-95 duration-150",
      )}
      style={{
        top: position.placement === "below" ? position.top : undefined,
        bottom:
          position.placement === "above"
            ? `calc(100vh - ${position.top}px)`
            : undefined,
        left: position.left,
      }}
    >
      {/* Title (linked if URL exists) */}
      {citation.url ? (
        <a
          href={citation.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-start gap-1.5 text-sm font-medium text-brand-blue hover:underline dark:text-blue-300 line-clamp-2"
        >
          <span className="flex-1">{citation.title}</span>
          <ExternalLink className="h-3.5 w-3.5 shrink-0 mt-0.5" />
        </a>
      ) : (
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 line-clamp-2">
          {citation.title}
        </p>
      )}

      {/* Excerpt */}
      {truncatedExcerpt && (
        <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
          {truncatedExcerpt}
        </p>
      )}

      {/* Published date */}
      {formattedDate && (
        <div className="mt-2 flex items-center gap-1.5 text-[11px] text-gray-400 dark:text-gray-500">
          <Calendar className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span>{formattedDate}</span>
        </div>
      )}

      {/* Signal link */}
      {citation.card_slug && (
        <a
          href={`/signals/${citation.card_slug}`}
          className="mt-2 flex items-center gap-1.5 text-[11px] font-medium text-brand-blue dark:text-blue-300 hover:underline"
        >
          <FileText className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span>View signal</span>
        </a>
      )}
    </div>
  );
}

export default ChatCitationCard;
