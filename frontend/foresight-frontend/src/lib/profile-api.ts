/**
 * Profile API client — user profile CRUD and reference data endpoints.
 */

import { API_BASE_URL } from "./config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ProfileData {
  id?: string;
  email?: string;
  display_name?: string;
  department?: string;
  department_id?: string;
  title?: string;
  bio?: string;
  program_name?: string;
  program_mission?: string;
  team_size?: string;
  budget_range?: string;
  grant_experience?: string;
  grant_categories?: string[];
  funding_range_min?: number;
  funding_range_max?: number;
  strategic_pillars?: string[];
  priorities?: string[];
  custom_priorities?: string;
  help_wanted?: string[];
  update_frequency?: string;
  profile_completed_at?: string | null;
  profile_step?: number;
}

export interface ProfileCompletion {
  percentage: number;
  completed_steps: number[];
  missing: string[];
  is_complete: boolean;
}

export interface DepartmentRef {
  id: string;
  name: string;
  abbreviation: string;
  category_ids: string[];
}

export interface PillarRef {
  id: string;
  name: string;
  description: string;
  code: string;
  color: string;
}

export interface GrantCategoryRef {
  id: string;
  name: string;
  description: string;
  color: string;
  icon: string;
}

export interface PriorityRef {
  id: string;
  name: string;
  description: string;
  category: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiRequest<T>(
  endpoint: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(
      error.detail || error.message || `Request failed (${res.status})`,
    );
  }

  if (res.status === 204) return {} as T;
  return res.json();
}

async function publicRequest<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${endpoint}`);
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Profile endpoints
// ---------------------------------------------------------------------------

export async function getProfile(token: string): Promise<ProfileData> {
  return apiRequest<ProfileData>("/api/v1/me", token);
}

export async function updateProfile(
  token: string,
  data: Partial<ProfileData>,
): Promise<ProfileData> {
  return apiRequest<ProfileData>("/api/v1/me", token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getProfileCompletion(
  token: string,
): Promise<ProfileCompletion> {
  return apiRequest<ProfileCompletion>("/api/v1/me/profile-completion", token);
}

// ---------------------------------------------------------------------------
// Reference data endpoints (no auth required)
// ---------------------------------------------------------------------------

export async function getDepartments(): Promise<DepartmentRef[]> {
  return publicRequest<DepartmentRef[]>("/api/v1/reference/departments");
}

export async function getPillarsRef(): Promise<PillarRef[]> {
  return publicRequest<PillarRef[]>("/api/v1/reference/pillars");
}

export async function getGrantCategoriesRef(): Promise<GrantCategoryRef[]> {
  return publicRequest<GrantCategoryRef[]>(
    "/api/v1/reference/grant-categories",
  );
}

export async function getPrioritiesRef(): Promise<PriorityRef[]> {
  return publicRequest<PriorityRef[]>("/api/v1/reference/priorities");
}
