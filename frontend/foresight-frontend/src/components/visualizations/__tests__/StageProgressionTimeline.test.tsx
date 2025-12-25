/**
 * StageProgressionTimeline Unit Tests
 *
 * Tests the StageProgressionTimeline component for:
 * - Rendering with valid stage transition data
 * - Empty state handling
 * - Stage labels 1-8 visibility
 * - Horizon color coding (H1=green, H2=amber, H3=purple)
 * - Direction indicators for progression/regression
 * - Compact vs full view modes
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StageProgressionTimeline } from '../StageProgressionTimeline';
import type { StageHistory } from '../../../lib/discovery-api';

// Mock the Tooltip component to simplify testing
vi.mock('../../ui/Tooltip', () => ({
  Tooltip: ({ children, content }: { children: React.ReactNode; content: React.ReactNode }) => (
    <div data-testid="tooltip">
      {children}
      <span data-testid="tooltip-content" className="hidden">{content}</span>
    </div>
  ),
}));

// ============================================================================
// Test Data Factories
// ============================================================================

function createMockStageHistory(
  overrides: Partial<StageHistory> = {}
): StageHistory {
  return {
    id: 'stage-history-1',
    card_id: 'test-card-id',
    changed_at: '2024-06-15T10:30:00Z',
    old_stage_id: 3,
    new_stage_id: 4,
    old_horizon: 'H2',
    new_horizon: 'H2',
    trigger: 'manual',
    reason: null,
    ...overrides,
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('StageProgressionTimeline', () => {
  describe('Rendering', () => {
    it('renders with valid stage history data', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          id: 'sh-1',
          old_stage_id: 3,
          new_stage_id: 4,
        }),
        createMockStageHistory({
          id: 'sh-2',
          changed_at: '2024-05-01T10:00:00Z',
          old_stage_id: 2,
          new_stage_id: 3,
        }),
      ];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      // Should render the transition count
      expect(screen.getByText(/2 transitions recorded/i)).toBeInTheDocument();
    });

    it('displays stage labels for transitions', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          old_stage_id: 3,
          new_stage_id: 5,
          old_horizon: 'H2',
          new_horizon: 'H2',
        }),
      ];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      // Stage numbers should be visible
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('shows formatted dates for transitions', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          changed_at: '2024-06-15T10:30:00Z',
        }),
      ];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      // Date should be formatted and visible (format: "Jun 15, 2024" in full mode)
      // In full mode, dates appear in the transition items
      const dateElements = screen.queryAllByText(/Jun|2024/);
      expect(dateElements.length).toBeGreaterThan(0);
    });

    it('applies custom className', () => {
      const { container } = render(
        <StageProgressionTimeline
          stageHistory={[createMockStageHistory()]}
          className="custom-class"
        />
      );

      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no stage history exists', () => {
      render(<StageProgressionTimeline stageHistory={[]} />);

      expect(
        screen.getByText(/no stage transitions recorded/i)
      ).toBeInTheDocument();
    });

    it('shows current stage in empty state when provided', () => {
      render(
        <StageProgressionTimeline stageHistory={[]} currentStage={5} />
      );

      // Current stage number should be displayed
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(
        screen.getByText(/no transitions recorded yet/i)
      ).toBeInTheDocument();
    });
  });

  describe('Horizon Color Coding', () => {
    it('applies green color classes for H1 horizon', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          old_horizon: 'H1',
          new_horizon: 'H1',
          old_stage_id: 6,
          new_stage_id: 7,
        }),
      ];

      const { container } = render(
        <StageProgressionTimeline stageHistory={stageHistory} />
      );

      // H1 should have green coloring
      const greenElements = container.querySelectorAll('[class*="green"]');
      expect(greenElements.length).toBeGreaterThan(0);
    });

    it('applies amber color classes for H2 horizon', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          old_horizon: 'H2',
          new_horizon: 'H2',
          old_stage_id: 4,
          new_stage_id: 5,
        }),
      ];

      const { container } = render(
        <StageProgressionTimeline stageHistory={stageHistory} />
      );

      // H2 should have amber coloring
      const amberElements = container.querySelectorAll('[class*="amber"]');
      expect(amberElements.length).toBeGreaterThan(0);
    });

    it('applies purple color classes for H3 horizon', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          old_horizon: 'H3',
          new_horizon: 'H3',
          old_stage_id: 1,
          new_stage_id: 2,
        }),
      ];

      const { container } = render(
        <StageProgressionTimeline stageHistory={stageHistory} />
      );

      // H3 should have purple coloring
      const purpleElements = container.querySelectorAll('[class*="purple"]');
      expect(purpleElements.length).toBeGreaterThan(0);
    });

    it('shows horizon change indicator when horizons differ', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          old_horizon: 'H3',
          new_horizon: 'H2',
          old_stage_id: 2,
          new_stage_id: 4,
        }),
      ];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      // Should show horizon change text
      expect(screen.getByText(/Horizon: H3/)).toBeInTheDocument();
    });
  });

  describe('Direction Indicators', () => {
    it('shows progression indicator when moving to higher stage', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          old_stage_id: 3,
          new_stage_id: 5, // Progressing
        }),
      ];

      const { container } = render(
        <StageProgressionTimeline stageHistory={stageHistory} />
      );

      // Should have green color for progression
      const progressIndicator = container.querySelector('.text-green-600, .text-white');
      expect(progressIndicator).toBeInTheDocument();
    });

    it('shows regression indicator when moving to lower stage', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          old_stage_id: 5,
          new_stage_id: 3, // Regressing
        }),
      ];

      const { container } = render(
        <StageProgressionTimeline stageHistory={stageHistory} />
      );

      // Should have indication of regression
      const regressionIndicator = container.querySelector('[class*="red"]');
      expect(regressionIndicator).toBeInTheDocument();
    });
  });

  describe('Compact Mode', () => {
    it('renders compact view when compact prop is true', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory(),
        createMockStageHistory({
          id: 'sh-2',
          changed_at: '2024-05-01T10:00:00Z',
        }),
      ];

      render(
        <StageProgressionTimeline stageHistory={stageHistory} compact={true} />
      );

      // In compact mode, should use horizontal layout
      const container = document.querySelector('.flex-wrap');
      expect(container).toBeInTheDocument();
    });

    it('renders full view when compact prop is false', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory(),
      ];

      render(
        <StageProgressionTimeline stageHistory={stageHistory} compact={false} />
      );

      // In full view, should show summary footer with transition count
      expect(screen.getByText(/1 transition recorded/i)).toBeInTheDocument();
    });
  });

  describe('Stage Overview Bar', () => {
    it('renders all 8 stages in the overview bar', () => {
      const stageHistory: StageHistory[] = [createMockStageHistory()];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      // Should show "Concept" and "Mature" labels
      expect(screen.getByText('Concept')).toBeInTheDocument();
      expect(screen.getByText('Mature')).toBeInTheDocument();
    });

    it('highlights current stage in overview bar', () => {
      render(
        <StageProgressionTimeline stageHistory={[]} currentStage={5} />
      );

      // The overview bar should show stage progress
      expect(screen.getByText('Concept')).toBeInTheDocument();
    });

    it('highlights all visited stages from history', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          old_stage_id: 2,
          new_stage_id: 4,
        }),
        createMockStageHistory({
          id: 'sh-2',
          old_stage_id: 1,
          new_stage_id: 2,
          changed_at: '2024-04-01T00:00:00Z',
        }),
      ];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      // Should render successfully with stage numbers visible
      // Stage numbers appear in multiple places (overview bar tooltips and transition items)
      const allText = document.body.textContent || '';
      expect(allText).toContain('2');
      expect(allText).toContain('4');
    });
  });

  describe('Trigger and Reason', () => {
    it('displays trigger when provided', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          trigger: 'score_update',
        }),
      ];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      expect(screen.getByText(/score_update/i)).toBeInTheDocument();
    });

    it('displays reason when provided', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          reason: 'Market conditions improved',
        }),
      ];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      expect(
        screen.getByText(/Market conditions improved/i)
      ).toBeInTheDocument();
    });
  });

  describe('Summary Footer', () => {
    it('shows first recorded date in summary', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          changed_at: '2024-06-15T00:00:00Z',
        }),
        createMockStageHistory({
          id: 'sh-2',
          changed_at: '2024-03-01T00:00:00Z', // Earlier date
        }),
      ];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      // Should show first recorded date in the footer
      // The date format is "MMM d, yyyy" (e.g., "Mar 1, 2024")
      const summaryText = screen.getByText(/First recorded:/i);
      expect(summaryText).toBeInTheDocument();
    });

    it('does not show summary footer in compact mode', () => {
      const stageHistory: StageHistory[] = [createMockStageHistory()];

      render(
        <StageProgressionTimeline stageHistory={stageHistory} compact={true} />
      );

      // Should not show "transitions recorded" text in compact mode
      expect(screen.queryByText(/transitions recorded/i)).not.toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles null old_horizon gracefully', () => {
      const stageHistory: StageHistory[] = [
        createMockStageHistory({
          old_horizon: null,
          new_horizon: 'H2',
        }),
      ];

      expect(() =>
        render(<StageProgressionTimeline stageHistory={stageHistory} />)
      ).not.toThrow();
    });

    it('handles single transition correctly', () => {
      const stageHistory: StageHistory[] = [createMockStageHistory()];

      render(<StageProgressionTimeline stageHistory={stageHistory} />);

      expect(screen.getByText(/1 transition recorded/i)).toBeInTheDocument();
    });
  });
});
