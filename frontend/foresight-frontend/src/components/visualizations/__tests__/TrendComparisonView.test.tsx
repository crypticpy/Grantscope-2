/**
 * TrendComparisonView Unit Tests
 *
 * Tests the TrendComparisonView component for:
 * - Side-by-side card comparison rendering
 * - Loading, error, and invalid params states
 * - Score comparison metrics
 * - Synchronized timeline charts
 * - Stage progression comparison
 */

import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { TrendComparisonView } from '../TrendComparisonView';
import type { CardComparisonResponse, ScoreHistory, StageHistory, CardData } from '../../../lib/discovery-api';

// Mock Recharts
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

// Mock the Tooltip component to avoid TooltipProvider requirement
vi.mock('../../ui/Tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// Mock badge components that use Tooltip
vi.mock('../../PillarBadge', () => ({
  PillarBadge: ({ pillarId }: { pillarId: string }) => <span data-testid="pillar-badge">{pillarId}</span>,
}));

vi.mock('../../HorizonBadge', () => ({
  HorizonBadge: ({ horizon }: { horizon: string }) => <span data-testid="horizon-badge">{horizon}</span>,
}));

vi.mock('../../StageBadge', () => ({
  StageBadge: ({ stage }: { stage: number }) => <span data-testid="stage-badge">{stage}</span>,
}));

// Mock the child visualization components
vi.mock('../ScoreTimelineChart', () => ({
  ScoreTimelineChart: ({ title }: { title?: string }) => (
    <div data-testid="score-timeline-chart">{title}</div>
  ),
  SCORE_CONFIGS: [
    { key: 'maturity_score', name: 'Maturity', color: '#8884d8' },
    { key: 'velocity_score', name: 'Velocity', color: '#82ca9d' },
    { key: 'novelty_score', name: 'Novelty', color: '#ffc658' },
    { key: 'impact_score', name: 'Impact', color: '#ff7c43' },
    { key: 'relevance_score', name: 'Relevance', color: '#00bcd4' },
    { key: 'risk_score', name: 'Risk', color: '#ef5350' },
    { key: 'opportunity_score', name: 'Opportunity', color: '#66bb6a' },
  ],
}));

vi.mock('../StageProgressionTimeline', () => ({
  StageProgressionTimeline: () => <div data-testid="stage-progression-timeline" />,
}));

// Mock react-router-dom hooks
const mockSearchParams = new URLSearchParams();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useSearchParams: () => [mockSearchParams, vi.fn()],
  };
});

// Mock auth context
const mockUser = { id: 'test-user-id', email: 'test@example.com' };
vi.mock('../../../hooks/useAuthContext', () => ({
  useAuthContext: () => ({ user: mockUser }),
}));

// Mock supabase
vi.mock('../../../App', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(() => Promise.resolve({
        data: { session: { access_token: 'mock-token' } },
      })),
    },
  },
}));

// Mock API calls
const mockCompareCards = vi.fn();
vi.mock('../../../lib/discovery-api', async () => {
  const actual = await vi.importActual('../../../lib/discovery-api');
  return {
    ...actual,
    compareCards: (...args: unknown[]) => mockCompareCards(...args),
  };
});

// ============================================================================
// Test Data Factories
// ============================================================================

function createMockCardData(overrides: Partial<CardData> = {}): CardData {
  return {
    id: 'card-1',
    name: 'Test Card',
    slug: 'test-card',
    summary: 'Test card summary',
    pillar_id: 'pillar-1',
    stage_id: '4_emerging',
    horizon: 'H2',
    maturity_score: 60,
    velocity_score: 55,
    novelty_score: 70,
    impact_score: 65,
    relevance_score: 50,
    risk_score: 40,
    opportunity_score: 75,
    ...overrides,
  };
}

function createMockScoreHistory(daysAgo: number): ScoreHistory {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return {
    id: `score-${daysAgo}`,
    card_id: 'card-1',
    recorded_at: date.toISOString(),
    maturity_score: 50 + daysAgo,
    velocity_score: 55,
    novelty_score: 70,
    impact_score: 65,
    relevance_score: 50,
    risk_score: 40,
    opportunity_score: 75,
  };
}

function createMockStageHistory(): StageHistory {
  return {
    id: 'stage-1',
    card_id: 'card-1',
    changed_at: new Date().toISOString(),
    old_stage_id: 3,
    new_stage_id: 4,
    old_horizon: 'H2',
    new_horizon: 'H2',
    trigger: 'manual',
    reason: null,
  };
}

function createMockComparisonResponse(): CardComparisonResponse {
  return {
    card1: {
      card: createMockCardData({ id: 'card-1', name: 'Card One' }),
      score_history: [createMockScoreHistory(0), createMockScoreHistory(7)],
      stage_history: [createMockStageHistory()],
    },
    card2: {
      card: createMockCardData({ id: 'card-2', name: 'Card Two', maturity_score: 70 }),
      score_history: [createMockScoreHistory(0), createMockScoreHistory(7)],
      stage_history: [],
    },
    comparison_generated_at: new Date().toISOString(),
  };
}

// ============================================================================
// Test Utilities
// ============================================================================

function renderWithRouter(
  component: React.ReactElement,
  { route = '/compare', cardIds = 'card-1,card-2' } = {}
) {
  mockSearchParams.set('card_ids', cardIds);

  return render(
    <MemoryRouter initialEntries={[`${route}?card_ids=${cardIds}`]}>
      <Routes>
        <Route path="/compare" element={component} />
        <Route path="/discover" element={<div>Discover Page</div>} />
        <Route path="/cards/:slug" element={<div>Card Detail Page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

// ============================================================================
// Tests
// ============================================================================

describe('TrendComparisonView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams.delete('card_ids');
  });

  describe('Loading State', () => {
    it('shows loading state while fetching data', async () => {
      // Never resolve the promise to keep loading state
      mockCompareCards.mockImplementation(() => new Promise(() => {}));
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      expect(screen.getByText('Loading comparison data...')).toBeInTheDocument();
    });

    it('shows loading spinner animation', async () => {
      mockCompareCards.mockImplementation(() => new Promise(() => {}));
      mockSearchParams.set('card_ids', 'card-1,card-2');

      const { container } = renderWithRouter(<TrendComparisonView />);

      expect(container.querySelector('.animate-spin')).toBeInTheDocument();
    });
  });

  describe('Invalid Params State', () => {
    it('shows invalid state when no card_ids param', () => {
      mockSearchParams.delete('card_ids');

      render(
        <MemoryRouter initialEntries={['/compare']}>
          <Routes>
            <Route path="/compare" element={<TrendComparisonView />} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByText('Select Two Cards to Compare')).toBeInTheDocument();
    });

    it('shows invalid state when only one card_id', () => {
      mockSearchParams.set('card_ids', 'card-1');

      render(
        <MemoryRouter initialEntries={['/compare?card_ids=card-1']}>
          <Routes>
            <Route path="/compare" element={<TrendComparisonView />} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByText('Select Two Cards to Compare')).toBeInTheDocument();
    });

    it('shows link to discover page', () => {
      mockSearchParams.delete('card_ids');

      render(
        <MemoryRouter initialEntries={['/compare']}>
          <Routes>
            <Route path="/compare" element={<TrendComparisonView />} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByText('Go to Discover')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('shows error state when API fails', async () => {
      mockCompareCards.mockRejectedValue(new Error('API Error'));
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('API Error')).toBeInTheDocument();
      });
    });

    it('shows retry button on error', async () => {
      mockCompareCards.mockRejectedValue(new Error('Network Error'));
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Try Again')).toBeInTheDocument();
      });
    });

    it('calls fetchComparisonData when retry is clicked', async () => {
      mockCompareCards
        .mockRejectedValueOnce(new Error('First Error'))
        .mockResolvedValueOnce(createMockComparisonResponse());

      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Try Again')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Try Again'));

      // Should have called the API twice (initial + retry)
      await waitFor(() => {
        expect(mockCompareCards).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Successful Rendering', () => {
    beforeEach(() => {
      mockCompareCards.mockResolvedValue(createMockComparisonResponse());
    });

    it('renders comparison view header', async () => {
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Trend Comparison')).toBeInTheDocument();
      });
    });

    it('renders card labels', async () => {
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Card A')).toBeInTheDocument();
        expect(screen.getByText('Card B')).toBeInTheDocument();
      });
    });

    it('renders score comparison section', async () => {
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Score Comparison')).toBeInTheDocument();
      });
    });

    it('renders stage progression comparison heading', async () => {
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Stage Progression Comparison')).toBeInTheDocument();
      });
    });
  });

  describe('Score Comparison Metrics', () => {
    beforeEach(() => {
      mockCompareCards.mockResolvedValue(createMockComparisonResponse());
    });

    it('displays metric columns', async () => {
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Metric')).toBeInTheDocument();
        expect(screen.getByText('Difference')).toBeInTheDocument();
      });
    });
  });

  describe('Timeline Interactions', () => {
    beforeEach(() => {
      mockCompareCards.mockResolvedValue(createMockComparisonResponse());
    });

    it('renders score selector dropdown', async () => {
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        // Find the select element
        const select = screen.getByRole('combobox');
        expect(select).toBeInTheDocument();
      });
    });

    it('allows changing selected score type', async () => {
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        const select = screen.getByRole('combobox');
        fireEvent.change(select, { target: { value: 'velocity_score' } });
        expect(select).toHaveValue('velocity_score');
      });
    });
  });

  describe('Direct Props', () => {
    beforeEach(() => {
      mockCompareCards.mockResolvedValue(createMockComparisonResponse());
    });

    it('accepts cardIds as props instead of URL params', async () => {
      mockSearchParams.delete('card_ids');

      render(
        <MemoryRouter>
          <TrendComparisonView cardIds={['card-1', 'card-2']} />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(mockCompareCards).toHaveBeenCalledWith(
          'mock-token',
          'card-1',
          'card-2'
        );
      });
    });

    it('applies custom className', async () => {
      mockSearchParams.delete('card_ids');

      const { container } = render(
        <MemoryRouter>
          <TrendComparisonView
            cardIds={['card-1', 'card-2']}
            className="custom-class"
          />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(container.querySelector('.custom-class')).toBeInTheDocument();
      });
    });
  });

  describe('Empty History Handling', () => {
    it('handles cards with no score history', async () => {
      const responseWithEmptyHistory = createMockComparisonResponse();
      responseWithEmptyHistory.card1.score_history = [];
      responseWithEmptyHistory.card2.score_history = [];
      mockCompareCards.mockResolvedValue(responseWithEmptyHistory);

      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        // Should show empty state for timeline
        expect(
          screen.getByText(/Not enough historical data/i)
        ).toBeInTheDocument();
      });
    });

    it('handles cards with no stage history', async () => {
      const responseWithEmptyStageHistory = createMockComparisonResponse();
      responseWithEmptyStageHistory.card1.stage_history = [];
      responseWithEmptyStageHistory.card2.stage_history = [];
      mockCompareCards.mockResolvedValue(responseWithEmptyStageHistory);

      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        expect(screen.getByText('Stage Progression Comparison')).toBeInTheDocument();
      });
    });
  });
});

describe('Utility Functions', () => {
  // Note: These are implicitly tested through the component tests above
  // If we want to test them directly, we'd need to export them from the component

  describe('Score Differences Calculation', () => {
    it('renders score difference values', async () => {
      // Card2 has higher maturity score (70 vs 60)
      const response = createMockComparisonResponse();
      mockCompareCards.mockResolvedValue(response);
      mockSearchParams.set('card_ids', 'card-1,card-2');

      renderWithRouter(<TrendComparisonView />);

      await waitFor(() => {
        // Score values should be visible
        const allText = document.body.textContent || '';
        expect(allText).toContain('60'); // Card1 maturity
        expect(allText).toContain('70'); // Card2 maturity
      });
    });
  });
});
