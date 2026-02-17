/**
 * useWorkstreamPreview Hook
 *
 * Manages filter preview state and fetching for workstream forms.
 * Provides both auto-debounced preview (for live preview in flat form)
 * and manual trigger (for wizard's Step 5).
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { supabase } from "../App";
import { fetchFilterPreview } from "../types/workstream";
import type { FilterPreviewResult, FormData } from "../types/workstream";

export function useWorkstreamPreview(formData: FormData, hasFilters: boolean) {
  const [preview, setPreview] = useState<FilterPreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchPreview = useCallback(async () => {
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

      // Fetch preview of matching opportunities based on current filters
      const result = await fetchFilterPreview(session.access_token, {
        pillar_ids: formData.pillar_ids,
        goal_ids: formData.goal_ids,
        stage_ids: formData.stage_ids,
        horizon: formData.horizon,
        keywords: formData.keywords,
        category_ids: formData.category_ids,
      });
      setPreview(result);
    } catch (error) {
      console.error("Failed to fetch opportunity preview:", error);
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
    formData.category_ids,
  ]);

  // Auto-debounced fetch when filters change (for live preview of matching opportunities)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!hasFilters) {
      setPreview(null);
      return;
    }
    debounceRef.current = setTimeout(() => {
      void fetchPreview();
    }, 500);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [hasFilters, fetchPreview]);

  // Manual trigger (for wizard's Step 5)
  const triggerPreviewFetch = useCallback(() => {
    void fetchPreview();
  }, [fetchPreview]);

  return { preview, previewLoading, triggerPreviewFetch };
}
