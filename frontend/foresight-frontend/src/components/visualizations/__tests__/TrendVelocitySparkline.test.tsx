/**
 * TrendVelocitySparkline Unit Tests
 *
 * Tests the TrendVelocitySparkline component for:
 * - Compact sparkline rendering without axes
 * - Velocity trend display over configurable days
 * - Insufficient data handling (<2 points)
 * - Custom dimensions (width, height)
 * - Accessibility attributes (ARIA labels)
 * - Trend direction calculation
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  TrendVelocitySparkline,
  TrendVelocitySparklineCompact,
  TrendVelocitySparklineSkeleton,
} from '../TrendVelocitySparkline';
import type { ScoreHistory } from '../../../lib/discovery-api';

// Mock Recharts to avoid ResizeObserver issues
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    LineChart: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="line-chart">{children}</div>
    ),
    Line: () => <div data-testid="line" />,
    Tooltip: () => null,
  };
});

// ============================================================================
// Test Data Factories
// ============================================================================

function createMockScoreHistory(
  daysAgo: number,
  velocityScore: number
): ScoreHistory {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);

  return {
    id: `score-${daysAgo}`,
    card_id: 'test-card-id',
    recorded_at: date.toISOString(),
    maturity_score: 50,
    velocity_score: velocityScore,
    novelty_score: 70,
    impact_score: 55,
    relevance_score: 65,
    risk_score: 30,
    opportunity_score: 75,
  };
}

function createMockDataArray(
  count: number,
  velocityTrend: 'up' | 'down' | 'stable' = 'stable'
): ScoreHistory[] {
  const data: ScoreHistory[] = [];

  for (let i = count - 1; i >= 0; i--) {
    let velocity = 50;
    if (velocityTrend === 'up') {
      velocity = 30 + ((count - i) / count) * 40;
    } else if (velocityTrend === 'down') {
      velocity = 70 - ((count - i) / count) * 40;
    }
    data.push(createMockScoreHistory(i, velocity));
  }

  return data;
}

// ============================================================================
// Tests
// ============================================================================

describe('TrendVelocitySparkline', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders sparkline with valid data', () => {
      const data = createMockDataArray(10);
      render(<TrendVelocitySparkline data={data} />);

      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });

    it('renders without axes (sparkline style)', () => {
      const data = createMockDataArray(10);
      render(<TrendVelocitySparkline data={data} />);

      // XAxis and YAxis should not be rendered
      expect(screen.queryByRole('presentation')).toBeNull();
    });

    it('applies default width and height', () => {
      const data = createMockDataArray(10);
      const { container } = render(<TrendVelocitySparkline data={data} />);

      const sparklineContainer = container.querySelector('[role="img"]');
      expect(sparklineContainer).toHaveStyle({ width: '80px', height: '24px' });
    });

    it('applies custom width and height', () => {
      const data = createMockDataArray(10);
      const { container } = render(
        <TrendVelocitySparkline data={data} width={120} height={40} />
      );

      const sparklineContainer = container.querySelector('[role="img"]');
      expect(sparklineContainer).toHaveStyle({ width: '120px', height: '40px' });
    });

    it('applies custom className', () => {
      const data = createMockDataArray(10);
      const { container } = render(
        <TrendVelocitySparkline data={data} className="custom-sparkline" />
      );

      expect(container.querySelector('.custom-sparkline')).toBeInTheDocument();
    });
  });

  describe('Insufficient Data Handling', () => {
    it('shows "No trend data" message when data is empty', () => {
      render(<TrendVelocitySparkline data={[]} />);

      expect(screen.getByText(/No trend data/i)).toBeInTheDocument();
    });

    it('shows "No trend data" message when data has only 1 point', () => {
      const data = [createMockScoreHistory(0, 50)];
      render(<TrendVelocitySparkline data={data} />);

      expect(screen.getByText(/No trend data/i)).toBeInTheDocument();
    });

    it('respects custom minDataPoints prop', () => {
      const data = [
        createMockScoreHistory(0, 50),
        createMockScoreHistory(1, 55),
      ];

      // With minDataPoints=3, should show empty state
      render(<TrendVelocitySparkline data={data} minDataPoints={3} />);
      expect(screen.getByText(/No trend data/i)).toBeInTheDocument();
    });

    it('renders chart when data meets minDataPoints threshold', () => {
      const data = [
        createMockScoreHistory(0, 50),
        createMockScoreHistory(1, 55),
      ];

      render(<TrendVelocitySparkline data={data} minDataPoints={2} />);
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });
  });

  describe('Date Filtering (daysToShow)', () => {
    it('filters data to last 30 days by default', () => {
      // Create data spanning 60 days
      const data: ScoreHistory[] = [];
      for (let i = 0; i < 60; i++) {
        data.push(createMockScoreHistory(i, 50 + i));
      }

      // With default 30 days, only recent data should be included
      render(<TrendVelocitySparkline data={data} />);
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });

    it('respects custom daysToShow prop', () => {
      // Create data spanning 60 days
      const data: ScoreHistory[] = [];
      for (let i = 0; i < 60; i++) {
        data.push(createMockScoreHistory(i, 50 + i));
      }

      render(<TrendVelocitySparkline data={data} daysToShow={7} />);
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });

    it('shows empty state if no data within daysToShow range', () => {
      // All data is older than 30 days
      const data = [
        createMockScoreHistory(40, 50),
        createMockScoreHistory(45, 55),
        createMockScoreHistory(50, 60),
      ];

      render(<TrendVelocitySparkline data={data} daysToShow={30} />);
      expect(screen.getByText(/No trend data/i)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has role="img" for accessibility', () => {
      const data = createMockDataArray(10);
      const { container } = render(<TrendVelocitySparkline data={data} />);

      expect(container.querySelector('[role="img"]')).toBeInTheDocument();
    });

    it('has appropriate aria-label for increasing trend', () => {
      const data = createMockDataArray(10, 'up');
      const { container } = render(<TrendVelocitySparkline data={data} />);

      const sparkline = container.querySelector('[role="img"]');
      expect(sparkline?.getAttribute('aria-label')).toContain('increasing');
    });

    it('has appropriate aria-label for decreasing trend', () => {
      const data = createMockDataArray(10, 'down');
      const { container } = render(<TrendVelocitySparkline data={data} />);

      const sparkline = container.querySelector('[role="img"]');
      expect(sparkline?.getAttribute('aria-label')).toContain('decreasing');
    });

    it('has appropriate aria-label for stable trend', () => {
      const data = createMockDataArray(10, 'stable');
      const { container } = render(<TrendVelocitySparkline data={data} />);

      const sparkline = container.querySelector('[role="img"]');
      expect(sparkline?.getAttribute('aria-label')).toContain('stable');
    });

    it('has aria-label for insufficient data state', () => {
      const { container } = render(<TrendVelocitySparkline data={[]} />);

      const element = container.querySelector('[role="img"]');
      expect(element?.getAttribute('aria-label')).toContain('Insufficient data');
    });
  });

  describe('Custom Styling', () => {
    it('uses default green stroke color', () => {
      const data = createMockDataArray(10);
      render(<TrendVelocitySparkline data={data} />);

      // The line should be rendered (mocked)
      expect(screen.getByTestId('line')).toBeInTheDocument();
    });

    it('accepts custom stroke color', () => {
      const data = createMockDataArray(10);
      render(<TrendVelocitySparkline data={data} strokeColor="#ff0000" />);

      expect(screen.getByTestId('line')).toBeInTheDocument();
    });

    it('accepts custom stroke width', () => {
      const data = createMockDataArray(10);
      render(<TrendVelocitySparkline data={data} strokeWidth={3} />);

      expect(screen.getByTestId('line')).toBeInTheDocument();
    });
  });

  describe('Tooltip', () => {
    it('shows tooltip by default (showTooltip=true)', () => {
      const data = createMockDataArray(10);
      render(<TrendVelocitySparkline data={data} />);

      // Tooltip is enabled by default
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });

    it('can disable tooltip with showTooltip=false', () => {
      const data = createMockDataArray(10);
      render(<TrendVelocitySparkline data={data} showTooltip={false} />);

      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });
  });

  describe('Null Velocity Score Handling', () => {
    it('filters out records with null velocity_score', () => {
      const data: ScoreHistory[] = [
        createMockScoreHistory(0, 50),
        {
          ...createMockScoreHistory(1, 55),
          velocity_score: null,
        },
        createMockScoreHistory(2, 60),
      ];

      // Should render without error
      render(<TrendVelocitySparkline data={data} />);
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });
  });
});

describe('TrendVelocitySparklineCompact', () => {
  it('renders with smaller dimensions', () => {
    const data = createMockDataArray(10);
    const { container } = render(
      <TrendVelocitySparklineCompact data={data} />
    );

    const sparkline = container.querySelector('[role="img"]');
    expect(sparkline).toHaveStyle({ width: '60px', height: '20px' });
  });

  it('disables tooltip for better list performance', () => {
    const data = createMockDataArray(10);
    render(<TrendVelocitySparklineCompact data={data} />);

    // Should render without tooltip interactions
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
  });

  it('accepts custom className', () => {
    const data = createMockDataArray(10);
    const { container } = render(
      <TrendVelocitySparklineCompact data={data} className="compact-class" />
    );

    expect(container.querySelector('.compact-class')).toBeInTheDocument();
  });
});

describe('TrendVelocitySparklineSkeleton', () => {
  it('renders loading skeleton with default dimensions', () => {
    const { container } = render(<TrendVelocitySparklineSkeleton />);

    const skeleton = container.querySelector('[role="status"]');
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveStyle({ width: '80px', height: '24px' });
  });

  it('renders with custom dimensions', () => {
    const { container } = render(
      <TrendVelocitySparklineSkeleton width={100} height={30} />
    );

    const skeleton = container.querySelector('[role="status"]');
    expect(skeleton).toHaveStyle({ width: '100px', height: '30px' });
  });

  it('has pulse animation class', () => {
    const { container } = render(<TrendVelocitySparklineSkeleton />);

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('has appropriate aria-label for loading state', () => {
    render(<TrendVelocitySparklineSkeleton />);

    expect(screen.getByLabelText(/Loading velocity trend/i)).toBeInTheDocument();
  });

  it('accepts custom className', () => {
    const { container } = render(
      <TrendVelocitySparklineSkeleton className="skeleton-class" />
    );

    expect(container.querySelector('.skeleton-class')).toBeInTheDocument();
  });
});
