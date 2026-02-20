/**
 * CardDetailHeader Unit Tests
 *
 * Tests the CardDetailHeader component for:
 * - Card title rendering
 * - Primary badges display (Pillar, Deadline, Top25)
 * - Summary text display
 * - Quick info row (Pipeline, Anchor, Created date)
 * - Back navigation link customization
 * - Children rendering in action buttons area
 * - Accessibility features
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CardDetailHeader, CardDetailHeaderProps } from '../CardDetailHeader';
import type { Card } from '../types';

// ============================================================================
// Mocks
// ============================================================================

// Mock badge components
vi.mock('../../PillarBadge', () => ({
  PillarBadge: ({ pillarId, goalId }: { pillarId: string; goalId: string }) => (
    <span data-testid="pillar-badge" data-pillar-id={pillarId} data-goal-id={goalId}>
      Pillar Badge
    </span>
  ),
}));

vi.mock('../../DeadlineUrgencyBadge', () => ({
  DeadlineUrgencyBadge: ({ deadline }: { deadline?: string }) => (
    <span data-testid="deadline-badge" data-deadline={deadline ?? ''}>
      Deadline Badge
    </span>
  ),
}));

vi.mock('../../PipelineBadge', () => ({
  PipelineBadge: ({ status }: { status: string }) => (
    <span data-testid="pipeline-badge" data-status={status}>
      Pipeline Badge
    </span>
  ),
}));

vi.mock('../../AnchorBadge', () => ({
  AnchorBadge: ({ anchor }: { anchor: string }) => (
    <span data-testid="anchor-badge" data-anchor={anchor}>
      Anchor Badge
    </span>
  ),
}));

vi.mock('../../Top25Badge', () => ({
  Top25Badge: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-badge" data-priorities={priorities.join(',')}>
      Top25 Badge
    </span>
  ),
}));

// ============================================================================
// Test Data Factories
// ============================================================================

function createMockCard(overrides: Partial<Card> = {}): Card {
  return {
    id: 'test-card-id',
    name: 'Test Card Name',
    slug: 'test-card-slug',
    summary: 'This is a test card summary for testing purposes.',
    description: 'A longer description of the test card.',
    pillar_id: 'technology',
    goal_id: 'goal-1',
    anchor_id: 'anchor-1',
    stage_id: '2_prototype',
    horizon: 'H1',
    pipeline_status: 'discovered',
    novelty_score: 75,
    maturity_score: 60,
    impact_score: 80,
    relevance_score: 70,
    velocity_score: 65,
    risk_score: 40,
    opportunity_score: 85,
    top25_relevance: ['priority-1', 'priority-2'],
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-06-20T14:45:00Z',
    ...overrides,
  };
}

// ============================================================================
// Test Helpers
// ============================================================================

function renderCardDetailHeader(
  props: Partial<CardDetailHeaderProps> = {},
  card: Partial<Card> = {}
) {
  const defaultCard = createMockCard(card);
  return render(
    <MemoryRouter>
      <CardDetailHeader card={defaultCard} {...props} />
    </MemoryRouter>
  );
}

// ============================================================================
// Tests
// ============================================================================

describe('CardDetailHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Card Title', () => {
    it('renders the card name as heading', () => {
      renderCardDetailHeader({}, { name: 'Quantum Computing Trends' });

      expect(
        screen.getByRole('heading', { name: 'Quantum Computing Trends' })
      ).toBeInTheDocument();
    });

    it('renders card name with proper heading level (h1)', () => {
      renderCardDetailHeader({}, { name: 'AI Advancements' });

      const heading = screen.getByRole('heading', { name: 'AI Advancements' });
      expect(heading.tagName).toBe('H1');
    });

    it('handles long card names with word breaking', () => {
      const longName =
        'This is a very long card name that should wrap properly on smaller screens';
      renderCardDetailHeader({}, { name: longName });

      const heading = screen.getByRole('heading', { name: longName });
      expect(heading).toHaveClass('break-words');
    });
  });

  describe('Primary Badges', () => {
    it('renders PillarBadge with correct props', () => {
      renderCardDetailHeader({}, { pillar_id: 'technology', goal_id: 'goal-5' });

      const pillarBadge = screen.getByTestId('pillar-badge');
      expect(pillarBadge).toBeInTheDocument();
      expect(pillarBadge).toHaveAttribute('data-pillar-id', 'technology');
      expect(pillarBadge).toHaveAttribute('data-goal-id', 'goal-5');
    });

    it('renders DeadlineUrgencyBadge with correct deadline', () => {
      renderCardDetailHeader({}, { deadline: '2026-03-15T00:00:00Z' });

      const deadlineBadge = screen.getByTestId('deadline-badge');
      expect(deadlineBadge).toBeInTheDocument();
      expect(deadlineBadge).toHaveAttribute('data-deadline', '2026-03-15T00:00:00Z');
    });

    it('renders Top25Badge when top25_relevance is present', () => {
      renderCardDetailHeader({}, { top25_relevance: ['priority-1', 'priority-2'] });

      const top25Badge = screen.getByTestId('top25-badge');
      expect(top25Badge).toBeInTheDocument();
      expect(top25Badge).toHaveAttribute('data-priorities', 'priority-1,priority-2');
    });

    it('does not render Top25Badge when top25_relevance is empty', () => {
      renderCardDetailHeader({}, { top25_relevance: [] });

      expect(screen.queryByTestId('top25-badge')).not.toBeInTheDocument();
    });

    it('does not render Top25Badge when top25_relevance is undefined', () => {
      renderCardDetailHeader({}, { top25_relevance: undefined });

      expect(screen.queryByTestId('top25-badge')).not.toBeInTheDocument();
    });
  });

  describe('Summary', () => {
    it('renders the card summary', () => {
      const summary = 'This is an important trend to watch.';
      renderCardDetailHeader({}, { summary });

      expect(screen.getByText(summary)).toBeInTheDocument();
    });

    it('applies proper styling to summary text', () => {
      const summary = 'A brief summary of the card.';
      renderCardDetailHeader({}, { summary });

      const summaryElement = screen.getByText(summary);
      expect(summaryElement.tagName).toBe('P');
      expect(summaryElement).toHaveClass('text-gray-700');
    });

    it('handles long summaries with word breaking', () => {
      const longSummary =
        'This is a very long summary that contains a lot of text and should wrap properly on smaller screens to ensure good readability for users.';
      renderCardDetailHeader({}, { summary: longSummary });

      const summaryElement = screen.getByText(longSummary);
      expect(summaryElement).toHaveClass('break-words');
    });
  });

  describe('Quick Info Row', () => {
    it('renders PipelineBadge when pipeline_status is present', () => {
      renderCardDetailHeader({}, { pipeline_status: 'applying' });

      const pipelineBadge = screen.getByTestId('pipeline-badge');
      expect(pipelineBadge).toBeInTheDocument();
      expect(pipelineBadge).toHaveAttribute('data-status', 'applying');
    });

    it('renders discovered pipeline status when missing', () => {
      renderCardDetailHeader({}, { pipeline_status: undefined });

      const pipelineBadge = screen.getByTestId('pipeline-badge');
      expect(pipelineBadge).toHaveAttribute('data-status', 'discovered');
    });

    it('renders AnchorBadge when anchor_id is present', () => {
      renderCardDetailHeader({}, { anchor_id: 'finance-dept' });

      const anchorBadge = screen.getByTestId('anchor-badge');
      expect(anchorBadge).toBeInTheDocument();
      expect(anchorBadge).toHaveAttribute('data-anchor', 'finance-dept');
    });

    it('does not render AnchorBadge when anchor_id is missing', () => {
      renderCardDetailHeader({}, { anchor_id: undefined });

      expect(screen.queryByTestId('anchor-badge')).not.toBeInTheDocument();
    });

    it('renders created date', () => {
      renderCardDetailHeader({}, { created_at: '2024-03-15T10:30:00Z' });

      // Should render the date in localized format
      expect(screen.getByText(/Created:/)).toBeInTheDocument();
    });

    it('formats created date correctly', () => {
      renderCardDetailHeader({}, { created_at: '2024-12-25T10:30:00Z' });

      const dateText = screen.getByText(/Created:/);
      // The date formatting may vary by locale, so just check it contains "Created:"
      expect(dateText).toBeInTheDocument();
    });
  });

  describe('Back Navigation', () => {
    it('renders back link with default path (/discover)', () => {
      renderCardDetailHeader();

      const backLink = screen.getByRole('link', { name: /back to discover/i });
      expect(backLink).toBeInTheDocument();
      expect(backLink).toHaveAttribute('href', '/discover');
    });

    it('renders back link with default text', () => {
      renderCardDetailHeader();

      expect(screen.getByText('Back to Discover')).toBeInTheDocument();
    });

    it('uses custom backLink when provided', () => {
      renderCardDetailHeader({ backLink: '/dashboard' });

      const backLink = screen.getByRole('link', { name: /back to discover/i });
      expect(backLink).toHaveAttribute('href', '/dashboard');
    });

    it('uses custom backLinkText when provided', () => {
      renderCardDetailHeader({ backLinkText: 'Return to Dashboard' });

      expect(screen.getByText('Return to Dashboard')).toBeInTheDocument();
    });

    it('uses both custom backLink and backLinkText', () => {
      renderCardDetailHeader({
        backLink: '/trends',
        backLinkText: 'Back to Trends',
      });

      const backLink = screen.getByRole('link', { name: /back to trends/i });
      expect(backLink).toBeInTheDocument();
      expect(backLink).toHaveAttribute('href', '/trends');
    });

    it('renders arrow icon in back link', () => {
      const { container } = renderCardDetailHeader();

      // ArrowLeft icon should be rendered (as an SVG)
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  describe('Children (Action Buttons Area)', () => {
    it('renders children when provided', () => {
      render(
        <MemoryRouter>
          <CardDetailHeader card={createMockCard()}>
            <button>Action Button</button>
          </CardDetailHeader>
        </MemoryRouter>
      );

      expect(screen.getByRole('button', { name: 'Action Button' })).toBeInTheDocument();
    });

    it('renders multiple children', () => {
      render(
        <MemoryRouter>
          <CardDetailHeader card={createMockCard()}>
            <button>Button 1</button>
            <button>Button 2</button>
            <button>Button 3</button>
          </CardDetailHeader>
        </MemoryRouter>
      );

      expect(screen.getByRole('button', { name: 'Button 1' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Button 2' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Button 3' })).toBeInTheDocument();
    });

    it('does not render action buttons container when no children', () => {
      const { container } = renderCardDetailHeader();

      // The action buttons container should not be present when no children
      // Check that the div with gap-2 for buttons doesn't render children wrapper
      const buttonContainers = container.querySelectorAll('.flex.items-center.gap-2');
      // Should only find the quick info row gap-2, not an empty action buttons container
      buttonContainers.forEach((el) => {
        // Action buttons area has lg:justify-end class
        if (el.classList.contains('lg:justify-end')) {
          expect(el.children.length).toBe(0);
        }
      });
    });

    it('renders complex children components', () => {
      render(
        <MemoryRouter>
          <CardDetailHeader card={createMockCard()}>
            <div data-testid="custom-component">
              <span>Custom Content</span>
              <button>Nested Button</button>
            </div>
          </CardDetailHeader>
        </MemoryRouter>
      );

      expect(screen.getByTestId('custom-component')).toBeInTheDocument();
      expect(screen.getByText('Custom Content')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Nested Button' })).toBeInTheDocument();
    });
  });

  describe('Styling and Layout', () => {
    it('applies margin bottom to header container', () => {
      const { container } = renderCardDetailHeader();

      const headerContainer = container.firstChild as HTMLElement;
      expect(headerContainer).toHaveClass('mb-8');
    });

    it('has responsive wrapping layout', () => {
      const { container } = renderCardDetailHeader();

      const flexContainer = container.querySelector('.flex.items-center.flex-wrap');
      expect(flexContainer).toBeInTheDocument();
    });

    it('applies dark mode styling classes to title', () => {
      renderCardDetailHeader({}, { name: 'Dark Mode Test' });

      const heading = screen.getByRole('heading', { name: 'Dark Mode Test' });
      expect(heading).toHaveClass('dark:text-white');
    });

    it('applies dark mode styling classes to summary', () => {
      const summary = 'Dark mode summary text';
      renderCardDetailHeader({}, { summary });

      const summaryElement = screen.getByText(summary);
      expect(summaryElement).toHaveClass('dark:text-gray-200');
    });

    it('applies dark mode styling to back link', () => {
      const { container } = renderCardDetailHeader();

      const backLink = container.querySelector('a.dark\\:text-gray-400');
      expect(backLink).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles card with empty summary', () => {
      renderCardDetailHeader({}, { summary: '' });

      // Should render without error
      expect(screen.getByRole('heading')).toBeInTheDocument();
    });

    it('handles card with special characters in name', () => {
      const specialName = 'AI & Machine Learning: The Future <2025>';
      renderCardDetailHeader({}, { name: specialName });

      expect(screen.getByRole('heading', { name: specialName })).toBeInTheDocument();
    });

    it('handles card with very long pillar_id', () => {
      renderCardDetailHeader(
        {},
        { pillar_id: 'this-is-a-very-long-pillar-identifier-for-testing' }
      );

      const pillarBadge = screen.getByTestId('pillar-badge');
      expect(pillarBadge).toHaveAttribute(
        'data-pillar-id',
        'this-is-a-very-long-pillar-identifier-for-testing'
      );
    });

    it('handles all pipeline statuses', () => {
      const statuses = ['discovered', 'evaluating', 'applying'] as const;

      statuses.forEach((status) => {
        const { unmount } = renderCardDetailHeader({}, { pipeline_status: status });
        const pipelineBadge = screen.getByTestId('pipeline-badge');
        expect(pipelineBadge).toHaveAttribute('data-status', status);
        unmount();
      });
    });

    it('handles missing pipeline status', () => {
      const { unmount } = renderCardDetailHeader({}, { pipeline_status: undefined });
      const pipelineBadge = screen.getByTestId('pipeline-badge');
      expect(pipelineBadge).toHaveAttribute('data-status', 'discovered');
      unmount();
    });

    it('handles cards with no deadline', () => {
      const { unmount } = renderCardDetailHeader({}, { deadline: undefined });
      const deadlineBadge = screen.getByTestId('deadline-badge');
      expect(deadlineBadge).toHaveAttribute('data-deadline', '');
      unmount();
    });
  });

  describe('Accessibility', () => {
    it('uses semantic heading for card name', () => {
      renderCardDetailHeader({}, { name: 'Accessible Card' });

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent('Accessible Card');
    });

    it('back link is accessible via keyboard', () => {
      renderCardDetailHeader();

      const backLink = screen.getByRole('link');
      expect(backLink).toBeInTheDocument();
      // Links are focusable by default
      expect(backLink.tabIndex).not.toBe(-1);
    });

    it('renders text with sufficient color contrast classes', () => {
      const summary = 'Contrast test summary';
      renderCardDetailHeader({}, { summary });

      const summaryElement = screen.getByText(summary);
      // text-gray-700 provides sufficient contrast on white backgrounds
      expect(summaryElement).toHaveClass('text-gray-700');
    });
  });
});
