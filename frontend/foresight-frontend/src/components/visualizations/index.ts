/**
 * Visualization Components
 *
 * Export all trend visualization components from a single entry point.
 */

// Score Timeline - Line chart showing score evolution over time
export {
  ScoreTimelineChart,
  SCORE_CONFIGS,
  getScoreConfig,
  type ScoreTimelineChartProps,
  type ScoreType,
} from './ScoreTimelineChart';

// Trend Velocity Sparkline - Compact velocity trend visualization
export {
  TrendVelocitySparkline,
  TrendVelocitySparklineCompact,
  TrendVelocitySparklineSkeleton,
  type TrendVelocitySparklineProps,
} from './TrendVelocitySparkline';

// Stage Progression Timeline - Visual stage transition history
export {
  StageProgressionTimeline,
  type StageProgressionTimelineProps,
} from './StageProgressionTimeline';
