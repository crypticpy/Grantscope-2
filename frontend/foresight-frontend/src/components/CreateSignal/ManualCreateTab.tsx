/**
 * ManualCreateTab Component
 *
 * A full-form interface for manually creating an intelligence signal
 * with explicit control over all metadata fields. Unlike QuickCreateTab,
 * this gives the user direct control over pillar assignment, horizon,
 * maturity stage, and seed URLs.
 *
 * Features:
 * - Name and description inputs (required)
 * - Pillar multi-select with "Exploratory" checkbox
 * - Horizon selector (Near-term / Mid-term / Long-term)
 * - Stage selector (Concept through Scaling)
 * - Seed URL input for initial research sources
 * - Form validation and loading states
 *
 * @example
 * ```tsx
 * <ManualCreateTab onCreated={(card) => navigate(`/cards/${card.slug}`)} />
 * ```
 *
 * @module CreateSignal/ManualCreateTab
 */

import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Loader2, CheckCircle, AlertTriangle } from "lucide-react";
import { supabase } from "../../App";
import { cn } from "../../lib/utils";
import { type Card } from "../../lib/discovery-api";
import { SeedUrlInput } from "./SeedUrlInput";

// =============================================================================
// Types
// =============================================================================

export interface ManualCreateTabProps {
  /** Callback when a card is successfully created */
  onCreated?: (card: Card) => void;
}

// =============================================================================
// Constants
// =============================================================================

/** Available strategic pillars for multi-select */
const PILLAR_OPTIONS = [
  { code: "CH", label: "Community Health" },
  { code: "EW", label: "Economic Workforce" },
  { code: "HG", label: "Home & Government" },
  { code: "HH", label: "Housing & Homelessness" },
  { code: "MC", label: "Mobility & Connectivity" },
  { code: "PS", label: "Public Safety" },
] as const;

/** Horizon options mapping display labels to API values */
const HORIZON_OPTIONS = [
  { value: "H1", label: "Near-term (H1)" },
  { value: "H2", label: "Mid-term (H2)" },
  { value: "H3", label: "Long-term (H3)" },
] as const;

/** Maturity stage options */
const STAGE_OPTIONS = [
  { value: "1", label: "Concept" },
  { value: "2", label: "Exploring" },
  { value: "3", label: "Pilot" },
  { value: "4", label: "Implementing" },
  { value: "5", label: "Scaling" },
] as const;

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// =============================================================================
// Component
// =============================================================================

/**
 * ManualCreateTab provides a detailed form for creating intelligence
 * signals with full user control over classification and metadata.
 */
export function ManualCreateTab({ onCreated }: ManualCreateTabProps) {
  // Form fields
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPillars, setSelectedPillars] = useState<string[]>([]);
  const [isExploratory, setIsExploratory] = useState(false);
  const [horizon, setHorizon] = useState("H2");
  const [stage, setStage] = useState("1");
  const [seedUrls, setSeedUrls] = useState<string[]>([]);

  // Async state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdCard, setCreatedCard] = useState<Card | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Validation
  const isValid = name.trim().length > 0 && description.trim().length > 0;

  /**
   * Toggle a pillar in the multi-select.
   */
  const handleTogglePillar = useCallback((code: string) => {
    setSelectedPillars((prev) =>
      prev.includes(code) ? prev.filter((p) => p !== code) : [...prev, code],
    );
  }, []);

  /**
   * Handle exploratory checkbox toggle.
   * When exploratory is enabled, clear pillar selections.
   */
  const handleExploratoryToggle = useCallback((checked: boolean) => {
    setIsExploratory(checked);
    if (checked) {
      setSelectedPillars([]);
    }
  }, []);

  /**
   * Submit the manual create form to the API.
   */
  const handleSubmit = useCallback(async () => {
    if (!isValid) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        setError("Please sign in to create signals.");
        return;
      }

      const payload = {
        name: name.trim(),
        description: description.trim(),
        pillar_ids: isExploratory ? [] : selectedPillars,
        is_exploratory: isExploratory,
        horizon,
        stage_id: parseInt(stage, 10),
        seed_urls: seedUrls.length > 0 ? seedUrls : undefined,
      };

      const response = await fetch(
        `${API_BASE_URL}/api/v1/cards/create-manual`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
          },
          body: JSON.stringify(payload),
        },
      );

      if (!response.ok) {
        const errData = await response
          .json()
          .catch(() => ({ message: "Request failed" }));
        throw new Error(errData.message || `API error: ${response.status}`);
      }

      const card: Card = await response.json();
      setCreatedCard(card);
      onCreated?.(card);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create signal.");
    } finally {
      setIsSubmitting(false);
    }
  }, [
    name,
    description,
    selectedPillars,
    isExploratory,
    horizon,
    stage,
    seedUrls,
    isValid,
    onCreated,
  ]);

  /**
   * Reset the form for creating another signal.
   */
  const handleReset = useCallback(() => {
    setName("");
    setDescription("");
    setSelectedPillars([]);
    setIsExploratory(false);
    setHorizon("H2");
    setStage("1");
    setSeedUrls([]);
    setCreatedCard(null);
    setError(null);
  }, []);

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
            &ldquo;{createdCard.name}&rdquo; has been created successfully.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to={`/signals/${createdCard.slug || createdCard.id}`}
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
      {/* Name */}
      <div>
        <label
          htmlFor="manual-create-name"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
        >
          Signal Name <span className="text-red-500">*</span>
        </label>
        <input
          id="manual-create-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., AI-Powered Traffic Signal Optimization"
          disabled={isSubmitting}
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
      </div>

      {/* Description */}
      <div>
        <label
          htmlFor="manual-create-description"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
        >
          Description <span className="text-red-500">*</span>
        </label>
        <textarea
          id="manual-create-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe the trend, technology, or emerging issue..."
          rows={4}
          disabled={isSubmitting}
          className={cn(
            "w-full px-3 py-2.5 text-sm rounded-md border resize-y",
            "bg-white dark:bg-dark-surface",
            "text-gray-900 dark:text-gray-100",
            "placeholder-gray-400 dark:placeholder-gray-500",
            "border-gray-300 dark:border-gray-600",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        />
      </div>

      {/* Pillar Multi-Select */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Strategic Pillar(s)
        </label>

        {/* Exploratory checkbox */}
        <label
          className={cn(
            "inline-flex items-center gap-2 mb-3 cursor-pointer",
            "text-sm text-gray-700 dark:text-gray-300",
          )}
        >
          <input
            type="checkbox"
            checked={isExploratory}
            onChange={(e) => handleExploratoryToggle(e.target.checked)}
            disabled={isSubmitting}
            className={cn(
              "h-4 w-4 rounded border-gray-300 dark:border-gray-600",
              "text-violet-600 focus:ring-violet-500",
              "disabled:opacity-50",
            )}
          />
          <span className="text-violet-700 dark:text-violet-400 font-medium">
            Exploratory
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            (cross-cutting, not pillar-specific)
          </span>
        </label>

        {/* Pillar checkboxes */}
        {!isExploratory && (
          <div className="grid grid-cols-2 gap-2">
            {PILLAR_OPTIONS.map((pillar) => (
              <label
                key={pillar.code}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer",
                  "transition-colors duration-200",
                  selectedPillars.includes(pillar.code)
                    ? "bg-brand-blue/10 border-brand-blue text-brand-blue dark:bg-brand-blue/20 dark:border-brand-blue/60"
                    : "bg-white dark:bg-dark-surface border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300",
                  "hover:border-brand-blue/50",
                  isSubmitting && "opacity-50 cursor-not-allowed",
                )}
              >
                <input
                  type="checkbox"
                  checked={selectedPillars.includes(pillar.code)}
                  onChange={() => handleTogglePillar(pillar.code)}
                  disabled={isSubmitting}
                  className="sr-only"
                />
                <span className="text-xs font-mono font-bold">
                  {pillar.code}
                </span>
                <span className="text-sm">{pillar.label}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Horizon */}
      <div>
        <label
          htmlFor="manual-create-horizon"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
        >
          Horizon
        </label>
        <div
          className="flex gap-2"
          role="radiogroup"
          aria-label="Horizon selection"
        >
          {HORIZON_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setHorizon(option.value)}
              disabled={isSubmitting}
              role="radio"
              aria-checked={horizon === option.value}
              className={cn(
                "flex-1 px-3 py-2 text-sm font-medium rounded-md border",
                "transition-colors duration-200",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                horizon === option.value
                  ? "bg-brand-blue text-white border-brand-blue"
                  : "bg-white dark:bg-dark-surface text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-brand-blue/50",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stage */}
      <div>
        <label
          htmlFor="manual-create-stage"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
        >
          Maturity Stage
        </label>
        <select
          id="manual-create-stage"
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          disabled={isSubmitting}
          className={cn(
            "w-full px-3 py-2.5 text-sm rounded-md border",
            "bg-white dark:bg-dark-surface",
            "text-gray-900 dark:text-gray-100",
            "border-gray-300 dark:border-gray-600",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          {STAGE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Seed URLs */}
      <SeedUrlInput urls={seedUrls} onChange={setSeedUrls} max={10} />

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

      {/* Submit button */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!isValid || isSubmitting}
        className={cn(
          "w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md",
          "bg-brand-blue text-white hover:bg-brand-dark-blue",
          "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          "transition-colors duration-200",
        )}
      >
        {isSubmitting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Creating Signal...
          </>
        ) : (
          "Create Signal"
        )}
      </button>
    </div>
  );
}

export default ManualCreateTab;
