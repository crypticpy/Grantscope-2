/**
 * CardDetail Components
 *
 * A modular component library for displaying and managing card details.
 * This directory contains the refactored CardDetail component split into
 * smaller, focused components following the Single Responsibility Principle.
 *
 * @module CardDetail
 *
 * Directory Structure:
 * - CardDetailHeader.tsx - Header with title, badges, and summary
 * - CardActionButtons.tsx - Action buttons (Compare, Update, Deep Research, Export, Follow)
 * - ExportDropdown.tsx - Export format dropdown menu (PDF, PPTX, CSV)
 * - types.ts - Shared TypeScript interfaces (Card, ResearchTask, Source, etc.)
 * - utils.ts - Utility functions and constants
 * - tabs/ - Individual tab content components (Overview, Sources, Timeline, Notes)
 *
 * @example
 * ```tsx
 * import {
 *   CardDetailHeader,
 *   CardActionButtons,
 *   OverviewTab,
 *   SourcesTab,
 *   TimelineTab,
 *   NotesTab,
 *   type Card,
 *   type CardDetailTab
 * } from '@/components/CardDetail';
 * ```
 */

// =============================================================================
// Main Component Export
// =============================================================================

/**
 * Main CardDetail component that orchestrates all sub-components.
 * This is the primary component for displaying card/trend details.
 */
export { CardDetail } from './CardDetail';
export type { CardDetailProps } from './CardDetail';

// =============================================================================
// Component Exports
// =============================================================================

/**
 * Header component with title, badges, summary, and back navigation
 */
export { CardDetailHeader } from './CardDetailHeader';
export type { CardDetailHeaderProps } from './CardDetailHeader';

/**
 * Action buttons for card interactions (Compare, Update, Deep Research, Export, Follow)
 */
export { CardActionButtons } from './CardActionButtons';
export type { CardActionButtonsProps } from './CardActionButtons';

/**
 * Export dropdown menu for downloading card in various formats
 */
export { ExportDropdown } from './ExportDropdown';
export type { ExportDropdownProps, ExportFormat } from './ExportDropdown';

/**
 * Research status banner for showing in-progress, completed, or error states
 */
export { ResearchStatusBanner } from './ResearchStatusBanner';
export type { ResearchStatusBannerProps } from './ResearchStatusBanner';

/**
 * Tab navigation component for switching between card detail sections
 */
export { CardDetailTabs, DEFAULT_TABS } from './CardDetailTabs';
export type { CardDetailTabsProps, TabDefinition } from './CardDetailTabs';

// =============================================================================
// Tab Component Exports
// =============================================================================

/**
 * Tab content components for different card detail sections.
 * Includes: OverviewTab components, SourcesTab, TimelineTab, NotesTab
 */
export * from './tabs';

// =============================================================================
// Type Exports
// =============================================================================

/**
 * Shared TypeScript interfaces and types.
 * Includes: Card, ResearchTask, Source, TimelineEvent, Note, CardDetailTab,
 *           ScoreColorClasses, MetricDefinition, MetricKey
 */
export * from './types';

// =============================================================================
// Utility Exports
// =============================================================================

/**
 * Utility functions and constants for CardDetail components.
 */
export {
  /** Backend API base URL */
  API_BASE_URL,
  /** Metric definitions with labels and descriptions for tooltips */
  metricDefinitions,
  /** Parse stage number from stage_id string (e.g., "1_concept" -> 1) */
  parseStageNumber,
  /** Get WCAG-compliant color classes based on score value */
  getScoreColorClasses,
  /** Format date string as relative time (e.g., "2h ago") */
  formatRelativeTime,
} from './utils';

// =============================================================================
// Custom Hooks Exports
// =============================================================================

/**
 * Custom hooks for CardDetail state management.
 * Includes: useCardData (data loading), useResearch (research tasks),
 *           useCardExport (export functionality)
 */
export {
  useCardData,
  useResearch,
  useCardExport,
  type UseCardDataReturn,
  type UseResearchReturn,
  type UseCardExportReturn,
  type ResearchTaskType,
  type ExportFormat,
  type ExportOptions,
} from './hooks';
