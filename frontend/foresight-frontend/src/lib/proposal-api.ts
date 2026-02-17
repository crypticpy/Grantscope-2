/**
 * Proposal API Client
 *
 * API functions for managing grant proposal drafts.
 * Handles CRUD operations and AI-assisted section generation.
 */

import { API_BASE_URL } from "./config";

// ============================================================================
// Types
// ============================================================================

/**
 * A single section of a proposal.
 */
export interface ProposalSection {
  /** User-edited content */
  content: string;
  /** AI-generated draft content (pending acceptance) */
  ai_draft: string | null;
  /** ISO timestamp of last edit */
  last_edited: string | null;
}

/**
 * Valid proposal status values.
 */
export type ProposalStatus =
  | "draft"
  | "in_review"
  | "final"
  | "submitted"
  | "archived";

/**
 * The six standard proposal sections.
 */
export type SectionName =
  | "executive_summary"
  | "needs_statement"
  | "project_description"
  | "budget_narrative"
  | "timeline"
  | "evaluation_plan";

/**
 * Sections map keyed by section name.
 */
export type ProposalSections = Record<SectionName, ProposalSection>;

/**
 * A grant proposal draft.
 */
export interface Proposal {
  id: string;
  card_id: string;
  workstream_id: string;
  user_id: string;
  application_id: string | null;
  title: string;
  version: number;
  status: ProposalStatus;
  sections: Partial<ProposalSections>;
  ai_model: string | null;
  ai_generation_metadata: Record<string, unknown>;
  reviewer_id: string | null;
  review_notes: string | null;
  reviewed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/**
 * Request payload to create a new proposal.
 */
export interface ProposalCreateRequest {
  card_id: string;
  workstream_id: string;
  title?: string;
}

/**
 * Request payload to update an existing proposal.
 */
export interface ProposalUpdateRequest {
  title?: string;
  status?: ProposalStatus;
  sections?: Partial<ProposalSections>;
  review_notes?: string;
}

/**
 * Response from the list proposals endpoint.
 */
export interface ProposalListResponse {
  proposals: Proposal[];
  total: number;
}

/**
 * Response from AI section generation.
 */
export interface GenerateSectionResponse {
  section_name: string;
  ai_draft: string;
  model_used: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Generic API request helper with authentication and error handling.
 * Follows the established pattern from workstream-api.ts.
 */
async function apiRequest<T>(
  endpoint: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ message: "Request failed" }));
    throw new Error(
      error.message || error.detail || `API error: ${response.status}`,
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Lists all proposals for the current user.
 *
 * @param token - Bearer authentication token
 * @returns List of proposals with total count
 */
export async function listProposals(
  token: string,
): Promise<ProposalListResponse> {
  return apiRequest<ProposalListResponse>("/api/v1/me/proposals", token);
}

/**
 * Creates a new proposal draft.
 *
 * @param token - Bearer authentication token
 * @param data - Proposal creation data (card_id, workstream_id, title)
 * @returns The newly created proposal
 */
export async function createProposal(
  token: string,
  data: ProposalCreateRequest,
): Promise<Proposal> {
  return apiRequest<Proposal>("/api/v1/me/proposals", token, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Fetches a single proposal by ID.
 *
 * @param token - Bearer authentication token
 * @param id - Proposal UUID
 * @returns The proposal with all sections
 */
export async function getProposal(
  token: string,
  id: string,
): Promise<Proposal> {
  return apiRequest<Proposal>(`/api/v1/me/proposals/${id}`, token);
}

/**
 * Updates an existing proposal.
 *
 * @param token - Bearer authentication token
 * @param id - Proposal UUID
 * @param data - Fields to update (title, status, sections, review_notes)
 * @returns The updated proposal
 */
export async function updateProposal(
  token: string,
  id: string,
  data: ProposalUpdateRequest,
): Promise<Proposal> {
  return apiRequest<Proposal>(`/api/v1/me/proposals/${id}`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/**
 * Deletes a proposal.
 *
 * @param token - Bearer authentication token
 * @param id - Proposal UUID
 */
export async function deleteProposal(token: string, id: string): Promise<void> {
  return apiRequest<void>(`/api/v1/me/proposals/${id}`, token, {
    method: "DELETE",
  });
}

/**
 * Generates a single proposal section using AI.
 *
 * @param token - Bearer authentication token
 * @param id - Proposal UUID
 * @param sectionName - Name of the section to generate
 * @param additionalContext - Optional extra context for the AI
 * @returns The generated section draft
 */
export async function generateSection(
  token: string,
  id: string,
  sectionName: string,
  additionalContext?: string,
): Promise<GenerateSectionResponse> {
  const body: Record<string, unknown> = { section_name: sectionName };
  if (additionalContext) {
    body.additional_context = additionalContext;
  }

  return apiRequest<GenerateSectionResponse>(
    `/api/v1/me/proposals/${id}/generate-section`,
    token,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

/**
 * Generates all proposal sections using AI.
 *
 * @param token - Bearer authentication token
 * @param id - Proposal UUID
 * @returns The updated proposal with all AI drafts
 */
export async function generateAllSections(
  token: string,
  id: string,
): Promise<Proposal> {
  return apiRequest<Proposal>(
    `/api/v1/me/proposals/${id}/generate-all`,
    token,
    {
      method: "POST",
    },
  );
}
