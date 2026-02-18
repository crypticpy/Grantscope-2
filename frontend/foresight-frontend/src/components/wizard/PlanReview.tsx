/**
 * PlanReview Component
 *
 * Step 3 of the Grant Application Wizard - structured plan review and editing.
 * Displays the AI-synthesized plan from the interview in editable sections:
 * Program Overview, Staffing Plan, Budget Breakdown, Timeline, Deliverables,
 * and Success Metrics.
 *
 * Features:
 * - Auto-synthesizes plan on mount if plan data is null
 * - Inline editing with view/edit toggle per section
 * - Add/remove rows for table sections
 * - Add/remove items for list sections
 * - Debounced auto-save to backend
 * - Currency formatting for budget/salary fields
 * - Dark mode support
 *
 * @module components/wizard/PlanReview
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  FileText,
  Users,
  DollarSign,
  CalendarRange,
  ListChecks,
  BarChart3,
  Pencil,
  Check,
  Plus,
  Trash2,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";
import { cn } from "../../lib/utils";
import {
  synthesizePlan,
  updateWizardSession,
  exportWizardPlan,
  type PlanData,
  type GrantContext,
  type ExportFormat,
} from "../../lib/wizard-api";
import { DownloadButton } from "./DownloadButton";

// ============================================================================
// Constants
// ============================================================================

/** Auto-save debounce delay in milliseconds. */
const AUTO_SAVE_DELAY_MS = 1500;

/** Currency formatter for USD display. */
const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

// ============================================================================
// Types
// ============================================================================

export interface PlanReviewProps {
  sessionId: string;
  planData: PlanData | null;
  grantContext?: GrantContext | null;
  /** Entry path for the wizard session (e.g. "have_grant", "build_program") */
  entryPath?: string;
  onComplete: () => void;
  onBack: () => void;
  onPlanUpdated: (plan: PlanData) => void;
}

type SectionKey =
  | "overview"
  | "staffing"
  | "budget"
  | "timeline"
  | "deliverables"
  | "metrics";

// ============================================================================
// Helpers
// ============================================================================

async function getToken(): Promise<string | null> {
  const token = localStorage.getItem("gs2_token");
  return token || null;
}

function emptyPlan(): PlanData {
  return {
    program_overview: "",
    staffing_plan: [],
    budget: [],
    timeline: [],
    deliverables: [],
    metrics: [],
    partnerships: [],
  };
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Section wrapper with header, icon, and edit toggle.
 */
function SectionCard({
  icon,
  title,
  editing,
  onToggleEdit,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  editing: boolean;
  onToggleEdit: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          {icon}
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
        </div>
        <button
          onClick={onToggleEdit}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
            editing
              ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/30"
              : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700",
          )}
        >
          {editing ? (
            <>
              <Check className="h-3.5 w-3.5" />
              Done
            </>
          ) : (
            <>
              <Pencil className="h-3.5 w-3.5" />
              Edit
            </>
          )}
        </button>
      </div>
      {children}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

const PlanReview: React.FC<PlanReviewProps> = ({
  sessionId,
  planData: initialPlanData,
  grantContext,
  entryPath,
  onComplete,
  onBack,
  onPlanUpdated,
}) => {
  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  const [plan, setPlan] = useState<PlanData>(initialPlanData || emptyPlan());
  const [loading, setLoading] = useState(!initialPlanData);
  const [error, setError] = useState<string | null>(null);
  const [editingSections, setEditingSections] = useState<
    Record<SectionKey, boolean>
  >({
    overview: false,
    staffing: false,
    budget: false,
    timeline: false,
    deliverables: false,
    metrics: false,
  });

  // Debounce auto-save
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestPlanRef = useRef<PlanData>(plan);

  // Keep ref in sync
  useEffect(() => {
    latestPlanRef.current = plan;
  }, [plan]);

  // ---------------------------------------------------------------------------
  // Synthesize plan on mount if not provided
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (initialPlanData) return;

    let cancelled = false;

    const doSynthesize = async () => {
      const token = await getToken();
      if (!token || cancelled) return;

      try {
        const planResult = await synthesizePlan(token, sessionId);
        if (cancelled) return;
        const synthesized = planResult || emptyPlan();
        setPlan(synthesized);
        onPlanUpdated(synthesized);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to synthesize plan",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    doSynthesize();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // ---------------------------------------------------------------------------
  // Auto-save (debounced)
  // ---------------------------------------------------------------------------

  const scheduleSave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = setTimeout(async () => {
      const token = await getToken();
      if (!token) return;
      try {
        await updateWizardSession(token, sessionId, {
          plan_data: latestPlanRef.current,
        });
      } catch {
        console.warn("Auto-save of plan data failed");
      }
    }, AUTO_SAVE_DELAY_MS);
  }, [sessionId]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Update helpers
  // ---------------------------------------------------------------------------

  const updatePlan = useCallback(
    (updater: (prev: PlanData) => PlanData) => {
      setPlan((prev) => {
        const next = updater(prev);
        onPlanUpdated(next);
        scheduleSave();
        return next;
      });
    },
    [onPlanUpdated, scheduleSave],
  );

  const toggleSection = useCallback((section: SectionKey) => {
    setEditingSections((prev) => ({ ...prev, [section]: !prev[section] }));
  }, []);

  // ---------------------------------------------------------------------------
  // Retry handler
  // ---------------------------------------------------------------------------

  const handleRetry = useCallback(async () => {
    setError(null);
    setLoading(true);
    const token = await getToken();
    if (!token) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }
    try {
      const planResult = await synthesizePlan(token, sessionId);
      const synthesized = planResult || emptyPlan();
      setPlan(synthesized);
      onPlanUpdated(synthesized);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to synthesize plan",
      );
    } finally {
      setLoading(false);
    }
  }, [sessionId, onPlanUpdated]);

  // ---------------------------------------------------------------------------
  // Download plan handler
  // ---------------------------------------------------------------------------

  const handleDownloadPlan = useCallback(
    async (format: ExportFormat) => {
      const token = await getToken();
      if (!token) return;

      try {
        const blob = await exportWizardPlan(token, sessionId, format);
        const ext = format === "pdf" ? "pdf" : "docx";
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `project-plan-${sessionId.slice(0, 8)}.${ext}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (err) {
        console.error("Failed to download plan:", err);
      }
    },
    [sessionId],
  );

  // ---------------------------------------------------------------------------
  // Render: Loading
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-8 sm:p-12">
        <div className="flex flex-col items-center justify-center text-center">
          <Loader2 className="h-8 w-8 animate-spin text-brand-blue mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Building your project plan from our conversation...
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md">
            This may take a moment as we structure your responses into a
            comprehensive plan.
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
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-8 sm:p-12">
        <div className="flex flex-col items-center justify-center text-center">
          <AlertCircle className="h-8 w-8 text-red-400 mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Failed to Build Plan
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4 max-w-md">
            {error}
          </p>
          <button
            onClick={handleRetry}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-brand-blue rounded-md hover:bg-brand-dark-blue transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Plan Sections
  // ---------------------------------------------------------------------------

  const budgetTotal = plan.budget.reduce((sum, b) => sum + (b.amount || 0), 0);

  return (
    <div className="space-y-4">
      {/* Grant context banner */}
      {grantContext?.grant_name && (
        <div className="bg-brand-blue/5 dark:bg-brand-blue/10 border border-brand-blue/20 rounded-lg px-4 py-3">
          <p className="text-sm text-brand-dark-blue dark:text-brand-blue font-medium">
            Plan for: {grantContext.grant_name}
            {grantContext.grantor ? ` (${grantContext.grantor})` : ""}
          </p>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* Program Overview */}
      {/* ------------------------------------------------------------------- */}
      <SectionCard
        icon={<FileText className="h-5 w-5 text-brand-blue" />}
        title="Program Overview"
        editing={editingSections.overview}
        onToggleEdit={() => toggleSection("overview")}
      >
        {editingSections.overview ? (
          <textarea
            value={plan.program_overview || ""}
            onChange={(e) =>
              updatePlan((p) => ({ ...p, program_overview: e.target.value }))
            }
            rows={6}
            className={cn(
              "w-full rounded-lg border border-gray-300 dark:border-gray-600",
              "bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100",
              "px-3 py-2.5 text-sm leading-relaxed resize-y",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
            )}
          />
        ) : (
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
            {plan.program_overview || (
              <span className="italic text-gray-400 dark:text-gray-500">
                No program overview yet. Click Edit to add one.
              </span>
            )}
          </p>
        )}
      </SectionCard>

      {/* ------------------------------------------------------------------- */}
      {/* Staffing Plan */}
      {/* ------------------------------------------------------------------- */}
      <SectionCard
        icon={<Users className="h-5 w-5 text-indigo-500" />}
        title="Staffing Plan"
        editing={editingSections.staffing}
        onToggleEdit={() => toggleSection("staffing")}
      >
        {plan.staffing_plan.length === 0 && !editingSections.staffing ? (
          <p className="text-sm italic text-gray-400 dark:text-gray-500">
            No staffing entries yet. Click Edit to add roles.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400">
                    Role
                  </th>
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400 w-16">
                    FTE
                  </th>
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400 w-32">
                    Salary Est.
                  </th>
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400">
                    Responsibilities
                  </th>
                  {editingSections.staffing && <th className="w-10" />}
                </tr>
              </thead>
              <tbody>
                {plan.staffing_plan.map((entry, idx) => (
                  <tr
                    key={idx}
                    className={cn(
                      "border-b border-gray-100 dark:border-gray-800",
                      idx % 2 === 1 && "bg-gray-50/50 dark:bg-gray-800/30",
                    )}
                  >
                    {editingSections.staffing ? (
                      <>
                        <td className="py-2 pr-2">
                          <input
                            type="text"
                            value={entry.role}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                staffing_plan: p.staffing_plan.map((s, i) =>
                                  i === idx
                                    ? { ...s, role: e.target.value }
                                    : s,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 pr-2">
                          <input
                            type="number"
                            step="0.1"
                            min="0"
                            value={entry.fte}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                staffing_plan: p.staffing_plan.map((s, i) =>
                                  i === idx
                                    ? {
                                        ...s,
                                        fte: parseFloat(e.target.value) || 0,
                                      }
                                    : s,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 pr-2">
                          <input
                            type="number"
                            min="0"
                            value={entry.salary_estimate}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                staffing_plan: p.staffing_plan.map((s, i) =>
                                  i === idx
                                    ? {
                                        ...s,
                                        salary_estimate:
                                          parseFloat(e.target.value) || 0,
                                      }
                                    : s,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 pr-2">
                          <input
                            type="text"
                            value={entry.responsibilities}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                staffing_plan: p.staffing_plan.map((s, i) =>
                                  i === idx
                                    ? { ...s, responsibilities: e.target.value }
                                    : s,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 text-center">
                          <button
                            onClick={() =>
                              updatePlan((p) => ({
                                ...p,
                                staffing_plan: p.staffing_plan.filter(
                                  (_, i) => i !== idx,
                                ),
                              }))
                            }
                            className="p-1 text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors"
                            aria-label="Remove row"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-2 pr-3 text-gray-900 dark:text-gray-100">
                          {entry.role}
                        </td>
                        <td className="py-2 pr-3 text-gray-700 dark:text-gray-300">
                          {entry.fte}
                        </td>
                        <td className="py-2 pr-3 text-gray-700 dark:text-gray-300">
                          {currencyFormatter.format(entry.salary_estimate)}
                        </td>
                        <td className="py-2 pr-3 text-gray-700 dark:text-gray-300">
                          {entry.responsibilities}
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {editingSections.staffing && (
          <button
            onClick={() =>
              updatePlan((p) => ({
                ...p,
                staffing_plan: [
                  ...p.staffing_plan,
                  {
                    role: "",
                    fte: 1.0,
                    salary_estimate: 0,
                    responsibilities: "",
                  },
                ],
              }))
            }
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-brand-blue hover:text-brand-dark-blue transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Role
          </button>
        )}
      </SectionCard>

      {/* ------------------------------------------------------------------- */}
      {/* Budget Breakdown */}
      {/* ------------------------------------------------------------------- */}
      <SectionCard
        icon={<DollarSign className="h-5 w-5 text-green-600" />}
        title="Budget Breakdown"
        editing={editingSections.budget}
        onToggleEdit={() => toggleSection("budget")}
      >
        {plan.budget.length === 0 && !editingSections.budget ? (
          <p className="text-sm italic text-gray-400 dark:text-gray-500">
            No budget entries yet. Click Edit to add line items.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400">
                    Category
                  </th>
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400 w-32">
                    Amount
                  </th>
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400">
                    Justification
                  </th>
                  {editingSections.budget && <th className="w-10" />}
                </tr>
              </thead>
              <tbody>
                {plan.budget.map((entry, idx) => (
                  <tr
                    key={idx}
                    className={cn(
                      "border-b border-gray-100 dark:border-gray-800",
                      idx % 2 === 1 && "bg-gray-50/50 dark:bg-gray-800/30",
                    )}
                  >
                    {editingSections.budget ? (
                      <>
                        <td className="py-2 pr-2">
                          <input
                            type="text"
                            value={entry.category}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                budget: p.budget.map((b, i) =>
                                  i === idx
                                    ? { ...b, category: e.target.value }
                                    : b,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 pr-2">
                          <input
                            type="number"
                            min="0"
                            value={entry.amount}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                budget: p.budget.map((b, i) =>
                                  i === idx
                                    ? {
                                        ...b,
                                        amount: parseFloat(e.target.value) || 0,
                                      }
                                    : b,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 pr-2">
                          <input
                            type="text"
                            value={entry.justification}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                budget: p.budget.map((b, i) =>
                                  i === idx
                                    ? { ...b, justification: e.target.value }
                                    : b,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 text-center">
                          <button
                            onClick={() =>
                              updatePlan((p) => ({
                                ...p,
                                budget: p.budget.filter((_, i) => i !== idx),
                              }))
                            }
                            className="p-1 text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors"
                            aria-label="Remove row"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-2 pr-3 text-gray-900 dark:text-gray-100">
                          {entry.category}
                        </td>
                        <td className="py-2 pr-3 text-gray-700 dark:text-gray-300">
                          {currencyFormatter.format(entry.amount)}
                        </td>
                        <td className="py-2 pr-3 text-gray-700 dark:text-gray-300">
                          {entry.justification}
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
              {/* Total row */}
              <tfoot>
                <tr className="border-t-2 border-gray-300 dark:border-gray-600">
                  <td className="py-2 pr-3 font-semibold text-gray-900 dark:text-white">
                    Total
                  </td>
                  <td className="py-2 pr-3 font-semibold text-gray-900 dark:text-white">
                    {currencyFormatter.format(budgetTotal)}
                  </td>
                  <td colSpan={editingSections.budget ? 2 : 1} />
                </tr>
              </tfoot>
            </table>
          </div>
        )}

        {editingSections.budget && (
          <button
            onClick={() =>
              updatePlan((p) => ({
                ...p,
                budget: [
                  ...p.budget,
                  { category: "", amount: 0, justification: "" },
                ],
              }))
            }
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-brand-blue hover:text-brand-dark-blue transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Line Item
          </button>
        )}
      </SectionCard>

      {/* ------------------------------------------------------------------- */}
      {/* Timeline */}
      {/* ------------------------------------------------------------------- */}
      <SectionCard
        icon={<CalendarRange className="h-5 w-5 text-amber-500" />}
        title="Timeline"
        editing={editingSections.timeline}
        onToggleEdit={() => toggleSection("timeline")}
      >
        {plan.timeline.length === 0 && !editingSections.timeline ? (
          <p className="text-sm italic text-gray-400 dark:text-gray-500">
            No timeline phases yet. Click Edit to add phases.
          </p>
        ) : (
          <div className="space-y-3">
            {plan.timeline.map((phase, idx) => (
              <div
                key={idx}
                className={cn(
                  "rounded-lg border p-4",
                  "border-gray-200 dark:border-gray-700",
                  "bg-gray-50/50 dark:bg-dark-surface-deep/50",
                )}
              >
                {editingSections.timeline ? (
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 space-y-2">
                        <input
                          type="text"
                          value={phase.phase}
                          onChange={(e) =>
                            updatePlan((p) => ({
                              ...p,
                              timeline: p.timeline.map((t, i) =>
                                i === idx ? { ...t, phase: e.target.value } : t,
                              ),
                            }))
                          }
                          placeholder="Phase name"
                          className="w-full px-2 py-1 text-sm font-medium border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                        />
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={phase.start}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                timeline: p.timeline.map((t, i) =>
                                  i === idx
                                    ? { ...t, start: e.target.value }
                                    : t,
                                ),
                              }))
                            }
                            placeholder="Start (e.g. Month 1)"
                            className="flex-1 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                          <input
                            type="text"
                            value={phase.end}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                timeline: p.timeline.map((t, i) =>
                                  i === idx ? { ...t, end: e.target.value } : t,
                                ),
                              }))
                            }
                            placeholder="End (e.g. Month 6)"
                            className="flex-1 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          updatePlan((p) => ({
                            ...p,
                            timeline: p.timeline.filter((_, i) => i !== idx),
                          }))
                        }
                        className="p-1 text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors mt-1"
                        aria-label="Remove phase"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>

                    {/* Milestone editing */}
                    <div className="pl-2 space-y-1.5">
                      <p className="text-xs font-medium text-gray-500 dark:text-gray-400">
                        Milestones
                      </p>
                      {phase.milestones.map((milestone, mIdx) => (
                        <div key={mIdx} className="flex items-center gap-2">
                          <span className="text-gray-400 dark:text-gray-500 text-xs">
                            &bull;
                          </span>
                          <input
                            type="text"
                            value={milestone}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                timeline: p.timeline.map((t, i) =>
                                  i === idx
                                    ? {
                                        ...t,
                                        milestones: t.milestones.map((m, mi) =>
                                          mi === mIdx ? e.target.value : m,
                                        ),
                                      }
                                    : t,
                                ),
                              }))
                            }
                            className="flex-1 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                          <button
                            onClick={() =>
                              updatePlan((p) => ({
                                ...p,
                                timeline: p.timeline.map((t, i) =>
                                  i === idx
                                    ? {
                                        ...t,
                                        milestones: t.milestones.filter(
                                          (_, mi) => mi !== mIdx,
                                        ),
                                      }
                                    : t,
                                ),
                              }))
                            }
                            className="p-0.5 text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors"
                            aria-label="Remove milestone"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                      <button
                        onClick={() =>
                          updatePlan((p) => ({
                            ...p,
                            timeline: p.timeline.map((t, i) =>
                              i === idx
                                ? { ...t, milestones: [...t.milestones, ""] }
                                : t,
                            ),
                          }))
                        }
                        className="inline-flex items-center gap-1 text-xs text-brand-blue hover:text-brand-dark-blue transition-colors"
                      >
                        <Plus className="h-3 w-3" />
                        Add Milestone
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
                        {phase.phase}
                      </h4>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {phase.start}
                        {phase.end ? ` \u2013 ${phase.end}` : ""}
                      </span>
                    </div>
                    {phase.milestones.length > 0 && (
                      <ul className="space-y-1">
                        {phase.milestones.map((m, mIdx) => (
                          <li
                            key={mIdx}
                            className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300"
                          >
                            <span className="text-gray-400 dark:text-gray-500 mt-0.5">
                              &bull;
                            </span>
                            {m}
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        {editingSections.timeline && (
          <button
            onClick={() =>
              updatePlan((p) => ({
                ...p,
                timeline: [
                  ...p.timeline,
                  { phase: "", start: "", end: "", milestones: [] },
                ],
              }))
            }
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-brand-blue hover:text-brand-dark-blue transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Phase
          </button>
        )}
      </SectionCard>

      {/* ------------------------------------------------------------------- */}
      {/* Deliverables */}
      {/* ------------------------------------------------------------------- */}
      <SectionCard
        icon={<ListChecks className="h-5 w-5 text-teal-500" />}
        title="Deliverables"
        editing={editingSections.deliverables}
        onToggleEdit={() => toggleSection("deliverables")}
      >
        {plan.deliverables.length === 0 && !editingSections.deliverables ? (
          <p className="text-sm italic text-gray-400 dark:text-gray-500">
            No deliverables yet. Click Edit to add items.
          </p>
        ) : (
          <ul className="space-y-2">
            {plan.deliverables.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                {editingSections.deliverables ? (
                  <>
                    <span className="text-gray-400 dark:text-gray-500 mt-2 text-sm">
                      &bull;
                    </span>
                    <input
                      type="text"
                      value={item}
                      onChange={(e) =>
                        updatePlan((p) => ({
                          ...p,
                          deliverables: p.deliverables.map((d, i) =>
                            i === idx ? e.target.value : d,
                          ),
                        }))
                      }
                      className="flex-1 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                    />
                    <button
                      onClick={() =>
                        updatePlan((p) => ({
                          ...p,
                          deliverables: p.deliverables.filter(
                            (_, i) => i !== idx,
                          ),
                        }))
                      }
                      className="p-1 text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors mt-0.5"
                      aria-label="Remove deliverable"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </>
                ) : (
                  <>
                    <span className="text-gray-400 dark:text-gray-500 mt-0.5 text-sm">
                      &bull;
                    </span>
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      {item}
                    </span>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}

        {editingSections.deliverables && (
          <button
            onClick={() =>
              updatePlan((p) => ({
                ...p,
                deliverables: [...p.deliverables, ""],
              }))
            }
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-brand-blue hover:text-brand-dark-blue transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Deliverable
          </button>
        )}
      </SectionCard>

      {/* ------------------------------------------------------------------- */}
      {/* Success Metrics */}
      {/* ------------------------------------------------------------------- */}
      <SectionCard
        icon={<BarChart3 className="h-5 w-5 text-purple-500" />}
        title="Success Metrics"
        editing={editingSections.metrics}
        onToggleEdit={() => toggleSection("metrics")}
      >
        {plan.metrics.length === 0 && !editingSections.metrics ? (
          <p className="text-sm italic text-gray-400 dark:text-gray-500">
            No success metrics yet. Click Edit to add metrics.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400">
                    Metric
                  </th>
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400">
                    Target
                  </th>
                  <th className="text-left py-2 pr-3 font-medium text-gray-600 dark:text-gray-400">
                    How Measured
                  </th>
                  {editingSections.metrics && <th className="w-10" />}
                </tr>
              </thead>
              <tbody>
                {plan.metrics.map((entry, idx) => (
                  <tr
                    key={idx}
                    className={cn(
                      "border-b border-gray-100 dark:border-gray-800",
                      idx % 2 === 1 && "bg-gray-50/50 dark:bg-gray-800/30",
                    )}
                  >
                    {editingSections.metrics ? (
                      <>
                        <td className="py-2 pr-2">
                          <input
                            type="text"
                            value={entry.metric}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                metrics: p.metrics.map((m, i) =>
                                  i === idx
                                    ? { ...m, metric: e.target.value }
                                    : m,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 pr-2">
                          <input
                            type="text"
                            value={entry.target}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                metrics: p.metrics.map((m, i) =>
                                  i === idx
                                    ? { ...m, target: e.target.value }
                                    : m,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 pr-2">
                          <input
                            type="text"
                            value={entry.measurement_method}
                            onChange={(e) =>
                              updatePlan((p) => ({
                                ...p,
                                metrics: p.metrics.map((m, i) =>
                                  i === idx
                                    ? {
                                        ...m,
                                        measurement_method: e.target.value,
                                      }
                                    : m,
                                ),
                              }))
                            }
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          />
                        </td>
                        <td className="py-2 text-center">
                          <button
                            onClick={() =>
                              updatePlan((p) => ({
                                ...p,
                                metrics: p.metrics.filter((_, i) => i !== idx),
                              }))
                            }
                            className="p-1 text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors"
                            aria-label="Remove row"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-2 pr-3 text-gray-900 dark:text-gray-100">
                          {entry.metric}
                        </td>
                        <td className="py-2 pr-3 text-gray-700 dark:text-gray-300">
                          {entry.target}
                        </td>
                        <td className="py-2 pr-3 text-gray-700 dark:text-gray-300">
                          {entry.measurement_method}
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {editingSections.metrics && (
          <button
            onClick={() =>
              updatePlan((p) => ({
                ...p,
                metrics: [
                  ...p.metrics,
                  { metric: "", target: "", measurement_method: "" },
                ],
              }))
            }
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-brand-blue hover:text-brand-dark-blue transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Metric
          </button>
        )}
      </SectionCard>

      {/* ------------------------------------------------------------------- */}
      {/* Bottom Actions */}
      {/* ------------------------------------------------------------------- */}
      <div className="flex items-center justify-between pt-2">
        <button
          onClick={onBack}
          className={cn(
            "inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-colors",
            "text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface",
            "border border-gray-300 dark:border-gray-600",
            "hover:bg-gray-50 dark:hover:bg-gray-800",
          )}
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Interview
        </button>

        <div className="flex items-center gap-3">
          <DownloadButton
            label="Download Plan"
            onDownload={handleDownloadPlan}
            disabled={!plan.program_overview}
            size="sm"
          />

          {entryPath === "build_program" ? (
            <button
              onClick={onComplete}
              className={cn(
                "inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white rounded-md transition-colors",
                "bg-brand-blue hover:bg-brand-dark-blue",
              )}
            >
              Find Matching Grants
              <ArrowRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={onComplete}
              className={cn(
                "inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white rounded-md transition-colors",
                "bg-brand-blue hover:bg-brand-dark-blue",
              )}
            >
              Generate Full Proposal
              <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default PlanReview;
