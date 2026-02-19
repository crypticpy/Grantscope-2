/**
 * OverviewTab Component
 *
 * Main container component for the Overview tab in CardDetail.
 * Composes all Overview sub-components into a responsive 2-column grid layout:
 * - Main column (2/3): Description, Classification, Score Timeline, Research History
 * - Sidebar (1/3): Impact Metrics, Maturity Score, Activity Stats, Key Entities
 *
 * @module CardDetail/tabs/OverviewTab
 */

import React from "react";

// Sub-components
import { CardDescription } from "./CardDescription";
import { CardClassification } from "./CardClassification";
import { DeepResearchPanel } from "./DeepResearchPanel";
import { ResearchHistoryPanel } from "./ResearchHistoryPanel";
import { GrantDetailsPanel } from "./GrantDetailsPanel";
import { ImpactMetricsPanel } from "./ImpactMetricsPanel";
import { MaturityScorePanel } from "./MaturityScorePanel";
import { ActivityStatsPanel } from "./ActivityStatsPanel";
import { KeyEntitiesPanel } from "./KeyEntitiesPanel";

// Visualization Components
import { ScoreTimelineChart } from "../../../visualizations/ScoreTimelineChart";

// Types
import type { Card, ResearchTask } from "../../types";
import type { ScoreHistory, StageHistory } from "../../../../lib/discovery-api";

/**
 * Props for the OverviewTab component
 */
export interface OverviewTabProps {
  /**
   * The card data to display
   */
  card: Card;

  /**
   * Number of sources associated with the card
   */
  sourcesCount: number;

  /**
   * Number of timeline events for the card
   */
  timelineCount: number;

  /**
   * Number of notes attached to the card
   */
  notesCount: number;

  /**
   * Score history data for timeline chart and velocity sparkline
   */
  scoreHistory: ScoreHistory[];

  /**
   * Whether score history is currently loading
   */
  scoreHistoryLoading: boolean;

  /**
   * Error message if score history failed to load
   */
  scoreHistoryError: string | null;

  /**
   * Callback to retry loading score history
   */
  onRetryScoreHistory: () => void;

  /**
   * Stage history data for the stage progression timeline
   */
  stageHistory: StageHistory[];

  /**
   * Whether stage history is currently loading
   */
  stageHistoryLoading: boolean;

  /**
   * Array of completed research tasks for the research history panel
   */
  researchHistory: ResearchTask[];

  /**
   * Callback to trigger new deep research
   */
  onRequestDeepResearch?: () => void;

  /**
   * Whether new deep research can be requested (rate limit)
   */
  canRequestDeepResearch?: boolean;

  /**
   * Callback when card data should be refreshed (e.g., after restoring a description)
   */
  onRefreshCard?: () => void;

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;
}

/**
 * OverviewTab displays the complete Overview content for a card.
 *
 * The component organizes sub-components into a responsive 2-column grid:
 *
 * **Main Column (lg:col-span-2):**
 * - CardDescription: Full description text
 * - CardClassification: Pillar, Goal, Anchor, Stage, Horizon, Top25
 * - ScoreTimelineChart: Historical score visualization
 * - ResearchHistoryPanel: Expandable research reports
 *
 * **Sidebar Column:**
 * - ImpactMetricsPanel: All 6 impact scores with tooltips
 * - MaturityScorePanel: Circular maturity score display
 * - ActivityStatsPanel: Sources, events, notes counts with timestamps
 * - KeyEntitiesPanel: Extracted entities grouped by type with color-coded chips
 *
 * Features:
 * - Responsive grid layout (single column on mobile, 3-column on lg+)
 * - Consistent spacing between components
 * - All sub-components support dark mode
 * - Loading and error states for async data
 *
 * @example
 * ```tsx
 * <OverviewTab
 *   card={card}
 *   sourcesCount={sources.length}
 *   timelineCount={timeline.length}
 *   notesCount={notes.length}
 *   scoreHistory={scoreHistory}
 *   scoreHistoryLoading={scoreHistoryLoading}
 *   scoreHistoryError={scoreHistoryError}
 *   onRetryScoreHistory={loadScoreHistory}
 *   stageHistory={stageHistory}
 *   stageHistoryLoading={stageHistoryLoading}
 *   researchHistory={researchHistory}
 * />
 * ```
 */
export const OverviewTab: React.FC<OverviewTabProps> = ({
  card,
  sourcesCount,
  timelineCount,
  notesCount,
  scoreHistory,
  scoreHistoryLoading,
  scoreHistoryError,
  onRetryScoreHistory,
  stageHistory: _stageHistory,
  stageHistoryLoading: _stageHistoryLoading,
  researchHistory,
  onRequestDeepResearch,
  canRequestDeepResearch,
  onRefreshCard,
  className = "",
}) => {
  // Filter deep research tasks for the prominent panel
  const deepResearchTasks = researchHistory.filter(
    (task) => task.task_type === "deep_research" && task.status === "completed",
  );

  return (
    <div
      className={`grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 lg:gap-8 ${className}`}
    >
      {/* Main Content Column */}
      <div className="lg:col-span-2 space-y-4 sm:space-y-6">
        {/* Deep Research Panel - Prominent placement when reports exist */}
        <DeepResearchPanel
          researchTasks={researchHistory}
          onRequestResearch={onRequestDeepResearch}
          canRequestResearch={canRequestDeepResearch}
        />

        {/* Description Panel */}
        <CardDescription
          description={card.description}
          cardId={card.id}
          onRestore={onRefreshCard}
        />

        {/* Classification Section */}
        <CardClassification card={card} />

        {/* Score Timeline Chart */}
        <ScoreTimelineChart
          data={scoreHistory}
          title="Score History"
          height={350}
          loading={scoreHistoryLoading}
          error={scoreHistoryError}
          onRetry={onRetryScoreHistory}
        />

        {/* Research History Panel - Shows all research including updates */}
        {researchHistory.length > deepResearchTasks.length && (
          <ResearchHistoryPanel
            researchHistory={researchHistory.filter(
              (t) => t.task_type !== "deep_research",
            )}
            title="Update History"
          />
        )}
      </div>

      {/* Sidebar Column */}
      <div className="space-y-4 sm:space-y-6">
        {/* Grant Details Panel */}
        <GrantDetailsPanel card={card} />

        {/* Impact Metrics Panel */}
        <ImpactMetricsPanel
          impactScore={card.impact_score}
          relevanceScore={card.relevance_score}
          velocityScore={card.velocity_score}
          noveltyScore={card.novelty_score}
          opportunityScore={card.opportunity_score}
          riskScore={card.risk_score}
        />

        {/* Maturity Score Panel */}
        <MaturityScorePanel
          maturityScore={card.maturity_score}
          pipelineStatus={card.pipeline_status ?? undefined}
        />

        {/* Activity Stats Panel */}
        <ActivityStatsPanel
          sourcesCount={sourcesCount}
          timelineCount={timelineCount}
          notesCount={notesCount}
          scoreHistory={scoreHistory}
          scoreHistoryLoading={scoreHistoryLoading}
          createdAt={card.created_at}
          updatedAt={card.updated_at}
          deepResearchAt={card.deep_research_at}
        />

        {/* Key Entities Panel */}
        <KeyEntitiesPanel cardId={card.id} />
      </div>
    </div>
  );
};

export default OverviewTab;

// Re-export all sub-components and their types for individual use
export { CardDescription } from "./CardDescription";
export type { CardDescriptionProps } from "./CardDescription";

export { CardClassification } from "./CardClassification";
export type { CardClassificationProps } from "./CardClassification";

export { DeepResearchPanel } from "./DeepResearchPanel";
export type { DeepResearchPanelProps } from "./DeepResearchPanel";

export { ResearchHistoryPanel } from "./ResearchHistoryPanel";
export type { ResearchHistoryPanelProps } from "./ResearchHistoryPanel";

export { GrantDetailsPanel } from "./GrantDetailsPanel";
export type { GrantDetailsPanelProps } from "./GrantDetailsPanel";

export { ImpactMetricsPanel } from "./ImpactMetricsPanel";
export type { ImpactMetricsPanelProps } from "./ImpactMetricsPanel";

export { MaturityScorePanel } from "./MaturityScorePanel";
export type { MaturityScorePanelProps } from "./MaturityScorePanel";

export { ActivityStatsPanel } from "./ActivityStatsPanel";
export type { ActivityStatsPanelProps } from "./ActivityStatsPanel";

export { KeyEntitiesPanel } from "./KeyEntitiesPanel";
export type { KeyEntitiesPanelProps } from "./KeyEntitiesPanel";
