/**
 * StepPreview - Preview & Launch (Step 5)
 *
 * Shows program configuration summary, readiness score,
 * estimated matching grants, and launch options.
 */

import { useEffect } from "react";
import {
  Loader2,
  Search,
  Radar,
  Zap,
  Pencil,
  CheckCircle2,
} from "lucide-react";
import { cn } from "../../../lib/utils";
import { ToggleSwitch } from "../ToggleSwitch";
import { grantCategories, departments } from "../../../data/taxonomy";
import type { FormData, FilterPreviewResult } from "../../../types/workstream";

interface ReadinessScore {
  overall_score: number;
  factors: Array<{
    name: string;
    score: number;
    description: string;
  }>;
  recommendations: string[];
}

interface StepPreviewProps {
  formData: FormData;
  preview: FilterPreviewResult | null;
  previewLoading: boolean;
  hasFilters: boolean;
  readinessScore: ReadinessScore | null;
  onAutoScanChange: (value: boolean) => void;
  onAnalyzeNowChange: (value: boolean) => void;
  triggerPreviewFetch: () => void;
}

export function StepPreview({
  formData,
  preview,
  previewLoading,
  hasFilters,
  readinessScore,
  onAutoScanChange,
  onAnalyzeNowChange,
  triggerPreviewFetch,
}: StepPreviewProps) {
  // Trigger preview fetch when arriving at this step
  useEffect(() => {
    if (hasFilters) {
      triggerPreviewFetch();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const matchCount = preview?.estimated_count ?? 0;
  const isLoading = previewLoading;
  const hasPreview = preview !== null && !isLoading;

  // Lookup helpers
  const selectedDept = departments.find((d) => d.id === formData.department_id);
  const selectedCategories = formData.category_ids
    .map((id) => grantCategories.find((c) => c.code === id))
    .filter(Boolean);

  const getScoreColor = (score: number): string => {
    if (score >= 80) return "text-green-600 dark:text-green-400";
    if (score >= 60) return "text-amber-600 dark:text-amber-400";
    return "text-red-600 dark:text-red-400";
  };

  const getScoreBarColor = (score: number): string => {
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-amber-500";
    return "bg-red-500";
  };

  return (
    <div className="space-y-6">
      {/* Program Configuration Summary */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-dark-surface-elevated">
        <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
          Program Summary
        </h4>
        <div className="space-y-2 text-sm">
          <div className="flex items-start gap-2">
            <span className="text-gray-500 dark:text-gray-400 w-24 flex-shrink-0">
              Program:
            </span>
            <span className="text-gray-900 dark:text-white font-medium">
              {formData.name || "Untitled Program"}
            </span>
          </div>
          {selectedDept && (
            <div className="flex items-start gap-2">
              <span className="text-gray-500 dark:text-gray-400 w-24 flex-shrink-0">
                Department:
              </span>
              <span className="text-gray-900 dark:text-white">
                {selectedDept.abbreviation} - {selectedDept.name}
              </span>
            </div>
          )}
          {selectedCategories.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-gray-500 dark:text-gray-400 w-24 flex-shrink-0">
                Categories:
              </span>
              <div className="flex flex-wrap gap-1">
                {selectedCategories.map((cat) => (
                  <span
                    key={cat!.code}
                    className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                    style={{
                      backgroundColor: cat!.colorLight,
                      color: cat!.colorDark,
                    }}
                  >
                    {cat!.name}
                  </span>
                ))}
              </div>
            </div>
          )}
          {formData.grant_types.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-gray-500 dark:text-gray-400 w-24 flex-shrink-0">
                Grant Types:
              </span>
              <span className="text-gray-900 dark:text-white">
                {formData.grant_types
                  .map((t) => t.charAt(0).toUpperCase() + t.slice(1))
                  .join(", ")}
              </span>
            </div>
          )}
          {(formData.budget_range_min || formData.budget_range_max) && (
            <div className="flex items-start gap-2">
              <span className="text-gray-500 dark:text-gray-400 w-24 flex-shrink-0">
                Funding:
              </span>
              <span className="text-gray-900 dark:text-white">
                {formData.budget_range_min
                  ? `$${formData.budget_range_min.toLocaleString()}`
                  : "$0"}
                {" - "}
                {formData.budget_range_max
                  ? `$${formData.budget_range_max.toLocaleString()}`
                  : "No limit"}
              </span>
            </div>
          )}
          {formData.keywords.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-gray-500 dark:text-gray-400 w-24 flex-shrink-0">
                Keywords:
              </span>
              <span className="text-gray-900 dark:text-white">
                {formData.keywords.slice(0, 5).join(", ")}
                {formData.keywords.length > 5 &&
                  ` +${formData.keywords.length - 5} more`}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Readiness Score Summary (if assessed) */}
      {readinessScore && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-dark-surface-elevated">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
                Grant Readiness Score
              </h4>
              <div className="flex items-center gap-3 mt-1">
                <span
                  className={cn(
                    "text-2xl font-bold",
                    getScoreColor(readinessScore.overall_score),
                  )}
                >
                  {readinessScore.overall_score}
                </span>
                <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      getScoreBarColor(readinessScore.overall_score),
                    )}
                    style={{
                      width: `${readinessScore.overall_score}%`,
                    }}
                  />
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  / 100
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Preview Result */}
      <div
        className={cn(
          "rounded-lg p-5 border transition-all duration-200",
          isLoading
            ? "bg-gray-50 dark:bg-dark-surface/50 border-gray-200 dark:border-gray-700"
            : hasPreview && matchCount >= 3
              ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700"
              : hasPreview && matchCount >= 1
                ? "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-700"
                : hasPreview && matchCount === 0
                  ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-700"
                  : "bg-gray-50 dark:bg-dark-surface/50 border-gray-200 dark:border-gray-700",
        )}
      >
        {isLoading ? (
          <div className="flex items-center gap-3 py-4">
            <Loader2 className="h-6 w-6 text-gray-400 animate-spin" />
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Searching for matching grant opportunities...
            </span>
          </div>
        ) : !hasFilters ? (
          <div className="flex items-center gap-3 py-4">
            <Search className="h-6 w-6 text-gray-400" />
            <span className="text-sm text-gray-600 dark:text-gray-400">
              No filters set. The program will start empty and you can add
              grants manually.
            </span>
          </div>
        ) : hasPreview && matchCount >= 3 ? (
          /* Green state: 3+ matches */
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <Search className="h-6 w-6 text-green-600 dark:text-green-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-green-800 dark:text-green-200">
                  Found <span className="text-xl font-bold">~{matchCount}</span>{" "}
                  matching grant opportunities!
                </p>
                <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                  They will be added to your program for review.
                </p>
              </div>
            </div>

            {/* Sample cards */}
            {preview && preview.sample_cards.length > 0 && (
              <div className="border-t border-green-200 dark:border-green-700 pt-3">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                  Sample matches:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {preview.sample_cards.slice(0, 3).map((card) => (
                    <span
                      key={card.id}
                      className="text-xs px-2 py-1 rounded bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600 truncate max-w-[200px]"
                      title={card.name}
                    >
                      {card.name}
                    </span>
                  ))}
                  {matchCount > 3 && (
                    <span className="text-xs text-gray-500 dark:text-gray-400 self-center">
                      +{matchCount - 3} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Auto-scan toggle */}
            <div className="border-t border-green-200 dark:border-green-700 pt-3">
              <ToggleSwitch
                checked={formData.auto_scan}
                onChange={onAutoScanChange}
                label="Enable continuous grant monitoring"
                description="Automatically scan for new grant opportunities on a regular basis and add them to your program."
              />
            </div>
          </div>
        ) : hasPreview && matchCount >= 1 ? (
          /* Amber state: 1-2 matches */
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <Search className="h-6 w-6 text-amber-600 dark:text-amber-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                  Found <span className="text-xl font-bold">{matchCount}</span>{" "}
                  grant
                  {matchCount !== 1 ? "s" : ""} matching your criteria, but
                  there may be more out there.
                </p>
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  What would you like to do?
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <button
                type="button"
                onClick={() => {
                  onAnalyzeNowChange(true);
                  onAutoScanChange(false);
                }}
                className={cn(
                  "w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-200",
                  formData.analyze_now && !formData.auto_scan
                    ? "border-brand-blue bg-brand-light-blue/30 dark:bg-brand-blue/10"
                    : "border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                )}
              >
                <Search className="h-5 w-5 text-brand-blue flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    Run a Grant Scan Now
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Search for new grant opportunities matching your criteria.
                    Takes 2-5 minutes.
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  onAnalyzeNowChange(true);
                  onAutoScanChange(true);
                }}
                className={cn(
                  "w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-200",
                  formData.analyze_now && formData.auto_scan
                    ? "border-brand-blue bg-brand-light-blue/30 dark:bg-brand-blue/10"
                    : "border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                )}
              >
                <Zap className="h-5 w-5 text-brand-blue flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    Auto-Pilot (Recommended)
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Scan now AND keep monitoring automatically on a weekly
                    basis.
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  onAnalyzeNowChange(false);
                  onAutoScanChange(false);
                }}
                className={cn(
                  "w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-200",
                  !formData.analyze_now && !formData.auto_scan
                    ? "border-brand-blue bg-brand-light-blue/30 dark:bg-brand-blue/10"
                    : "border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                )}
              >
                <Pencil className="h-5 w-5 text-gray-500 flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    I will add grants manually
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Skip scanning. You can always run one later.
                  </div>
                </div>
              </button>
            </div>
          </div>
        ) : (
          /* Blue state: 0 matches */
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <Radar className="h-6 w-6 text-blue-600 dark:text-blue-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                  No existing grants match this program yet -- but we can search
                  for some.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <button
                type="button"
                onClick={() => {
                  onAnalyzeNowChange(true);
                  onAutoScanChange(true);
                }}
                className={cn(
                  "w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-200",
                  formData.analyze_now && formData.auto_scan
                    ? "border-brand-blue bg-brand-light-blue/30 dark:bg-brand-blue/10"
                    : "border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                )}
              >
                <Zap className="h-5 w-5 text-brand-blue flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    Auto-Pilot (Recommended)
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Let AI scan for grants now and keep monitoring weekly.
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  onAnalyzeNowChange(true);
                  onAutoScanChange(false);
                }}
                className={cn(
                  "w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-200",
                  formData.analyze_now && !formData.auto_scan
                    ? "border-brand-blue bg-brand-light-blue/30 dark:bg-brand-blue/10"
                    : "border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                )}
              >
                <Search className="h-5 w-5 text-brand-blue flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    Run a One-Time Scan
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Search the web once for matching grant opportunities.
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  onAnalyzeNowChange(false);
                  onAutoScanChange(false);
                }}
                className={cn(
                  "w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-200",
                  !formData.analyze_now && !formData.auto_scan
                    ? "border-brand-blue bg-brand-light-blue/30 dark:bg-brand-blue/10"
                    : "border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                )}
              >
                <Pencil className="h-5 w-5 text-gray-500 flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    Skip for Now
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Create the program empty. You can scan later.
                  </div>
                </div>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Auto-scan explanation (always visible for context) */}
      <p className="text-xs text-gray-400 dark:text-gray-500 italic">
        Continuous monitoring: When enabled, the AI will periodically scan for
        new grant opportunities and add them to your program.
      </p>
    </div>
  );
}
