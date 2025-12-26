/**
 * RelatedTab Component
 *
 * Displays the Related tab for a card, showing an interactive network diagram
 * of related trends using the ConceptNetworkDiagram visualization.
 *
 * Features:
 * - Interactive network graph with pan/zoom
 * - Clickable nodes for navigation to related cards
 * - Horizon-based color coding (H1=green, H2=amber, H3=purple)
 * - Loading, error, and empty states
 * - Minimap for navigation in large networks
 *
 * @module CardDetail/tabs/RelatedTab
 */

import React from 'react';
import { ConceptNetworkDiagram } from '../../visualizations/ConceptNetworkDiagram';
import type { RelatedCard } from '../../../lib/discovery-api';
import type { Card } from '../types';

/**
 * Props for the RelatedTab component
 */
export interface RelatedTabProps {
  /**
   * The source/central card data
   * Used to display the current card in the center of the network
   */
  card: Pick<Card, 'id' | 'name' | 'summary' | 'horizon'>;

  /**
   * Array of related cards to display in the network
   * Each card shows as a node connected to the central card
   */
  relatedCards: RelatedCard[];

  /**
   * Whether the related cards are currently loading
   * Shows a loading spinner when true
   */
  loading?: boolean;

  /**
   * Error message to display if loading failed
   * Shows an error state with retry option when set
   */
  error?: string | null;

  /**
   * Callback when the retry button is clicked after an error
   */
  onRetry?: () => void;

  /**
   * Callback when a related card node is clicked
   * @param cardId - The ID of the clicked card
   * @param cardSlug - The slug of the clicked card for navigation
   */
  onCardClick?: (cardId: string, cardSlug: string) => void;

  /**
   * Height of the network diagram in pixels
   * @default 600
   */
  height?: number;

  /**
   * Whether to show the minimap for navigation
   * @default true
   */
  showMinimap?: boolean;

  /**
   * Whether to show the background grid pattern
   * @default true
   */
  showBackground?: boolean;

  /**
   * Title displayed above the network diagram
   * @default "Related Trends Network"
   */
  title?: string;

  /**
   * Optional additional CSS classes for the container
   */
  className?: string;
}

/**
 * RelatedTab displays an interactive network diagram of related trends.
 *
 * The network shows the current card in the center with related cards
 * arranged radially around it. Relationships are shown as labeled edges
 * with thickness based on relationship strength.
 *
 * Features:
 * - Horizon-based node coloring for quick visual identification
 * - Interactive pan, zoom, and drag functionality
 * - Clickable nodes that navigate to card details
 * - Legend explaining the color coding
 * - Loading and error states with retry capability
 * - Empty state when no related cards exist
 *
 * @example
 * ```tsx
 * const [relatedCards, setRelatedCards] = useState<RelatedCard[]>([]);
 * const [loading, setLoading] = useState(true);
 * const [error, setError] = useState<string | null>(null);
 *
 * const handleCardClick = (cardId: string, cardSlug: string) => {
 *   navigate(`/cards/${cardSlug}`);
 * };
 *
 * const loadRelatedCards = async () => {
 *   setLoading(true);
 *   setError(null);
 *   try {
 *     const data = await fetchRelatedCards(card.id);
 *     setRelatedCards(data);
 *   } catch (err) {
 *     setError('Failed to load related cards');
 *   } finally {
 *     setLoading(false);
 *   }
 * };
 *
 * <RelatedTab
 *   card={card}
 *   relatedCards={relatedCards}
 *   loading={loading}
 *   error={error}
 *   onRetry={loadRelatedCards}
 *   onCardClick={handleCardClick}
 * />
 * ```
 */
export const RelatedTab: React.FC<RelatedTabProps> = ({
  card,
  relatedCards,
  loading = false,
  error = null,
  onRetry,
  onCardClick,
  height = 600,
  showMinimap = true,
  showBackground = true,
  title = 'Related Trends Network',
  className,
}) => {
  return (
    <ConceptNetworkDiagram
      sourceCardId={card.id}
      sourceCardName={card.name}
      sourceCardSummary={card.summary}
      sourceCardHorizon={card.horizon}
      relatedCards={relatedCards}
      height={height}
      loading={loading}
      error={error}
      onRetry={onRetry}
      onCardClick={onCardClick}
      showMinimap={showMinimap}
      showBackground={showBackground}
      title={title}
      className={className}
    />
  );
};

export default RelatedTab;
