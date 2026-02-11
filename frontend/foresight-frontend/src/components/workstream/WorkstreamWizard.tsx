/**
 * WorkstreamWizard - 5-Step guided workstream creation wizard
 *
 * Steps:
 *   1. Start     - Template selection or build your own
 *   2. Details   - Name & description
 *   3. Focus     - Pillars, stages, horizon
 *   4. Keywords  - Keywords & AI suggestions
 *   5. Review    - Preview & launch options
 *
 * Only used for CREATE mode. Edit mode uses WorkstreamForm.
 */

import { useState, useCallback } from "react";
import { ArrowLeft, ArrowRight, Loader2, Rocket } from "lucide-react";
import { cn } from "../../lib/utils";
import { useWorkstreamForm } from "../../hooks/useWorkstreamForm";
import { WizardProgress } from "./WizardProgress";
import { StepStart } from "./steps/StepStart";
import { StepDetails } from "./steps/StepDetails";
import { StepFocus } from "./steps/StepFocus";
import { StepKeywords } from "./steps/StepKeywords";
import { StepPreview } from "./steps/StepPreview";
import type {
  WorkstreamFormProps,
  WorkstreamTemplate,
} from "../../types/workstream";

const TOTAL_STEPS = 5;

export function WorkstreamWizard({
  onSuccess,
  onCancel,
  onCreatedWithZeroMatches,
}: Omit<WorkstreamFormProps, "workstream">) {
  const [step, setStep] = useState(1);
  const [direction, setDirection] = useState<"forward" | "backward">("forward");

  const form = useWorkstreamForm({
    onSuccess,
    onCreatedWithZeroMatches,
  });

  // ============================================================================
  // Wizard-specific step validation (not generic form logic)
  // ============================================================================

  const validateStep = useCallback(
    (stepNum: number): boolean => {
      if (stepNum === 2) {
        if (!form.formData.name.trim()) {
          form.setErrors({ name: "Name is required" });
          return false;
        }
        form.setErrors({});
      }
      return true;
    },
    [form],
  );

  // ============================================================================
  // Navigation
  // ============================================================================

  const goToStep = useCallback(
    (newStep: number, dir: "forward" | "backward") => {
      setDirection(dir);
      setStep(newStep);
    },
    [],
  );

  const handleNext = useCallback(() => {
    // Per-step validation gate
    if (step === 2 && !validateStep(2)) {
      return;
    }
    if (step < TOTAL_STEPS) {
      goToStep(step + 1, "forward");
    }
  }, [step, validateStep, goToStep]);

  const handleBack = useCallback(() => {
    if (step > 1) {
      goToStep(step - 1, "backward");
    }
  }, [step, goToStep]);

  const handleSelectTemplate = useCallback(
    (template: WorkstreamTemplate) => {
      form.handleApplyTemplate(template);
      goToStep(2, "forward");
    },
    [form, goToStep],
  );

  const handleBuildYourOwn = useCallback(() => {
    goToStep(2, "forward");
  }, [goToStep]);

  const handleCreate = useCallback(() => {
    form.handleSubmit();
  }, [form]);

  // ============================================================================
  // Step Content
  // ============================================================================

  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <StepStart
            onSelectTemplate={handleSelectTemplate}
            onBuildYourOwn={handleBuildYourOwn}
          />
        );
      case 2:
        return (
          <StepDetails
            formData={form.formData}
            errors={form.errors}
            onNameChange={(name) =>
              form.setFormData((prev) => ({ ...prev, name }))
            }
            onDescriptionChange={(description) =>
              form.setFormData((prev) => ({ ...prev, description }))
            }
            onClearNameError={() =>
              form.setErrors((prev) => ({ ...prev, name: undefined }))
            }
          />
        );
      case 3:
        return (
          <StepFocus
            formData={form.formData}
            onPillarToggle={form.handlePillarToggle}
            onGoalToggle={form.handleGoalToggle}
            onStageToggle={form.handleStageToggle}
            onHorizonChange={form.handleHorizonChange}
          />
        );
      case 4:
        return (
          <StepKeywords
            formData={form.formData}
            keywordInput={form.keywordInput}
            setKeywordInput={form.setKeywordInput}
            suggestedKeywords={form.suggestedKeywords}
            isSuggestingKeywords={form.isSuggestingKeywords}
            onKeywordAdd={form.handleKeywordAdd}
            onKeywordInputKeyDown={form.handleKeywordInputKeyDown}
            onKeywordRemove={form.handleKeywordRemove}
            onSuggestKeywords={form.handleSuggestKeywords}
            onAddSuggestedKeyword={form.handleAddSuggestedKeyword}
          />
        );
      case 5:
        return (
          <StepPreview
            formData={form.formData}
            preview={form.preview}
            previewLoading={form.previewLoading}
            hasFilters={form.hasFilters}
            onAutoScanChange={(value) =>
              form.setFormData((prev) => ({ ...prev, auto_scan: value }))
            }
            onAnalyzeNowChange={(value) =>
              form.setFormData((prev) => ({ ...prev, analyze_now: value }))
            }
            triggerPreviewFetch={form.triggerPreviewFetch}
          />
        );
      default:
        return null;
    }
  };

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div className="flex flex-col h-full max-h-[85vh]">
      {/* Progress bar at top */}
      <WizardProgress currentStep={step} totalSteps={TOTAL_STEPS} />

      {/* Step content - scrollable middle area */}
      <div className="flex-1 overflow-y-auto px-6 py-5 min-h-0">
        <div
          className={cn(
            "transition-all duration-200",
            direction === "forward"
              ? "animate-in fade-in slide-in-from-right-4"
              : "animate-in fade-in slide-in-from-left-4",
          )}
          key={step}
        >
          {renderStep()}
        </div>

        {/* Submit Error */}
        {form.errors.submit && (
          <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-md">
            <p className="text-sm text-red-800 dark:text-red-300">
              {form.errors.submit}
            </p>
          </div>
        )}
      </div>

      {/* Navigation buttons at bottom - always visible */}
      <div className="border-t border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between bg-white dark:bg-dark-surface">
        <div>
          {step > 1 ? (
            <button
              type="button"
              onClick={handleBack}
              disabled={form.isSubmitting}
              className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface-elevated border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface disabled:opacity-50 transition-colors"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back
            </button>
          ) : (
            <button
              type="button"
              onClick={onCancel}
              className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface-elevated border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors"
            >
              Cancel
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Skip to end (on steps 3-4, user can jump to review if they have at least a name) */}
          {(step === 3 || step === 4) && form.formData.name.trim() && (
            <button
              type="button"
              onClick={() => goToStep(5, "forward")}
              className="text-sm text-gray-500 dark:text-gray-400 hover:text-brand-blue dark:hover:text-brand-light-blue transition-colors px-3 py-2"
            >
              Skip to Review
            </button>
          )}

          {step < TOTAL_STEPS ? (
            <button
              type="button"
              onClick={handleNext}
              className={cn(
                "inline-flex items-center px-5 py-2 text-sm font-medium text-white rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors",
                "bg-brand-blue hover:bg-brand-dark-blue",
              )}
            >
              Next
              <ArrowRight className="h-4 w-4 ml-1" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleCreate}
              disabled={form.isSubmitting}
              className={cn(
                "inline-flex items-center px-5 py-2 text-sm font-medium text-white rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors",
                form.isSubmitting
                  ? "bg-brand-blue/60 cursor-not-allowed"
                  : "bg-brand-blue hover:bg-brand-dark-blue",
              )}
            >
              {form.isSubmitting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Rocket className="h-4 w-4 mr-2" />
              )}
              Create Workstream
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default WorkstreamWizard;
