/**
 * AdminJobs Page
 *
 * Background job queue management dashboard with:
 * - Stats bar: queued / running / completed (24h) / failed (24h)
 * - Filter bar: status dropdown, task type dropdown
 * - Data table: task_id, type, status, card name, created_at, started_at, duration, actions
 * - Bulk actions: "Retry All Failed" button
 * - Auto-refresh toggle (poll every 10s)
 *
 * @module pages/Admin/AdminJobs
 */

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Cog,
  RefreshCw,
  XCircle,
  RotateCcw,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  Activity,
  Clock,
  Zap,
  Timer,
} from "lucide-react";
import {
  fetchJobs,
  fetchJobStats,
  retryJob,
  cancelJob,
  retryAllFailed,
} from "../../lib/admin-api";
import type { AdminJob, JobStats, JobQueryParams } from "../../lib/admin-api";

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

function StatCard({
  label,
  value,
  icon: Icon,
  color = "text-gray-900 dark:text-white",
  bgColor = "bg-white dark:bg-dark-surface",
  loading,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  color?: string;
  bgColor?: string;
  loading: boolean;
}) {
  return (
    <div
      className={`${bgColor} rounded-lg border border-gray-200 dark:border-gray-700 p-4`}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-gray-400" />
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          {label}
        </span>
      </div>
      {loading ? (
        <div className="animate-pulse h-7 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
      ) : (
        <p className={`text-2xl font-semibold ${color}`}>{value}</p>
      )}
    </div>
  );
}

function JobStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    running: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    processing:
      "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    queued:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
    pending:
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
// Constants
// ============================================================================

const STATUS_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "queued", label: "Queued" },
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "processing", label: "Processing" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

const TASK_TYPE_OPTIONS = [
  { value: "", label: "All Types" },
  { value: "research", label: "Research" },
  { value: "deep_research", label: "Deep Research" },
  { value: "classify", label: "Classification" },
  { value: "enrich", label: "Enrichment" },
  { value: "embed", label: "Embedding" },
  { value: "discovery", label: "Discovery" },
  { value: "brief", label: "Brief" },
  { value: "scan", label: "Scan" },
];

// ============================================================================
// Main Component
// ============================================================================

export default function AdminJobs() {
  const token = localStorage.getItem("gs2_token") || "";

  // Data state
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [stats, setStats] = useState<JobStats | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [taskTypeFilter, setTaskTypeFilter] = useState("");

  // Loading
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingStats, setLoadingStats] = useState(true);
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const [retryingAll, setRetryingAll] = useState(false);

  // Auto-refresh
  const [autoRefresh, setAutoRefresh] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Toast
  const [toast, setToast] = useState<ToastState | null>(null);

  // --------------------------------------------------------------------------
  // Load data
  // --------------------------------------------------------------------------

  const loadStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const data = await fetchJobStats(token);
      setStats(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to load job stats",
        type: "error",
      });
    } finally {
      setLoadingStats(false);
    }
  }, [token]);

  const loadJobs = useCallback(async () => {
    setLoadingJobs(true);
    try {
      const params: JobQueryParams = { limit: 100 };
      if (statusFilter) params.status = statusFilter;
      if (taskTypeFilter) params.task_type = taskTypeFilter;
      const data = await fetchJobs(token, params);
      setJobs(data);
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to load jobs",
        type: "error",
      });
    } finally {
      setLoadingJobs(false);
    }
  }, [token, statusFilter, taskTypeFilter]);

  const loadAll = useCallback(() => {
    loadStats();
    loadJobs();
  }, [loadStats, loadJobs]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // --------------------------------------------------------------------------
  // Auto-refresh
  // --------------------------------------------------------------------------

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(() => {
        loadAll();
      }, 10000);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh, loadAll]);

  // --------------------------------------------------------------------------
  // Actions
  // --------------------------------------------------------------------------

  const handleRetryJob = async (taskId: string) => {
    setRetryingJobId(taskId);
    try {
      await retryJob(token, taskId);
      setToast({ message: "Job queued for retry.", type: "success" });
      await loadAll();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to retry job",
        type: "error",
      });
    } finally {
      setRetryingJobId(null);
    }
  };

  const handleCancelJob = async (taskId: string) => {
    if (!window.confirm("Cancel this job?")) return;
    setCancellingJobId(taskId);
    try {
      await cancelJob(token, taskId);
      setToast({ message: "Job cancelled.", type: "success" });
      await loadAll();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to cancel job",
        type: "error",
      });
    } finally {
      setCancellingJobId(null);
    }
  };

  const handleRetryAllFailed = async () => {
    if (!window.confirm("Retry all failed jobs?")) return;
    setRetryingAll(true);
    try {
      const result = await retryAllFailed(token);
      setToast({
        message: `${result.retried} failed job${result.retried !== 1 ? "s" : ""} queued for retry.`,
        type: "success",
      });
      await loadAll();
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to retry all failed jobs",
        type: "error",
      });
    } finally {
      setRetryingAll(false);
    }
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  const failedCount = stats?.by_status.failed ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Background Jobs
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Monitor and manage background job processing queue.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Auto-refresh toggle */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Auto-refresh
            </span>
            <ToggleSwitch checked={autoRefresh} onChange={setAutoRefresh} />
          </div>
          <button
            onClick={handleRetryAllFailed}
            disabled={retryingAll || failedCount === 0}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {retryingAll ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RotateCcw className="w-4 h-4" />
            )}
            Retry All Failed
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatCard
          label="Queued"
          value={stats ? stats.by_status.queued.toLocaleString() : "--"}
          icon={Clock}
          color="text-yellow-600 dark:text-yellow-400"
          loading={loadingStats}
        />
        <StatCard
          label="Processing"
          value={stats ? stats.by_status.processing.toLocaleString() : "--"}
          icon={Activity}
          color="text-blue-600 dark:text-blue-400"
          loading={loadingStats}
        />
        <StatCard
          label="Completed (24h)"
          value={stats ? stats.completed_24h.toLocaleString() : "--"}
          icon={Zap}
          color="text-green-600 dark:text-green-400"
          loading={loadingStats}
        />
        <StatCard
          label="Failed (24h)"
          value={stats ? stats.failed_24h.toLocaleString() : "--"}
          icon={AlertCircle}
          color="text-red-600 dark:text-red-400"
          loading={loadingStats}
        />
        <StatCard
          label="Avg Duration"
          value={
            stats?.avg_duration_seconds != null
              ? `${stats.avg_duration_seconds.toFixed(1)}s`
              : "--"
          }
          icon={Timer}
          loading={loadingStats}
        />
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          value={taskTypeFilter}
          onChange={(e) => setTaskTypeFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
        >
          {TASK_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <button
          onClick={loadAll}
          disabled={loadingJobs}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
        >
          {loadingJobs ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          Refresh
        </button>
        {autoRefresh && (
          <span className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
            <Timer className="w-3 h-3" />
            Refreshing every 10s
          </span>
        )}
      </div>

      {/* Jobs table */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loadingJobs && jobs.length === 0 ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse flex items-center gap-4 p-3 rounded-lg border border-gray-100 dark:border-gray-800"
              >
                <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-5 w-16 bg-gray-200 dark:bg-gray-700 rounded-full" />
                <div className="flex-1 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <Cog className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No jobs found matching the current filters.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Task ID
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Type
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Status
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Card
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Created
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Started
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Duration
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <code className="text-xs font-mono text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">
                        {job.id.substring(0, 8)}
                      </code>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                        {job.task_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <JobStatusBadge status={job.status} />
                    </td>
                    <td className="px-4 py-3 max-w-[200px]">
                      {job.card_name ? (
                        <span
                          className="text-xs text-gray-600 dark:text-gray-400 truncate block"
                          title={job.card_name}
                        >
                          {job.card_name}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                          --
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {formatDate(job.created_at)}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {formatDate(job.started_at)}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600 dark:text-gray-400">
                      {formatDuration(job.started_at, job.completed_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {(job.status === "failed" ||
                          job.status === "cancelled") && (
                          <button
                            onClick={() => handleRetryJob(job.id)}
                            disabled={retryingJobId === job.id}
                            className="p-1.5 text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
                            title="Retry"
                          >
                            {retryingJobId === job.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <RefreshCw className="w-4 h-4" />
                            )}
                          </button>
                        )}
                        {(job.status === "queued" ||
                          job.status === "pending" ||
                          job.status === "running" ||
                          job.status === "processing") && (
                          <button
                            onClick={() => handleCancelJob(job.id)}
                            disabled={cancellingJobId === job.id}
                            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors disabled:opacity-50"
                            title="Cancel"
                          >
                            {cancellingJobId === job.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <XCircle className="w-4 h-4" />
                            )}
                          </button>
                        )}
                        {job.error_message && (
                          <span
                            className="p-1.5 text-red-400 cursor-help"
                            title={job.error_message}
                          >
                            <AlertCircle className="w-4 h-4" />
                          </span>
                        )}
                      </div>
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
