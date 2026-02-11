/**
 * WorkstreamForm Component
 *
 * A flat form layout for creating and editing workstreams.
 * In the new architecture:
 * - EDIT mode: Uses this flat form (unchanged UX)
 * - CREATE mode: The wizard (WorkstreamWizard) is preferred,
 *   but this form still works as a fallback.
 *
 * State management is handled by the useWorkstreamForm hook.
 * Types are imported from types/workstream.ts.
 */

import React from "react";
import {
  Plus,
  Loader2,
  AlertCircle,
  Sparkles,
  Search,
  Wand2,
  Radar,
} from "lucide-react";
import { cn } from "../lib/utils";
import { PillarBadge } from "./PillarBadge";
import { pillars, stages, horizons, getGoalsByPillar } from "../data/taxonomy";
import { useWorkstreamForm } from "../hooks/useWorkstreamForm";
import { FormSection } from "./workstream/FormSection";
import { KeywordTag } from "./workstream/KeywordTag";
import { ToggleSwitch } from "./workstream/ToggleSwitch";
import { TemplateCard } from "./workstream/TemplateCard";
import { WORKSTREAM_TEMPLATES } from "./workstream/steps/StepStart";

// Re-export types for backward compatibility
export type { Workstream, WorkstreamFormProps } from "../types/workstream";

export function WorkstreamForm({
  workstream,
  onSuccess,
  onCancel,
  onCreatedWithZeroMatches,
}: {
  workstream?: import("../types/workstream").Workstream;
  onSuccess: (createdId?: string, scanTriggered?: boolean) => void;
  onCancel: () => void;
  onCreatedWithZeroMatches?: (workstreamId: string) => void;
}) {
  const form = useWorkstreamForm({
    workstream,
    onSuccess,
    onCreatedWithZeroMatches,
  });

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <form onSubmit={form.handleSubmit} className="space-y-6">
      {/* Quick Start Templates - Only in CREATE mode */}
      {!form.isEditMode && (
        <div className="space-y-3">
          <div>
            <h4 className="text-sm font-medium text-gray-900 dark:text-white">
              Quick Start Templates
            </h4>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Choose a template to pre-fill the form, or start from scratch
              below
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {WORKSTREAM_TEMPLATES.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                onSelect={form.handleApplyTemplate}
              />
            ))}
          </div>
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200 dark:border-gray-700" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white dark:bg-dark-surface px-2 text-gray-500 dark:text-gray-400">
                or customize your own
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Name Field */}
      <div>
        <label
          htmlFor="workstream-name"
          className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
        >
          Name <span className="text-red-500">*</span>
        </label>
        <input
          id="workstream-name"
          type="text"
          value={form.formData.name}
          onChange={(e) => {
            form.setFormData((prev) => ({ ...prev, name: e.target.value }));
            if (form.errors.name) {
              form.setErrors((prev) => ({ ...prev, name: undefined }));
            }
          }}
          placeholder="e.g., Smart Mobility Initiatives"
          className={cn(
            "w-full px-3 py-2 border rounded-md shadow-sm text-sm",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue",
            "dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400",
            form.errors.name
              ? "border-red-300 bg-red-50 dark:border-red-500 dark:bg-red-900/20"
              : "border-gray-300 bg-white dark:border-gray-600",
          )}
          aria-invalid={Boolean(form.errors.name)}
          aria-describedby={form.errors.name ? "name-error" : undefined}
        />
        {form.errors.name && (
          <p
            id="name-error"
            className="mt-1 text-xs text-red-600 dark:text-red-400"
          >
            {form.errors.name}
          </p>
        )}
      </div>

      {/* Description Field */}
      <div>
        <label
          htmlFor="workstream-description"
          className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
        >
          Description
        </label>
        <textarea
          id="workstream-description"
          value={form.formData.description}
          onChange={(e) =>
            form.setFormData((prev) => ({
              ...prev,
              description: e.target.value,
            }))
          }
          placeholder="Describe the focus and purpose of this workstream..."
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400 resize-none"
        />
      </div>

      {/* Pillars Selection */}
      <FormSection
        title="Pillars"
        description="Optionally select strategic pillars to filter by, or leave empty for a topic-driven workstream"
      >
        <div className="flex flex-wrap gap-2">
          {pillars.map((pillar) => (
            <button
              key={pillar.code}
              type="button"
              onClick={() => form.handlePillarToggle(pillar.code)}
              className={cn(
                "transition-all duration-200",
                form.formData.pillar_ids.includes(pillar.code)
                  ? "ring-2 ring-brand-blue ring-offset-1 dark:ring-offset-[#2d3166] rounded"
                  : "opacity-60 hover:opacity-100",
              )}
              aria-pressed={form.formData.pillar_ids.includes(pillar.code)}
              aria-label={`${pillar.name} pillar`}
            >
              <PillarBadge
                pillarId={pillar.code}
                size="md"
                showIcon={true}
                disableTooltip
              />
            </button>
          ))}
        </div>
      </FormSection>

      {/* Goals Selection (grouped by pillar, only show if pillars selected) */}
      {form.formData.pillar_ids.length > 0 && (
        <FormSection
          title="Goals"
          description="Narrow down by specific goals within selected pillars"
        >
          <div className="space-y-4 max-h-48 overflow-y-auto border border-gray-200 dark:border-gray-600 rounded-md p-3 bg-gray-50 dark:bg-dark-surface-elevated">
            {form.formData.pillar_ids.map((pillarCode) => {
              const pillarGoals = getGoalsByPillar(pillarCode);
              const pillar = pillars.find((p) => p.code === pillarCode);
              if (!pillar || pillarGoals.length === 0) return null;

              return (
                <div key={pillarCode}>
                  <div className="flex items-center gap-2 mb-2">
                    <PillarBadge
                      pillarId={pillarCode}
                      size="sm"
                      showIcon={false}
                      disableTooltip
                    />
                    <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
                      {pillar.name}
                    </span>
                  </div>
                  <div className="space-y-1 ml-4">
                    {pillarGoals.map((goal) => (
                      <label
                        key={goal.code}
                        className="flex items-start gap-2 cursor-pointer group"
                      >
                        <input
                          type="checkbox"
                          checked={form.formData.goal_ids.includes(goal.code)}
                          onChange={() => form.handleGoalToggle(goal.code)}
                          className="mt-0.5 h-4 w-4 text-brand-blue border-gray-300 dark:border-gray-500 rounded focus:ring-brand-blue"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white">
                          <span className="font-mono text-xs text-gray-500 dark:text-gray-400 mr-1">
                            {goal.code}
                          </span>
                          {goal.name}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </FormSection>
      )}

      {/* Stages Selection */}
      <FormSection
        title="Maturity Stages"
        description="Filter by technology maturity stage (1-8)"
      >
        <div className="flex flex-wrap gap-2">
          {stages.map((stage) => (
            <button
              key={stage.stage}
              type="button"
              onClick={() => form.handleStageToggle(stage.stage)}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-md border transition-colors",
                form.formData.stage_ids.includes(stage.stage.toString())
                  ? "bg-brand-light-blue dark:bg-brand-blue/20 border-brand-blue text-brand-dark-blue dark:text-brand-light-blue"
                  : "bg-white dark:bg-dark-surface-elevated border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
              )}
              aria-pressed={form.formData.stage_ids.includes(
                stage.stage.toString(),
              )}
              title={`${stage.name}: ${stage.description}`}
            >
              {stage.stage}. {stage.name}
            </button>
          ))}
        </div>
      </FormSection>

      {/* Horizon Selection */}
      <FormSection
        title="Horizon"
        description="Filter by strategic planning horizon"
      >
        <div className="flex flex-wrap gap-2">
          {[
            { code: "ALL", name: "All Horizons", timeframe: "" },
            ...horizons,
          ].map((h) => (
            <button
              key={h.code}
              type="button"
              onClick={() => form.handleHorizonChange(h.code)}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-md border transition-colors",
                form.formData.horizon === h.code
                  ? "bg-brand-light-blue dark:bg-brand-blue/20 border-brand-blue text-brand-dark-blue dark:text-brand-light-blue"
                  : "bg-white dark:bg-dark-surface-elevated border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
              )}
              aria-pressed={form.formData.horizon === h.code}
            >
              {h.code === "ALL" ? "All" : h.code}
              {h.code !== "ALL" && (
                <span className="ml-1 text-xs text-gray-500 dark:text-gray-400">
                  ({(h as (typeof horizons)[0]).timeframe})
                </span>
              )}
            </button>
          ))}
        </div>
      </FormSection>

      {/* Keywords Input */}
      <FormSection
        title="Keywords"
        description="Add keywords to match against signal content (press Enter or comma to add)"
      >
        <div className="space-y-2">
          <div className="flex gap-2">
            <input
              type="text"
              value={form.keywordInput}
              onChange={(e) => form.setKeywordInput(e.target.value)}
              onKeyDown={form.handleKeywordInputKeyDown}
              placeholder="Type a keyword and press Enter..."
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400"
            />
            <button
              type="button"
              onClick={form.handleKeywordAdd}
              disabled={!form.keywordInput.trim()}
              className={cn(
                "px-3 py-2 text-sm font-medium rounded-md border transition-colors",
                form.keywordInput.trim()
                  ? "bg-brand-blue border-brand-blue text-white hover:bg-brand-dark-blue"
                  : "bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-400 cursor-not-allowed",
              )}
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
          {form.formData.keywords.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {form.formData.keywords.map((keyword) => (
                <KeywordTag
                  key={keyword}
                  keyword={keyword}
                  onRemove={() => form.handleKeywordRemove(keyword)}
                />
              ))}
            </div>
          )}
          {/* Suggest Related Terms */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={form.handleSuggestKeywords}
              disabled={
                form.isSuggestingKeywords ||
                (!form.keywordInput.trim() &&
                  !form.formData.name.trim() &&
                  !form.formData.description.trim())
              }
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-colors",
                form.isSuggestingKeywords ||
                  (!form.keywordInput.trim() &&
                    !form.formData.name.trim() &&
                    !form.formData.description.trim())
                  ? "bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-400 cursor-not-allowed"
                  : "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-700 text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/40",
              )}
            >
              {form.isSuggestingKeywords ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Wand2 className="h-3.5 w-3.5" />
              )}
              {form.isSuggestingKeywords
                ? "Suggesting..."
                : "Suggest Related Terms"}
            </button>
          </div>
          {/* Suggested Keywords Chips */}
          {form.suggestedKeywords.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Click to add suggested terms:
              </p>
              <div className="flex flex-wrap gap-1.5">
                {form.suggestedKeywords.map((kw) => (
                  <button
                    key={kw}
                    type="button"
                    onClick={() => form.handleAddSuggestedKeyword(kw)}
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
      </FormSection>

      {/* Active Toggle */}
      <div className="pt-2">
        <ToggleSwitch
          checked={form.formData.is_active}
          onChange={(checked) =>
            form.setFormData((prev) => ({ ...prev, is_active: checked }))
          }
          label="Active"
          description="Active workstreams will appear in your feed and receive new signals"
        />
      </div>

      {/* Analyze Now Toggle - Only in CREATE mode */}
      {!form.isEditMode && (
        <div className="pt-2">
          <ToggleSwitch
            checked={form.formData.analyze_now}
            onChange={(checked) =>
              form.setFormData((prev) => ({ ...prev, analyze_now: checked }))
            }
            label="Analyze Now"
            description="Immediately run AI research to find matching signals and discover new technologies based on your keywords"
          />
        </div>
      )}

      {/* Auto-scan on Create Toggle - Only in CREATE mode */}
      {!form.isEditMode && (
        <div className="pt-2">
          <ToggleSwitch
            checked={form.formData.auto_scan}
            onChange={(checked) =>
              form.setFormData((prev) => ({ ...prev, auto_scan: checked }))
            }
            label="Auto-scan for sources on create"
            description={
              form.formData.pillar_ids.length === 0
                ? "Recommended for topic-driven workstreams without pillars -- automatically discover relevant content sources"
                : "Automatically scan for content sources matching your workstream filters"
            }
          />
        </div>
      )}

      {/* Filter Preview - Match Count */}
      {form.hasFilters && (
        <div
          className={cn(
            "rounded-lg p-4 border transition-all",
            form.preview && form.preview.estimated_count > 0
              ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700"
              : form.preview && form.preview.estimated_count === 0
                ? "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-700"
                : "bg-gray-50 dark:bg-dark-surface/50 border-gray-200 dark:border-gray-700",
          )}
        >
          <div className="flex items-center gap-3">
            {form.previewLoading ? (
              <>
                <Loader2 className="h-5 w-5 text-gray-400 animate-spin" />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Searching for matching signals...
                </span>
              </>
            ) : form.preview ? (
              <>
                {form.preview.estimated_count > 0 ? (
                  <Search className="h-5 w-5 text-green-600 dark:text-green-400" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                )}
                <div className="flex-1">
                  <div className="flex items-baseline gap-2">
                    <span
                      className={cn(
                        "text-2xl font-bold",
                        form.preview.estimated_count > 0
                          ? "text-green-700 dark:text-green-300"
                          : "text-amber-700 dark:text-amber-300",
                      )}
                    >
                      ~{form.preview.estimated_count}
                    </span>
                    <span
                      className={cn(
                        "text-sm",
                        form.preview.estimated_count > 0
                          ? "text-green-600 dark:text-green-400"
                          : "text-amber-600 dark:text-amber-400",
                      )}
                    >
                      {form.preview.estimated_count === 1
                        ? "signal matches"
                        : "signals match"}{" "}
                      these filters
                    </span>
                  </div>
                  {form.preview.sample_cards.length > 0 && (
                    <div className="mt-2">
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                        Sample matches:
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {form.preview.sample_cards.slice(0, 3).map((card) => (
                          <span
                            key={card.id}
                            className="text-xs px-2 py-0.5 rounded bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600 truncate max-w-[200px]"
                            title={card.name}
                          >
                            {card.name}
                          </span>
                        ))}
                        {form.preview.estimated_count > 3 && (
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            +{form.preview.estimated_count - 3} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                  {form.preview.estimated_count === 0 && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                      Try broadening your filters or adding different keywords
                    </p>
                  )}
                </div>
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5 text-gray-400" />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Add filters to see matching signals
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Validation Error for Filters */}
      {form.errors.filters && (
        <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md">
          <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <p className="text-sm text-amber-800 dark:text-amber-300">
            {form.errors.filters}
          </p>
        </div>
      )}

      {/* Submit Error */}
      {form.errors.submit && (
        <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-md">
          <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-800 dark:text-red-300">
            {form.errors.submit}
          </p>
        </div>
      )}

      {/* Zero Match Prompt - shown after creation when no existing cards match */}
      {form.showZeroMatchPrompt && form.createdWorkstreamId && (
        <div className="rounded-lg p-4 border border-blue-200 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20">
          <div className="flex items-start gap-3">
            <Radar className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div className="flex-1 space-y-2">
              <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                No existing signals match this topic.
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-400">
                Would you like to discover new content?
              </p>
              <button
                type="button"
                onClick={() => {
                  if (onCreatedWithZeroMatches) {
                    onCreatedWithZeroMatches(form.createdWorkstreamId!);
                  }
                  form.setShowZeroMatchPrompt(false);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
              >
                <Radar className="h-3.5 w-3.5" />
                Start Discovery Scan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Form Actions */}
      <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-600">
        <button
          type="button"
          onClick={onCancel}
          disabled={form.isSubmitting}
          className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface-elevated border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface disabled:opacity-50 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={form.isSubmitting}
          className={cn(
            "inline-flex items-center px-4 py-2 text-sm font-medium text-white rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors",
            form.isSubmitting
              ? "bg-brand-blue/60 cursor-not-allowed"
              : "bg-brand-blue hover:bg-brand-dark-blue",
          )}
        >
          {form.isSubmitting && (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          )}
          {form.isEditMode ? "Save Changes" : "Create Workstream"}
        </button>
      </div>
    </form>
  );
}

export default WorkstreamForm;
