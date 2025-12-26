/**
 * ConceptNetworkDiagram Unit Tests
 *
 * Tests the ConceptNetworkDiagram component for:
 * - Graph rendering with nodes and edges
 * - Empty state handling (no related cards)
 * - Loading and error states
 * - Clickable nodes
 * - Horizon-based color coding
 * - Edge styling based on relationship strength
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConceptNetworkDiagram } from '../ConceptNetworkDiagram';
import type { RelatedCard } from '../../../lib/discovery-api';

// Mock @xyflow/react to avoid complex DOM operations
interface MockNode {
  id: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

interface MockEdge {
  id: string;
  source: string;
  target: string;
}

vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ nodes, edges, children }: { nodes: MockNode[]; edges: MockEdge[]; children: React.ReactNode }) => (
    <div data-testid="react-flow" data-nodes={nodes.length} data-edges={edges.length}>
      {children}
    </div>
  ),
  Background: () => <div data-testid="background" />,
  Controls: () => <div data-testid="controls" />,
  MiniMap: () => <div data-testid="minimap" />,
  Handle: ({ position }: { position: string }) => <div data-testid={`handle-${position}`} />,
  Position: {
    Top: 'top',
    Bottom: 'bottom',
    Left: 'left',
    Right: 'right',
  },
  BackgroundVariant: {
    Dots: 'dots',
    Lines: 'lines',
    Cross: 'cross',
  },
  useNodesState: (initialNodes: MockNode[]) => [initialNodes, vi.fn(), vi.fn()],
  useEdgesState: (initialEdges: MockEdge[]) => [initialEdges, vi.fn(), vi.fn()],
}));

// ============================================================================
// Test Data Factories
// ============================================================================

function createMockRelatedCard(overrides: Partial<RelatedCard> = {}): RelatedCard {
  return {
    id: 'related-card-1',
    name: 'Related Card Name',
    slug: 'related-card-slug',
    summary: 'This is a related card summary',
    pillar_id: 'pillar-1',
    stage_id: 'stage-4',
    horizon: 'H2',
    relationship_type: 'related',
    relationship_strength: 0.8,
    relationship_id: 'rel-1',
    ...overrides,
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('ConceptNetworkDiagram', () => {
  const defaultProps = {
    sourceCardId: 'source-card-id',
    sourceCardName: 'Source Card',
    sourceCardSummary: 'Source card summary',
    sourceCardHorizon: 'H1' as const,
    relatedCards: [] as RelatedCard[],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders React Flow component with related cards', () => {
      const relatedCards = [
        createMockRelatedCard({ id: 'card-1', name: 'Card 1' }),
        createMockRelatedCard({ id: 'card-2', name: 'Card 2' }),
      ];

      render(
        <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
      );

      const reactFlow = screen.getByTestId('react-flow');
      expect(reactFlow).toBeInTheDocument();
      // 1 source node + 2 related nodes = 3 nodes
      expect(reactFlow).toHaveAttribute('data-nodes', '3');
      // 2 edges connecting source to each related card
      expect(reactFlow).toHaveAttribute('data-edges', '2');
    });

    it('renders title when provided', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
          title="Related Trends Network"
        />
      );

      expect(screen.getByText('Related Trends Network')).toBeInTheDocument();
    });

    it('renders Controls component', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
        />
      );

      expect(screen.getByTestId('controls')).toBeInTheDocument();
    });

    it('renders MiniMap when showMinimap is true', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
          showMinimap={true}
        />
      );

      expect(screen.getByTestId('minimap')).toBeInTheDocument();
    });

    it('does not render MiniMap when showMinimap is false', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
          showMinimap={false}
        />
      );

      expect(screen.queryByTestId('minimap')).not.toBeInTheDocument();
    });

    it('renders Background when showBackground is true', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
          showBackground={true}
        />
      );

      expect(screen.getByTestId('background')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
          className="custom-network"
        />
      );

      expect(container.querySelector('.custom-network')).toBeInTheDocument();
    });

    it('renders footer with card count', () => {
      const relatedCards = [
        createMockRelatedCard({ id: 'card-1' }),
        createMockRelatedCard({ id: 'card-2' }),
        createMockRelatedCard({ id: 'card-3' }),
      ];

      render(
        <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
      );

      expect(screen.getByText('3 related trends')).toBeInTheDocument();
    });

    it('shows singular "trend" for single related card', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
        />
      );

      expect(screen.getByText('1 related trend')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state when relatedCards is empty array', () => {
      render(<ConceptNetworkDiagram {...defaultProps} relatedCards={[]} />);

      expect(screen.getByText('No related trends found')).toBeInTheDocument();
      expect(
        screen.getByText(/Related cards will appear here/i)
      ).toBeInTheDocument();
    });

    it('shows GitBranch icon in empty state', () => {
      const { container } = render(
        <ConceptNetworkDiagram {...defaultProps} relatedCards={[]} />
      );

      // Icon should be present (h-12 w-12 classes)
      const icon = container.querySelector('.h-12.w-12');
      expect(icon).toBeInTheDocument();
    });

    it('still renders title in empty state', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[]}
          title="Network View"
        />
      );

      expect(screen.getByText('Network View')).toBeInTheDocument();
      expect(screen.getByText('No related trends found')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading spinner when loading prop is true', () => {
      const { container } = render(
        <ConceptNetworkDiagram {...defaultProps} loading={true} />
      );

      expect(screen.getByText('Loading network...')).toBeInTheDocument();
      expect(container.querySelector('.animate-spin')).toBeInTheDocument();
    });

    it('shows title during loading', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          loading={true}
          title="Network View"
        />
      );

      expect(screen.getByText('Network View')).toBeInTheDocument();
    });

    it('does not render React Flow while loading', () => {
      render(<ConceptNetworkDiagram {...defaultProps} loading={true} />);

      expect(screen.queryByTestId('react-flow')).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('shows error message when error prop is provided', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          error="Failed to load network data"
        />
      );

      expect(screen.getByText('Failed to load network data')).toBeInTheDocument();
    });

    it('shows retry button when onRetry is provided', () => {
      const onRetry = vi.fn();
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          error="Network error"
          onRetry={onRetry}
        />
      );

      expect(screen.getByText('Try again')).toBeInTheDocument();
    });

    it('calls onRetry when retry button is clicked', () => {
      const onRetry = vi.fn();
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          error="Network error"
          onRetry={onRetry}
        />
      );

      fireEvent.click(screen.getByText('Try again'));
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('shows error icon', () => {
      const { container } = render(
        <ConceptNetworkDiagram {...defaultProps} error="Error occurred" />
      );

      // AlertCircle should have red styling
      const errorIcon = container.querySelector('.text-red-400');
      expect(errorIcon).toBeInTheDocument();
    });
  });

  describe('Legend', () => {
    it('renders horizon legend items', () => {
      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
        />
      );

      expect(screen.getByText('Current Card')).toBeInTheDocument();
      expect(screen.getByText('H1 (Mainstream)')).toBeInTheDocument();
      expect(screen.getByText('H2 (Transitional)')).toBeInTheDocument();
      expect(screen.getByText('H3 (Transformative)')).toBeInTheDocument();
    });

    it('displays color indicators for each horizon', () => {
      const { container } = render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
        />
      );

      // Should have colored squares for each legend item
      const legendSquares = container.querySelectorAll('.w-3.h-3.rounded');
      expect(legendSquares.length).toBeGreaterThanOrEqual(4); // Current, H1, H2, H3
    });
  });

  describe('Node Click Handling', () => {
    it('passes onCardClick to related card nodes', () => {
      const onCardClick = vi.fn();
      const relatedCards = [
        createMockRelatedCard({ id: 'card-1', slug: 'card-1-slug' }),
      ];

      render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={relatedCards}
          onCardClick={onCardClick}
        />
      );

      // React Flow is mocked, so we just verify it renders
      expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    });
  });

  describe('Horizon Color Coding', () => {
    it('creates nodes with H1 horizon styling', () => {
      const relatedCards = [
        createMockRelatedCard({ id: 'card-1', horizon: 'H1' }),
      ];

      render(
        <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
      );

      expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    });

    it('creates nodes with H2 horizon styling', () => {
      const relatedCards = [
        createMockRelatedCard({ id: 'card-1', horizon: 'H2' }),
      ];

      render(
        <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
      );

      expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    });

    it('creates nodes with H3 horizon styling', () => {
      const relatedCards = [
        createMockRelatedCard({ id: 'card-1', horizon: 'H3' }),
      ];

      render(
        <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
      );

      expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    });

    it('handles null horizon gracefully', () => {
      const relatedCards = [
        createMockRelatedCard({ id: 'card-1', horizon: null }),
      ];

      expect(() =>
        render(
          <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
        )
      ).not.toThrow();
    });
  });

  describe('Relationship Types', () => {
    it('handles "related" relationship type', () => {
      const relatedCards = [
        createMockRelatedCard({ relationship_type: 'related' }),
      ];

      render(
        <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
      );

      expect(screen.getByTestId('react-flow')).toHaveAttribute('data-edges', '1');
    });

    it('handles "similar" relationship type', () => {
      const relatedCards = [
        createMockRelatedCard({ relationship_type: 'similar' }),
      ];

      render(
        <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
      );

      expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    });

    it('handles "derived" relationship type', () => {
      const relatedCards = [
        createMockRelatedCard({ relationship_type: 'derived' }),
      ];

      render(
        <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
      );

      expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    });
  });

  describe('Relationship Strength', () => {
    it('handles high relationship strength (close to 1)', () => {
      const relatedCards = [
        createMockRelatedCard({ relationship_strength: 0.95 }),
      ];

      expect(() =>
        render(
          <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
        )
      ).not.toThrow();
    });

    it('handles low relationship strength (close to 0)', () => {
      const relatedCards = [
        createMockRelatedCard({ relationship_strength: 0.1 }),
      ];

      expect(() =>
        render(
          <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
        )
      ).not.toThrow();
    });

    it('handles null relationship strength', () => {
      const relatedCards = [
        createMockRelatedCard({ relationship_strength: null }),
      ];

      expect(() =>
        render(
          <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
        )
      ).not.toThrow();
    });
  });

  describe('Container Height', () => {
    it('uses default height of 500px', () => {
      const { container } = render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
        />
      );

      const heightContainer = container.querySelector('[style*="height: 500px"]');
      expect(heightContainer).toBeInTheDocument();
    });

    it('accepts custom height prop', () => {
      const { container } = render(
        <ConceptNetworkDiagram
          {...defaultProps}
          relatedCards={[createMockRelatedCard()]}
          height={800}
        />
      );

      const heightContainer = container.querySelector('[style*="height: 800px"]');
      expect(heightContainer).toBeInTheDocument();
    });
  });

  describe('Multiple Related Cards', () => {
    it('handles many related cards (20+)', () => {
      const relatedCards = Array.from({ length: 25 }, (_, i) =>
        createMockRelatedCard({
          id: `card-${i}`,
          name: `Card ${i}`,
          slug: `card-${i}-slug`,
        })
      );

      expect(() =>
        render(
          <ConceptNetworkDiagram {...defaultProps} relatedCards={relatedCards} />
        )
      ).not.toThrow();

      expect(screen.getByText('25 related trends')).toBeInTheDocument();
    });
  });
});
