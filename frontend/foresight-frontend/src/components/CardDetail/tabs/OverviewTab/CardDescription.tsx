/**
 * CardDescription Component
 *
 * Displays the description panel for a card in the Overview tab.
 * Renders markdown content with full styling support, falling back
 * to plain text for non-markdown descriptions.
 *
 * @module CardDetail/tabs/OverviewTab/CardDescription
 */

import React from "react";
import { MarkdownReport } from "../../MarkdownReport";

/**
 * Props for the CardDescription component
 */
export interface CardDescriptionProps {
  /**
   * The description text to display. Supports markdown formatting.
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
 * Returns true if the text likely contains markdown formatting.
 */
function containsMarkdown(text: string): boolean {
  return /(?:^#{1,4}\s|\*\*|^- |^\d+\. |^>\s|\[.*\]\(.*\)|```)/m.test(text);
}

export const CardDescription: React.FC<CardDescriptionProps> = ({
  description,
  className = "",
  title = "Description",
}) => {
  if (!description || !description.trim()) {
    return (
      <div
        className={`bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6 ${className}`}
      >
        <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
          {title}
        </h2>
        <p className="text-gray-500 dark:text-gray-400 italic text-sm sm:text-base">
          No description available.
        </p>
      </div>
    );
  }

  const isMarkdown = containsMarkdown(description);

  return (
    <div
      className={`bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6 ${className}`}
    >
      <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">
        {title}
      </h2>
      {isMarkdown ? (
        <MarkdownReport content={description} />
      ) : (
        <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words text-sm sm:text-base">
          {description}
        </p>
      )}
    </div>
  );
};

export default CardDescription;
