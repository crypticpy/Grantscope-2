/**
 * ChatMentionAutocomplete Component
 *
 * A positioned dropdown that provides @mention autocomplete for signals
 * and workstreams in the chat input. Supports keyboard navigation,
 * debounced search, and type-differentiated icons.
 *
 * @module components/Chat/ChatMentionAutocomplete
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { BarChart3, Kanban, Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";
import { searchMentions, type MentionResult } from "../../lib/chat-api";

// ============================================================================
// Types
// ============================================================================

export interface ChatMentionAutocompleteProps {
  /** The current search query (text after the @ trigger) */
  query: string;
  /** Position for the dropdown relative to its container */
  position: { top: number; left: number };
  /** Called when the user selects a mention result */
  onSelect: (mention: MentionResult) => void;
  /** Called when the dropdown should close (Escape or click outside) */
  onClose: () => void;
}

// ============================================================================
// Component
// ============================================================================

export function ChatMentionAutocomplete({
  query,
  position,
  onSelect,
  onClose,
}: ChatMentionAutocompleteProps) {
  const [results, setResults] = useState<MentionResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --------------------------------------------------------------------------
  // Debounced search
  // --------------------------------------------------------------------------

  useEffect(() => {
    // Clear previous debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // Don't search on empty query
    if (!query.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    debounceRef.current = setTimeout(async () => {
      try {
        const data = await searchMentions(query.trim());
        setResults(data);
        setActiveIndex(0);
      } catch {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query]);

  // --------------------------------------------------------------------------
  // Click outside to close
  // --------------------------------------------------------------------------

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [onClose]);

  // --------------------------------------------------------------------------
  // Keyboard navigation (exposed via parent's onKeyDown intercept)
  // --------------------------------------------------------------------------

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        e.stopPropagation();
        setActiveIndex((prev) => (prev < results.length - 1 ? prev + 1 : 0));
        return;
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        e.stopPropagation();
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : results.length - 1));
        return;
      }

      if (e.key === "Enter" || e.key === "Tab") {
        const selected = results[activeIndex];
        if (results.length > 0 && selected) {
          e.preventDefault();
          e.stopPropagation();
          onSelect(selected);
        }
        return;
      }
    },
    [results, activeIndex, onSelect, onClose],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [handleKeyDown]);

  // --------------------------------------------------------------------------
  // Scroll active item into view
  // --------------------------------------------------------------------------

  useEffect(() => {
    const activeEl = dropdownRef.current?.querySelector(
      `[data-mention-index="${activeIndex}"]`,
    );
    activeEl?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  const showEmpty =
    !isLoading && results.length === 0 && query.trim().length > 0;

  return (
    <div
      ref={dropdownRef}
      className={cn(
        "absolute z-50",
        "w-72 max-h-64 overflow-y-auto",
        "bg-white dark:bg-dark-surface-elevated",
        "border border-gray-200 dark:border-gray-700",
        "rounded-lg shadow-lg",
        "animate-in fade-in-0 zoom-in-95 duration-150",
      )}
      style={{
        bottom: position.top,
        left: Math.min(position.left, 200),
      }}
      role="listbox"
      aria-label="Mention suggestions"
    >
      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-4">
          <Loader2
            className="h-4 w-4 animate-spin text-gray-400 dark:text-gray-500"
            aria-hidden="true"
          />
          <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">
            Searching...
          </span>
        </div>
      )}

      {/* Empty state */}
      {showEmpty && (
        <div className="px-3 py-4 text-center">
          <p className="text-xs text-gray-400 dark:text-gray-500">
            No opportunities or programs found
          </p>
        </div>
      )}

      {/* Results */}
      {!isLoading &&
        results.map((result, index) => (
          <button
            key={`${result.type}-${result.id}`}
            type="button"
            data-mention-index={index}
            onClick={() => onSelect(result)}
            onMouseEnter={() => setActiveIndex(index)}
            className={cn(
              "w-full text-left px-3 py-2 flex items-center gap-2.5",
              "transition-colors duration-100",
              "focus:outline-none",
              index === activeIndex
                ? "bg-brand-blue/10 dark:bg-brand-blue/20"
                : "hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
            )}
            role="option"
            aria-selected={index === activeIndex}
          >
            {/* Type icon */}
            <span
              className={cn(
                "flex items-center justify-center w-6 h-6 rounded shrink-0",
                result.type === "signal"
                  ? "bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
                  : "bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400",
              )}
            >
              {result.type === "signal" ? (
                <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <Kanban className="h-3.5 w-3.5" aria-hidden="true" />
              )}
            </span>

            {/* Title and type label */}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-900 dark:text-gray-100 truncate leading-snug">
                {result.title}
              </p>
              <p className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">
                {result.type === "signal" ? "Opportunity" : "Workstream"}
              </p>
            </div>
          </button>
        ))}
    </div>
  );
}

export default ChatMentionAutocomplete;
