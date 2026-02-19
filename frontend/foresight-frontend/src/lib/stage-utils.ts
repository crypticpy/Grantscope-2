/**
 * Stage utility functions for parsing and manipulating stage identifiers.
 *
 * NOTE: parseStageNumber is deprecated for new code. Use pipeline_status instead.
 * Pipeline status utilities are also provided below.
 */

import {
  getPipelineStatusById,
  getPipelinePhase,
  pipelinePhases,
  type PipelinePhase,
} from "../data/taxonomy";

/**
 * Parse stage number from stage_id string.
 *
 * @deprecated Use pipeline_status instead of stage_id for new code.
 *
 * @param stageId - The stage ID string (e.g., "1_concept", "2_emerging")
 * @returns The numeric stage number, or null if invalid/missing
 *
 * @example
 * parseStageNumber("1_concept")   // returns 1
 * parseStageNumber("2_emerging")  // returns 2
 * parseStageNumber("10_mature")   // returns 10
 * parseStageNumber(null)          // returns null
 * parseStageNumber(undefined)     // returns null
 * parseStageNumber("")            // returns null
 * parseStageNumber("invalid")     // returns null
 */
export function parseStageNumber(
  stageId: string | null | undefined,
): number | null {
  if (!stageId) return null;
  const match = stageId.match(/^(\d+)/);
  return match?.[1] ? parseInt(match[1], 10) : null;
}

// ============================================================================
// Pipeline Status Utilities
// ============================================================================

/**
 * Get a human-readable label for a pipeline status ID.
 *
 * @param statusId - Pipeline status ID (e.g., "discovered", "evaluating")
 * @returns The status display name, or the raw ID if not found
 */
export function getPipelineStatusLabel(
  statusId: string | null | undefined,
): string {
  if (!statusId) return "Unknown";
  const status = getPipelineStatusById(statusId);
  return status?.name || statusId;
}

/**
 * Get the pipeline phase label for a given status ID.
 *
 * @param statusId - Pipeline status ID (e.g., "discovered", "evaluating")
 * @returns The phase label (e.g., "Pipeline", "Pursuing", "Active", "Archived")
 */
export function getPipelinePhaseLabel(
  statusId: string | null | undefined,
): string {
  if (!statusId) return "Pipeline";
  const phase = getPipelinePhase(statusId);
  return pipelinePhases[phase].label;
}

/**
 * Check if a pipeline status is in a specific phase.
 *
 * @param statusId - Pipeline status ID
 * @param phase - Pipeline phase to check against
 * @returns true if the status belongs to the given phase
 */
export function isInPipelinePhase(
  statusId: string | null | undefined,
  phase: PipelinePhase,
): boolean {
  if (!statusId) return phase === "pipeline";
  return getPipelinePhase(statusId) === phase;
}
