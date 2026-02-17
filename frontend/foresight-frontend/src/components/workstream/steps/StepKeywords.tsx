/**
 * StepKeywords - Search Configuration (Step 4)
 *
 * Grant search terms, agencies to monitor, and deadline preferences.
 * Keeps keyword tag input mechanism from original, adds grant context.
 */

import { useEffect, useRef, KeyboardEvent } from "react";
import { Plus, Loader2, Wand2, X } from "lucide-react";
import { cn } from "../../../lib/utils";
import { KeywordTag } from "../KeywordTag";
import { deadlineUrgencyTiers } from "../../../data/taxonomy";
import type { FormData } from "../../../types/workstream";

// Suggested federal agencies to monitor
const FEDERAL_AGENCIES = [
  {
    id: "grants-gov",
    name: "Grants.gov",
    description: "Federal grant clearinghouse",
  },
  {
    id: "sam-gov",
    name: "SAM.gov",
    description: "System for Award Management",
  },
  {
    id: "hud",
    name: "HUD",
    description: "Dept. of Housing & Urban Development",
  },
  { id: "dot", name: "DOT", description: "Dept. of Transportation" },
  { id: "epa", name: "EPA", description: "Environmental Protection Agency" },
  { id: "doj", name: "DOJ", description: "Dept. of Justice" },
  { id: "doe", name: "DOE", description: "Dept. of Energy" },
  { id: "fema", name: "FEMA", description: "Federal Emergency Mgmt. Agency" },
  { id: "hhs", name: "HHS", description: "Dept. of Health & Human Services" },
  { id: "usda", name: "USDA", description: "Dept. of Agriculture" },
  { id: "ed", name: "ED", description: "Dept. of Education" },
  { id: "nsf", name: "NSF", description: "National Science Foundation" },
];

interface StepKeywordsProps {
  formData: FormData;
  keywordInput: string;
  setKeywordInput: (value: string) => void;
  suggestedKeywords: string[];
  isSuggestingKeywords: boolean;
  onKeywordAdd: () => void;
  onKeywordInputKeyDown: (e: KeyboardEvent<HTMLInputElement>) => void;
  onKeywordRemove: (keyword: string) => void;
  onSuggestKeywords: () => void;
  onAddSuggestedKeyword: (keyword: string) => void;
  onDeadlinePreferenceChange: (preference: string) => void;
}

export function StepKeywords({
  formData,
  keywordInput,
  setKeywordInput,
  suggestedKeywords,
  isSuggestingKeywords,
  onKeywordAdd,
  onKeywordInputKeyDown,
  onKeywordRemove,
  onSuggestKeywords,
  onAddSuggestedKeyword,
  onDeadlinePreferenceChange,
}: StepKeywordsProps) {
  const hasAutoTriggered = useRef(false);

  // Auto-trigger AI suggestions when arriving at this step
  useEffect(() => {
    if (
      !hasAutoTriggered.current &&
      suggestedKeywords.length === 0 &&
      !isSuggestingKeywords &&
      (formData.name.trim() || formData.description.trim())
    ) {
      hasAutoTriggered.current = true;
      onSuggestKeywords();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const canSuggest =
    !isSuggestingKeywords &&
    (keywordInput.trim() ||
      formData.name.trim() ||
      formData.description.trim());

  // Derive deadline_preference from horizon field (reuse existing form field)
  const deadlinePreference = formData.horizon;

  return (
    <div className="space-y-8">
      {/* Inline help */}
      <div className="bg-brand-light-blue/30 dark:bg-brand-blue/10 rounded-lg p-4 border border-brand-blue/20">
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          Configure your grant search terms to find the most relevant
          opportunities. Add specific keywords, select agencies to monitor, and
          set your deadline preferences.
        </p>
      </div>

      {/* Section 1: Grant Search Terms */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Grant Search Terms
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Be specific -- "COPS hiring grant 2026" works better than just
            "police". Use "Suggest Related Terms" to get AI-powered
            recommendations based on your program setup.
          </p>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            onKeyDown={onKeywordInputKeyDown}
            placeholder="Type a search term and press Enter..."
            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400"
            autoFocus
          />
          <button
            type="button"
            onClick={onKeywordAdd}
            disabled={!keywordInput.trim()}
            className={cn(
              "px-3 py-2 text-sm font-medium rounded-md border transition-colors",
              keywordInput.trim()
                ? "bg-brand-blue border-brand-blue text-white hover:bg-brand-dark-blue"
                : "bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-400 cursor-not-allowed",
            )}
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {/* Current keywords */}
        {formData.keywords.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {formData.keywords.map((keyword) => (
              <KeywordTag
                key={keyword}
                keyword={keyword}
                onRemove={() => onKeywordRemove(keyword)}
              />
            ))}
          </div>
        )}

        {/* Suggest Related Terms */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSuggestKeywords}
            disabled={!canSuggest}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-colors",
              !canSuggest
                ? "bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-400 cursor-not-allowed"
                : "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-700 text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/40",
            )}
          >
            {isSuggestingKeywords ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Wand2 className="h-3.5 w-3.5" />
            )}
            {isSuggestingKeywords ? "Suggesting..." : "Suggest Related Terms"}
          </button>
        </div>

        {/* Suggested Keywords Chips */}
        {suggestedKeywords.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Click to add suggested terms:
            </p>
            <div className="flex flex-wrap gap-1.5">
              {suggestedKeywords.map((kw) => (
                <button
                  key={kw}
                  type="button"
                  onClick={() => onAddSuggestedKeyword(kw)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border border-dashed border-purple-300 dark:border-purple-600 text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-900/10 hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors"
                >
                  <Plus className="h-3 w-3" />
                  {kw}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Section 2: Agencies to Monitor */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Agencies to Monitor
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Select federal agencies whose grant programs are most relevant to
            your department. These will be prioritized in searches.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {FEDERAL_AGENCIES.map((agency) => {
            // Use keywords to track selected agencies
            const agencyKeyword = agency.name;
            const isSelected = formData.keywords.includes(agencyKeyword);
            return (
              <button
                key={agency.id}
                type="button"
                onClick={() => {
                  if (isSelected) {
                    onKeywordRemove(agencyKeyword);
                  } else {
                    onAddSuggestedKeyword(agencyKeyword);
                  }
                }}
                className={cn(
                  "flex items-center gap-2 p-2 rounded-md border text-left text-xs transition-all duration-200",
                  isSelected
                    ? "border-brand-blue bg-brand-light-blue/30 dark:bg-brand-blue/10"
                    : "border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                )}
                aria-pressed={isSelected}
              >
                {isSelected && (
                  <X className="h-3 w-3 text-brand-blue flex-shrink-0" />
                )}
                <div className="min-w-0">
                  <div
                    className={cn(
                      "font-medium",
                      isSelected
                        ? "text-brand-dark-blue dark:text-brand-light-blue"
                        : "text-gray-900 dark:text-white",
                    )}
                  >
                    {agency.name}
                  </div>
                  <div className="text-gray-500 dark:text-gray-400 truncate">
                    {agency.description}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Section 3: Deadline Preferences */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Deadline Preference
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            How urgent should the grant opportunities be? This helps prioritize
            which opportunities to surface first.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            {
              code: "ALL",
              name: "All Deadlines",
              description: "Show all opportunities regardless of deadline",
              color: "#3b82f6",
            },
            ...deadlineUrgencyTiers.map((tier) => ({
              code: tier.code,
              name: tier.name,
              description: tier.description,
              color: tier.color,
            })),
          ].map((pref) => (
            <button
              key={pref.code}
              type="button"
              onClick={() => onDeadlinePreferenceChange(pref.code)}
              className={cn(
                "flex flex-col items-start p-3 rounded-lg border transition-all duration-200 text-left",
                deadlinePreference === pref.code
                  ? "bg-brand-light-blue dark:bg-brand-blue/20 border-brand-blue ring-2 ring-brand-blue/30"
                  : "bg-white dark:bg-dark-surface-elevated border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
              )}
              aria-pressed={deadlinePreference === pref.code}
            >
              <div className="flex items-center gap-2">
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: pref.color }}
                />
                <span
                  className={cn(
                    "text-sm font-semibold",
                    deadlinePreference === pref.code
                      ? "text-brand-dark-blue dark:text-brand-light-blue"
                      : "text-gray-900 dark:text-white",
                  )}
                >
                  {pref.name}
                </span>
              </div>
              <span className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {pref.description}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
