/**
 * OverviewTab Components
 *
 * Components for the Overview tab in CardDetail.
 * Each component handles a specific section of the overview display.
 *
 * @module CardDetail/tabs/OverviewTab
 */

// Description panel
export { CardDescription } from './CardDescription';
export type { CardDescriptionProps } from './CardDescription';

// Classification section
export { CardClassification } from './CardClassification';
export type { CardClassificationProps } from './CardClassification';

// Research history with expandable reports
export { ResearchHistoryPanel } from './ResearchHistoryPanel';
export type { ResearchHistoryPanelProps } from './ResearchHistoryPanel';

// Impact metrics panel
export { ImpactMetricsPanel } from './ImpactMetricsPanel';
export type { ImpactMetricsPanelProps } from './ImpactMetricsPanel';

// Maturity score with circular display and stage badge
export { MaturityScorePanel } from './MaturityScorePanel';
export type { MaturityScorePanelProps } from './MaturityScorePanel';

// Activity stats panel with sources, events, notes, velocity trend, and timestamps
export { ActivityStatsPanel } from './ActivityStatsPanel';
export type { ActivityStatsPanelProps } from './ActivityStatsPanel';
