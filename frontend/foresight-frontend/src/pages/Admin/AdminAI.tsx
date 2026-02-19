/**
 * AdminAI Page
 *
 * AI configuration and monitoring dashboard with:
 * - Model deployment cards (read-only)
 * - Chat settings form (temperature, max tokens, etc.)
 * - Usage statistics (requests, tokens, latency in last 24h)
 * - Model breakdown table
 *
 * @module pages/Admin/AdminAI
 */

import { useState, useEffect, useCallback } from "react";
import {
  Brain,
  Zap,
  Settings,
  Save,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  Activity,
  Cpu,
} from "lucide-react";
import {
  fetchAiConfig,
  updateAiConfig,
  fetchAiUsage,
} from "../../lib/admin-api";
import type { AiConfig, AiUsageStats } from "../../lib/admin-api";

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
  loading,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  color?: string;
  loading: boolean;
}) {
  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-gray-400" />
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          {label}
        </span>
      </div>
      {loading ? (
        <div className="animate-pulse h-7 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
      ) : (
        <p className={`text-2xl font-semibold ${color}`}>{value}</p>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdminAI() {
  const token = localStorage.getItem("gs2_token") || "";

  // Data state
  const [config, setConfig] = useState<AiConfig | null>(null);
  const [usage, setUsage] = useState<AiUsageStats | null>(null);

  // Form state (local draft of editable fields)
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(4096);

  // Loading
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [loadingUsage, setLoadingUsage] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Toast
  const [toast, setToast] = useState<ToastState | null>(null);

  // --------------------------------------------------------------------------
  // Load data
  // --------------------------------------------------------------------------

  const loadConfig = useCallback(async () => {
    setLoadingConfig(true);
    try {
      const data = await fetchAiConfig(token);
      setConfig(data);
      setTemperature(Number(data.temperature) || 0.7);
      setMaxTokens(Number(data.max_tokens) || 4096);
      setDirty(false);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to load AI config",
        type: "error",
      });
    } finally {
      setLoadingConfig(false);
    }
  }, [token]);

  const loadUsage = useCallback(async () => {
    setLoadingUsage(true);
    try {
      const data = await fetchAiUsage(token);
      setUsage(data);
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to load AI usage",
        type: "error",
      });
    } finally {
      setLoadingUsage(false);
    }
  }, [token]);

  useEffect(() => {
    loadConfig();
    loadUsage();
  }, [loadConfig, loadUsage]);

  // --------------------------------------------------------------------------
  // Save config
  // --------------------------------------------------------------------------

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateAiConfig(token, {
        temperature,
        max_tokens: maxTokens,
      });
      setConfig((prev) =>
        prev ? { ...prev, temperature, max_tokens: maxTokens } : prev,
      );
      setDirty(false);
      setToast({ message: "AI configuration saved.", type: "success" });
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to save AI config",
        type: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  // --------------------------------------------------------------------------
  // Model deployment cards data
  // --------------------------------------------------------------------------

  const modelCards = config
    ? [
        {
          label: "Model Deployment",
          value: config.model_deployment,
          hint: "Primary model for classification and analysis",
        },
        {
          label: "Embedding Deployment",
          value: config.embedding_deployment,
          hint: "Model for vector embeddings",
        },
        {
          label: "Mini Deployment",
          value: config.mini_deployment,
          hint: "Fast model for lightweight tasks",
        },
      ]
    : [];

  // --------------------------------------------------------------------------
  // Usage breakdown
  // --------------------------------------------------------------------------

  const taskTypeBreakdown = usage?.period_24h.by_type
    ? Object.entries(usage.period_24h.by_type)
    : [];

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            AI Configuration
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Configure AI models, parameters, and monitor usage.
          </p>
        </div>
        {dirty && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-brand-blue hover:bg-brand-blue/90 rounded-lg transition-colors disabled:opacity-50"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Save Changes
          </button>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Section 1: Model Deployments */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Cpu className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Model Deployments
          </h2>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            (read-only)
          </span>
        </div>

        {loadingConfig ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse p-4 border border-gray-100 dark:border-gray-800 rounded-lg"
              >
                <div className="h-4 w-28 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
                <div className="h-6 w-40 bg-gray-200 dark:bg-gray-700 rounded mb-1" />
                <div className="h-3 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {modelCards.map((card) => (
              <div
                key={card.label}
                className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg"
              >
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                  {card.label}
                </p>
                <p className="text-sm font-semibold text-gray-900 dark:text-white font-mono">
                  {card.value || "--"}
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                  {card.hint}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Section 2: Chat Settings Form */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-6">
          <Settings className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Chat Settings
          </h2>
        </div>

        {loadingConfig ? (
          <div className="space-y-6">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
                <div className="h-10 w-full max-w-md bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-6 max-w-lg">
            {/* Temperature */}
            <div>
              <label
                htmlFor="temperature"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Temperature
              </label>
              <div className="flex items-center gap-4">
                <input
                  id="temperature"
                  type="range"
                  min={0}
                  max={2}
                  step={0.1}
                  value={temperature}
                  onChange={(e) => {
                    setTemperature(parseFloat(e.target.value));
                    setDirty(true);
                  }}
                  className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-brand-blue"
                />
                <span className="text-sm font-mono font-medium text-gray-900 dark:text-white w-12 text-right">
                  {temperature.toFixed(1)}
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Controls randomness. Lower values are more deterministic (0.0 -
                2.0).
              </p>
            </div>

            {/* Max Tokens */}
            <div>
              <label
                htmlFor="max-tokens"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Max Tokens
              </label>
              <input
                id="max-tokens"
                type="number"
                min={1024}
                max={16384}
                step={256}
                value={maxTokens}
                onChange={(e) => {
                  setMaxTokens(parseInt(e.target.value, 10) || 4096);
                  setDirty(true);
                }}
                className="w-full max-w-[200px] px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
              />
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Maximum output tokens per request (1024 - 16384).
              </p>
            </div>

            {/* Save button within form */}
            <div className="pt-2">
              <button
                onClick={handleSave}
                disabled={saving || !dirty}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-brand-blue hover:bg-brand-blue/90 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Save Settings
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Section 3: Usage Statistics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          label="Tasks (24h)"
          value={usage ? usage.period_24h.total.toLocaleString() : "--"}
          icon={Zap}
          color="text-brand-blue"
          loading={loadingUsage}
        />
        <StatCard
          label="Completed (24h)"
          value={usage ? usage.period_24h.completed.toLocaleString() : "--"}
          icon={Activity}
          color="text-brand-green"
          loading={loadingUsage}
        />
        <StatCard
          label="Failed (24h)"
          value={usage ? usage.period_24h.failed.toLocaleString() : "--"}
          icon={Activity}
          color="text-red-600 dark:text-red-400"
          loading={loadingUsage}
        />
      </div>

      {/* Section 4: Task Type Breakdown */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Brain className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Task Type Breakdown (Last 24 Hours)
          </h2>
        </div>

        {loadingUsage ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50"
              >
                <div className="h-4 w-40 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="flex items-center gap-6">
                  <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : taskTypeBreakdown.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left px-4 py-2 font-medium text-gray-500 dark:text-gray-400">
                    Task Type
                  </th>
                  <th className="text-right px-4 py-2 font-medium text-gray-500 dark:text-gray-400">
                    Count (24h)
                  </th>
                </tr>
              </thead>
              <tbody>
                {taskTypeBreakdown.map(([taskType, count]) => (
                  <tr
                    key={taskType}
                    className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <code className="text-xs font-mono text-gray-900 dark:text-gray-100 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                        {taskType}
                      </code>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">
                      {(count as number).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8">
            <Brain className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No usage data available for the last 24 hours.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
