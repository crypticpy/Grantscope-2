/**
 * CardDescription Component
 *
 * Displays the description panel for a card in the Overview tab.
 * Shows the full description text with proper styling and dark mode support.
 *
 * @module CardDetail/tabs/OverviewTab/CardDescription
 */

import React from 'react';

/**
 * Props for the CardDescription component
 */
export interface CardDescriptionProps {
  /**
   * The description text to display.
   * Will be rendered with whitespace preserved and word breaks.
   */
  description: string;

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;

  /**
   * Optional title for the panel (defaults to "Description")
   */
  title?: string;
}

/**
 * CardDescription displays the description panel for a card.
 *
 * Features:
 * - Responsive text sizing (smaller on mobile)
 * - Dark mode support with appropriate color scheme
 * - Preserved whitespace formatting for multi-line descriptions
 * - Word breaking for long text to prevent overflow
 *
 * @example
 * ```tsx
 * <CardDescription
 *   description="This is a detailed description of the trend..."
 * />
 * ```
 *
 * @example
 * ```tsx
 * <CardDescription
 *   description={card.description}
 *   title="About This Trend"
 *   className="mt-4"
 * />
 * ```
 */
export const CardDescription: React.FC<CardDescriptionProps> = ({
  description,
  className = '',
  title = 'Description',
}) => {
  return (
    <div
      className={`bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6 ${className}`}
    >
      <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
        {title}
      </h2>
      <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words text-sm sm:text-base">
        {description}
      </p>
    </div>
  );
};

export default CardDescription;
