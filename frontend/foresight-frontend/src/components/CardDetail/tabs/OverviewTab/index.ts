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

// Future exports (as components are created):
// export { ImpactMetricsPanel } from './ImpactMetricsPanel';
// export type { ImpactMetricsPanelProps } from './ImpactMetricsPanel';
// export { MaturityScorePanel } from './MaturityScorePanel';
// export type { MaturityScorePanelProps } from './MaturityScorePanel';
// export { ActivityStatsPanel } from './ActivityStatsPanel';
// export type { ActivityStatsPanelProps } from './ActivityStatsPanel';
