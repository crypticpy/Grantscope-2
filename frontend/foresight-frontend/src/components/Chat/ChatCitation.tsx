/**
 * ChatCitation Component
 *
 * Renders a citation reference as a compact pill badge with the citation
 * number and source title. Supports hover tooltips with excerpt previews
 * and click navigation to cards or external URLs.
 *
 * @module components/Chat/ChatCitation
 */

import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { cn } from "../../lib/utils";
import type { Citation } from "../../lib/chat-api";

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
  const [showTooltip, setShowTooltip] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Position tooltip to stay within viewport
  useEffect(() => {
    if (showTooltip && tooltipRef.current && triggerRef.current) {
      const tooltip = tooltipRef.current;
      const trigger = triggerRef.current;
      const triggerRect = trigger.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();

      // Check if tooltip overflows right edge
      if (triggerRect.left + tooltipRect.width > window.innerWidth - 16) {
        tooltip.style.left = "auto";
        tooltip.style.right = "0";
      }
    }
  }, [showTooltip]);

  // Truncate excerpt to 150 characters
  const truncatedExcerpt = citation.excerpt
    ? citation.excerpt.length > 150
      ? citation.excerpt.slice(0, 150) + "..."
      : citation.excerpt
    : null;

  const handleClick = () => {
    if (onClick) {
      onClick(citation);
      return;
    }

    // Default navigation behavior: prioritize source URL
    if (citation.url) {
      window.open(citation.url, "_blank", "noopener,noreferrer");
    } else if (citation.card_slug) {
      navigate(`/signals/${citation.card_slug}`);
    } else if (citation.card_id) {
      navigate(`/signals/${citation.card_id}`);
    }
  };

  return (
    <div className="relative inline-block">
      <button
        ref={triggerRef}
        type="button"
        onClick={handleClick}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onFocus={() => setShowTooltip(true)}
        onBlur={() => setShowTooltip(false)}
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

      {/* Tooltip */}
      {showTooltip && (
        <div
          ref={tooltipRef}
          className={cn(
            "absolute z-50 bottom-full mb-2 left-0",
            "w-72 max-w-[calc(100vw-2rem)]",
            "bg-white dark:bg-dark-surface-elevated",
            "border border-gray-200 dark:border-gray-600",
            "rounded-lg shadow-lg",
            "p-3",
            "animate-in fade-in-0 zoom-in-95 duration-150",
            "pointer-events-none",
          )}
          role="tooltip"
        >
          {/* Title */}
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 line-clamp-2">
            {citation.title}
          </p>

          {/* Excerpt */}
          {truncatedExcerpt && (
            <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
              {truncatedExcerpt}
            </p>
          )}

          {/* Source type indicator */}
          <div className="mt-2 flex items-center gap-1.5">
            {citation.card_id && (
              <span className="text-[10px] font-medium text-brand-blue dark:text-blue-300 bg-brand-blue/10 dark:bg-brand-blue/20 px-1.5 py-0.5 rounded">
                Signal
              </span>
            )}
            {citation.url && !citation.card_id && (
              <span className="text-[10px] font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-dark-surface px-1.5 py-0.5 rounded truncate max-w-[200px]">
                {(() => {
                  try {
                    return new URL(citation.url).hostname;
                  } catch {
                    return citation.url;
                  }
                })()}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatCitation;
