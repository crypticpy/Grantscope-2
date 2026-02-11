/**
 * SeedUrlInput Component
 *
 * A tag-style input for managing a list of seed URLs. Users can add URLs
 * one at a time via a text input, and remove them by clicking the "x" on
 * each tag/chip. Validates that URLs start with http:// or https://.
 *
 * @example
 * ```tsx
 * const [urls, setUrls] = useState<string[]>([]);
 * <SeedUrlInput urls={urls} onChange={setUrls} max={5} />
 * ```
 *
 * @module CreateSignal/SeedUrlInput
 */

import React, { useState, useCallback } from "react";
import { X, Plus, Link as LinkIcon } from "lucide-react";
import { cn } from "../../lib/utils";

// =============================================================================
// Types
// =============================================================================

export interface SeedUrlInputProps {
  /** Current list of URLs */
  urls: string[];
  /** Callback when URLs change (add or remove) */
  onChange: (urls: string[]) => void;
  /** Maximum number of URLs allowed (default: 10) */
  max?: number;
  /** Additional CSS classes for the container */
  className?: string;
}

// =============================================================================
// Constants
// =============================================================================

/** Default maximum number of seed URLs */
const DEFAULT_MAX_URLS = 10;

/** Regex to validate URL format (must start with http:// or https://) */
const URL_PATTERN = /^https?:\/\/.+/i;

// =============================================================================
// Component
// =============================================================================

/**
 * SeedUrlInput provides a tag-style interface for adding and removing
 * seed URLs. Each URL is validated and displayed as a removable chip.
 */
export function SeedUrlInput({
  urls,
  onChange,
  max = DEFAULT_MAX_URLS,
  className,
}: SeedUrlInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const canAddMore = urls.length < max;

  /**
   * Validates and adds a URL to the list.
   * Checks for valid format, duplicates, and max count.
   */
  const handleAddUrl = useCallback(() => {
    const trimmed = inputValue.trim();

    if (!trimmed) {
      return;
    }

    // Validate URL format
    if (!URL_PATTERN.test(trimmed)) {
      setError("URL must start with http:// or https://");
      return;
    }

    // Check for duplicates
    if (urls.includes(trimmed)) {
      setError("This URL has already been added");
      return;
    }

    // Check max limit
    if (urls.length >= max) {
      setError(`Maximum of ${max} URLs allowed`);
      return;
    }

    setError(null);
    setInputValue("");
    onChange([...urls, trimmed]);
  }, [inputValue, urls, max, onChange]);

  /**
   * Removes a URL from the list by index.
   */
  const handleRemoveUrl = useCallback(
    (index: number) => {
      const updated = urls.filter((_, i) => i !== index);
      onChange(updated);
      setError(null);
    },
    [urls, onChange],
  );

  /**
   * Handle keyboard events - Enter to add, Escape to clear input.
   */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddUrl();
      } else if (e.key === "Escape") {
        setInputValue("");
        setError(null);
      }
    },
    [handleAddUrl],
  );

  return (
    <div className={cn("space-y-2", className)}>
      {/* Label and count */}
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
          Seed URLs
        </label>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {urls.length} / {max}
        </span>
      </div>

      {/* Input row */}
      {canAddMore && (
        <div className="flex gap-2">
          <div className="relative flex-1">
            <LinkIcon
              className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400"
              aria-hidden="true"
            />
            <input
              type="url"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                if (error) setError(null);
              }}
              onKeyDown={handleKeyDown}
              placeholder="https://example.com/article"
              className={cn(
                "w-full pl-8 pr-3 py-2 text-sm rounded-md border",
                "bg-white dark:bg-dark-surface",
                "text-gray-900 dark:text-gray-100",
                "placeholder-gray-400 dark:placeholder-gray-500",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
                error
                  ? "border-red-300 dark:border-red-700"
                  : "border-gray-300 dark:border-gray-600",
              )}
              aria-label="Add seed URL"
              aria-invalid={!!error}
              aria-describedby={error ? "seed-url-error" : undefined}
            />
          </div>
          <button
            type="button"
            onClick={handleAddUrl}
            disabled={!inputValue.trim()}
            className={cn(
              "inline-flex items-center gap-1 px-3 py-2 text-sm font-medium rounded-md",
              "bg-brand-blue text-white hover:bg-brand-dark-blue",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "transition-colors duration-200",
            )}
            aria-label="Add URL"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add
          </button>
        </div>
      )}

      {/* Error message */}
      {error && (
        <p
          id="seed-url-error"
          className="text-xs text-red-600 dark:text-red-400"
          role="alert"
        >
          {error}
        </p>
      )}

      {/* URL tags */}
      {urls.length > 0 && (
        <div
          className="flex flex-wrap gap-2"
          role="list"
          aria-label="Added seed URLs"
        >
          {urls.map((url, index) => (
            <div
              key={url}
              role="listitem"
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full",
                "bg-gray-100 dark:bg-dark-surface-elevated",
                "text-xs text-gray-700 dark:text-gray-300",
                "border border-gray-200 dark:border-gray-600",
                "max-w-[300px]",
              )}
            >
              <LinkIcon
                className="h-3 w-3 shrink-0 text-gray-400"
                aria-hidden="true"
              />
              <span className="truncate" title={url}>
                {url}
              </span>
              <button
                type="button"
                onClick={() => handleRemoveUrl(index)}
                className={cn(
                  "shrink-0 p-0.5 rounded-full",
                  "text-gray-400 hover:text-red-500 dark:hover:text-red-400",
                  "hover:bg-gray-200 dark:hover:bg-gray-600",
                  "focus:outline-none focus:ring-1 focus:ring-red-400",
                  "transition-colors duration-200",
                )}
                aria-label={`Remove ${url}`}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Max reached message */}
      {!canAddMore && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Maximum number of URLs reached ({max}).
        </p>
      )}
    </div>
  );
}

export default SeedUrlInput;
