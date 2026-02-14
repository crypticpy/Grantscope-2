/**
 * CardDescription Component
 *
 * Displays the description panel for a card in the Overview tab.
 * Renders markdown content with full styling support, falling back
 * to plain text for non-markdown descriptions.
 *
 * Includes a version history badge when snapshots exist, allowing
 * users to browse and restore previous description versions.
 *
 * @module CardDetail/tabs/OverviewTab/CardDescription
 */

import React, { useState, useEffect, useCallback } from "react";
import { MarkdownReport } from "../../MarkdownReport";
import { DescriptionHistory } from "./DescriptionHistory";
import { fetchCardSnapshots } from "../../../../lib/discovery-api";
import { supabase } from "../../../../App";

/**
 * Props for the CardDescription component
 */
export interface CardDescriptionProps {
  /**
   * The description text to display. Supports markdown formatting.
   */
  description: string;

  /**
   * Card ID for fetching version history
   */
  cardId?: string;

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;

  /**
   * Optional title for the panel (defaults to "Description")
   */
  title?: string;

  /**
   * Callback when a version is restored (to refresh card data)
   */
  onRestore?: () => void;
}

/**
 * Returns true if the text likely contains markdown formatting.
 */
function containsMarkdown(text: string): boolean {
  return /(?:^#{1,4}\s|\*\*|^- |^\d+\. |^>\s|\[.*\]\(.*\)|```)/m.test(text);
}

export const CardDescription: React.FC<CardDescriptionProps> = ({
  description,
  cardId,
  className = "",
  title = "Description",
  onRestore,
}) => {
  const [snapshotCount, setSnapshotCount] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);

  const loadSnapshotCount = useCallback(async () => {
    if (!cardId) return;
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session?.access_token) {
        const result = await fetchCardSnapshots(
          session.access_token,
          cardId,
          "description",
        );
        setSnapshotCount(result.snapshots.length);
      }
    } catch {
      // Silently handle
    }
  }, [cardId]);

  useEffect(() => {
    loadSnapshotCount();
  }, [loadSnapshotCount]);

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
    <>
      <div
        className={`bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6 ${className}`}
      >
        <div className="flex items-center justify-between mb-3 sm:mb-4">
          <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white">
            {title}
          </h2>
          {cardId && snapshotCount > 0 && (
            <button
              onClick={() => setHistoryOpen(true)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
              title="View description version history"
            >
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              v{snapshotCount + 1}
            </button>
          )}
        </div>
        {isMarkdown ? (
          <MarkdownReport content={description} />
        ) : (
          <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words text-sm sm:text-base">
            {description}
          </p>
        )}
      </div>

      {cardId && (
        <DescriptionHistory
          cardId={cardId}
          isOpen={historyOpen}
          onClose={() => setHistoryOpen(false)}
          onRestore={() => {
            onRestore?.();
            loadSnapshotCount();
          }}
        />
      )}
    </>
  );
};

export default CardDescription;
