/**
 * AskForesightBar Component
 *
 * A large, prominent search input bar for the dashboard that navigates
 * to the /ask page with the user's query. Features a sparkles icon,
 * keyboard shortcut hint, and focus glow animation.
 *
 * @module components/Chat/AskForesightBar
 */

import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { cn } from "../../lib/utils";

// ============================================================================
// Types
// ============================================================================

export interface AskForesightBarProps {
  /** Additional CSS classes to apply to the root element */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

export function AskForesightBar({ className }: AskForesightBarProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // ============================================================================
  // Submit handler
  // ============================================================================

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (!trimmed) return;

      navigate(`/ask?q=${encodeURIComponent(trimmed)}`);
      setQuery("");
    },
    [query, navigate],
  );

  return (
    <form onSubmit={handleSubmit} className={cn("relative w-full", className)}>
      <div
        className={cn(
          "relative flex items-center",
          "bg-white dark:bg-dark-surface",
          "border border-gray-200 dark:border-gray-600",
          "rounded-2xl",
          "shadow-lg",
          "transition-all duration-300",
          isFocused && [
            "ring-2 ring-brand-blue/30",
            "border-brand-blue/50 dark:border-brand-blue/40",
            "shadow-brand-blue/10 shadow-xl",
          ],
        )}
      >
        {/* Sparkles icon */}
        <div className="pl-5 pr-1 flex items-center pointer-events-none">
          <Sparkles
            className={cn(
              "h-5 w-5 transition-colors duration-200",
              isFocused
                ? "text-brand-blue"
                : "text-brand-blue/60 dark:text-brand-blue/50",
            )}
            aria-hidden="true"
          />
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Ask Foresight anything about signals, trends, and strategy..."
          className={cn(
            "flex-1 py-4 px-3",
            "bg-transparent",
            "text-base text-gray-900 dark:text-gray-100",
            "placeholder-gray-400 dark:placeholder-gray-500",
            "focus:outline-none",
          )}
          aria-label="Ask Foresight a question"
        />

        {/* Keyboard shortcut hint */}
        <div className="pr-5 flex items-center pointer-events-none">
          <kbd
            className={cn(
              "hidden sm:inline-flex items-center gap-0.5",
              "px-2 py-1 rounded-md",
              "text-xs font-medium",
              "bg-gray-100 dark:bg-dark-surface-elevated",
              "text-gray-500 dark:text-gray-400",
              "border border-gray-200 dark:border-gray-600",
            )}
          >
            {"\u2318"}K
          </kbd>
        </div>
      </div>
    </form>
  );
}

export default AskForesightBar;
