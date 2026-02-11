/**
 * CreateSignalModal Component
 *
 * A multi-step wizard for creating new intelligence signals. Provides
 * three steps:
 *
 * - **Step 1: Define Signal** - Choose Quick (topic phrase) or Manual (full form)
 * - **Step 2: Source Preferences** - Configure source categories, domains, keywords
 * - **Step 3: Review & Create** - Confirmation summary with research depth option
 *
 * Uses a custom overlay-based modal (no Radix Dialog dependency required).
 * Includes keyboard accessibility (Escape to close, focus trapping).
 *
 * @example
 * ```tsx
 * const [isOpen, setIsOpen] = useState(false);
 *
 * <CreateSignalModal
 *   isOpen={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   workstreamId="ws-abc-123"
 * />
 * ```
 *
 * @module CreateSignal/CreateSignalModal
 */

import React, { useState, useCallback, useEffect, useRef } from "react";
import {
  X,
  Zap,
  PenTool,
  ChevronRight,
  ChevronLeft,
  Check,
  Loader2,
  Sparkles,
  AlertTriangle,
  CheckCircle,
  Search,
  Telescope,
} from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "../../lib/utils";
import { supabase } from "../../App";
import {
  createCardFromTopic,
  suggestKeywords,
  type CreateCardFromTopicResponse,
  type Card,
} from "../../lib/discovery-api";
import { SeedUrlInput } from "./SeedUrlInput";
import {
  SourcePreferencesStep,
  type SourcePreferences,
} from "./SourcePreferencesStep";

// =============================================================================
// Types
// =============================================================================

export interface CreateSignalModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Optional pre-selected workstream ID (passed to QuickCreateTab) */
  workstreamId?: string;
  /** Optional callback fired after a signal is successfully created */
  onSuccess?: () => void;
}

/** Wizard step numbers */
type WizardStep = 1 | 2 | 3;

/** Signal creation mode */
type CreateMode = "quick" | "manual";

/** Research depth option */
type ResearchDepth = "quick" | "deep";

/** Full wizard state */
interface WizardState {
  step: WizardStep;
  mode: CreateMode;
  // Quick mode data
  topic: string;
  workstreamId: string;
  keywords: string[];
  // Manual mode data
  name: string;
  description: string;
  selectedPillars: string[];
  isExploratory: boolean;
  horizon: string;
  stage: string;
  seedUrls: string[];
  // Source preferences (step 2)
  sourcePreferences: SourcePreferences;
  // Step 3
  researchDepth: ResearchDepth;
}

// =============================================================================
// Constants
// =============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

/** Step labels for the indicator */
const STEP_LABELS: Record<WizardStep, string> = {
  1: "Define Signal",
  2: "Source Preferences",
  3: "Review & Create",
};

/** Default source preferences */
const DEFAULT_SOURCE_PREFERENCES: SourcePreferences = {
  enabled_categories: ["news", "government"],
  preferred_type: "news",
  priority_domains: [],
  custom_rss_feeds: [],
  keywords: [],
};

/** Workstream option for the dropdown */
interface WorkstreamOption {
  id: string;
  name: string;
}

/** Initial wizard state factory */
function createInitialState(workstreamId?: string): WizardState {
  return {
    step: 1,
    mode: "quick",
    topic: "",
    workstreamId: workstreamId || "",
    keywords: [],
    name: "",
    description: "",
    selectedPillars: [],
    isExploratory: false,
    horizon: "H2",
    stage: "1",
    seedUrls: [],
    sourcePreferences: { ...DEFAULT_SOURCE_PREFERENCES },
    researchDepth: "quick",
  };
}

// =============================================================================
// Step Indicator Component
// =============================================================================

interface StepIndicatorProps {
  currentStep: WizardStep;
  onStepClick: (step: WizardStep) => void;
}

function StepIndicator({ currentStep, onStepClick }: StepIndicatorProps) {
  const steps: WizardStep[] = [1, 2, 3];

  return (
    <div className="flex items-center justify-between px-6 py-3">
      {steps.map((step, index) => {
        const isCompleted = step < currentStep;
        const isCurrent = step === currentStep;
        const isUpcoming = step > currentStep;
        const isClickable = step < currentStep;

        return (
          <React.Fragment key={step}>
            {/* Step circle + label */}
            <button
              type="button"
              onClick={() => isClickable && onStepClick(step)}
              disabled={!isClickable}
              className={cn(
                "flex items-center gap-2 group",
                isClickable ? "cursor-pointer" : "cursor-default",
              )}
              aria-label={`Step ${step}: ${STEP_LABELS[step]}${isCompleted ? " (completed)" : isCurrent ? " (current)" : ""}`}
              aria-current={isCurrent ? "step" : undefined}
            >
              <div
                className={cn(
                  "flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold",
                  "transition-colors duration-150",
                  isCompleted && "bg-brand-blue text-white",
                  isCurrent &&
                    "bg-brand-blue text-white ring-2 ring-brand-blue/30 ring-offset-1 ring-offset-white dark:ring-offset-[#1e2158]",
                  isUpcoming &&
                    "bg-gray-200 dark:bg-[#3d4176] text-gray-500 dark:text-gray-400",
                  isClickable &&
                    "group-hover:bg-brand-dark-blue group-hover:text-white",
                )}
              >
                {isCompleted ? (
                  <Check className="h-3.5 w-3.5" aria-hidden="true" />
                ) : (
                  step
                )}
              </div>
              <span
                className={cn(
                  "text-xs font-medium hidden sm:inline",
                  isCurrent
                    ? "text-gray-900 dark:text-gray-100"
                    : "text-gray-500 dark:text-gray-400",
                  isClickable &&
                    "group-hover:text-gray-900 dark:group-hover:text-gray-100",
                )}
              >
                {STEP_LABELS[step]}
              </span>
            </button>

            {/* Connector line */}
            {index < steps.length - 1 && (
              <div
                className={cn(
                  "flex-1 h-0.5 mx-2 rounded-full",
                  step < currentStep
                    ? "bg-brand-blue"
                    : "bg-gray-200 dark:bg-[#3d4176]",
                )}
                aria-hidden="true"
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// =============================================================================
// Component
// =============================================================================

/**
 * CreateSignalModal provides a multi-step wizard for creating
 * new intelligence signals. Handles overlay behavior, keyboard events,
 * and clean state reset on close.
 */
export function CreateSignalModal({
  isOpen,
  onClose,
  workstreamId,
  onSuccess,
}: CreateSignalModalProps) {
  const [state, setState] = useState<WizardState>(() =>
    createInitialState(workstreamId),
  );
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Async state
  const [isCreating, setIsCreating] = useState(false);
  const [isSuggestingKeywords, setIsSuggestingKeywords] = useState(false);
  const [createdCard, setCreatedCard] = useState<
    CreateCardFromTopicResponse | Card | null
  >(null);
  const [error, setError] = useState<string | null>(null);

  // Workstreams for dropdown
  const [workstreams, setWorkstreams] = useState<WorkstreamOption[]>([]);
  const [loadingWorkstreams, setLoadingWorkstreams] = useState(true);

  /**
   * Reset wizard state when modal opens.
   */
  useEffect(() => {
    if (isOpen) {
      setState(createInitialState(workstreamId));
      setCreatedCard(null);
      setError(null);
      setIsCreating(false);
      requestAnimationFrame(() => {
        closeButtonRef.current?.focus();
      });
    }
  }, [isOpen, workstreamId]);

  /**
   * Load workstreams on mount.
   */
  useEffect(() => {
    if (!isOpen) return;

    async function loadWorkstreams() {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) return;

        const { data } = await supabase
          .from("workstreams")
          .select("id, name")
          .eq("user_id", session.user.id)
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
  }, [isOpen]);

  /**
   * Handle keyboard events: Escape to close, Tab trapping.
   */
  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }

      // Simple focus trap
      if (e.key === "Tab" && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  /**
   * Prevent body scroll when modal is open.
   */
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  /**
   * Handle overlay click to close (only when clicking the backdrop).
   */
  const handleOverlayClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [onClose],
  );

  // ===========================================================================
  // State update helpers
  // ===========================================================================

  const updateState = useCallback((partial: Partial<WizardState>) => {
    setState((prev) => ({ ...prev, ...partial }));
  }, []);

  const goToStep = useCallback((step: WizardStep) => {
    setState((prev) => ({ ...prev, step }));
    setError(null);
  }, []);

  // ===========================================================================
  // Step 1 Handlers
  // ===========================================================================

  /**
   * Toggle a pillar in the multi-select.
   */
  const handleTogglePillar = useCallback((code: string) => {
    setState((prev) => ({
      ...prev,
      selectedPillars: prev.selectedPillars.includes(code)
        ? prev.selectedPillars.filter((p) => p !== code)
        : [...prev.selectedPillars, code],
    }));
  }, []);

  /**
   * Handle exploratory checkbox toggle.
   */
  const handleExploratoryToggle = useCallback((checked: boolean) => {
    setState((prev) => ({
      ...prev,
      isExploratory: checked,
      selectedPillars: checked ? [] : prev.selectedPillars,
    }));
  }, []);

  /**
   * Request AI-suggested keywords for the current topic.
   */
  const handleSuggestKeywords = useCallback(async () => {
    if (!state.topic.trim()) return;

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

      const result = await suggestKeywords(
        state.topic.trim(),
        session.access_token,
      );
      updateState({ keywords: result.keywords || [] });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to get keyword suggestions.",
      );
    } finally {
      setIsSuggestingKeywords(false);
    }
  }, [state.topic, updateState]);

  /**
   * Remove a keyword from the suggested list.
   */
  const handleRemoveKeyword = useCallback(
    (keyword: string) => {
      updateState({
        keywords: state.keywords.filter((k) => k !== keyword),
      });
    },
    [state.keywords, updateState],
  );

  /**
   * Validate step 1 data before proceeding.
   */
  const isStep1Valid =
    state.mode === "quick"
      ? state.topic.trim().length > 0
      : state.name.trim().length > 0 && state.description.trim().length > 0;

  // ===========================================================================
  // Step 3: Submit
  // ===========================================================================

  /**
   * Submit the wizard to create the signal.
   */
  const handleCreate = useCallback(async () => {
    setIsCreating(true);
    setError(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        setError("Please sign in to create signals.");
        return;
      }

      if (state.mode === "quick") {
        const result = await createCardFromTopic(
          {
            topic: state.topic.trim(),
            workstream_id: state.workstreamId || undefined,
            source_preferences: state.sourcePreferences,
            research_depth: state.researchDepth,
            keywords: state.keywords.length > 0 ? state.keywords : undefined,
          } as Record<string, unknown> & {
            topic: string;
            workstream_id?: string;
          },
          session.access_token,
        );
        setCreatedCard(result);
        onSuccess?.();
      } else {
        // Manual mode
        const payload = {
          name: state.name.trim(),
          description: state.description.trim(),
          pillar_ids: state.isExploratory ? [] : state.selectedPillars,
          is_exploratory: state.isExploratory,
          horizon: state.horizon,
          stage: state.stage,
          seed_urls: state.seedUrls.length > 0 ? state.seedUrls : undefined,
          source_preferences: state.sourcePreferences,
          research_depth: state.researchDepth,
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
        onSuccess?.();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create signal.");
    } finally {
      setIsCreating(false);
    }
  }, [state, onSuccess]);

  // ===========================================================================
  // Render helpers
  // ===========================================================================

  /** Get the display name for a created card regardless of mode. */
  const getCreatedCardName = (): string => {
    if (!createdCard) return "";
    if ("card_name" in createdCard) return createdCard.card_name;
    if ("name" in createdCard) return createdCard.name;
    return "";
  };

  /** Get the link path for a created card. */
  const getCreatedCardPath = (): string => {
    if (!createdCard) return "/";
    if ("card_id" in createdCard) return `/cards/${createdCard.card_id}`;
    if ("slug" in createdCard)
      return `/cards/${createdCard.slug || createdCard.id}`;
    return "/";
  };

  /** Get pillar label from code. */
  const getPillarLabel = (code: string): string => {
    return PILLAR_OPTIONS.find((p) => p.code === code)?.label || code;
  };

  /** Get stage label from value. */
  const getStageLabel = (value: string): string => {
    return STAGE_OPTIONS.find((s) => s.value === value)?.label || value;
  };

  /** Get horizon label from value. */
  const getHorizonLabel = (value: string): string => {
    return HORIZON_OPTIONS.find((h) => h.value === value)?.label || value;
  };

  /** Count enabled source preferences for summary. */
  const getSourceSummary = (): string => {
    const count = state.sourcePreferences.enabled_categories.length;
    const domains = state.sourcePreferences.priority_domains.length;
    const feeds = state.sourcePreferences.custom_rss_feeds.length;
    const keywords = state.sourcePreferences.keywords.length;
    const parts: string[] = [];
    if (count > 0)
      parts.push(`${count} source categor${count === 1 ? "y" : "ies"}`);
    if (domains > 0)
      parts.push(`${domains} priority domain${domains === 1 ? "" : "s"}`);
    if (feeds > 0) parts.push(`${feeds} custom feed${feeds === 1 ? "" : "s"}`);
    if (keywords > 0)
      parts.push(`${keywords} keyword${keywords === 1 ? "" : "s"}`);
    return parts.length > 0 ? parts.join(", ") : "Default settings";
  };

  if (!isOpen) return null;

  // ===========================================================================
  // Success State
  // ===========================================================================

  if (createdCard) {
    return (
      <div
        className={cn(
          "fixed inset-0 z-50 flex items-start justify-center",
          "bg-black/50 dark:bg-black/70",
          "backdrop-blur-sm",
          "overflow-y-auto py-8 sm:py-16",
        )}
        onClick={handleOverlayClick}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-signal-title"
      >
        <div
          ref={modalRef}
          className={cn(
            "relative w-full max-w-2xl mx-4",
            "bg-white dark:bg-[#1e2158]",
            "rounded-xl shadow-2xl",
            "border border-gray-200 dark:border-gray-700",
            "animate-in fade-in-0 zoom-in-95 duration-200",
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <h2
              id="create-signal-title"
              className="text-lg font-semibold text-gray-900 dark:text-gray-100"
            >
              Signal Created
            </h2>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              className={cn(
                "p-1.5 rounded-md",
                "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
                "hover:bg-gray-100 dark:hover:bg-gray-700",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue",
                "transition-colors duration-150",
              )}
              aria-label="Close dialog"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Success content */}
          <div className="flex flex-col items-center justify-center px-6 py-10 space-y-4">
            <div className="flex items-center justify-center w-14 h-14 rounded-full bg-green-100 dark:bg-green-900/40">
              <CheckCircle className="h-7 w-7 text-green-600 dark:text-green-400" />
            </div>
            <div className="text-center space-y-1">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Signal Created Successfully
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                &ldquo;{getCreatedCardName()}&rdquo; has been created and
                {state.researchDepth === "deep"
                  ? " deep research has been queued."
                  : " a quick scan has been initiated."}
              </p>
            </div>
            <div className="flex items-center gap-3 pt-2">
              <Link
                to={getCreatedCardPath()}
                className={cn(
                  "inline-flex items-center px-4 py-2 text-sm font-medium rounded-md",
                  "bg-brand-blue text-white hover:bg-brand-dark-blue",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                  "transition-colors duration-150",
                )}
              >
                View Card
              </Link>
              <button
                type="button"
                onClick={() => {
                  setState(createInitialState(workstreamId));
                  setCreatedCard(null);
                  setError(null);
                }}
                className={cn(
                  "inline-flex items-center px-4 py-2 text-sm font-medium rounded-md",
                  "bg-white text-gray-700 border border-gray-300",
                  "hover:bg-gray-50",
                  "dark:bg-[#3d4176] dark:text-gray-300 dark:border-gray-600 dark:hover:bg-[#4d5186]",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                  "transition-colors duration-150",
                )}
              >
                Create Another
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ===========================================================================
  // Wizard Content
  // ===========================================================================

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-start justify-center",
        "bg-black/50 dark:bg-black/70",
        "backdrop-blur-sm",
        "overflow-y-auto py-8 sm:py-16",
      )}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-signal-title"
    >
      <div
        ref={modalRef}
        className={cn(
          "relative w-full max-w-2xl mx-4",
          "bg-white dark:bg-[#1e2158]",
          "rounded-xl shadow-2xl",
          "border border-gray-200 dark:border-gray-700",
          "animate-in fade-in-0 zoom-in-95 duration-200",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2
            id="create-signal-title"
            className="text-lg font-semibold text-gray-900 dark:text-gray-100"
          >
            Create Signal
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className={cn(
              "p-1.5 rounded-md",
              "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
              "hover:bg-gray-100 dark:hover:bg-gray-700",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue",
              "transition-colors duration-150",
            )}
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Step Indicator */}
        <StepIndicator currentStep={state.step} onStepClick={goToStep} />

        {/* Divider */}
        <div className="border-b border-gray-200 dark:border-gray-700" />

        {/* Step Content */}
        <div className="px-6 py-5 max-h-[60vh] overflow-y-auto">
          {/* ================================================================
              Step 1: Define Signal
              ================================================================ */}
          {state.step === 1 && (
            <div className="space-y-5">
              {/* Mode toggle */}
              <div>
                <div
                  className="flex rounded-lg bg-gray-100 dark:bg-[#2d3166] p-1"
                  role="tablist"
                  aria-label="Signal creation method"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={state.mode === "quick"}
                    onClick={() => updateState({ mode: "quick" })}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md",
                      "transition-all duration-150",
                      "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-inset",
                      state.mode === "quick"
                        ? "bg-white dark:bg-[#3d4176] text-gray-900 dark:text-gray-100 shadow-sm"
                        : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300",
                    )}
                  >
                    <Zap className="h-4 w-4" aria-hidden="true" />
                    Quick Create
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={state.mode === "manual"}
                    onClick={() => updateState({ mode: "manual" })}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md",
                      "transition-all duration-150",
                      "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-inset",
                      state.mode === "manual"
                        ? "bg-white dark:bg-[#3d4176] text-gray-900 dark:text-gray-100 shadow-sm"
                        : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300",
                    )}
                  >
                    <PenTool className="h-4 w-4" aria-hidden="true" />
                    Manual Create
                  </button>
                </div>
                <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 text-center">
                  {state.mode === "quick"
                    ? "Enter a topic and let AI do the rest"
                    : "Full control over all signal fields"}
                </p>
              </div>

              {/* Quick Mode Fields */}
              {state.mode === "quick" && (
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
                      value={state.topic}
                      onChange={(e) => updateState({ topic: e.target.value })}
                      placeholder="e.g., forensics technology for law enforcement"
                      className={cn(
                        "w-full px-3 py-2.5 text-sm rounded-md border",
                        "bg-white dark:bg-[#2d3166]",
                        "text-gray-900 dark:text-gray-100",
                        "placeholder-gray-400 dark:placeholder-gray-500",
                        "border-gray-300 dark:border-gray-600",
                        "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
                      )}
                    />
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      Describe a trend, technology, or emerging issue in a short
                      phrase.
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
                      value={state.workstreamId}
                      onChange={(e) =>
                        updateState({ workstreamId: e.target.value })
                      }
                      disabled={loadingWorkstreams}
                      className={cn(
                        "w-full px-3 py-2.5 text-sm rounded-md border",
                        "bg-white dark:bg-[#2d3166]",
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
                      disabled={!state.topic.trim() || isSuggestingKeywords}
                      className={cn(
                        "inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md",
                        "bg-white text-gray-700 border border-gray-300",
                        "hover:bg-gray-50",
                        "dark:bg-[#3d4176] dark:text-gray-300 dark:border-gray-600 dark:hover:bg-[#4d5186]",
                        "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "transition-colors duration-150",
                      )}
                    >
                      {isSuggestingKeywords ? (
                        <Loader2
                          className="h-4 w-4 animate-spin"
                          aria-hidden="true"
                        />
                      ) : (
                        <Sparkles className="h-4 w-4" aria-hidden="true" />
                      )}
                      {isSuggestingKeywords
                        ? "Suggesting..."
                        : "Suggest Keywords"}
                    </button>

                    {/* Keyword chips */}
                    {state.keywords.length > 0 && (
                      <div
                        className="mt-3 flex flex-wrap gap-2"
                        role="list"
                        aria-label="Suggested keywords"
                      >
                        {state.keywords.map((keyword) => (
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
                                "transition-colors duration-150",
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
                </div>
              )}

              {/* Manual Mode Fields */}
              {state.mode === "manual" && (
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
                      value={state.name}
                      onChange={(e) => updateState({ name: e.target.value })}
                      placeholder="e.g., AI-Powered Traffic Signal Optimization"
                      className={cn(
                        "w-full px-3 py-2.5 text-sm rounded-md border",
                        "bg-white dark:bg-[#2d3166]",
                        "text-gray-900 dark:text-gray-100",
                        "placeholder-gray-400 dark:placeholder-gray-500",
                        "border-gray-300 dark:border-gray-600",
                        "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
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
                      value={state.description}
                      onChange={(e) =>
                        updateState({ description: e.target.value })
                      }
                      placeholder="Describe the trend, technology, or emerging issue..."
                      rows={3}
                      className={cn(
                        "w-full px-3 py-2.5 text-sm rounded-md border resize-y",
                        "bg-white dark:bg-[#2d3166]",
                        "text-gray-900 dark:text-gray-100",
                        "placeholder-gray-400 dark:placeholder-gray-500",
                        "border-gray-300 dark:border-gray-600",
                        "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
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
                        checked={state.isExploratory}
                        onChange={(e) =>
                          handleExploratoryToggle(e.target.checked)
                        }
                        className={cn(
                          "h-4 w-4 rounded border-gray-300 dark:border-gray-600",
                          "text-violet-600 focus:ring-violet-500",
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
                    {!state.isExploratory && (
                      <div className="grid grid-cols-2 gap-2">
                        {PILLAR_OPTIONS.map((pillar) => (
                          <label
                            key={pillar.code}
                            className={cn(
                              "flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer",
                              "transition-colors duration-150",
                              state.selectedPillars.includes(pillar.code)
                                ? "bg-brand-blue/10 border-brand-blue text-brand-blue dark:bg-brand-blue/20 dark:border-brand-blue/60"
                                : "bg-white dark:bg-[#2d3166] border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300",
                              "hover:border-brand-blue/50",
                            )}
                          >
                            <input
                              type="checkbox"
                              checked={state.selectedPillars.includes(
                                pillar.code,
                              )}
                              onChange={() => handleTogglePillar(pillar.code)}
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
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
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
                          onClick={() => updateState({ horizon: option.value })}
                          role="radio"
                          aria-checked={state.horizon === option.value}
                          className={cn(
                            "flex-1 px-3 py-2 text-sm font-medium rounded-md border",
                            "transition-colors duration-150",
                            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                            state.horizon === option.value
                              ? "bg-brand-blue text-white border-brand-blue"
                              : "bg-white dark:bg-[#2d3166] text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-brand-blue/50",
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
                      value={state.stage}
                      onChange={(e) => updateState({ stage: e.target.value })}
                      className={cn(
                        "w-full px-3 py-2.5 text-sm rounded-md border",
                        "bg-white dark:bg-[#2d3166]",
                        "text-gray-900 dark:text-gray-100",
                        "border-gray-300 dark:border-gray-600",
                        "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
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
                  <SeedUrlInput
                    urls={state.seedUrls}
                    onChange={(urls) => updateState({ seedUrls: urls })}
                    max={10}
                  />
                </div>
              )}
            </div>
          )}

          {/* ================================================================
              Step 2: Source Preferences
              ================================================================ */}
          {state.step === 2 && (
            <SourcePreferencesStep
              value={state.sourcePreferences}
              onChange={(prefs) => updateState({ sourcePreferences: prefs })}
            />
          )}

          {/* ================================================================
              Step 3: Review & Create
              ================================================================ */}
          {state.step === 3 && (
            <div className="space-y-5">
              {/* Signal Summary */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Signal Summary
                </h3>
                <div
                  className={cn(
                    "rounded-xl border p-4 space-y-3",
                    "bg-gray-50 dark:bg-[#2d3166]",
                    "border-gray-200 dark:border-gray-600",
                  )}
                >
                  {state.mode === "quick" ? (
                    <>
                      <div className="flex items-start gap-2">
                        <Zap
                          className="h-4 w-4 mt-0.5 text-brand-blue shrink-0"
                          aria-hidden="true"
                        />
                        <div>
                          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                            Mode
                          </div>
                          <div className="text-sm text-gray-900 dark:text-gray-100">
                            Quick Create (AI-generated)
                          </div>
                        </div>
                      </div>
                      <div className="flex items-start gap-2">
                        <Search
                          className="h-4 w-4 mt-0.5 text-gray-400 shrink-0"
                          aria-hidden="true"
                        />
                        <div>
                          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                            Topic
                          </div>
                          <div className="text-sm text-gray-900 dark:text-gray-100">
                            {state.topic}
                          </div>
                        </div>
                      </div>
                      {state.workstreamId && (
                        <div className="flex items-start gap-2">
                          <div className="h-4 w-4 mt-0.5 shrink-0" />
                          <div>
                            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                              Workstream
                            </div>
                            <div className="text-sm text-gray-900 dark:text-gray-100">
                              {workstreams.find(
                                (ws) => ws.id === state.workstreamId,
                              )?.name || state.workstreamId}
                            </div>
                          </div>
                        </div>
                      )}
                      {state.keywords.length > 0 && (
                        <div className="flex items-start gap-2">
                          <div className="h-4 w-4 mt-0.5 shrink-0" />
                          <div>
                            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                              Keywords
                            </div>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {state.keywords.map((kw) => (
                                <span
                                  key={kw}
                                  className={cn(
                                    "inline-flex items-center px-2 py-0.5 rounded-full",
                                    "bg-blue-50 text-blue-700 border border-blue-200",
                                    "dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700",
                                    "text-xs",
                                  )}
                                >
                                  {kw}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <div className="flex items-start gap-2">
                        <PenTool
                          className="h-4 w-4 mt-0.5 text-brand-blue shrink-0"
                          aria-hidden="true"
                        />
                        <div>
                          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                            Mode
                          </div>
                          <div className="text-sm text-gray-900 dark:text-gray-100">
                            Manual Create
                          </div>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                            Signal Name
                          </div>
                          <div className="text-sm text-gray-900 dark:text-gray-100 mt-0.5">
                            {state.name}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                            Horizon
                          </div>
                          <div className="text-sm text-gray-900 dark:text-gray-100 mt-0.5">
                            {getHorizonLabel(state.horizon)}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                            Stage
                          </div>
                          <div className="text-sm text-gray-900 dark:text-gray-100 mt-0.5">
                            {getStageLabel(state.stage)}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                            Pillar(s)
                          </div>
                          <div className="text-sm text-gray-900 dark:text-gray-100 mt-0.5">
                            {state.isExploratory
                              ? "Exploratory"
                              : state.selectedPillars.length > 0
                                ? state.selectedPillars
                                    .map(getPillarLabel)
                                    .join(", ")
                                : "None selected"}
                          </div>
                        </div>
                      </div>
                      <div>
                        <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Description
                        </div>
                        <div className="text-sm text-gray-900 dark:text-gray-100 mt-0.5 line-clamp-3">
                          {state.description}
                        </div>
                      </div>
                      {state.seedUrls.length > 0 && (
                        <div>
                          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                            Seed URLs
                          </div>
                          <div className="text-sm text-gray-900 dark:text-gray-100 mt-0.5">
                            {state.seedUrls.length} URL
                            {state.seedUrls.length !== 1 ? "s" : ""}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Source Preferences Summary */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Source Preferences
                </h3>
                <div
                  className={cn(
                    "rounded-xl border p-4",
                    "bg-gray-50 dark:bg-[#2d3166]",
                    "border-gray-200 dark:border-gray-600",
                  )}
                >
                  <div className="text-sm text-gray-900 dark:text-gray-100">
                    {getSourceSummary()}
                  </div>
                  {state.sourcePreferences.enabled_categories.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {state.sourcePreferences.enabled_categories.map((cat) => (
                        <span
                          key={cat}
                          className={cn(
                            "inline-flex items-center px-2 py-0.5 rounded-full",
                            "bg-brand-blue/10 text-brand-blue border border-brand-blue/20",
                            "dark:bg-brand-blue/20 dark:text-blue-300 dark:border-brand-blue/30",
                            "text-xs capitalize",
                          )}
                        >
                          {cat.replace("_", " ")}
                        </span>
                      ))}
                    </div>
                  )}
                  {state.sourcePreferences.preferred_type && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                      Preferred type:{" "}
                      <span className="text-gray-700 dark:text-gray-300">
                        {state.sourcePreferences.preferred_type.replace(
                          "_",
                          " ",
                        )}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Research Depth */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Initial Research
                </h3>
                <div
                  className="space-y-2"
                  role="radiogroup"
                  aria-label="Research depth"
                >
                  <label
                    className={cn(
                      "flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer",
                      "transition-colors duration-150",
                      state.researchDepth === "quick"
                        ? "bg-brand-blue/10 border-brand-blue dark:bg-brand-blue/20 dark:border-brand-blue/60"
                        : "bg-white dark:bg-[#2d3166] border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500",
                    )}
                  >
                    <input
                      type="radio"
                      name="research_depth"
                      value="quick"
                      checked={state.researchDepth === "quick"}
                      onChange={() => updateState({ researchDepth: "quick" })}
                      className={cn(
                        "h-4 w-4 border-gray-300 dark:border-gray-600",
                        "text-brand-blue focus:ring-brand-blue",
                      )}
                    />
                    <div className="flex items-center gap-2.5 flex-1">
                      <Search
                        className={cn(
                          "h-5 w-5 shrink-0",
                          state.researchDepth === "quick"
                            ? "text-brand-blue"
                            : "text-gray-400",
                        )}
                        aria-hidden="true"
                      />
                      <div>
                        <div
                          className={cn(
                            "text-sm font-medium",
                            state.researchDepth === "quick"
                              ? "text-brand-blue dark:text-blue-300"
                              : "text-gray-900 dark:text-gray-100",
                          )}
                        >
                          Quick scan
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          ~5 sources, faster results
                        </div>
                      </div>
                    </div>
                  </label>

                  <label
                    className={cn(
                      "flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer",
                      "transition-colors duration-150",
                      state.researchDepth === "deep"
                        ? "bg-brand-blue/10 border-brand-blue dark:bg-brand-blue/20 dark:border-brand-blue/60"
                        : "bg-white dark:bg-[#2d3166] border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500",
                    )}
                  >
                    <input
                      type="radio"
                      name="research_depth"
                      value="deep"
                      checked={state.researchDepth === "deep"}
                      onChange={() => updateState({ researchDepth: "deep" })}
                      className={cn(
                        "h-4 w-4 border-gray-300 dark:border-gray-600",
                        "text-brand-blue focus:ring-brand-blue",
                      )}
                    />
                    <div className="flex items-center gap-2.5 flex-1">
                      <Telescope
                        className={cn(
                          "h-5 w-5 shrink-0",
                          state.researchDepth === "deep"
                            ? "text-brand-blue"
                            : "text-gray-400",
                        )}
                        aria-hidden="true"
                      />
                      <div>
                        <div
                          className={cn(
                            "text-sm font-medium",
                            state.researchDepth === "deep"
                              ? "text-brand-blue dark:text-blue-300"
                              : "text-gray-900 dark:text-gray-100",
                          )}
                        >
                          Deep dive
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          ~15 sources, comprehensive analysis
                        </div>
                      </div>
                    </div>
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="px-6 pb-2">
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
          </div>
        )}

        {/* Footer with navigation buttons */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-700">
          {/* Left side: Back button */}
          <div>
            {state.step > 1 && (
              <button
                type="button"
                onClick={() => goToStep((state.step - 1) as WizardStep)}
                disabled={isCreating}
                className={cn(
                  "inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md",
                  "bg-white text-gray-700 border border-gray-300",
                  "hover:bg-gray-50",
                  "dark:bg-[#3d4176] dark:text-gray-300 dark:border-gray-600 dark:hover:bg-[#4d5186]",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                  "transition-colors duration-150",
                )}
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                Back
              </button>
            )}
          </div>

          {/* Right side: Next/Create button */}
          <div>
            {state.step === 1 && (
              <button
                type="button"
                onClick={() => goToStep(2)}
                disabled={!isStep1Valid}
                className={cn(
                  "inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium rounded-md",
                  "bg-brand-blue text-white hover:bg-brand-dark-blue",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                  "transition-colors duration-150",
                )}
              >
                Next: Configure Sources
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            )}

            {state.step === 2 && (
              <button
                type="button"
                onClick={() => goToStep(3)}
                className={cn(
                  "inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium rounded-md",
                  "bg-brand-blue text-white hover:bg-brand-dark-blue",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                  "transition-colors duration-150",
                )}
              >
                Next: Review
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            )}

            {state.step === 3 && (
              <button
                type="button"
                onClick={handleCreate}
                disabled={isCreating}
                className={cn(
                  "inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-medium rounded-md",
                  "bg-brand-blue text-white hover:bg-brand-dark-blue",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                  "transition-colors duration-150",
                )}
              >
                {isCreating ? (
                  <>
                    <Loader2
                      className="h-4 w-4 animate-spin"
                      aria-hidden="true"
                    />
                    Creating Signal...
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4" aria-hidden="true" />
                    Create Signal
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default CreateSignalModal;
