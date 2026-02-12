/**
 * ChatSuggestionChips Component
 *
 * Renders a row of pill-shaped suggestion buttons that wrap on small screens.
 * Each suggestion appears with a staggered fade-in animation. Includes a
 * loading state with skeleton pills.
 *
 * @module components/Chat/ChatSuggestionChips
 */

import { Sparkles } from "lucide-react";
import { cn } from "../../lib/utils";

// ============================================================================
// Types
// ============================================================================

export interface ChatSuggestionChipsProps {
  /** Array of suggested question strings */
  suggestions: string[];
  /** Callback when a suggestion pill is clicked */
  onSelect: (question: string) => void;
  /** Show skeleton loading state */
  isLoading?: boolean;
}

// ============================================================================
// Component
// ============================================================================

export function ChatSuggestionChips({
  suggestions,
  onSelect,
  isLoading = false,
}: ChatSuggestionChipsProps) {
  // Loading skeleton
  if (isLoading) {
    return (
      <div className="flex flex-wrap gap-2" aria-label="Loading suggestions">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className={cn(
              "h-9 rounded-full animate-pulse",
              "bg-gray-200 dark:bg-dark-surface-elevated",
              i === 1 ? "w-48" : i === 2 ? "w-56" : "w-40",
            )}
            aria-hidden="true"
          />
        ))}
      </div>
    );
  }

  if (suggestions.length === 0) return null;

  return (
    <div
      className="flex flex-wrap gap-2"
      role="list"
      aria-label="Suggested questions"
    >
      {suggestions.map((suggestion, index) => (
        <button
          key={suggestion}
          type="button"
          role="listitem"
          onClick={() => onSelect(suggestion)}
          className={cn(
            "inline-flex items-center gap-1.5",
            "px-4 py-2 rounded-full",
            "text-sm text-gray-700 dark:text-gray-300",
            "border border-gray-200 dark:border-gray-600",
            "bg-white dark:bg-dark-surface",
            "hover:bg-brand-blue/5 hover:border-brand-blue dark:hover:bg-brand-blue/10 dark:hover:border-brand-blue/60",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-1",
            "transition-all duration-200",
            "animate-in fade-in-0 slide-in-from-bottom-1 duration-300",
            "cursor-pointer",
          )}
          style={{
            animationDelay: `${index * 50}ms`,
            animationFillMode: "both",
          }}
        >
          <Sparkles
            className="h-3.5 w-3.5 text-brand-blue shrink-0"
            aria-hidden="true"
          />
          <span className="text-left">{suggestion}</span>
        </button>
      ))}
    </div>
  );
}

export default ChatSuggestionChips;
