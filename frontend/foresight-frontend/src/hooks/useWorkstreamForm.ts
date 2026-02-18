/**
 * useWorkstreamForm Hook
 *
 * Extracts all state management, handlers, effects, and validation
 * from WorkstreamForm into a reusable hook. Used by both the flat
 * WorkstreamForm (edit mode) and WorkstreamWizard (create mode).
 *
 * Composes sub-hooks:
 * - useWorkstreamPreview: filter preview state and fetching
 * - useKeywordSuggestions: AI keyword suggestion state and fetching
 */

import { useState, useEffect, useCallback, KeyboardEvent } from "react";
import { useAuthContext } from "./useAuthContext";
import { useWorkstreamPreview } from "./useWorkstreamPreview";
import { useKeywordSuggestions } from "./useKeywordSuggestions";
import { getGoalsByPillar } from "../data/taxonomy";
import { startWorkstreamScan } from "../lib/workstream-api";
import { API_BASE_URL } from "../lib/config";
import type {
  Workstream,
  FormData,
  FormErrors,
  WorkstreamTemplate,
} from "../types/workstream";

interface UseWorkstreamFormProps {
  workstream?: Workstream;
  onSuccess: (createdId?: string, scanTriggered?: boolean) => void;
  onCreatedWithZeroMatches?: (workstreamId: string) => void;
}

export function useWorkstreamForm({
  workstream,
  onSuccess,
  onCreatedWithZeroMatches,
}: UseWorkstreamFormProps) {
  const { user } = useAuthContext();
  const isEditMode = Boolean(workstream);

  // Form state
  const [formData, setFormData] = useState<FormData>({
    name: workstream?.name || "",
    description: workstream?.description || "",
    pillar_ids: workstream?.pillar_ids || [],
    goal_ids: workstream?.goal_ids || [],
    stage_ids: workstream?.stage_ids || [],
    horizon: workstream?.horizon || "ALL",
    keywords: workstream?.keywords || [],
    is_active: workstream?.is_active ?? true,
    analyze_now: false,
    auto_scan: false,
    // Grant program fields
    department_id: workstream?.department_id || "",
    program_type: workstream?.program_type || "",
    budget_range_min: workstream?.budget ?? null,
    budget_range_max: workstream?.budget ?? null,
    fiscal_year: workstream?.fiscal_year || "",
    category_ids: workstream?.category_ids || [],
    grant_types: [],
  });

  // UI state
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [keywordInput, setKeywordInput] = useState("");

  // Post-creation zero-match prompt state
  const [showZeroMatchPrompt, setShowZeroMatchPrompt] = useState(false);
  const [createdWorkstreamId, setCreatedWorkstreamId] = useState<string | null>(
    null,
  );

  // Derived state: available goals based on selected pillars
  const availableGoals = formData.pillar_ids.flatMap((pillarCode) =>
    getGoalsByPillar(pillarCode),
  );

  // Check if any filters are set
  const hasFilters =
    formData.pillar_ids.length > 0 ||
    formData.goal_ids.length > 0 ||
    formData.stage_ids.length > 0 ||
    formData.horizon !== "ALL" ||
    formData.keywords.length > 0 ||
    formData.category_ids.length > 0;

  // ============================================================================
  // Sub-hooks
  // ============================================================================

  // Helper to get auth token
  const getAuthToken = useCallback(async (): Promise<string | undefined> => {
    const token = localStorage.getItem("gs2_token");
    return token ?? undefined;
  }, []);

  // Preview sub-hook
  const { preview, previewLoading, triggerPreviewFetch } = useWorkstreamPreview(
    formData,
    hasFilters,
  );

  // Keyword suggestions sub-hook
  const getTopicContext = useCallback(
    () => ({
      name: formData.name,
      description: formData.description,
      keywords: formData.keywords,
    }),
    [formData.name, formData.description, formData.keywords],
  );

  const {
    suggestedKeywords,
    isSuggestingKeywords,
    handleSuggestKeywords: suggestKeywordsFromHook,
    removeSuggestion,
    setSuggestedKeywords,
  } = useKeywordSuggestions(getTopicContext, getAuthToken);

  // Wrap handleSuggestKeywords to pass keywordInput as topicOverride
  const handleSuggestKeywords = useCallback(async () => {
    await suggestKeywordsFromHook(keywordInput);
  }, [suggestKeywordsFromHook, keywordInput]);

  // ============================================================================
  // Effects
  // ============================================================================

  // When pillars change, filter out goals that are no longer valid
  useEffect(() => {
    const validGoalCodes = new Set(availableGoals.map((g) => g.code));
    const filteredGoals = formData.goal_ids.filter((id) =>
      validGoalCodes.has(id),
    );
    if (filteredGoals.length !== formData.goal_ids.length) {
      setFormData((prev) => ({ ...prev, goal_ids: filteredGoals }));
    }
  }, [formData.pillar_ids, availableGoals, formData.goal_ids]);

  // Sync auto_scan default based on pillar selection
  useEffect(() => {
    if (!isEditMode) {
      setFormData((prev) => ({
        ...prev,
        auto_scan: prev.pillar_ids.length === 0,
      }));
    }
  }, [formData.pillar_ids.length, isEditMode]);

  // ============================================================================
  // Validation
  // ============================================================================

  const validateForm = useCallback((): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = "Name is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  // ============================================================================
  // Handlers
  // ============================================================================

  const handlePillarToggle = (pillarCode: string) => {
    setFormData((prev) => ({
      ...prev,
      pillar_ids: prev.pillar_ids.includes(pillarCode)
        ? prev.pillar_ids.filter((id) => id !== pillarCode)
        : [...prev.pillar_ids, pillarCode],
    }));
    if (errors.filters) {
      setErrors((prev) => ({ ...prev, filters: undefined }));
    }
  };

  const handleGoalToggle = (goalCode: string) => {
    setFormData((prev) => ({
      ...prev,
      goal_ids: prev.goal_ids.includes(goalCode)
        ? prev.goal_ids.filter((id) => id !== goalCode)
        : [...prev.goal_ids, goalCode],
    }));
    if (errors.filters) {
      setErrors((prev) => ({ ...prev, filters: undefined }));
    }
  };

  const handleStageToggle = (stageNum: number) => {
    const stageId = stageNum.toString();
    setFormData((prev) => ({
      ...prev,
      stage_ids: prev.stage_ids.includes(stageId)
        ? prev.stage_ids.filter((id) => id !== stageId)
        : [...prev.stage_ids, stageId],
    }));
    if (errors.filters) {
      setErrors((prev) => ({ ...prev, filters: undefined }));
    }
  };

  const handleHorizonChange = (horizon: string) => {
    setFormData((prev) => ({ ...prev, horizon }));
    if (errors.filters) {
      setErrors((prev) => ({ ...prev, filters: undefined }));
    }
  };

  const handleKeywordAdd = () => {
    const trimmed = keywordInput.trim();
    if (trimmed && !formData.keywords.includes(trimmed)) {
      setFormData((prev) => ({
        ...prev,
        keywords: [...prev.keywords, trimmed],
      }));
      setKeywordInput("");
      if (errors.filters) {
        setErrors((prev) => ({ ...prev, filters: undefined }));
      }
    }
  };

  const handleKeywordInputKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleKeywordAdd();
    } else if (e.key === "," && keywordInput.trim()) {
      e.preventDefault();
      handleKeywordAdd();
    }
  };

  const handleKeywordRemove = (keyword: string) => {
    setFormData((prev) => ({
      ...prev,
      keywords: prev.keywords.filter((k) => k !== keyword),
    }));
  };

  // Add a suggested keyword to the form and remove from suggestions
  const handleAddSuggestedKeyword = (keyword: string) => {
    if (!formData.keywords.includes(keyword)) {
      setFormData((prev) => ({
        ...prev,
        keywords: [...prev.keywords, keyword],
      }));
      if (errors.filters) {
        setErrors((prev) => ({ ...prev, filters: undefined }));
      }
    }
    removeSuggestion(keyword);
  };

  // Apply a template to the form
  const handleApplyTemplate = useCallback((template: WorkstreamTemplate) => {
    setFormData((prev) => ({
      ...prev,
      name: template.config.name,
      description: template.config.description,
      pillar_ids: template.config.pillar_ids,
      goal_ids: template.config.goal_ids,
      stage_ids: template.config.stage_ids,
      horizon: template.config.horizon,
      keywords: template.config.keywords,
      // Apply grant-specific template fields if present
      ...(template.config.category_ids
        ? { category_ids: template.config.category_ids }
        : {}),
      ...(template.config.program_type
        ? { program_type: template.config.program_type }
        : {}),
      ...(template.config.department_id
        ? { department_id: template.config.department_id }
        : {}),
    }));
    setErrors({});
  }, []);

  // Trigger workstream scan via the real scan pipeline (workstream_scans table -> worker)
  const triggerWorkstreamAnalysis = async (
    workstreamId: string,
  ): Promise<string | null> => {
    const token = await getAuthToken();
    if (!token) return null;

    try {
      const response = await startWorkstreamScan(token, workstreamId);
      return response.scan_id;
    } catch (error) {
      console.error("Error triggering workstream scan:", error);
      return null;
    }
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      const payload = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        pillar_ids: formData.pillar_ids,
        goal_ids: formData.goal_ids,
        stage_ids: formData.stage_ids,
        horizon: formData.horizon,
        keywords: formData.keywords,
        is_active: formData.is_active,
        ...(formData.auto_scan ? { auto_scan: true } : {}),
        // Grant program fields
        department_id: formData.department_id || null,
        program_type: formData.program_type || null,
        budget: formData.budget_range_max || null,
        fiscal_year: formData.fiscal_year || null,
        category_ids: formData.category_ids,
      };

      if (isEditMode && workstream) {
        // EDIT mode: use backend API
        const token = localStorage.getItem("gs2_token");
        if (!token) throw new Error("Authentication required");

        const editResponse = await fetch(
          `${API_BASE_URL}/api/v1/me/workstreams/${workstream.id}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify(payload),
          },
        );

        if (!editResponse.ok) {
          const errBody = await editResponse.json().catch(() => ({}));
          throw new Error(
            errBody.detail || `Update failed: ${editResponse.status}`,
          );
        }

        onSuccess();
      } else {
        // CREATE mode: use backend API so auto-populate and auto-scan queueing runs
        const token = localStorage.getItem("gs2_token");

        const response = await fetch(`${API_BASE_URL}/api/v1/me/workstreams`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({}));
          throw new Error(errBody.detail || "Failed to create workstream");
        }

        const data = await response.json();
        // If user requested a scan, always treat as triggered — the backend
        // may have already queued one during creation (auto_scan + <3 matches),
        // so our explicit call might get "already in progress" and return null.
        // Either way a scan IS running and the kanban should show feedback.
        let scanTriggered = false;

        if (formData.analyze_now && data?.id) {
          await triggerWorkstreamAnalysis(data.id);
          scanTriggered = true;
        }

        if (data?.id && preview?.estimated_count === 0) {
          setCreatedWorkstreamId(data.id);
          setShowZeroMatchPrompt(true);
          if (onCreatedWithZeroMatches) {
            onCreatedWithZeroMatches(data.id);
          }
        }

        onSuccess(data?.id, scanTriggered);
      }
    } catch (error) {
      console.error("Error saving workstream:", error);
      setErrors({
        submit:
          error instanceof Error
            ? error.message
            : "Failed to save workstream. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    // State
    formData,
    setFormData,
    errors,
    setErrors,
    isSubmitting,
    keywordInput,
    setKeywordInput,
    suggestedKeywords,
    setSuggestedKeywords,
    isSuggestingKeywords,
    showZeroMatchPrompt,
    setShowZeroMatchPrompt,
    createdWorkstreamId,
    preview,
    previewLoading,

    // Derived state
    availableGoals,
    hasFilters,
    isEditMode,

    // Handlers
    handlePillarToggle,
    handleGoalToggle,
    handleStageToggle,
    handleHorizonChange,
    handleKeywordAdd,
    handleKeywordInputKeyDown,
    handleKeywordRemove,
    handleSuggestKeywords,
    handleAddSuggestedKeyword,
    handleApplyTemplate,
    handleSubmit,

    // Validation
    validateForm,

    // Utilities
    getAuthToken,
    triggerWorkstreamAnalysis,
    triggerPreviewFetch,
  };
}
