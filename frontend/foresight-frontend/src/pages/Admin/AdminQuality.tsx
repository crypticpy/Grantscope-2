/**
 * AdminQuality Page
 *
 * Quality scoring management dashboard with:
 * - Score distribution overview cards
 * - Score distribution bar chart (recharts BarChart)
 * - SQI weight editor: sliders that must sum to 1.0, with save button
 * - "Recalculate All" button with confirmation dialog
 *
 * @module pages/Admin/AdminQuality
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Shield,
  RefreshCw,
  Sliders,
  Save,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  BarChart3,
} from "lucide-react";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  fetchQualityDistribution,
  fetchQualityWeights,
  updateQualityWeights,
  recalculateAllQuality,
} from "../../lib/admin-api";
import type { QualityDistribution, QualityWeights } from "../../lib/admin-api";

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
  color = "text-gray-900 dark:text-white",
  bgColor,
  loading,
}: {
  label: string;
  value: string | number;
  color?: string;
  bgColor?: string;
  loading: boolean;
}) {
  return (
    <div
      className={`${bgColor || "bg-white dark:bg-dark-surface"} rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center`}
    >
      {loading ? (
        <div className="animate-pulse h-8 w-14 bg-gray-200 dark:bg-gray-700 rounded mx-auto mb-1" />
      ) : (
        <p className={`text-2xl font-semibold ${color}`}>{value}</p>
      )}
      <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
        {label}
      </span>
    </div>
  );
}

// ============================================================================
// Constants
// ============================================================================

const WEIGHT_COMPONENTS: Array<{
  key: keyof QualityWeights;
  name: string;
  description: string;
}> = [
  {
    key: "source_authority",
    name: "Source Authority",
    description: "Credibility of source institutions",
  },
  {
    key: "source_diversity",
    name: "Source Diversity",
    description: "Number and variety of source types",
  },
  {
    key: "corroboration",
    name: "Corroboration",
    description: "Independent story clusters validating claims",
  },
  {
    key: "recency",
    name: "Recency",
    description: "Freshness and timeliness of information",
  },
  {
    key: "municipal_specificity",
    name: "Municipal Specificity",
    description: "Relevance to municipal government operations",
  },
];

// ============================================================================
// Main Component
// ============================================================================

export default function AdminQuality() {
  const token = localStorage.getItem("gs2_token") || "";

  // Data state
  const [distribution, setDistribution] = useState<QualityDistribution | null>(
    null,
  );
  const [, setWeights] = useState<QualityWeights | null>(null);

  // Draft weights for editing
  const [draftWeights, setDraftWeights] = useState<QualityWeights | null>(null);

  // Loading
  const [loadingDist, setLoadingDist] = useState(true);
  const [loadingWeights, setLoadingWeights] = useState(true);
  const [savingWeights, setSavingWeights] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Toast
  const [toast, setToast] = useState<ToastState | null>(null);

  // --------------------------------------------------------------------------
  // Load data
  // --------------------------------------------------------------------------

  const loadDistribution = useCallback(async () => {
    setLoadingDist(true);
    try {
      const data = await fetchQualityDistribution(token);
      setDistribution(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to load quality distribution",
        type: "error",
      });
    } finally {
      setLoadingDist(false);
    }
  }, [token]);

  const loadWeights = useCallback(async () => {
    setLoadingWeights(true);
    try {
      const data = await fetchQualityWeights(token);
      setWeights(data);
      setDraftWeights(data);
      setDirty(false);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to load quality weights",
        type: "error",
      });
    } finally {
      setLoadingWeights(false);
    }
  }, [token]);

  useEffect(() => {
    loadDistribution();
    loadWeights();
  }, [loadDistribution, loadWeights]);

  // --------------------------------------------------------------------------
  // Weight management
  // --------------------------------------------------------------------------

  const weightSum = useMemo(() => {
    if (!draftWeights) return 0;
    return Object.values(draftWeights).reduce(
      (sum, val) => sum + (typeof val === "number" ? val : 0),
      0,
    );
  }, [draftWeights]);

  const isWeightSumValid = Math.abs(weightSum - 1.0) < 0.01;

  const handleWeightChange = (key: keyof QualityWeights, value: number) => {
    if (!draftWeights) return;
    setDraftWeights({ ...draftWeights, [key]: value });
    setDirty(true);
  };

  const handleSaveWeights = async () => {
    if (!draftWeights || !isWeightSumValid) return;
    setSavingWeights(true);
    try {
      await updateQualityWeights(token, draftWeights);
      setWeights(draftWeights);
      setDirty(false);
      setToast({ message: "Quality weights saved.", type: "success" });
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to save quality weights",
        type: "error",
      });
    } finally {
      setSavingWeights(false);
    }
  };

  // --------------------------------------------------------------------------
  // Recalculate
  // --------------------------------------------------------------------------

  const handleRecalculateAll = async () => {
    if (
      !window.confirm(
        "This will recalculate quality scores for all cards. This may take several minutes. Continue?",
      )
    )
      return;

    setRecalculating(true);
    try {
      await recalculateAllQuality(token);
      setToast({
        message:
          "Quality recalculation started. Scores will be updated in the background.",
        type: "success",
      });
      // Reload distribution after a delay
      setTimeout(() => loadDistribution(), 3000);
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to start quality recalculation",
        type: "error",
      });
    } finally {
      setRecalculating(false);
    }
  };

  // --------------------------------------------------------------------------
  // Chart data
  // --------------------------------------------------------------------------

  const chartData = useMemo(() => {
    if (!distribution) return [];
    return [
      {
        tier: "High",
        count: distribution.high,
        fill: "#22c55e",
      },
      {
        tier: "Moderate",
        count: distribution.moderate,
        fill: "#eab308",
      },
      {
        tier: "Low",
        count: distribution.low,
        fill: "#ef4444",
      },
      {
        tier: "Unscored",
        count: distribution.unscored,
        fill: "#9ca3af",
      },
    ];
  }, [distribution]);

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Quality Scoring
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Configure Source Quality Index (SQI) weights and view score
            distribution.
          </p>
        </div>
        <button
          onClick={handleRecalculateAll}
          disabled={recalculating}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-blue hover:bg-brand-blue/90 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {recalculating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Recalculate All
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

      {/* Distribution overview cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          label="High Confidence"
          value={distribution ? distribution.high.toLocaleString() : "--"}
          color="text-green-600 dark:text-green-400"
          bgColor="bg-green-50/50 dark:bg-green-900/10"
          loading={loadingDist}
        />
        <StatCard
          label="Moderate"
          value={distribution ? distribution.moderate.toLocaleString() : "--"}
          color="text-yellow-600 dark:text-yellow-400"
          bgColor="bg-yellow-50/50 dark:bg-yellow-900/10"
          loading={loadingDist}
        />
        <StatCard
          label="Low"
          value={distribution ? distribution.low.toLocaleString() : "--"}
          color="text-red-600 dark:text-red-400"
          bgColor="bg-red-50/50 dark:bg-red-900/10"
          loading={loadingDist}
        />
        <StatCard
          label="Unscored"
          value={distribution ? distribution.unscored.toLocaleString() : "--"}
          color="text-gray-500"
          bgColor="bg-gray-50 dark:bg-gray-800/50"
          loading={loadingDist}
        />
        <StatCard
          label="Average Score"
          value={
            distribution && distribution.avg_score > 0
              ? distribution.avg_score.toFixed(1)
              : "--"
          }
          color="text-brand-blue"
          bgColor="bg-brand-blue/5 dark:bg-brand-blue/10"
          loading={loadingDist}
        />
      </div>

      {/* Score Distribution Chart */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Quality Distribution
          </h2>
        </div>

        {loadingDist ? (
          <div className="animate-pulse h-48 bg-gray-200 dark:bg-gray-700 rounded" />
        ) : chartData.length > 0 ? (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} barCategoryGap="20%">
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="currentColor"
                  className="text-gray-200 dark:text-gray-700"
                />
                <XAxis
                  dataKey="tier"
                  tick={{ fontSize: 12 }}
                  className="text-gray-600 dark:text-gray-400"
                />
                <YAxis
                  tick={{ fontSize: 12 }}
                  className="text-gray-600 dark:text-gray-400"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--tooltip-bg, #fff)",
                    border: "1px solid var(--tooltip-border, #e5e7eb)",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={index} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="text-center py-8">
            <Shield className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No quality distribution data available.
            </p>
          </div>
        )}

        {/* Distribution progress bar */}
        {distribution && distribution.total > 0 && (
          <div className="mt-4">
            <div className="w-full h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden flex">
              {distribution.high > 0 && (
                <div
                  className="h-full bg-green-500 transition-all duration-500"
                  style={{
                    width: `${(distribution.high / distribution.total) * 100}%`,
                  }}
                  title={`High: ${distribution.high}`}
                />
              )}
              {distribution.moderate > 0 && (
                <div
                  className="h-full bg-yellow-500 transition-all duration-500"
                  style={{
                    width: `${(distribution.moderate / distribution.total) * 100}%`,
                  }}
                  title={`Moderate: ${distribution.moderate}`}
                />
              )}
              {distribution.low > 0 && (
                <div
                  className="h-full bg-red-500 transition-all duration-500"
                  style={{
                    width: `${(distribution.low / distribution.total) * 100}%`,
                  }}
                  title={`Low: ${distribution.low}`}
                />
              )}
              {distribution.unscored > 0 && (
                <div
                  className="h-full bg-gray-400 transition-all duration-500"
                  style={{
                    width: `${(distribution.unscored / distribution.total) * 100}%`,
                  }}
                  title={`Unscored: ${distribution.unscored}`}
                />
              )}
            </div>
            <div className="flex items-center justify-between mt-1.5 text-xs text-gray-500 dark:text-gray-400">
              <span>Total: {distribution.total.toLocaleString()} cards</span>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  High
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-yellow-500" />
                  Moderate
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  Low
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-gray-400" />
                  Unscored
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Weight Configuration */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Sliders className="w-5 h-5 text-brand-blue" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              SQI Weight Configuration
            </h2>
          </div>
          <div className="flex items-center gap-3">
            {/* Weight sum indicator */}
            <span
              className={`text-sm font-mono ${
                isWeightSumValid
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              Sum: {weightSum.toFixed(2)}
              {!isWeightSumValid && " (must be 1.00)"}
            </span>
            {dirty && (
              <button
                onClick={handleSaveWeights}
                disabled={savingWeights || !isWeightSumValid}
                className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-brand-blue hover:bg-brand-blue/90 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {savingWeights ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Save className="w-3.5 h-3.5" />
                )}
                Save Weights
              </button>
            )}
          </div>
        </div>

        {loadingWeights ? (
          <div className="space-y-4">
            {WEIGHT_COMPONENTS.map((component) => (
              <div
                key={component.key}
                className="animate-pulse flex items-center gap-4 p-3 rounded-lg border border-gray-100 dark:border-gray-800"
              >
                <div className="flex-1 min-w-0">
                  <div className="h-4 w-28 bg-gray-200 dark:bg-gray-700 rounded mb-1" />
                  <div className="h-3 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
                </div>
                <div className="flex items-center gap-3 w-48">
                  <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full" />
                  <div className="h-6 w-12 bg-gray-200 dark:bg-gray-700 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : draftWeights ? (
          <div className="space-y-4">
            {WEIGHT_COMPONENTS.map((component) => {
              const value = draftWeights[component.key];
              return (
                <div
                  key={component.key}
                  className="flex items-center gap-4 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {component.name}
                    </span>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      {component.description}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 w-56">
                    <input
                      type="range"
                      min={0}
                      max={0.5}
                      step={0.01}
                      value={value}
                      onChange={(e) =>
                        handleWeightChange(
                          component.key,
                          parseFloat(e.target.value),
                        )
                      }
                      className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-brand-blue"
                    />
                    <span className="text-sm font-mono font-medium text-gray-900 dark:text-white w-12 text-right">
                      {value.toFixed(2)}
                    </span>
                  </div>
                </div>
              );
            })}

            {/* Save button within form */}
            <div className="pt-2">
              <button
                onClick={handleSaveWeights}
                disabled={savingWeights || !dirty || !isWeightSumValid}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-brand-blue hover:bg-brand-blue/90 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {savingWeights ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Save Weights
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
