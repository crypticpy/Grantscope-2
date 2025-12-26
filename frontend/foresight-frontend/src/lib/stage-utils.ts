/**
 * Stage utility functions for parsing and manipulating stage identifiers.
 */

/**
 * Parse stage number from stage_id string.
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
export function parseStageNumber(stageId: string | null | undefined): number | null {
  if (!stageId) return null;
  const match = stageId.match(/^(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}
