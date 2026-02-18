/**
 * GrantWizard Page
 *
 * Top-level wizard page for guided grant application preparation.
 * Manages wizard session state, step navigation, and renders the
 * appropriate step component based on current progress.
 *
 * Features:
 * - 6-step guided workflow (Welcome -> Grant Details -> Interview -> Plan Review -> Proposal -> Export)
 * - Session persistence via backend API
 * - URL param support for resuming sessions and card-based entry
 * - Auto-save on step changes
 * - Step progress indicator
 * - Dark mode support
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  Suspense,
  lazy,
} from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { Loader2, XCircle } from "lucide-react";
import { WizardStepProgress } from "../components/wizard/WizardStepProgress";
import { WizardSaveExit } from "../components/wizard/WizardSaveExit";
import {
  getWizardSession,
  createWizardSession,
  updateWizardSession,
  type WizardSession,
  type GrantContext,
  type PlanData,
  type EntryPath,
} from "../lib/wizard-api";

// Lazy-load step components
const WizardWelcome = lazy(() => import("../components/wizard/WizardWelcome"));
const GrantInput = lazy(() => import("../components/wizard/GrantInput"));
const GrantSearch = lazy(() => import("../components/wizard/GrantSearch"));
const WizardInterview = lazy(
  () => import("../components/wizard/WizardInterview"),
);
const PlanReview = lazy(() => import("../components/wizard/PlanReview"));
const ProposalPreview = lazy(
  () => import("../components/wizard/ProposalPreview"),
);
const ExportComplete = lazy(
  () => import("../components/wizard/ExportComplete"),
);
const GrantMatching = lazy(() => import("../components/wizard/GrantMatching"));

// =============================================================================
// Constants
// =============================================================================

const STEP_LABELS = [
  "Welcome",
  "Grant Details",
  "Interview",
  "Plan Review",
  "Proposal",
  "Export",
];

// =============================================================================
// Helper
// =============================================================================

/**
 * Retrieves the current session access token.
 */
async function getToken(): Promise<string | null> {
  const token = localStorage.getItem("gs2_token");
  return token || null;
}

// =============================================================================
// Component
// =============================================================================

const GrantWizard: React.FC = () => {
  const { sessionId: routeSessionId } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Core state
  const [currentStep, setCurrentStep] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(
    routeSessionId || null,
  );
  const [sessionData, setSessionData] = useState<WizardSession | null>(null);
  const [entryPath, setEntryPath] = useState<EntryPath | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Track if initial load has completed to avoid double-saves
  const initialLoadDone = useRef(false);
  // Track previous step to detect changes for auto-save
  const prevStep = useRef<number>(0);

  // URL query params
  const cardId = searchParams.get("card_id");
  // workstream_id available via searchParams.get("workstream_id") when needed
  const querySessionId = searchParams.get("session_id");

  // ---------------------------------------------------------------------------
  // Data Fetching & Initialization
  // ---------------------------------------------------------------------------

  const loadSession = useCallback(async (id: string) => {
    const token = await getToken();
    if (!token) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    try {
      const data = await getWizardSession(token, id);
      setSessionData(data);
      setSessionId(data.id);
      setCurrentStep(data.current_step);
      setEntryPath(data.entry_path);
      prevStep.current = data.current_step;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load wizard session",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const createSessionForCard = useCallback(async () => {
    const token = await getToken();
    if (!token) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    try {
      // Pass card_id so the backend pre-populates grant context from card data,
      // sources, and deep research reports.
      const data = await createWizardSession(
        token,
        "have_grant",
        cardId ?? undefined,
      );
      setSessionData(data);
      setSessionId(data.id);
      // Backend sets current_step=2 when card context is loaded; use that.
      const step = data.current_step ?? 2;
      setCurrentStep(step);
      prevStep.current = step;
      // Update URL for bookmarking/resume
      navigate(`/apply/${data.id}`, { replace: true });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create wizard session",
      );
    } finally {
      setLoading(false);
    }
  }, [cardId, navigate]);

  useEffect(() => {
    const init = async () => {
      // Priority 1: Route param session ID (e.g. /apply/:sessionId)
      if (routeSessionId) {
        await loadSession(routeSessionId);
        initialLoadDone.current = true;
        return;
      }

      // Priority 2: Query param session_id (e.g. /apply?session_id=xxx)
      if (querySessionId) {
        await loadSession(querySessionId);
        initialLoadDone.current = true;
        return;
      }

      // Priority 3: Card ID — create session and skip to interview
      if (cardId) {
        await createSessionForCard();
        initialLoadDone.current = true;
        return;
      }

      // Default: show welcome step (step 0)
      setLoading(false);
      initialLoadDone.current = true;
    };

    init();
  }, [
    routeSessionId,
    querySessionId,
    cardId,
    loadSession,
    createSessionForCard,
  ]);

  // ---------------------------------------------------------------------------
  // Auto-save on step change
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!initialLoadDone.current || !sessionId) return;
    if (prevStep.current === currentStep) return;

    prevStep.current = currentStep;

    const autoSave = async () => {
      const token = await getToken();
      if (!token) return;

      setIsSaving(true);
      try {
        const updated = await updateWizardSession(token, sessionId, {
          current_step: currentStep,
        });
        setSessionData(updated);
      } catch {
        // Auto-save failures are non-critical; don't disrupt the user
        console.warn("Auto-save failed for wizard step", currentStep);
      } finally {
        setIsSaving(false);
      }
    };

    autoSave();
  }, [currentStep, sessionId]);

  // ---------------------------------------------------------------------------
  // Step Navigation
  // ---------------------------------------------------------------------------

  const goNext = useCallback(() => {
    setCurrentStep((prev) => Math.min(prev + 1, STEP_LABELS.length - 1));
  }, []);

  const goBack = useCallback(() => {
    setCurrentStep((prev) => Math.max(prev - 1, 0));
  }, []);

  /**
   * Called when the user selects an entry path on the Welcome step.
   * Creates a new wizard session and advances to step 1.
   */
  const handleSelectPath = useCallback(
    async (path: EntryPath) => {
      const token = await getToken();
      if (!token) {
        setError("Not authenticated");
        return;
      }

      try {
        const newSession = await createWizardSession(token, path);
        setSessionId(newSession.id);
        setSessionData(newSession);
        setEntryPath(path);
        // Update URL to include session ID for bookmarking/resume
        navigate(`/apply/${newSession.id}`, { replace: true });
        // For build_program, backend sets current_step=2 (skip grant details)
        const nextStep =
          newSession.current_step > 0 ? newSession.current_step : 1;
        setCurrentStep(nextStep);
        // Do NOT set prevStep.current here — let the auto-save effect
        // detect the change (0 → nextStep) and persist it to the backend.
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to create wizard session",
        );
      }
    },
    [navigate],
  );

  /**
   * Called when GrantInput finishes processing a grant URL/file.
   * Saves the extracted grant context to the session and advances.
   */
  const handleGrantProcessed = useCallback(
    async (grantContext: GrantContext, _newCardId?: string) => {
      const token = await getToken();
      if (!token || !sessionId) return;

      try {
        const updated = await updateWizardSession(token, sessionId, {
          grant_context: grantContext,
        });
        setSessionData(updated);
        goNext();
      } catch {
        console.warn("Failed to save grant context");
        // Still advance — data was processed even if save failed
        goNext();
      }
    },
    [sessionId, goNext],
  );

  /**
   * Called when GrantSearch selects a grant card.
   * Saves the partial grant context to the session and advances.
   */
  const handleGrantSelected = useCallback(
    async (_selectedCardId: string, grantContext: Partial<GrantContext>) => {
      const token = await getToken();
      if (!token || !sessionId) return;

      try {
        const updated = await updateWizardSession(token, sessionId, {
          grant_context: grantContext as GrantContext,
        });
        setSessionData(updated);
        goNext();
      } catch {
        console.warn("Failed to save selected grant");
        goNext();
      }
    },
    [sessionId, goNext],
  );

  /**
   * Called when PlanReview updates the plan data locally.
   * Keeps sessionData in sync so downstream steps see updated plan.
   */
  const handlePlanUpdated = useCallback((plan: PlanData) => {
    setSessionData((prev) => (prev ? { ...prev, plan_data: plan } : prev));
  }, []);

  /**
   * Called when GrantMatching attaches a grant to the session.
   * Reloads session data to pick up the new grant_context and card_id.
   * Stays on step 4 so renderStep4 re-renders as ProposalPreview
   * (since card_id is now set).
   */
  const handleGrantAttached = useCallback(async () => {
    if (!sessionId) return;
    const token = await getToken();
    if (!token) return;
    try {
      const updated = await getWizardSession(token, sessionId);
      setSessionData(updated);
    } catch {
      // Non-critical — grant was attached server-side, proceed anyway
    }
    // Do NOT call goNext() — stay on step 4 so the user sees
    // ProposalPreview now that card_id is attached.
  }, [sessionId]);

  // ---------------------------------------------------------------------------
  // Render: Loading
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-brand-faded-white dark:bg-brand-dark-blue">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-brand-blue mx-auto" />
          <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
            Loading grant wizard...
          </p>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Error
  // ---------------------------------------------------------------------------

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-brand-faded-white dark:bg-brand-dark-blue">
        <div className="text-center max-w-md">
          <XCircle className="h-10 w-10 text-red-400 mx-auto" />
          <h2 className="mt-3 text-lg font-semibold text-gray-900 dark:text-white">
            Failed to Load Wizard
          </h2>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            {error}
          </p>
          <button
            onClick={() => navigate(-1)}
            className="mt-4 px-4 py-2 text-sm font-medium text-white bg-brand-blue rounded-md hover:bg-brand-dark-blue transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Step Content
  // ---------------------------------------------------------------------------

  /** Suspense fallback spinner shared by all lazy-loaded step components. */
  const suspenseFallback = (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="h-6 w-6 animate-spin text-brand-blue" />
    </div>
  );

  /**
   * Step 4 branches between GrantMatching (build_program path without a
   * grant attached) and ProposalPreview (default).
   */
  const renderStep4 = () => {
    if (entryPath === "build_program" && !sessionData?.card_id) {
      return (
        <Suspense fallback={suspenseFallback}>
          <GrantMatching
            sessionId={sessionId!}
            onGrantAttached={handleGrantAttached}
            onSkip={goNext}
            onBack={goBack}
          />
        </Suspense>
      );
    }
    return (
      <Suspense fallback={suspenseFallback}>
        <ProposalPreview
          sessionId={sessionId!}
          proposalId={sessionData?.proposal_id ?? null}
          grantContext={sessionData?.grant_context ?? null}
          onComplete={goNext}
          onBack={goBack}
        />
      </Suspense>
    );
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <Suspense fallback={suspenseFallback}>
            <WizardWelcome onSelectPath={handleSelectPath} />
          </Suspense>
        );

      case 1: {
        // Decide which grant details component based on entry path
        const entryPath = sessionData?.entry_path ?? "have_grant";

        if (entryPath === "find_grant") {
          return (
            <Suspense fallback={suspenseFallback}>
              <GrantSearch
                sessionId={sessionId!}
                onGrantSelected={handleGrantSelected}
                onBack={goBack}
              />
            </Suspense>
          );
        }

        // Default: "have_grant" path
        return (
          <Suspense fallback={suspenseFallback}>
            <GrantInput
              sessionId={sessionId!}
              onGrantProcessed={handleGrantProcessed}
              onBack={goBack}
            />
          </Suspense>
        );
      }

      case 2:
        return (
          <Suspense fallback={suspenseFallback}>
            <WizardInterview
              sessionId={sessionId!}
              conversationId={sessionData?.conversation_id ?? null}
              grantContext={sessionData?.grant_context ?? undefined}
              entryPath={entryPath ?? undefined}
              onComplete={goNext}
              onBack={goBack}
            />
          </Suspense>
        );

      case 3:
        return (
          <Suspense fallback={suspenseFallback}>
            <PlanReview
              sessionId={sessionId!}
              planData={sessionData?.plan_data ?? null}
              grantContext={sessionData?.grant_context ?? null}
              entryPath={entryPath ?? undefined}
              onComplete={goNext}
              onBack={goBack}
              onPlanUpdated={handlePlanUpdated}
            />
          </Suspense>
        );

      case 4:
        return renderStep4();

      case 5:
        return (
          <Suspense fallback={suspenseFallback}>
            <ExportComplete
              sessionId={sessionId!}
              proposalId={sessionData?.proposal_id ?? null}
              grantContext={sessionData?.grant_context ?? null}
              entryPath={entryPath ?? undefined}
              hasPlan={!!sessionData?.plan_data}
            />
          </Suspense>
        );

      default:
        return null;
    }
  };

  // ---------------------------------------------------------------------------
  // Render: Main Layout
  // ---------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-brand-faded-white dark:bg-brand-dark-blue">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Step progress + save bar - hidden on welcome step */}
        {currentStep > 0 && (
          <>
            <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 mb-4">
              <WizardStepProgress currentStep={currentStep} />
            </div>
            <div className="mb-6 rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
              <WizardSaveExit
                saving={isSaving}
                lastSaved={sessionData?.updated_at ?? null}
              />
            </div>
          </>
        )}

        {/* Step content */}
        <div className="mb-6">{renderStepContent()}</div>
      </div>
    </div>
  );
};

export default GrantWizard;
