/**
 * Workstream Types & Templates
 *
 * Shared types, interfaces, templates, and helper functions
 * used by both WorkstreamForm (edit mode) and WorkstreamWizard (create mode).
 */

import React from "react";

// ============================================================================
// Core Types
// ============================================================================

export interface Workstream {
  id: string;
  name: string;
  description: string;
  pillar_ids: string[];
  goal_ids: string[];
  stage_ids: string[];
  horizon: string;
  keywords: string[];
  is_active: boolean;
  auto_add: boolean;
  auto_scan?: boolean;
  created_at: string;
}

export interface WorkstreamFormProps {
  /** If provided, form operates in EDIT mode; otherwise CREATE mode */
  workstream?: Workstream;
  /** Called after successful save. Receives the created workstream ID and whether a scan was triggered. */
  onSuccess: (createdId?: string, scanTriggered?: boolean) => void;
  /** Called when form is cancelled */
  onCancel: () => void;
  /** Called after creation when auto-populate finds zero matching cards */
  onCreatedWithZeroMatches?: (workstreamId: string) => void;
}

export interface FormData {
  name: string;
  description: string;
  pillar_ids: string[];
  goal_ids: string[];
  stage_ids: string[];
  horizon: string;
  keywords: string[];
  is_active: boolean;
  analyze_now: boolean;
  auto_scan: boolean;
}

export interface FormErrors {
  name?: string;
  filters?: string;
  submit?: string;
}

// ============================================================================
// Filter Preview
// ============================================================================

export interface FilterPreviewResult {
  estimated_count: number;
  sample_cards: Array<{
    id: string;
    name: string;
    pillar_id?: string;
    horizon?: string;
  }>;
}

export async function fetchFilterPreview(
  token: string,
  filters: {
    pillar_ids: string[];
    goal_ids: string[];
    stage_ids: string[];
    horizon: string;
    keywords: string[];
  },
): Promise<FilterPreviewResult> {
  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const response = await fetch(`${API_BASE_URL}/api/v1/cards/filter-preview`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      pillar_ids: filters.pillar_ids,
      goal_ids: filters.goal_ids,
      stage_ids: filters.stage_ids,
      horizon: filters.horizon === "ALL" ? null : filters.horizon,
      keywords: filters.keywords,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to fetch filter preview");
  }

  return response.json();
}

// ============================================================================
// Workstream Templates
// ============================================================================

export interface WorkstreamTemplate {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  config: {
    name: string;
    description: string;
    pillar_ids: string[];
    goal_ids: string[];
    stage_ids: string[];
    horizon: string;
    keywords: string[];
  };
}

/**
 * Template color class mapping for consistent styling
 */
export function getTemplateColorClasses(color: string): {
  bg: string;
  border: string;
  text: string;
  hover: string;
} {
  const defaultColor = {
    bg: "bg-blue-50 dark:bg-blue-900/20",
    border: "border-blue-200 dark:border-blue-700",
    text: "text-blue-700 dark:text-blue-300",
    hover: "hover:bg-blue-100 dark:hover:bg-blue-900/40",
  };
  const colorMap: Record<
    string,
    { bg: string; border: string; text: string; hover: string }
  > = {
    purple: {
      bg: "bg-purple-50 dark:bg-purple-900/20",
      border: "border-purple-200 dark:border-purple-700",
      text: "text-purple-700 dark:text-purple-300",
      hover: "hover:bg-purple-100 dark:hover:bg-purple-900/40",
    },
    amber: {
      bg: "bg-amber-50 dark:bg-amber-900/20",
      border: "border-amber-200 dark:border-amber-700",
      text: "text-amber-700 dark:text-amber-300",
      hover: "hover:bg-amber-100 dark:hover:bg-amber-900/40",
    },
    green: {
      bg: "bg-green-50 dark:bg-green-900/20",
      border: "border-green-200 dark:border-green-700",
      text: "text-green-700 dark:text-green-300",
      hover: "hover:bg-green-100 dark:hover:bg-green-900/40",
    },
    red: {
      bg: "bg-red-50 dark:bg-red-900/20",
      border: "border-red-200 dark:border-red-700",
      text: "text-red-700 dark:text-red-300",
      hover: "hover:bg-red-100 dark:hover:bg-red-900/40",
    },
    indigo: {
      bg: "bg-indigo-50 dark:bg-indigo-900/20",
      border: "border-indigo-200 dark:border-indigo-700",
      text: "text-indigo-700 dark:text-indigo-300",
      hover: "hover:bg-indigo-100 dark:hover:bg-indigo-900/40",
    },
    blue: defaultColor,
  };
  return colorMap[color] ?? defaultColor;
}
