/**
 * StepDetails - Name & Description (Step 2)
 *
 * Name input (required) and description textarea with a
 * "Generate with AI" placeholder button.
 */

import { Sparkles } from "lucide-react";
import { cn } from "../../../lib/utils";
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
            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-400 dark:text-gray-500 rounded border border-gray-200 dark:border-gray-600 cursor-not-allowed"
            title="Coming soon"
            disabled
          >
            <Sparkles className="h-3 w-3" />
            Generate with AI
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
