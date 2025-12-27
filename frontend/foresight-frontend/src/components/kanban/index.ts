/**
 * Kanban Components
 *
 * A complete kanban board implementation for workstream card management.
 * Uses @dnd-kit for accessible drag-and-drop functionality.
 *
 * @example
 * ```tsx
 * import {
 *   KanbanBoard,
 *   type KanbanStatus,
 *   type WorkstreamCard,
 * } from '@/components/kanban';
 *
 * function WorkstreamView({ workstreamId }: { workstreamId: string }) {
 *   const [cards, setCards] = useState<Record<KanbanStatus, WorkstreamCard[]>>({
 *     inbox: [],
 *     screening: [],
 *     research: [],
 *     brief: [],
 *     watching: [],
 *     archived: [],
 *   });
 *
 *   const handleCardMove = async (
 *     cardId: string,
 *     newStatus: KanbanStatus,
 *     newPosition: number
 *   ) => {
 *     // Update local state optimistically
 *     // Then sync with backend
 *     await api.updateWorkstreamCard(workstreamId, cardId, {
 *       status: newStatus,
 *       position: newPosition,
 *     });
 *   };
 *
 *   return (
 *     <KanbanBoard
 *       cards={cards}
 *       onCardMove={handleCardMove}
 *       onCardClick={(card) => navigate(`/cards/${card.card.slug}`)}
 *     />
 *   );
 * }
 * ```
 */

// =============================================================================
// Components
// =============================================================================

export { KanbanBoard } from './KanbanBoard';
export { KanbanColumn } from './KanbanColumn';
export { KanbanCard } from './KanbanCard';
export { CardActions } from './CardActions';
export { KanbanErrorBoundary } from './KanbanErrorBoundary';

// =============================================================================
// Types
// =============================================================================

export type {
  // Status types
  KanbanStatus,
  AddedFrom,
  // Data types
  EmbeddedCard,
  WorkstreamCard,
  // Column types
  KanbanColumn as KanbanColumnType,
  KanbanColumnDefinition,
  // Callback types
  OnCardMoveCallback,
  OnCardClickCallback,
  OnNotesUpdateCallback,
  OnDeepDiveCallback,
  OnRemoveCardCallback,
  OnMoveToColumnCallback,
  CardActionCallbacks,
} from './types';

// =============================================================================
// Constants
// =============================================================================

export { KANBAN_COLUMNS } from './types';

// =============================================================================
// Component Props Types
// =============================================================================

export type { KanbanBoardProps } from './KanbanBoard';
export type { KanbanColumnProps } from './KanbanColumn';
export type { KanbanCardProps } from './KanbanCard';
export type { CardActionsProps } from './CardActions';
