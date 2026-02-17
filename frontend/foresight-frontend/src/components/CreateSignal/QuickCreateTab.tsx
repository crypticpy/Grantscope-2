/**
 * QuickCreateTab Component
 *
 * A streamlined form for creating a new intelligence signal from a
 * simple topic phrase. The backend handles AI classification, scoring,
 * and initial research context generation.
 *
 * Features:
 * - Topic phrase input with placeholder guidance
 * - Optional workstream selector dropdown
 * - "Suggest Keywords" button for AI-generated keyword chips
 * - Loading and success states with link to the new card
 *
 * @example
 * ```tsx
 * <QuickCreateTab workstreamId="ws-123" onCreated={(card) => console.log(card)} />
 * ```
 *
 * @module CreateSignal/QuickCreateTab
 */

import { useState, useCallback, useEffect } from "react";
import { Link } from "react-router-dom";
import { Loader2, Sparkles, CheckCircle, X, AlertTriangle } from "lucide-react";
import { supabase } from "../../App";
import { cn } from "../../lib/utils";
import {
  createCardFromTopic,
  suggestKeywords,
  type CreateCardFromTopicResponse,
} from "../../lib/discovery-api";

// =============================================================================
// Types
// =============================================================================

export interface QuickCreateTabProps {
  /** Pre-selected workstream ID (optional) */
  workstreamId?: string;
  /** Callback when a card is successfully created */
  onCreated?: (card: CreateCardFromTopicResponse) => void;
}

/** Workstream option for the dropdown */
interface WorkstreamOption {
  id: string;
  name: string;
}

// =============================================================================
// Component
// =============================================================================

/**
 * QuickCreateTab allows users to create a new signal by entering a
 * short topic phrase. The system uses AI to generate a full intelligence
 * card from the topic.
 */
export function QuickCreateTab({
  workstreamId,
  onCreated,
}: QuickCreateTabProps) {
  // Form state
  const [topic, setTopic] = useState("");
  const [selectedWorkstreamId, setSelectedWorkstreamId] = useState(
    workstreamId || "",
  );
  const [keywords, setKeywords] = useState<string[]>([]);

  // Async state
  const [isCreating, setIsCreating] = useState(false);
  const [isSuggestingKeywords, setIsSuggestingKeywords] = useState(false);
  const [createdCard, setCreatedCard] =
    useState<CreateCardFromTopicResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Workstreams for dropdown
  const [workstreams, setWorkstreams] = useState<WorkstreamOption[]>([]);
  const [loadingWorkstreams, setLoadingWorkstreams] = useState(true);

  /**
   * Fetch available workstreams for the dropdown on mount.
   */
  useEffect(() => {
    async function loadWorkstreams() {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) return;

        const { data } = await supabase
          .from("workstreams")
          .select("id, name")
          .eq("created_by", session.user.id)
          .order("name");

        if (data) {
          setWorkstreams(data);
        }
      } catch {
        // Silently fail - workstream selector is optional
      } finally {
        setLoadingWorkstreams(false);
      }
    }

    loadWorkstreams();
  }, []);

  /**
   * Request AI-suggested keywords for the current topic.
   */
  const handleSuggestKeywords = useCallback(async () => {
    if (!topic.trim()) return;

    setIsSuggestingKeywords(true);
    setError(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        setError("Please sign in to use this feature.");
        return;
      }

      const result = await suggestKeywords(topic.trim(), session.access_token);
      setKeywords(result.suggestions || []);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to get keyword suggestions.",
      );
    } finally {
      setIsSuggestingKeywords(false);
    }
  }, [topic]);

  /**
   * Remove a keyword from the suggested list.
   */
  const handleRemoveKeyword = useCallback((keyword: string) => {
    setKeywords((prev) => prev.filter((k) => k !== keyword));
  }, []);

  /**
   * Create the signal card from the topic.
   */
  const handleCreate = useCallback(async () => {
    if (!topic.trim()) return;

    setIsCreating(true);
    setError(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        setError("Please sign in to create opportunities.");
        return;
      }

      const result = await createCardFromTopic(
        {
          topic: topic.trim(),
          workstream_id: selectedWorkstreamId || undefined,
        },
        session.access_token,
      );

      setCreatedCard(result);
      onCreated?.(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create opportunity.",
      );
    } finally {
      setIsCreating(false);
    }
  }, [topic, selectedWorkstreamId, keywords, onCreated]);

  /**
   * Reset form to create another signal.
   */
  const handleReset = useCallback(() => {
    setTopic("");
    setKeywords([]);
    setCreatedCard(null);
    setError(null);
    setSelectedWorkstreamId(workstreamId || "");
  }, [workstreamId]);

  // =========================================================================
  // Success State
  // =========================================================================

  if (createdCard) {
    return (
      <div className="flex flex-col items-center justify-center py-8 space-y-4">
        <div className="flex items-center justify-center w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/40">
          <CheckCircle className="h-6 w-6 text-green-600 dark:text-green-400" />
        </div>
        <div className="text-center space-y-1">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Signal Created
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            &ldquo;{createdCard.card_name}&rdquo; has been created successfully.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to={`/signals/${createdCard.card_id}`}
            className={cn(
              "inline-flex items-center px-4 py-2 text-sm font-medium rounded-md",
              "bg-brand-blue text-white hover:bg-brand-dark-blue",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
              "transition-colors duration-200",
            )}
          >
            View Card
          </Link>
          <button
            type="button"
            onClick={handleReset}
            className={cn(
              "inline-flex items-center px-4 py-2 text-sm font-medium rounded-md",
              "bg-white text-gray-700 border border-gray-300",
              "hover:bg-gray-50",
              "dark:bg-dark-surface-elevated dark:text-gray-300 dark:border-gray-600 dark:hover:bg-dark-surface-hover",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
              "transition-colors duration-200",
            )}
          >
            Create Another
          </button>
        </div>
      </div>
    );
  }

  // =========================================================================
  // Form State
  // =========================================================================

  return (
    <div className="space-y-5">
      {/* Topic input */}
      <div>
        <label
          htmlFor="quick-create-topic"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
        >
          Topic or Signal Phrase
        </label>
        <input
          id="quick-create-topic"
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g., forensics technology for law enforcement"
          disabled={isCreating}
          className={cn(
            "w-full px-3 py-2.5 text-sm rounded-md border",
            "bg-white dark:bg-dark-surface",
            "text-gray-900 dark:text-gray-100",
            "placeholder-gray-400 dark:placeholder-gray-500",
            "border-gray-300 dark:border-gray-600",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Describe a trend, technology, or emerging issue in a short phrase.
        </p>
      </div>

      {/* Workstream selector */}
      <div>
        <label
          htmlFor="quick-create-workstream"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
        >
          Workstream{" "}
          <span className="text-gray-400 dark:text-gray-500 font-normal">
            (optional)
          </span>
        </label>
        <select
          id="quick-create-workstream"
          value={selectedWorkstreamId}
          onChange={(e) => setSelectedWorkstreamId(e.target.value)}
          disabled={isCreating || loadingWorkstreams}
          className={cn(
            "w-full px-3 py-2.5 text-sm rounded-md border",
            "bg-white dark:bg-dark-surface",
            "text-gray-900 dark:text-gray-100",
            "border-gray-300 dark:border-gray-600",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          <option value="">No workstream</option>
          {workstreams.map((ws) => (
            <option key={ws.id} value={ws.id}>
              {ws.name}
            </option>
          ))}
        </select>
      </div>

      {/* Suggest Keywords */}
      <div>
        <button
          type="button"
          onClick={handleSuggestKeywords}
          disabled={!topic.trim() || isSuggestingKeywords || isCreating}
          className={cn(
            "inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md",
            "bg-white text-gray-700 border border-gray-300",
            "hover:bg-gray-50",
            "dark:bg-dark-surface-elevated dark:text-gray-300 dark:border-gray-600 dark:hover:bg-dark-surface-hover",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "transition-colors duration-200",
          )}
        >
          {isSuggestingKeywords ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          )}
          {isSuggestingKeywords ? "Suggesting..." : "Suggest Keywords"}
        </button>

        {/* Keyword chips */}
        {keywords.length > 0 && (
          <div
            className="mt-3 flex flex-wrap gap-2"
            role="list"
            aria-label="Suggested keywords"
          >
            {keywords.map((keyword) => (
              <span
                key={keyword}
                role="listitem"
                className={cn(
                  "inline-flex items-center gap-1 px-2.5 py-1 rounded-full",
                  "bg-blue-50 text-blue-700 border border-blue-200",
                  "dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700",
                  "text-xs font-medium",
                )}
              >
                {keyword}
                <button
                  type="button"
                  onClick={() => handleRemoveKeyword(keyword)}
                  className={cn(
                    "p-0.5 rounded-full",
                    "text-blue-400 hover:text-blue-600 dark:hover:text-blue-200",
                    "hover:bg-blue-100 dark:hover:bg-blue-800",
                    "focus:outline-none focus:ring-1 focus:ring-blue-400",
                    "transition-colors duration-200",
                  )}
                  aria-label={`Remove keyword: ${keyword}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div
          className={cn(
            "flex items-start gap-2 px-3 py-2.5 rounded-md",
            "bg-red-50 dark:bg-red-900/20",
            "text-sm text-red-700 dark:text-red-400",
          )}
          role="alert"
        >
          <AlertTriangle
            className="h-4 w-4 shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <span>{error}</span>
        </div>
      )}

      {/* Create button */}
      <button
        type="button"
        onClick={handleCreate}
        disabled={!topic.trim() || isCreating}
        className={cn(
          "w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md",
          "bg-brand-blue text-white hover:bg-brand-dark-blue",
          "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          "transition-colors duration-200",
        )}
      >
        {isCreating ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Creating Signal...
          </>
        ) : (
          "Create Opportunity"
        )}
      </button>
    </div>
  );
}

export default QuickCreateTab;
