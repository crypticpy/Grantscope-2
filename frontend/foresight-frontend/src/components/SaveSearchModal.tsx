/**
 * SaveSearchModal Component
 *
 * Modal dialog for saving the current search configuration.
 * Captures the current filters and search query into a named saved search.
 */

import React, { useState, useEffect, useRef } from "react";
import { X, Bookmark, Loader2, AlertCircle, Check } from "lucide-react";
import { cn } from "../lib/utils";
import {
  createSavedSearch,
  SavedSearchQueryConfig,
} from "../lib/discovery-api";
import { supabase } from "../App";

// ============================================================================
// Types
// ============================================================================

export interface SaveSearchModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Called when modal should close */
  onClose: () => void;
  /** Called after successful save */
  onSuccess?: () => void;
  /** Current search configuration to save */
  queryConfig: SavedSearchQueryConfig;
}

// ============================================================================
// Main Component
// ============================================================================

export function SaveSearchModal({
  isOpen,
  onClose,
  onSuccess,
  queryConfig,
}: SaveSearchModalProps) {
  // Form state
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Ref for focus management
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setName("");
      setError(null);
      setSuccess(false);
      // Focus input after a brief delay for animation
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // Get auth token helper
  const getAuthToken = async (): Promise<string | null> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token || null;
  };

  // Build a description of what's being saved
  const getSearchDescription = (): string => {
    const parts: string[] = [];

    if (queryConfig.query) {
      parts.push(`"${queryConfig.query}"`);
    }

    if (queryConfig.filters) {
      const { pillar_ids, stage_ids, horizon, date_range, score_thresholds } =
        queryConfig.filters;

      if (pillar_ids && pillar_ids.length > 0) {
        parts.push(`${pillar_ids.length} pillar(s)`);
      }
      if (stage_ids && stage_ids.length > 0) {
        parts.push(`${stage_ids.length} stage(s)`);
      }
      if (horizon && horizon !== "ALL") {
        parts.push(`Horizon ${horizon}`);
      }
      if (date_range && (date_range.start || date_range.end)) {
        parts.push("date filter");
      }
      if (score_thresholds && Object.keys(score_thresholds).length > 0) {
        parts.push("score thresholds");
      }
    }

    if (queryConfig.use_vector_search) {
      parts.push("semantic search");
    }

    return parts.length > 0 ? parts.join(" + ") : "No filters applied";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate
    if (!name.trim()) {
      setError("Please enter a name for this search");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error("Not authenticated");
      }

      await createSavedSearch(token, {
        name: name.trim(),
        query_config: queryConfig,
      });

      setSuccess(true);

      // Close after brief success message
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 1000);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to save search. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="save-search-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Content */}
      <div className="relative bg-white dark:bg-dark-surface rounded-xl shadow-2xl w-full max-w-md transform transition-all">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Bookmark className="h-5 w-5 text-brand-blue" />
            <h2
              id="save-search-title"
              className="text-lg font-semibold text-gray-900 dark:text-white"
            >
              Save Search
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-md transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Success Message */}
          {success && (
            <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded-md">
              <Check className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0" />
              <p className="text-sm text-green-800 dark:text-green-300">
                Search saved successfully!
              </p>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-md">
              <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0" />
              <p className="text-sm text-red-800 dark:text-red-300">{error}</p>
            </div>
          )}

          {/* Name Field */}
          <div>
            <label
              htmlFor="search-name"
              className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
            >
              Search Name <span className="text-red-500">*</span>
            </label>
            <input
              ref={inputRef}
              id="search-name"
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (error) setError(null);
              }}
              placeholder="e.g., High Impact AI Technologies"
              disabled={isSubmitting || success}
              className={cn(
                "w-full px-3 py-2 border rounded-md shadow-sm text-sm",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue",
                "dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400",
                "border-gray-300 bg-white dark:border-gray-600",
                "disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            />
          </div>

          {/* Search Configuration Preview */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Search Configuration
            </label>
            <div className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-dark-surface-elevated/50 rounded-md border border-gray-200 dark:border-gray-600">
              {getSearchDescription()}
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface-elevated border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || success}
              className={cn(
                "inline-flex items-center px-4 py-2 text-sm font-medium text-white rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors",
                isSubmitting || success
                  ? "bg-brand-blue/60 cursor-not-allowed"
                  : "bg-brand-blue hover:bg-brand-dark-blue",
              )}
            >
              {isSubmitting && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {success && <Check className="h-4 w-4 mr-2" />}
              {success ? "Saved!" : "Save Search"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default SaveSearchModal;
