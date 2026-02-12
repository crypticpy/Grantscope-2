/**
 * StepDetails - Name & Description (Step 2)
 *
 * Name input (required) and description textarea with AI generation.
 */

import { useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import { cn } from "../../../lib/utils";
import { supabase } from "../../../App";
import { API_BASE_URL } from "../../../lib/config";
import type { FormData, FormErrors } from "../../../types/workstream";

interface StepDetailsProps {
  formData: FormData;
  errors: FormErrors;
  onNameChange: (name: string) => void;
  onDescriptionChange: (description: string) => void;
  onClearNameError: () => void;
}

export function StepDetails({
  formData,
  errors,
  onNameChange,
  onDescriptionChange,
  onClearNameError,
}: StepDetailsProps) {
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerateDescription = async () => {
    if (!formData.name.trim()) return;
    setIsGenerating(true);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch(
        `${API_BASE_URL}/api/v1/ai/suggest-description`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
          },
          body: JSON.stringify({
            name: formData.name,
            pillar_ids: formData.pillar_ids,
            keywords: formData.keywords,
          }),
        },
      );
      if (response.ok) {
        const data = await response.json();
        if (data.description) {
          onDescriptionChange(data.description);
        }
      }
    } catch (error) {
      console.error("Failed to generate description:", error);
    } finally {
      setIsGenerating(false);
    }
  };

  const canGenerate = formData.name.trim().length > 0 && !isGenerating;

  return (
    <div className="space-y-6">
      {/* Inline help */}
      <div className="bg-brand-light-blue/30 dark:bg-brand-blue/10 rounded-lg p-4 border border-brand-blue/20">
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          Give your workstream a clear name and description. This helps the AI
          understand what signals to look for.
        </p>
      </div>

      {/* Name Field */}
      <div>
        <label
          htmlFor="wizard-workstream-name"
          className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
        >
          Name <span className="text-red-500">*</span>
        </label>
        <input
          id="wizard-workstream-name"
          type="text"
          value={formData.name}
          onChange={(e) => {
            onNameChange(e.target.value);
            if (errors.name) {
              onClearNameError();
            }
          }}
          placeholder="e.g., Smart Mobility Initiatives"
          className={cn(
            "w-full px-3 py-2 border rounded-md shadow-sm text-sm",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue",
            "dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400",
            errors.name
              ? "border-red-300 bg-red-50 dark:border-red-500 dark:bg-red-900/20"
              : "border-gray-300 bg-white dark:border-gray-600",
          )}
          aria-invalid={Boolean(errors.name)}
          aria-describedby={errors.name ? "wizard-name-error" : undefined}
          autoFocus
        />
        {errors.name && (
          <p
            id="wizard-name-error"
            className="mt-1 text-xs text-red-600 dark:text-red-400"
          >
            {errors.name}
          </p>
        )}
      </div>

      {/* Description Field */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label
            htmlFor="wizard-workstream-description"
            className="block text-sm font-medium text-gray-900 dark:text-white"
          >
            Description
          </label>
          <button
            type="button"
            onClick={handleGenerateDescription}
            disabled={!canGenerate}
            className={cn(
              "inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border transition-colors",
              canGenerate
                ? "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-700 text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/40"
                : "bg-gray-100 dark:bg-gray-700 border-gray-200 dark:border-gray-600 text-gray-400 cursor-not-allowed",
            )}
          >
            {isGenerating ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Sparkles className="h-3 w-3" />
            )}
            {isGenerating ? "Generating..." : "Generate with AI"}
          </button>
        </div>
        <textarea
          id="wizard-workstream-description"
          value={formData.description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          placeholder="Describe the focus and purpose of this workstream..."
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400 resize-none"
        />
      </div>
    </div>
  );
}
