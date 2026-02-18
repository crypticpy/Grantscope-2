/**
 * Wizard API Client
 *
 * API functions for the Grant Application Wizard.
 * Handles session management, grant processing, plan synthesis,
 * proposal generation, and PDF export.
 */

import { API_BASE_URL } from "./config";

// ============================================================================
// Types
// ============================================================================

/**
 * A single grant requirement extracted from a grant document.
 */
export interface GrantRequirement {
  category: string;
  description: string;
  is_mandatory: boolean;
}

/**
 * A key date associated with a grant.
 */
export interface KeyDate {
  date: string;
  description: string;
}

/**
 * Full grant context extracted from a grant URL or uploaded file.
 */
export interface GrantContext {
  grant_name: string | null;
  grantor: string | null;
  cfda_number: string | null;
  deadline: string | null;
  funding_amount_min: number | null;
  funding_amount_max: number | null;
  grant_type: string | null;
  eligibility_text: string | null;
  match_requirement: string | null;
  requirements: GrantRequirement[];
  key_dates: KeyDate[];
  evaluation_criteria: string | null;
  contact_info: string | null;
  summary: string | null;
}

/**
 * A staffing entry in the plan.
 */
export interface StaffingEntry {
  role: string;
  fte: number;
  salary_estimate: number;
  responsibilities: string;
}

/**
 * A budget line item in the plan.
 */
export interface BudgetEntry {
  category: string;
  amount: number;
  justification: string;
}

/**
 * A timeline phase in the plan.
 */
export interface TimelinePhase {
  phase: string;
  start: string;
  end: string;
  milestones: string[];
}

/**
 * A metric entry for evaluation.
 */
export interface MetricEntry {
  metric: string;
  target: string;
  measurement_method: string;
}

/**
 * Full plan data synthesized from interview responses.
 */
export interface PlanData {
  program_overview: string | null;
  staffing_plan: StaffingEntry[];
  budget: BudgetEntry[];
  timeline: TimelinePhase[];
  deliverables: string[];
  metrics: MetricEntry[];
  partnerships: string[];
}

/**
 * Valid wizard session status values.
 */
export type WizardStatus = "in_progress" | "completed" | "abandoned";

/**
 * Valid wizard entry path values.
 */
export type EntryPath = "have_grant" | "find_grant" | "build_program";

/**
 * AI-generated program summary from interview conversation.
 */
export interface ProgramSummary {
  program_name: string;
  department: string;
  problem_statement: string;
  program_description: string;
  target_population: string;
  key_needs: string[];
  estimated_budget: string;
  team_overview: string;
  timeline_overview: string;
  strategic_alignment: string;
}

/**
 * A wizard session record.
 */
export interface WizardSession {
  id: string;
  user_id: string;
  conversation_id: string | null;
  proposal_id: string | null;
  card_id: string | null;
  entry_path: EntryPath;
  current_step: number;
  status: WizardStatus;
  grant_context: GrantContext | null;
  interview_data: Record<string, unknown> | null;
  plan_data: PlanData | null;
  program_summary: ProgramSummary | null;
  profile_context: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
}

/**
 * Response from the process-grant endpoint.
 */
export interface ProcessGrantResponse {
  grant_context: GrantContext;
  card_id: string | null;
}

/**
 * Request payload for updating a wizard session.
 */
export interface WizardSessionUpdateRequest {
  current_step?: number;
  grant_context?: Partial<GrantContext>;
  interview_data?: Record<string, unknown>;
  plan_data?: Partial<PlanData>;
  status?: WizardStatus;
}

/**
 * A matched grant returned from the grant matching endpoint.
 */
export interface MatchedGrant {
  card_id: string;
  grant_name: string;
  grantor: string;
  summary: string;
  deadline: string | null;
  funding_amount_min: number | null;
  funding_amount_max: number | null;
  grant_type: string | null;
  similarity: number;
}

/**
 * Response from the match-grants endpoint.
 */
export interface MatchGrantsResponse {
  grants: MatchedGrant[];
  query_used: string;
}

/**
 * Valid export format types.
 */
export type ExportFormat = "pdf" | "docx";

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Generic API request helper with authentication and error handling.
 * Follows the established pattern from proposal-api.ts.
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

/**
 * API request helper for FormData uploads (no Content-Type header).
 * The browser auto-sets the multipart boundary when Content-Type is omitted.
 */
async function apiRequestFormData<T>(
  endpoint: string,
  token: string,
  formData: FormData,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ message: "Request failed" }));
    throw new Error(
      error.message || error.detail || `API error: ${response.status}`,
    );
  }

  return response.json();
}

/**
 * API request helper for blob responses (e.g. PDF export).
 */
async function apiRequestBlob(endpoint: string, token: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: {
      Authorization: `Bearer ${token}`,
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

  return response.blob();
}

// ============================================================================
// API Functions
// ============================================================================

const BASE = "/api/v1/me/wizard/sessions";

/**
 * Creates a new wizard session.
 *
 * @param token - Bearer authentication token
 * @param entryPath - How the user is entering the wizard
 * @returns The newly created wizard session
 */
export async function createWizardSession(
  token: string,
  entryPath: EntryPath,
  cardId?: string,
): Promise<WizardSession> {
  const payload: Record<string, string> = { entry_path: entryPath };
  if (cardId) payload.card_id = cardId;
  return apiRequest<WizardSession>(BASE, token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Lists all wizard sessions for the current user.
 *
 * @param token - Bearer authentication token
 * @returns Array of wizard sessions
 */
export async function listWizardSessions(
  token: string,
): Promise<WizardSession[]> {
  return apiRequest<WizardSession[]>(BASE, token);
}

/**
 * Fetches a single wizard session by ID.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @returns The wizard session with all data
 */
export async function getWizardSession(
  token: string,
  sessionId: string,
): Promise<WizardSession> {
  return apiRequest<WizardSession>(`${BASE}/${sessionId}`, token);
}

/**
 * Updates an existing wizard session.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @param data - Fields to update
 * @returns The updated wizard session
 */
export async function updateWizardSession(
  token: string,
  sessionId: string,
  data: WizardSessionUpdateRequest,
): Promise<WizardSession> {
  return apiRequest<WizardSession>(`${BASE}/${sessionId}`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/**
 * Processes a grant from a URL. Extracts grant context using AI.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @param url - URL of the grant opportunity page
 * @returns Extracted grant context and optional card ID
 */
export async function processGrantUrl(
  token: string,
  sessionId: string,
  url: string,
): Promise<ProcessGrantResponse> {
  const formData = new FormData();
  formData.append("url", url);

  return apiRequestFormData<ProcessGrantResponse>(
    `${BASE}/${sessionId}/process-grant`,
    token,
    formData,
  );
}

/**
 * Processes a grant from an uploaded file. Extracts grant context using AI.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @param file - Uploaded grant document file
 * @returns Extracted grant context and optional card ID
 */
export async function processGrantFile(
  token: string,
  sessionId: string,
  file: File,
): Promise<ProcessGrantResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return apiRequestFormData<ProcessGrantResponse>(
    `${BASE}/${sessionId}/process-grant`,
    token,
    formData,
  );
}

/**
 * Synthesizes a plan from the interview data in the session.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @returns The synthesized plan data
 */
export async function synthesizePlan(
  token: string,
  sessionId: string,
): Promise<PlanData> {
  return apiRequest<PlanData>(`${BASE}/${sessionId}/synthesize-plan`, token, {
    method: "POST",
  });
}

/**
 * Generates a full proposal from the session data.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @returns The updated wizard session with proposal ID
 */
export async function generateWizardProposal(
  token: string,
  sessionId: string,
): Promise<WizardSession> {
  return apiRequest<WizardSession>(
    `${BASE}/${sessionId}/generate-proposal`,
    token,
    {
      method: "POST",
    },
  );
}

/**
 * Exports the wizard session proposal as a PDF.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @returns PDF file as a Blob
 */
export async function exportWizardPdf(
  token: string,
  sessionId: string,
): Promise<Blob> {
  return apiRequestBlob(`${BASE}/${sessionId}/export/pdf`, token);
}

/**
 * Synthesizes a program summary from the interview conversation.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @returns The synthesized program summary
 */
export async function synthesizeProgramSummary(
  token: string,
  sessionId: string,
): Promise<ProgramSummary> {
  return apiRequest<ProgramSummary>(
    `${BASE}/${sessionId}/synthesize-summary`,
    token,
    { method: "POST" },
  );
}

/**
 * Finds matching grants based on program description and profile.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @returns Matched grants and the search query used
 */
export async function matchGrants(
  token: string,
  sessionId: string,
): Promise<MatchGrantsResponse> {
  return apiRequest<MatchGrantsResponse>(
    `${BASE}/${sessionId}/match-grants`,
    token,
    { method: "POST" },
  );
}

/**
 * Attaches a grant (card) to a wizard session.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @param cardId - Card UUID to attach
 * @returns The updated wizard session
 */
export async function attachGrant(
  token: string,
  sessionId: string,
  cardId: string,
): Promise<WizardSession> {
  return apiRequest<WizardSession>(`${BASE}/${sessionId}/attach-grant`, token, {
    method: "POST",
    body: JSON.stringify({ card_id: cardId }),
  });
}

/**
 * Exports the program summary as PDF or DOCX.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @param format - Export format (pdf or docx)
 * @returns File as a Blob
 */
export async function exportWizardSummary(
  token: string,
  sessionId: string,
  format: ExportFormat = "pdf",
): Promise<Blob> {
  return apiRequestBlob(`${BASE}/${sessionId}/export/summary/${format}`, token);
}

/**
 * Exports the project plan as PDF or DOCX.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @param format - Export format (pdf or docx)
 * @returns File as a Blob
 */
export async function exportWizardPlan(
  token: string,
  sessionId: string,
  format: ExportFormat = "pdf",
): Promise<Blob> {
  return apiRequestBlob(`${BASE}/${sessionId}/export/plan/${format}`, token);
}

/**
 * Exports the proposal as PDF or DOCX.
 *
 * @param token - Bearer authentication token
 * @param sessionId - Wizard session UUID
 * @param format - Export format (pdf or docx)
 * @returns File as a Blob
 */
export async function exportWizardProposal(
  token: string,
  sessionId: string,
  format: ExportFormat = "pdf",
): Promise<Blob> {
  return apiRequestBlob(
    `${BASE}/${sessionId}/export/proposal/${format}`,
    token,
  );
}
