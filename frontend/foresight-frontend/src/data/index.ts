/**
 * Data Module Index
 *
 * Export all taxonomy data and helper functions
 */

export {
  // Types
  type Pillar,
  type Goal,
  type Anchor,
  type MaturityStage,
  type Horizon,
  type Top25Priority,
  type SteepCategory,
  type TriageScore,
  type GrantCategory,
  type GrantLifecycleStage,
  type DeadlineUrgency,
  type PipelineStatus,
  type Department,

  // Data
  pillars,
  goals,
  anchors,
  stages,
  horizons,
  top25Priorities,
  steepCategories,
  triageScores,
  grantCategories,
  grantLifecycleStages,
  deadlineUrgencyTiers,
  pipelineStatuses,

  // Lookup Maps
  pillarMap,
  goalMap,
  stageMap,
  horizonMap,
  anchorMap,
  grantCategoryMap,
  pipelineStatusMap,

  // Helper Functions
  getPillarByCode,
  getGoalByCode,
  getGoalsByPillar,
  getStageByNumber,
  getStagesByHorizon,
  getHorizonByCode,
  getAnchorByName,
  getTop25ByPillar,
  getTop25ByTitle,
  getSteepByCode,
  getTriageScore,
  getHorizonForStage,
  getGrantCategoryByCode,
  getDeadlineUrgency,
  getPipelineStatusById,
} from "./taxonomy";
