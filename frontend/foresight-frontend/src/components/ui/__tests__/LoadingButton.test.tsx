/**
 * LoadingButton Unit Tests
 *
 * Tests the LoadingButton component for:
 * - Basic rendering
 * - Loading state with spinner
 * - Loading text display
 * - Button disabled during loading
 * - All variants (primary, secondary, danger)
 * - All sizes (sm, md, lg)
 * - Click handler behavior
 * - Accessibility attributes
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LoadingButton } from '../LoadingButton';

// ============================================================================
// Rendering Tests
// ============================================================================

describe('LoadingButton', () => {
  describe('Rendering', () => {
    it('renders children in default state', () => {
      render(<LoadingButton>Submit</LoadingButton>);

      expect(screen.getByRole('button')).toHaveTextContent('Submit');
    });

    it('renders as a button element', () => {
      render(<LoadingButton>Click me</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button.tagName).toBe('BUTTON');
    });

    it('renders with default primary variant styles', () => {
      render(<LoadingButton>Submit</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-brand-blue');
      expect(button).toHaveClass('text-white');
    });

    it('renders with default md size styles', () => {
      render(<LoadingButton>Submit</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('px-4', 'py-2', 'text-sm');
    });

    it('is not disabled by default', () => {
      render(<LoadingButton>Submit</LoadingButton>);

      expect(screen.getByRole('button')).not.toBeDisabled();
    });

    it('does not show spinner in default state', () => {
      const { container } = render(<LoadingButton>Submit</LoadingButton>);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).not.toBeInTheDocument();
    });
  });

  // ============================================================================
  // Loading State Tests
  // ============================================================================

  describe('Loading State', () => {
    it('renders spinner when loading=true', () => {
      const { container } = render(
        <LoadingButton loading>Submit</LoadingButton>
      );

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('spinner has aria-hidden="true"', () => {
      const { container } = render(
        <LoadingButton loading>Submit</LoadingButton>
      );

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveAttribute('aria-hidden', 'true');
    });

    it('displays children when loading without loadingText', () => {
      render(<LoadingButton loading>Submit</LoadingButton>);

      expect(screen.getByRole('button')).toHaveTextContent('Submit');
    });

    it('displays loadingText when provided during loading', () => {
      render(
        <LoadingButton loading loadingText="Submitting...">
          Submit
        </LoadingButton>
      );

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Submitting...');
      expect(button).not.toHaveTextContent(/^Submit$/);
    });

    it('ignores loadingText when not loading', () => {
      render(
        <LoadingButton loadingText="Submitting...">Submit</LoadingButton>
      );

      expect(screen.getByRole('button')).toHaveTextContent('Submit');
    });

    it('button is disabled when loading', () => {
      render(<LoadingButton loading>Submit</LoadingButton>);

      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('button is disabled when both loading and disabled props are true', () => {
      render(
        <LoadingButton loading disabled>
          Submit
        </LoadingButton>
      );

      expect(screen.getByRole('button')).toBeDisabled();
    });
  });

  // ============================================================================
  // Variant Tests
  // ============================================================================

  describe('Variants', () => {
    it('applies primary variant styles', () => {
      render(<LoadingButton variant="primary">Primary</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-brand-blue');
      expect(button).toHaveClass('text-white');
      expect(button).toHaveClass('hover:bg-brand-dark-blue');
    });

    it('applies secondary variant styles', () => {
      render(<LoadingButton variant="secondary">Secondary</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-white');
      expect(button).toHaveClass('text-gray-700');
      expect(button).toHaveClass('border');
      expect(button).toHaveClass('border-gray-300');
    });

    it('applies danger variant styles', () => {
      render(<LoadingButton variant="danger">Delete</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-red-600');
      expect(button).toHaveClass('text-white');
      expect(button).toHaveClass('hover:bg-red-700');
    });

    it('applies secondary variant dark mode styles', () => {
      render(<LoadingButton variant="secondary">Secondary</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('dark:bg-[#3d4176]');
      expect(button).toHaveClass('dark:text-gray-300');
    });

    it('applies danger variant dark mode styles', () => {
      render(<LoadingButton variant="danger">Delete</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('dark:bg-red-700');
      expect(button).toHaveClass('dark:hover:bg-red-800');
    });
  });

  // ============================================================================
  // Size Tests
  // ============================================================================

  describe('Sizes', () => {
    it('applies sm size styles', () => {
      render(<LoadingButton size="sm">Small</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('px-3', 'py-1.5', 'text-sm');
    });

    it('applies md size styles', () => {
      render(<LoadingButton size="md">Medium</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('px-4', 'py-2', 'text-sm');
    });

    it('applies lg size styles', () => {
      render(<LoadingButton size="lg">Large</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('px-6', 'py-3', 'text-base');
    });

    it('spinner uses smaller size for sm buttons', () => {
      const { container } = render(
        <LoadingButton size="sm" loading>
          Small
        </LoadingButton>
      );

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('h-3.5', 'w-3.5');
    });

    it('spinner uses default size for md buttons', () => {
      const { container } = render(
        <LoadingButton size="md" loading>
          Medium
        </LoadingButton>
      );

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('h-4', 'w-4');
    });

    it('spinner uses default size for lg buttons', () => {
      const { container } = render(
        <LoadingButton size="lg" loading>
          Large
        </LoadingButton>
      );

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('h-4', 'w-4');
    });
  });

  // ============================================================================
  // Click Handler Tests
  // ============================================================================

  describe('Click Handling', () => {
    it('calls onClick handler when clicked', () => {
      const handleClick = vi.fn();
      render(<LoadingButton onClick={handleClick}>Click me</LoadingButton>);

      fireEvent.click(screen.getByRole('button'));
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('does not call onClick when loading', () => {
      const handleClick = vi.fn();
      render(
        <LoadingButton onClick={handleClick} loading>
          Click me
        </LoadingButton>
      );

      fireEvent.click(screen.getByRole('button'));
      expect(handleClick).not.toHaveBeenCalled();
    });

    it('does not call onClick when disabled', () => {
      const handleClick = vi.fn();
      render(
        <LoadingButton onClick={handleClick} disabled>
          Click me
        </LoadingButton>
      );

      fireEvent.click(screen.getByRole('button'));
      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Accessibility Tests
  // ============================================================================

  describe('Accessibility', () => {
    it('has aria-busy="true" when loading', () => {
      render(<LoadingButton loading>Submit</LoadingButton>);

      expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
    });

    it('has aria-busy="false" when not loading', () => {
      render(<LoadingButton>Submit</LoadingButton>);

      expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'false');
    });

    it('has aria-disabled="true" when loading', () => {
      render(<LoadingButton loading>Submit</LoadingButton>);

      expect(screen.getByRole('button')).toHaveAttribute(
        'aria-disabled',
        'true'
      );
    });

    it('has aria-disabled="true" when disabled', () => {
      render(<LoadingButton disabled>Submit</LoadingButton>);

      expect(screen.getByRole('button')).toHaveAttribute(
        'aria-disabled',
        'true'
      );
    });

    it('has aria-disabled="false" when not disabled and not loading', () => {
      render(<LoadingButton>Submit</LoadingButton>);

      expect(screen.getByRole('button')).toHaveAttribute(
        'aria-disabled',
        'false'
      );
    });

    it('supports custom aria-label', () => {
      render(
        <LoadingButton aria-label="Submit form">Submit</LoadingButton>
      );

      expect(screen.getByRole('button')).toHaveAttribute(
        'aria-label',
        'Submit form'
      );
    });

    it('has focus ring styles for keyboard navigation', () => {
      render(<LoadingButton>Submit</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('focus:outline-none');
      expect(button).toHaveClass('focus:ring-2');
      expect(button).toHaveClass('focus:ring-offset-2');
    });

    it('has dark mode focus ring offset', () => {
      render(<LoadingButton>Submit</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('dark:focus:ring-offset-[#2d3166]');
    });
  });

  // ============================================================================
  // Custom ClassName Tests
  // ============================================================================

  describe('Custom ClassName', () => {
    it('accepts custom className', () => {
      render(
        <LoadingButton className="custom-class">Submit</LoadingButton>
      );

      expect(screen.getByRole('button')).toHaveClass('custom-class');
    });

    it('merges custom className with existing classes', () => {
      render(<LoadingButton className="w-full">Submit</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('w-full');
      expect(button).toHaveClass('bg-brand-blue'); // Default variant
    });
  });

  // ============================================================================
  // Disabled State Tests
  // ============================================================================

  describe('Disabled State', () => {
    it('applies disabled styles when disabled', () => {
      render(<LoadingButton disabled>Submit</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('disabled:opacity-50');
      expect(button).toHaveClass('disabled:cursor-not-allowed');
    });

    it('applies disabled styles when loading', () => {
      render(<LoadingButton loading>Submit</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('disabled:opacity-50');
      expect(button).toHaveClass('disabled:cursor-not-allowed');
    });
  });

  // ============================================================================
  // Dark Mode Support Tests
  // ============================================================================

  describe('Dark Mode Support', () => {
    it('has dark mode focus ring offset for primary variant', () => {
      render(<LoadingButton variant="primary">Submit</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('dark:focus:ring-offset-[#2d3166]');
    });

    it('has dark mode styles for secondary variant', () => {
      render(<LoadingButton variant="secondary">Cancel</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('dark:bg-[#3d4176]');
      expect(button).toHaveClass('dark:text-gray-300');
      expect(button).toHaveClass('dark:border-gray-600');
      expect(button).toHaveClass('dark:hover:bg-[#4d5186]');
    });

    it('has dark mode styles for danger variant', () => {
      render(<LoadingButton variant="danger">Delete</LoadingButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('dark:bg-red-700');
      expect(button).toHaveClass('dark:hover:bg-red-800');
    });
  });

  // ============================================================================
  // Ref Forwarding Tests
  // ============================================================================

  describe('Ref Forwarding', () => {
    it('forwards ref to button element', () => {
      const ref = vi.fn();
      render(<LoadingButton ref={ref}>Submit</LoadingButton>);

      expect(ref).toHaveBeenCalled();
      expect(ref.mock.calls[0][0]).toBeInstanceOf(HTMLButtonElement);
    });
  });

  // ============================================================================
  // Type Attribute Tests
  // ============================================================================

  describe('Type Attribute', () => {
    it('supports type="submit"', () => {
      render(<LoadingButton type="submit">Submit</LoadingButton>);

      expect(screen.getByRole('button')).toHaveAttribute('type', 'submit');
    });

    it('supports type="button"', () => {
      render(<LoadingButton type="button">Click</LoadingButton>);

      expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
    });

    it('supports type="reset"', () => {
      render(<LoadingButton type="reset">Reset</LoadingButton>);

      expect(screen.getByRole('button')).toHaveAttribute('type', 'reset');
    });
  });
});
