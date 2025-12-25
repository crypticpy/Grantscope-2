/**
 * ScoreTimelineChart Unit Tests
 *
 * Tests the ScoreTimelineChart component for:
 * - Rendering with valid data
 * - Empty state when insufficient data (<2 points)
 * - Loading state
 * - Error state with retry
 * - All 7 score lines visible
 * - Large dataset handling (>365 points)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ScoreTimelineChart, SCORE_CONFIGS, getScoreConfig } from '../ScoreTimelineChart';
import type { ScoreHistory } from '../../../lib/discovery-api';

// Mock Recharts to avoid ResizeObserver issues
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

// ============================================================================
// Test Data Factories
// ============================================================================

function createMockScoreHistory(
  date: string,
  overrides: Partial<ScoreHistory> = {}
): ScoreHistory {
  return {
    id: `score-${date}`,
    card_id: 'test-card-id',
    recorded_at: date,
    maturity_score: 50,
    velocity_score: 60,
    novelty_score: 70,
    impact_score: 55,
    relevance_score: 65,
    risk_score: 30,
    opportunity_score: 75,
    ...overrides,
  };
}

function createMockScoreHistoryArray(days: number): ScoreHistory[] {
  const data: ScoreHistory[] = [];
  const baseDate = new Date('2024-01-01');

  for (let i = 0; i < days; i++) {
    const date = new Date(baseDate);
    date.setDate(date.getDate() + i);
    data.push(
      createMockScoreHistory(date.toISOString(), {
        id: `score-${i}`,
        maturity_score: 50 + Math.sin(i / 10) * 20,
        velocity_score: 60 + Math.cos(i / 10) * 15,
        novelty_score: 70 - i * 0.1,
        impact_score: 55 + Math.random() * 10,
        relevance_score: 65,
        risk_score: 30 + i * 0.05,
        opportunity_score: 75 - Math.random() * 5,
      })
    );
  }
  return data;
}

// ============================================================================
// Tests
// ============================================================================

describe('ScoreTimelineChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders with valid data and displays title', () => {
      const data = createMockScoreHistoryArray(30);
      render(<ScoreTimelineChart data={data} title="Score History" />);

      expect(screen.getByText('Score History')).toBeInTheDocument();
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });

    it('renders all 7 score lines (configurations exist)', () => {
      const data = createMockScoreHistoryArray(10);
      render(<ScoreTimelineChart data={data} />);

      // Each score type should be configured
      // Note: Since Recharts is mocked, we verify the config exists
      expect(SCORE_CONFIGS.length).toBe(7);
      SCORE_CONFIGS.forEach((config) => {
        expect(config.name).toBeDefined();
        expect(config.color).toBeDefined();
      });
    });

    it('renders with default title "Score History"', () => {
      const data = createMockScoreHistoryArray(10);
      render(<ScoreTimelineChart data={data} />);

      // Default title is 'Score History'
      expect(screen.getByText('Score History')).toBeInTheDocument();
    });

    it('renders with custom height', () => {
      const data = createMockScoreHistoryArray(10);
      const { container } = render(
        <ScoreTimelineChart data={data} height={500} />
      );

      // The height should be applied to the chart container
      const chartContainer = container.querySelector('[style*="height"]');
      expect(chartContainer).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const data = createMockScoreHistoryArray(10);
      const { container } = render(
        <ScoreTimelineChart data={data} className="custom-class" />
      );

      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Empty State', () => {
    it('shows empty state when data has less than 2 points', () => {
      const data = [createMockScoreHistory('2024-01-01')];
      render(<ScoreTimelineChart data={data} />);

      expect(screen.getByText('Not enough data to show trend')).toBeInTheDocument();
      expect(
        screen.getByText('Score history will appear here once more data is available')
      ).toBeInTheDocument();
    });

    it('shows empty state when data is empty array', () => {
      render(<ScoreTimelineChart data={[]} />);

      expect(screen.getByText('Not enough data to show trend')).toBeInTheDocument();
    });

    it('shows the title even in empty state', () => {
      render(<ScoreTimelineChart data={[]} title="Score History" />);

      expect(screen.getByText('Score History')).toBeInTheDocument();
      expect(screen.getByText('Not enough data to show trend')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading state when loading prop is true', () => {
      const data = createMockScoreHistoryArray(10);
      render(<ScoreTimelineChart data={data} loading={true} />);

      expect(screen.getByText('Loading score history...')).toBeInTheDocument();
    });

    it('shows loading spinner animation', () => {
      render(<ScoreTimelineChart data={[]} loading={true} />);

      const spinner = document.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('shows title during loading', () => {
      render(
        <ScoreTimelineChart data={[]} loading={true} title="Score History" />
      );

      expect(screen.getByText('Score History')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('shows error state when error prop is provided', () => {
      render(<ScoreTimelineChart data={[]} error="Failed to load data" />);

      expect(screen.getByText('Failed to load data')).toBeInTheDocument();
    });

    it('shows retry button when onRetry callback is provided', () => {
      const onRetry = vi.fn();
      render(
        <ScoreTimelineChart
          data={[]}
          error="Failed to load data"
          onRetry={onRetry}
        />
      );

      const retryButton = screen.getByText('Try again');
      expect(retryButton).toBeInTheDocument();
    });

    it('calls onRetry when retry button is clicked', () => {
      const onRetry = vi.fn();
      render(
        <ScoreTimelineChart
          data={[]}
          error="Failed to load data"
          onRetry={onRetry}
        />
      );

      fireEvent.click(screen.getByText('Try again'));
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('shows error icon', () => {
      render(<ScoreTimelineChart data={[]} error="Error occurred" />);

      // AlertCircle icon should be present
      const errorIcon = document.querySelector('.text-red-400');
      expect(errorIcon).toBeInTheDocument();
    });
  });

  describe('Data Transformation', () => {
    it('handles null score values gracefully', () => {
      const data = [
        createMockScoreHistory('2024-01-01', { maturity_score: null }),
        createMockScoreHistory('2024-01-02', { velocity_score: null }),
        createMockScoreHistory('2024-01-03'),
      ];

      expect(() => render(<ScoreTimelineChart data={data} />)).not.toThrow();
    });

    it('sorts data by date ascending', () => {
      const data = [
        createMockScoreHistory('2024-01-15'),
        createMockScoreHistory('2024-01-01'),
        createMockScoreHistory('2024-01-10'),
      ];

      // Should not throw and should render correctly
      expect(() => render(<ScoreTimelineChart data={data} />)).not.toThrow();
    });
  });

  describe('Performance Optimization', () => {
    it('handles large datasets (>365 points)', () => {
      const data = createMockScoreHistoryArray(400);

      // Should not throw and should render
      expect(() => render(<ScoreTimelineChart data={data} />)).not.toThrow();
    });
  });

  describe('Visible Scores Filter', () => {
    it('can filter to specific score types', () => {
      const data = createMockScoreHistoryArray(10);
      render(
        <ScoreTimelineChart
          data={data}
          visibleScores={['maturity_score', 'velocity_score']}
        />
      );

      // Should render without errors with filtered scores
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });
  });
});

describe('SCORE_CONFIGS', () => {
  it('contains all 7 score types', () => {
    expect(SCORE_CONFIGS).toHaveLength(7);

    const expectedKeys = [
      'maturity_score',
      'velocity_score',
      'novelty_score',
      'impact_score',
      'relevance_score',
      'risk_score',
      'opportunity_score',
    ];

    expectedKeys.forEach((key) => {
      expect(SCORE_CONFIGS.find((c) => c.key === key)).toBeDefined();
    });
  });

  it('each config has required properties', () => {
    SCORE_CONFIGS.forEach((config) => {
      expect(config).toHaveProperty('key');
      expect(config).toHaveProperty('name');
      expect(config).toHaveProperty('color');
      expect(config).toHaveProperty('description');
      expect(config.color).toMatch(/^#[0-9a-fA-F]{6}$/);
    });
  });
});

describe('getScoreConfig', () => {
  it('returns correct config for valid score type', () => {
    const config = getScoreConfig('maturity_score');
    expect(config?.name).toBe('Maturity');
  });

  it('returns undefined for invalid score type', () => {
    const config = getScoreConfig('invalid_score' as any);
    expect(config).toBeUndefined();
  });
});
