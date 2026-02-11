/**
 * StepKeywords - Keywords & AI Suggestions (Step 4)
 *
 * Keyword tag input with AI suggestion button and chips.
 * Auto-triggers suggestions when arriving at this step.
 */

import { useEffect, useRef, KeyboardEvent } from "react";
import { Plus, Loader2, Wand2 } from "lucide-react";
import { cn } from "../../../lib/utils";
import { KeywordTag } from "../KeywordTag";
import type { FormData } from "../../../types/workstream";

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

  return (
    <div className="space-y-6">
      {/* Inline help */}
      <div className="bg-brand-light-blue/30 dark:bg-brand-blue/10 rounded-lg p-4 border border-brand-blue/20">
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          Keywords drive the AI's search queries. Be specific -- "autonomous bus
          pilots" works better than just "buses". Click "Suggest Related Terms"
          to get AI-powered recommendations.
        </p>
      </div>

      {/* Keyword Input */}
      <div className="space-y-3">
        <label className="block text-sm font-medium text-gray-900 dark:text-white">
          Keywords
        </label>

        <div className="flex gap-2">
          <input
            type="text"
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            onKeyDown={onKeywordInputKeyDown}
            placeholder="Type a keyword and press Enter..."
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
    </div>
  );
}
