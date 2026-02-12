/**
 * StepPreview - Preview & Launch (Step 5)
 *
 * Shows filter preview with match count and sample cards.
 * Three outcome states: green (3+), amber (1-2), blue (0).
 * Controls for auto_scan and analyze_now.
 */

import { useEffect } from "react";
import { Loader2, Search, Radar, Zap, Pencil } from "lucide-react";
import { cn } from "../../../lib/utils";
import { ToggleSwitch } from "../ToggleSwitch";
import type { FormData, FilterPreviewResult } from "../../../types/workstream";

interface StepPreviewProps {
  formData: FormData;
  preview: FilterPreviewResult | null;
  previewLoading: boolean;
  hasFilters: boolean;
  onAutoScanChange: (value: boolean) => void;
  onAnalyzeNowChange: (value: boolean) => void;
  triggerPreviewFetch: () => void;
}

export function StepPreview({
  formData,
  preview,
  previewLoading,
  hasFilters,
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

  return (
    <div className="space-y-6">
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
              Searching for matching signals...
            </span>
          </div>
        ) : !hasFilters ? (
          <div className="flex items-center gap-3 py-4">
            <Search className="h-6 w-6 text-gray-400" />
            <span className="text-sm text-gray-600 dark:text-gray-400">
              No filters set. The workstream will start empty and you can add
              signals manually.
            </span>
          </div>
        ) : hasPreview && matchCount >= 3 ? (
          /* Green state: 3+ matches */
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <Search className="h-6 w-6 text-green-600 dark:text-green-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-green-800 dark:text-green-200">
                  Great news -- we found{" "}
                  <span className="text-xl font-bold">~{matchCount}</span>{" "}
                  signals that match your workstream!
                </p>
                <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                  They'll be added to your inbox for review.
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
                label="Keep scanning for new signals automatically"
                description="When enabled, the AI will periodically scan for new signals and add them to your workstream inbox."
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
                  We found{" "}
                  <span className="text-xl font-bold">{matchCount}</span> signal
                  {matchCount !== 1 ? "s" : ""} matching your criteria, but
                  there's more out there.
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
                    Run an AI Scan Now
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Search the web for new signals matching your criteria. Takes
                    2-5 minutes.
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
                    Scan now AND keep scanning automatically on a weekly basis.
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
                    I'll add signals manually
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
                  No existing signals match this topic yet -- but we can find
                  some for you.
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
                    Let AI scan for signals now and keep scanning weekly.
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
                    Search the web once for matching signals.
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
                    Create the workstream empty. You can scan later.
                  </div>
                </div>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Auto-scan explanation (always visible for context) */}
      <p className="text-xs text-gray-400 dark:text-gray-500 italic">
        Auto-scan: When enabled, the AI will periodically scan for new signals
        and add them to your workstream inbox.
      </p>
    </div>
  );
}
