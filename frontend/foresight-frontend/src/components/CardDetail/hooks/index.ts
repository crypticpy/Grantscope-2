/**
 * CardDetail Custom Hooks
 *
 * This module exports custom hooks for managing CardDetail component state
 * and operations. These hooks encapsulate complex logic for data loading,
 * research task management, and card export functionality.
 *
 * @module CardDetail/hooks
 *
 * @example
 * ```tsx
 * import {
 *   useCardData,
 *   useResearch,
 *   useCardExport,
 * } from '@/components/CardDetail/hooks';
 *
 * function MyComponent() {
 *   const { card, sources, loading } = useCardData(slug, user);
 *   const { triggerResearch, isResearching } = useResearch(card, getAuthToken);
 *   const { exportCard, isExporting } = useCardExport(card, getAuthToken);
 *
 *   // ...
 * }
 * ```
 */

// =============================================================================
// useCardData Hook
// =============================================================================

/**
 * Hook for loading and managing card-related data.
 * Handles card details, sources, timeline, notes, research history,
 * score/stage history, and related cards.
 */
export { useCardData } from './useCardData';
export { default as useCardDataDefault } from './useCardData';
export type { UseCardDataReturn } from './useCardData';

// =============================================================================
// useResearch Hook
// =============================================================================

/**
 * Hook for managing research task operations.
 * Handles triggering research tasks, polling for status,
 * and managing research UI state.
 */
export { useResearch } from './useResearch';
export { default as useResearchDefault } from './useResearch';
export type { UseResearchReturn, ResearchTaskType } from './useResearch';

// =============================================================================
// useCardExport Hook
// =============================================================================

/**
 * Hook for managing card export functionality.
 * Handles exporting cards in various formats (PDF, PPTX, CSV)
 * with loading states and error handling.
 */
export { useCardExport } from './useCardExport';
export { default as useCardExportDefault } from './useCardExport';
export type {
  UseCardExportReturn,
  ExportFormat,
  ExportOptions,
} from './useCardExport';
