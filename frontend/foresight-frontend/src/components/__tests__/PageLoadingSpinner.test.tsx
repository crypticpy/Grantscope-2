/**
 * PageLoadingSpinner Unit Tests
 *
 * Tests the PageLoadingSpinner component for:
 * - Basic rendering
 * - Custom message prop
 * - Size variants (sm, md, lg)
 * - Custom className support
 * - Accessibility attributes
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PageLoadingSpinner } from '../PageLoadingSpinner';

// ============================================================================
// Tests
// ============================================================================

describe('PageLoadingSpinner', () => {
  describe('Rendering', () => {
    it('renders spinner container with default props', () => {
      render(<PageLoadingSpinner />);

      const container = screen.getByRole('status');
      expect(container).toBeInTheDocument();
    });

    it('renders spinner element with animation class', () => {
      const { container } = render(<PageLoadingSpinner />);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('renders with brand-blue border', () => {
      const { container } = render(<PageLoadingSpinner />);

      const spinner = container.querySelector('.border-brand-blue');
      expect(spinner).toBeInTheDocument();
    });

    it('renders full-height container', () => {
      const { container } = render(<PageLoadingSpinner />);

      expect(container.firstChild).toHaveClass('min-h-screen');
    });

    it('has centered content', () => {
      const { container } = render(<PageLoadingSpinner />);

      expect(container.firstChild).toHaveClass('items-center', 'justify-center');
    });
  });

  describe('Message Prop', () => {
    it('renders without message by default', () => {
      render(<PageLoadingSpinner />);

      // Should not have a visible message text (only sr-only)
      expect(screen.queryByText('Loading page content...')).toHaveClass('sr-only');
    });

    it('renders custom message when provided', () => {
      const { container } = render(<PageLoadingSpinner message="Loading dashboard..." />);

      // Message appears in both visible paragraph and sr-only span
      const visibleMessage = container.querySelector('p.mt-4');
      expect(visibleMessage).toHaveTextContent('Loading dashboard...');
    });

    it('displays message in paragraph element', () => {
      const { container } = render(<PageLoadingSpinner message="Please wait..." />);

      const message = container.querySelector('p.mt-4');
      expect(message).toBeInTheDocument();
      expect(message?.tagName.toLowerCase()).toBe('p');
    });

    it('applies correct styling to message', () => {
      const { container } = render(<PageLoadingSpinner message="Loading..." />);

      const message = container.querySelector('p.mt-4');
      expect(message).toHaveClass('mt-4', 'text-sm');
    });
  });

  describe('Size Prop', () => {
    it('uses large size by default', () => {
      const { container } = render(<PageLoadingSpinner />);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('h-32', 'w-32');
    });

    it('renders small size when size="sm"', () => {
      const { container } = render(<PageLoadingSpinner size="sm" />);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('h-16', 'w-16');
    });

    it('renders medium size when size="md"', () => {
      const { container } = render(<PageLoadingSpinner size="md" />);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('h-24', 'w-24');
    });

    it('renders large size when size="lg"', () => {
      const { container } = render(<PageLoadingSpinner size="lg" />);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('h-32', 'w-32');
    });
  });

  describe('Custom ClassName', () => {
    it('accepts custom className', () => {
      const { container } = render(
        <PageLoadingSpinner className="custom-class" />
      );

      expect(container.querySelector('.custom-class')).toBeInTheDocument();
    });

    it('merges custom className with existing classes', () => {
      const { container } = render(
        <PageLoadingSpinner className="custom-test-class" />
      );

      const spinnerContainer = container.firstChild;
      expect(spinnerContainer).toHaveClass('min-h-screen');
      expect(spinnerContainer).toHaveClass('custom-test-class');
    });
  });

  describe('Accessibility', () => {
    it('has role="status" for screen readers', () => {
      render(<PageLoadingSpinner />);

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has aria-label for default state', () => {
      render(<PageLoadingSpinner />);

      const container = screen.getByRole('status');
      expect(container).toHaveAttribute('aria-label', 'Loading');
    });

    it('uses custom message for aria-label when provided', () => {
      render(<PageLoadingSpinner message="Loading analytics..." />);

      const container = screen.getByRole('status');
      expect(container).toHaveAttribute('aria-label', 'Loading analytics...');
    });

    it('has aria-live="polite" for live region', () => {
      render(<PageLoadingSpinner />);

      const container = screen.getByRole('status');
      expect(container).toHaveAttribute('aria-live', 'polite');
    });

    it('has aria-hidden="true" on spinner element', () => {
      const { container } = render(<PageLoadingSpinner />);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveAttribute('aria-hidden', 'true');
    });

    it('provides screen reader text', () => {
      render(<PageLoadingSpinner />);

      const srText = screen.getByText('Loading page content...');
      expect(srText).toHaveClass('sr-only');
    });

    it('uses custom message in screen reader text when provided', () => {
      const { container } = render(<PageLoadingSpinner message="Loading cards..." />);

      const srText = container.querySelector('.sr-only');
      expect(srText).toHaveTextContent('Loading cards...');
    });
  });

  describe('Dark Mode Support', () => {
    it('has dark mode background class', () => {
      const { container } = render(<PageLoadingSpinner />);

      expect(container.firstChild).toHaveClass('dark:bg-brand-dark-blue');
    });

    it('has dark mode text classes for message', () => {
      const { container } = render(<PageLoadingSpinner message="Loading..." />);

      const message = container.querySelector('p');
      expect(message).toBeInTheDocument();
      // Check that the paragraph has the dark mode class in its class list
      expect(message?.className).toContain('dark:text-gray-400');
    });
  });
});
