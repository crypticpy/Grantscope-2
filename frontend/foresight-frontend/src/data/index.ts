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

  // Data
  pillars,
  goals,
  anchors,
  stages,
  horizons,
  top25Priorities,
  steepCategories,
  triageScores,

  // Lookup Maps
  pillarMap,
  goalMap,
  stageMap,
  horizonMap,
  anchorMap,

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
} from './taxonomy';
