/**
 * AdminScheduler Page
 *
 * Scheduler management dashboard with:
 * - Scheduler status indicator (running/stopped badge)
 * - Job table: name, schedule, enabled toggle, next run, last run, last result, "Run Now" button
 * - Each toggle calls toggleSchedulerJob(jobId)
 * - Each "Run Now" button calls triggerSchedulerJob(jobId)
 *
 * @module pages/Admin/AdminScheduler
 */

import { useState, useEffect, useCallback } from "react";
import {
  Clock,
  Play,
  Activity,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  RefreshCw,
} from "lucide-react";
import {
  fetchSchedulerJobs,
  fetchSchedulerStatus,
  toggleSchedulerJob,
  triggerSchedulerJob,
} from "../../lib/admin-api";
import type { SchedulerJob, SchedulerStatus } from "../../lib/admin-api";

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

function SchedulerStatusBadge({ running }: { running: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full ${
        running
          ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
          : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
      }`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          running ? "bg-green-500 animate-pulse" : "bg-red-500"
        }`}
      />
      {running ? "Running" : "Stopped"}
    </span>
  );
}

function JobResultBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    success:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    error: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    running: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    idle: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
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

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (hours < 24) return `${hours}h ${remainingMinutes}m`;
  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return `${days}d ${remainingHours}h`;
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdminScheduler() {
  const token = localStorage.getItem("gs2_token") || "";

  // Data state
  const [jobs, setJobs] = useState<SchedulerJob[]>([]);
  const [status, setStatus] = useState<SchedulerStatus | null>(null);

  // Loading
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [togglingJobId, setTogglingJobId] = useState<string | null>(null);
  const [triggeringJobId, setTriggeringJobId] = useState<string | null>(null);

  // Toast
  const [toast, setToast] = useState<ToastState | null>(null);

  // --------------------------------------------------------------------------
  // Load data
  // --------------------------------------------------------------------------

  const loadJobs = useCallback(async () => {
    setLoadingJobs(true);
    try {
      const data = await fetchSchedulerJobs(token);
      setJobs(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to load scheduler jobs",
        type: "error",
      });
    } finally {
      setLoadingJobs(false);
    }
  }, [token]);

  const loadStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const data = await fetchSchedulerStatus(token);
      setStatus(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to load scheduler status",
        type: "error",
      });
    } finally {
      setLoadingStatus(false);
    }
  }, [token]);

  useEffect(() => {
    loadJobs();
    loadStatus();
  }, [loadJobs, loadStatus]);

  // --------------------------------------------------------------------------
  // Actions
  // --------------------------------------------------------------------------

  const handleToggleJob = async (jobId: string) => {
    setTogglingJobId(jobId);
    try {
      await toggleSchedulerJob(token, jobId);
      // Optimistically update the local state
      setJobs((prev) =>
        prev.map((job) =>
          job.id === jobId ? { ...job, enabled: !job.enabled } : job,
        ),
      );
      const job = jobs.find((j) => j.id === jobId);
      setToast({
        message: `Job "${job?.name || jobId}" ${job?.enabled ? "disabled" : "enabled"}.`,
        type: "success",
      });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to toggle job",
        type: "error",
      });
      // Reload to get correct state
      await loadJobs();
    } finally {
      setTogglingJobId(null);
    }
  };

  const handleTriggerJob = async (jobId: string) => {
    setTriggeringJobId(jobId);
    try {
      await triggerSchedulerJob(token, jobId);
      const job = jobs.find((j) => j.id === jobId);
      setToast({
        message: `Job "${job?.name || jobId}" triggered.`,
        type: "success",
      });
      // Reload after a short delay to show updated last_run
      setTimeout(() => loadJobs(), 2000);
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to trigger job",
        type: "error",
      });
    } finally {
      setTriggeringJobId(null);
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
            Scheduler Management
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            View and control scheduled background tasks.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Status indicator */}
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Status:
            </span>
            {loadingStatus ? (
              <div className="animate-pulse h-5 w-16 bg-gray-200 dark:bg-gray-700 rounded-full" />
            ) : status ? (
              <SchedulerStatusBadge running={status.running} />
            ) : (
              <span className="text-xs text-gray-400">Unknown</span>
            )}
          </div>
          <button
            onClick={() => {
              loadJobs();
              loadStatus();
            }}
            disabled={loadingJobs}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            {loadingJobs ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
            Refresh
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

      {/* Status details */}
      {status && !loadingStatus && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-gray-400" />
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Status
              </span>
            </div>
            <p
              className={`text-lg font-semibold ${status.running ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
            >
              {status.running ? "Running" : "Stopped"}
            </p>
          </div>
          <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-gray-400" />
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Uptime
              </span>
            </div>
            <p className="text-lg font-semibold text-gray-900 dark:text-white">
              {formatUptime(status.uptime_seconds)}
            </p>
          </div>
          <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-gray-400" />
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Jobs Count
              </span>
            </div>
            <p className="text-lg font-semibold text-brand-blue">
              {status.jobs_count}
            </p>
          </div>
        </div>
      )}

      {/* Scheduler jobs table */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="flex items-center gap-2 px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <Clock className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Scheduled Jobs
          </h2>
          {!loadingJobs && (
            <span className="text-xs text-gray-400 dark:text-gray-500">
              ({jobs.length} job{jobs.length !== 1 ? "s" : ""})
            </span>
          )}
        </div>

        {loadingJobs ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse flex items-center gap-4 p-3 rounded-lg border border-gray-100 dark:border-gray-800"
              >
                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="flex-1 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-6 w-11 bg-gray-200 dark:bg-gray-700 rounded-full" />
                <div className="h-8 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <Clock className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No scheduled jobs found.
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
                  <th className="text-center px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Enabled
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Next Run
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Last Run
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Last Result
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
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                      {job.name}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      <code className="text-xs font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                        {job.schedule}
                      </code>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <ToggleSwitch
                        checked={job.enabled}
                        onChange={() => handleToggleJob(job.id)}
                        disabled={togglingJobId === job.id}
                      />
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {formatDate(job.next_run)}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {formatDate(job.last_run)}
                    </td>
                    <td className="px-4 py-3">
                      <JobResultBadge status={job.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleTriggerJob(job.id)}
                        disabled={triggeringJobId === job.id}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-brand-blue border border-brand-blue/30 rounded-lg hover:bg-brand-blue/5 transition-colors disabled:opacity-50"
                      >
                        {triggeringJobId === job.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Play className="w-3.5 h-3.5" />
                        )}
                        Run Now
                      </button>
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
