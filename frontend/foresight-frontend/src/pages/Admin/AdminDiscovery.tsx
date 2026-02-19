/**
 * AdminDiscovery Page
 *
 * Discovery pipeline management dashboard with:
 * - Discovery config form (max results, dedup threshold, auto-classify)
 * - Recent discovery runs table with expandable details
 * - "Run Discovery Now" trigger button
 * - Blocked topics management (add/delete)
 * - Discovery schedules overview
 *
 * @module pages/Admin/AdminDiscovery
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  Compass,
  Play,
  Ban,
  Settings,
  Plus,
  Trash2,
  Save,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  ChevronDown,
  ChevronRight,
  Clock,
  Calendar,
} from "lucide-react";
import {
  fetchDiscoveryConfig,
  updateDiscoveryConfig,
  fetchDiscoveryRuns,
  triggerDiscovery,
  fetchDiscoveryBlocks,
  addDiscoveryBlock,
  removeDiscoveryBlock,
  fetchSchedulerJobs,
} from "../../lib/admin-api";
import type {
  DiscoveryConfig,
  DiscoveryRun,
  DiscoveryBlock,
  SchedulerJob,
} from "../../lib/admin-api";

// ============================================================================
// Types
// ============================================================================

interface ToastState {
  message: string;
  type: "success" | "error";
}

// ============================================================================
// Sub-Components
// ============================================================================

function Toast({
  message,
  type,
  onDismiss,
}: {
  message: string;
  type: "success" | "error";
  onDismiss: () => void;
}) {
  useEffect(() => {
    if (type === "success") {
      const t = setTimeout(onDismiss, 3000);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [type, onDismiss]);

  const isSuccess = type === "success";
  return (
    <div
      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm ${
        isSuccess
          ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800/50"
          : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800/50"
      }`}
    >
      {isSuccess ? (
        <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
      ) : (
        <AlertCircle className="w-4 h-4 flex-shrink-0" />
      )}
      <span className="flex-1">{message}</span>
      <button
        onClick={onDismiss}
        className="p-0.5 rounded hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function ToggleSwitch({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-brand-blue/50 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${
        checked ? "bg-brand-blue" : "bg-gray-300 dark:bg-gray-600"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          checked ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function RunStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    running: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    queued:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
    cancelled: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
  };
  return (
    <span
      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${styles[status] || "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"}`}
    >
      {status}
    </span>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "--";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(
  startedAt: string | null,
  completedAt: string | null,
): string {
  if (!startedAt) return "--";
  if (!completedAt) return "In progress";
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdminDiscovery() {
  const token = localStorage.getItem("gs2_token") || "";

  // Data state
  const [, setConfig] = useState<DiscoveryConfig | null>(null);
  const [runs, setRuns] = useState<DiscoveryRun[]>([]);
  const [blocks, setBlocks] = useState<DiscoveryBlock[]>([]);
  const [schedules, setSchedules] = useState<SchedulerJob[]>([]);

  // Form draft
  const [draftMaxResults, setDraftMaxResults] = useState(50);
  const [draftDedupThreshold, setDraftDedupThreshold] = useState(0.92);
  const [draftEnabled, setDraftEnabled] = useState(true);
  const [draftAutoClassify, setDraftAutoClassify] = useState(true);

  // Loading
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingBlocks, setLoadingBlocks] = useState(true);
  const [loadingSchedules, setLoadingSchedules] = useState(true);
  const [savingConfig, setSavingConfig] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Blocks
  const [newBlockTopic, setNewBlockTopic] = useState("");
  const [addingBlock, setAddingBlock] = useState(false);
  const [deletingBlockId, setDeletingBlockId] = useState<string | null>(null);

  // Expandable runs
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  // Toast
  const [toast, setToast] = useState<ToastState | null>(null);

  // --------------------------------------------------------------------------
  // Load data
  // --------------------------------------------------------------------------

  const loadConfig = useCallback(async () => {
    setLoadingConfig(true);
    try {
      const data = await fetchDiscoveryConfig(token);
      setConfig(data);
      const s = data.settings ?? {};
      const d = data.defaults ?? {};
      setDraftMaxResults(
        Number(s["discovery.total_cap"] ?? d["discovery.total_cap"] ?? 500),
      );
      setDraftDedupThreshold(
        Number(
          s["discovery.auto_approve_threshold"] ??
            d["discovery.auto_approve_threshold"] ??
            0.92,
        ),
      );
      setDraftEnabled(
        !(s["discovery.dry_run"] ?? d["discovery.dry_run"] ?? false),
      );
      setDraftAutoClassify(true); // not a discrete backend setting; always on
      setDirty(false);
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to load discovery config",
        type: "error",
      });
    } finally {
      setLoadingConfig(false);
    }
  }, [token]);

  const loadRuns = useCallback(async () => {
    setLoadingRuns(true);
    try {
      const data = await fetchDiscoveryRuns(token);
      setRuns(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to load discovery runs",
        type: "error",
      });
    } finally {
      setLoadingRuns(false);
    }
  }, [token]);

  const loadBlocks = useCallback(async () => {
    setLoadingBlocks(true);
    try {
      const data = await fetchDiscoveryBlocks(token);
      setBlocks(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to load discovery blocks",
        type: "error",
      });
    } finally {
      setLoadingBlocks(false);
    }
  }, [token]);

  const loadSchedules = useCallback(async () => {
    setLoadingSchedules(true);
    try {
      const data = await fetchSchedulerJobs(token);
      // Filter to discovery-related jobs
      const discoveryJobs = data.filter(
        (j) =>
          j.name.toLowerCase().includes("discovery") ||
          j.name.toLowerCase().includes("scan"),
      );
      setSchedules(discoveryJobs);
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to load discovery schedules",
        type: "error",
      });
    } finally {
      setLoadingSchedules(false);
    }
  }, [token]);

  useEffect(() => {
    loadConfig();
    loadRuns();
    loadBlocks();
    loadSchedules();
  }, [loadConfig, loadRuns, loadBlocks, loadSchedules]);

  // --------------------------------------------------------------------------
  // Config save
  // --------------------------------------------------------------------------

  const handleSaveConfig = async () => {
    setSavingConfig(true);
    try {
      await updateDiscoveryConfig(token, {
        "discovery.total_cap": draftMaxResults,
        "discovery.auto_approve_threshold": draftDedupThreshold,
        "discovery.dry_run": !draftEnabled,
      });
      setConfig((prev) =>
        prev
          ? {
              ...prev,
              settings: {
                ...prev.settings,
                "discovery.total_cap": draftMaxResults,
                "discovery.auto_approve_threshold": draftDedupThreshold,
                "discovery.dry_run": !draftEnabled,
              },
            }
          : prev,
      );
      setDirty(false);
      setToast({
        message: "Discovery configuration saved.",
        type: "success",
      });
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to save discovery config",
        type: "error",
      });
    } finally {
      setSavingConfig(false);
    }
  };

  // --------------------------------------------------------------------------
  // Trigger discovery
  // --------------------------------------------------------------------------

  const handleTriggerDiscovery = async () => {
    setTriggering(true);
    try {
      const result = await triggerDiscovery(token);
      setToast({
        message: `Discovery run started (ID: ${result.id}).`,
        type: "success",
      });
      // Reload runs after a short delay to show the new run
      setTimeout(() => loadRuns(), 2000);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to trigger discovery",
        type: "error",
      });
    } finally {
      setTriggering(false);
    }
  };

  // --------------------------------------------------------------------------
  // Block topics
  // --------------------------------------------------------------------------

  const handleAddBlock = async () => {
    if (!newBlockTopic.trim()) return;
    setAddingBlock(true);
    try {
      await addDiscoveryBlock(token, newBlockTopic.trim());
      setNewBlockTopic("");
      setToast({
        message: "Blocked topic added.",
        type: "success",
      });
      await loadBlocks();
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to add blocked topic",
        type: "error",
      });
    } finally {
      setAddingBlock(false);
    }
  };

  const handleRemoveBlock = async (blockId: string) => {
    if (!window.confirm("Remove this blocked topic?")) return;
    setDeletingBlockId(blockId);
    try {
      await removeDiscoveryBlock(token, blockId);
      setToast({ message: "Blocked topic removed.", type: "success" });
      await loadBlocks();
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to remove blocked topic",
        type: "error",
      });
    } finally {
      setDeletingBlockId(null);
    }
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Discovery Pipeline
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Configure and monitor the automated content discovery pipeline.
          </p>
        </div>
        <button
          onClick={handleTriggerDiscovery}
          disabled={triggering}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-green hover:bg-brand-green/90 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {triggering ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          Run Discovery Now
        </button>
      </div>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Section 1: Pipeline Configuration */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-brand-blue" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Pipeline Configuration
            </h2>
          </div>
          {dirty && (
            <button
              onClick={handleSaveConfig}
              disabled={savingConfig}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-brand-blue hover:bg-brand-blue/90 rounded-lg transition-colors disabled:opacity-50"
            >
              {savingConfig ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Save className="w-3.5 h-3.5" />
              )}
              Save
            </button>
          )}
        </div>

        {loadingConfig ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
                <div className="h-10 w-full bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Auto-Discovery Toggle */}
            <div className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  Auto-Discovery
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Enable automatic content discovery runs
                </p>
              </div>
              <ToggleSwitch
                checked={draftEnabled}
                onChange={(v) => {
                  setDraftEnabled(v);
                  setDirty(true);
                }}
                disabled={savingConfig}
              />
            </div>

            {/* Auto-Classify Toggle */}
            <div className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  Auto-Classification
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Automatically classify discovered content
                </p>
              </div>
              <ToggleSwitch
                checked={draftAutoClassify}
                onChange={(v) => {
                  setDraftAutoClassify(v);
                  setDirty(true);
                }}
                disabled={savingConfig}
              />
            </div>

            {/* Max Results per Run */}
            <div>
              <label
                htmlFor="max-results"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Max Results per Run
              </label>
              <input
                id="max-results"
                type="number"
                min={1}
                max={500}
                value={draftMaxResults}
                onChange={(e) => {
                  setDraftMaxResults(parseInt(e.target.value, 10) || 50);
                  setDirty(true);
                }}
                disabled={savingConfig}
                className="w-full max-w-[200px] px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors disabled:opacity-50"
              />
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Maximum cards to discover per run (1-500).
              </p>
            </div>

            {/* Deduplication Threshold */}
            <div>
              <label
                htmlFor="dedup-threshold"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Deduplication Threshold
              </label>
              <div className="flex items-center gap-4">
                <input
                  id="dedup-threshold"
                  type="range"
                  min={0.5}
                  max={1}
                  step={0.01}
                  value={draftDedupThreshold}
                  onChange={(e) => {
                    setDraftDedupThreshold(parseFloat(e.target.value));
                    setDirty(true);
                  }}
                  disabled={savingConfig}
                  className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-brand-blue disabled:opacity-50"
                />
                <span className="text-sm font-mono font-medium text-gray-900 dark:text-white w-12 text-right">
                  {draftDedupThreshold.toFixed(2)}
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Vector similarity threshold for deduplication (0.50 - 1.00).
                Higher = stricter.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Section 2: Recent Discovery Runs */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Compass className="w-5 h-5 text-brand-blue" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Recent Discovery Runs
            </h2>
            {!loadingRuns && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                ({runs.length} run{runs.length !== 1 ? "s" : ""})
              </span>
            )}
          </div>
        </div>

        {loadingRuns ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse flex items-center gap-4 p-3 rounded-lg border border-gray-100 dark:border-gray-800"
              >
                <div className="h-5 w-16 bg-gray-200 dark:bg-gray-700 rounded-full" />
                <div className="flex-1 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <Compass className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No discovery runs recorded yet. Trigger a run to get started.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400 w-8" />
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Status
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Started
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Duration
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Discovered
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Deduped
                  </th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <React.Fragment key={run.id}>
                    <tr
                      onClick={() =>
                        setExpandedRunId(
                          expandedRunId === run.id ? null : run.id,
                        )
                      }
                      className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors cursor-pointer"
                    >
                      <td className="px-4 py-3">
                        {expandedRunId === run.id ? (
                          <ChevronDown className="w-4 h-4 text-gray-400" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-gray-400" />
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <RunStatusBadge status={run.status} />
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400 whitespace-nowrap">
                        {formatDate(run.started_at)}
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                        {formatDuration(run.started_at, run.completed_at)}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">
                        {run.stats?.cards_created ?? 0}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">
                        {run.stats?.cards_deduplicated ?? 0}
                      </td>
                    </tr>
                    {/* Expanded details */}
                    {expandedRunId === run.id && (
                      <tr key={`${run.id}-details`}>
                        <td
                          colSpan={6}
                          className="px-8 py-4 bg-gray-50 dark:bg-gray-800/30 border-b border-gray-100 dark:border-gray-800"
                        >
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                            <div>
                              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                                Run ID
                              </p>
                              <code className="text-xs font-mono text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded">
                                {run.id.substring(0, 12)}...
                              </code>
                            </div>
                            <div>
                              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                                Completed
                              </p>
                              <p className="text-gray-700 dark:text-gray-300">
                                {formatDate(run.completed_at)}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                                Net Cards Created
                              </p>
                              <p className="font-semibold text-gray-900 dark:text-white">
                                {(run.stats?.cards_created ?? 0) -
                                  (run.stats?.cards_deduplicated ?? 0)}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                                Errors
                              </p>
                              {run.error_message ? (
                                <p
                                  className="text-red-600 dark:text-red-400 text-xs truncate"
                                  title={run.error_message}
                                >
                                  {run.error_message}
                                </p>
                              ) : (
                                <p className="text-green-600 dark:text-green-400">
                                  None
                                </p>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Section 3: Blocked Topics */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Ban className="w-5 h-5 text-brand-blue" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Blocked Topics
            </h2>
            {!loadingBlocks && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                ({blocks.length})
              </span>
            )}
          </div>
        </div>

        {/* Add block form */}
        <div className="flex items-center gap-2 mb-4">
          <input
            type="text"
            value={newBlockTopic}
            onChange={(e) => setNewBlockTopic(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAddBlock();
            }}
            placeholder="Enter topic to block..."
            className="flex-1 max-w-md px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
          />
          <button
            onClick={handleAddBlock}
            disabled={addingBlock || !newBlockTopic.trim()}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-brand-blue hover:bg-brand-blue/90 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {addingBlock ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            Add
          </button>
        </div>

        {loadingBlocks ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50"
              >
                <div className="h-4 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-4 w-4 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : blocks.length === 0 ? (
          <div className="text-center py-6">
            <Ban className="w-6 h-6 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No blocked topics. Add topics to exclude from discovery results.
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {blocks.map((block) => (
              <div
                key={block.id}
                className="flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800/70 transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {block.topic}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">
                    Added {formatDate(block.created_at)}
                  </span>
                </div>
                <button
                  onClick={() => handleRemoveBlock(block.id)}
                  disabled={deletingBlockId === block.id}
                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-50"
                  title="Remove block"
                >
                  {deletingBlockId === block.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Section 4: Discovery Schedules */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="flex items-center gap-2 px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <Calendar className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Discovery Schedules
          </h2>
        </div>

        {loadingSchedules ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse flex items-center gap-4 p-3 rounded-lg border border-gray-100 dark:border-gray-800"
              >
                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="flex-1 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-5 w-14 bg-gray-200 dark:bg-gray-700 rounded-full" />
              </div>
            ))}
          </div>
        ) : schedules.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <Clock className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No discovery schedules configured. Manage schedules in the
              Scheduler tab.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Name
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Schedule
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Last Run
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Next Run
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((job) => (
                  <tr
                    key={job.id}
                    className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                      {job.name}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      <code className="text-xs font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                        {job.schedule}
                      </code>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {formatDate(job.last_run)}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {formatDate(job.next_run)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                          job.enabled
                            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                            : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
                        }`}
                      >
                        {job.enabled ? "Enabled" : "Disabled"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
