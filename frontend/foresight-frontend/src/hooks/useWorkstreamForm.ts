/**
 * useWorkstreamForm Hook
 *
 * Extracts all state management, handlers, effects, and validation
 * from WorkstreamForm into a reusable hook. Used by both the flat
 * WorkstreamForm (edit mode) and WorkstreamWizard (create mode).
 */

import { useState, useEffect, useCallback, useRef, KeyboardEvent } from "react";
import { supabase } from "../App";
import { useAuthContext } from "./useAuthContext";
import { getGoalsByPillar } from "../data/taxonomy";
import { suggestKeywords } from "../lib/discovery-api";
import type {
  Workstream,
  FormData,
  FormErrors,
  FilterPreviewResult,
  WorkstreamTemplate,
} from "../types/workstream";
import { fetchFilterPreview } from "../types/workstream";

interface UseWorkstreamFormProps {
  workstream?: Workstream;
  onSuccess: () => void;
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
  });

  // UI state
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [keywordInput, setKeywordInput] = useState("");

  // Suggest keywords state
  const [suggestedKeywords, setSuggestedKeywords] = useState<string[]>([]);
  const [isSuggestingKeywords, setIsSuggestingKeywords] = useState(false);

  // Post-creation zero-match prompt state
  const [showZeroMatchPrompt, setShowZeroMatchPrompt] = useState(false);
  const [createdWorkstreamId, setCreatedWorkstreamId] = useState<string | null>(
    null,
  );

  // Filter preview state
  const [preview, setPreview] = useState<FilterPreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    formData.keywords.length > 0;

  // Fetch filter preview when filters change
  useEffect(() => {
    if (previewDebounceRef.current) {
      clearTimeout(previewDebounceRef.current);
    }

    if (!hasFilters) {
      setPreview(null);
      return;
    }

    previewDebounceRef.current = setTimeout(async () => {
      setPreviewLoading(true);
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session?.access_token) return;

        const result = await fetchFilterPreview(session.access_token, {
          pillar_ids: formData.pillar_ids,
          goal_ids: formData.goal_ids,
          stage_ids: formData.stage_ids,
          horizon: formData.horizon,
          keywords: formData.keywords,
        });
        setPreview(result);
      } catch (error) {
        console.error("Failed to fetch filter preview:", error);
        setPreview(null);
      } finally {
        setPreviewLoading(false);
      }
    }, 500);

    return () => {
      if (previewDebounceRef.current) {
        clearTimeout(previewDebounceRef.current);
      }
    };
  }, [
    formData.pillar_ids,
    formData.goal_ids,
    formData.stage_ids,
    formData.horizon,
    formData.keywords,
    hasFilters,
  ]);

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

  /**
   * Validate only the current step (for wizard per-step gates)
   */
  const validateStep = useCallback(
    (step: number): boolean => {
      const newErrors: FormErrors = {};

      if (step === 2) {
        if (!formData.name.trim()) {
          newErrors.name = "Name is required";
        }
      }

      setErrors(newErrors);
      return Object.keys(newErrors).length === 0;
    },
    [formData],
  );

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

  // Helper to get auth token
  const getAuthToken = async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token;
  };

  // Suggest related keywords using AI
  const handleSuggestKeywords = async () => {
    const topic =
      keywordInput.trim() ||
      formData.name.trim() ||
      formData.description.trim();
    if (!topic) return;

    setIsSuggestingKeywords(true);
    setSuggestedKeywords([]);
    try {
      const token = await getAuthToken();
      if (!token) return;
      const result = await suggestKeywords(topic, token);
      const newSuggestions = result.suggestions.filter(
        (kw) => !formData.keywords.includes(kw),
      );
      setSuggestedKeywords(newSuggestions);
    } catch (error) {
      console.error("Failed to suggest keywords:", error);
    } finally {
      setIsSuggestingKeywords(false);
    }
  };

  // Add a suggested keyword to the form
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
    setSuggestedKeywords((prev) => prev.filter((kw) => kw !== keyword));
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
    }));
    setErrors({});
  }, []);

  // Trigger workstream analysis via API
  const triggerWorkstreamAnalysis = async (workstreamId: string) => {
    const token = await getAuthToken();
    if (!token) return;

    const API_BASE_URL =
      import.meta.env.VITE_API_URL || "http://localhost:8000";

    try {
      await fetch(`${API_BASE_URL}/api/v1/research`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          workstream_id: workstreamId,
          task_type: "workstream_analysis",
        }),
      });
    } catch (error) {
      console.error("Error triggering workstream analysis:", error);
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
      };

      if (isEditMode && workstream) {
        const { error } = await supabase
          .from("workstreams")
          .update(payload)
          .eq("id", workstream.id)
          .eq("user_id", user?.id);

        if (error) throw error;
      } else {
        const { data, error } = await supabase
          .from("workstreams")
          .insert({
            ...payload,
            user_id: user?.id,
            auto_add: false,
          })
          .select("id")
          .single();

        if (error) throw error;

        if (formData.analyze_now && data?.id) {
          await triggerWorkstreamAnalysis(data.id);
        }

        if (data?.id && preview?.estimated_count === 0) {
          setCreatedWorkstreamId(data.id);
          setShowZeroMatchPrompt(true);
          if (onCreatedWithZeroMatches) {
            onCreatedWithZeroMatches(data.id);
          }
        }
      }

      onSuccess();
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

  /**
   * Manually trigger the filter preview fetch (used by wizard's StepPreview)
   */
  const triggerPreviewFetch = useCallback(async () => {
    if (!hasFilters) {
      setPreview(null);
      return;
    }
    setPreviewLoading(true);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const result = await fetchFilterPreview(session.access_token, {
        pillar_ids: formData.pillar_ids,
        goal_ids: formData.goal_ids,
        stage_ids: formData.stage_ids,
        horizon: formData.horizon,
        keywords: formData.keywords,
      });
      setPreview(result);
    } catch (error) {
      console.error("Failed to fetch filter preview:", error);
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [
    hasFilters,
    formData.pillar_ids,
    formData.goal_ids,
    formData.stage_ids,
    formData.horizon,
    formData.keywords,
  ]);

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
    validateStep,

    // Utilities
    getAuthToken,
    triggerWorkstreamAnalysis,
    triggerPreviewFetch,
  };
}
