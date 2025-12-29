/**
 * Discover Page Utilities
 *
 * Utility functions for the Discover page.
 */

import { format, formatDistanceToNow } from 'date-fns';
import type { SortOption } from './types';

/**
 * Get color classes for score values
 * Green for high (80+), amber for medium (60-79), red for low (<60)
 */
export const getScoreColorClasses = (score: number): string => {
  if (score >= 80) return 'text-green-600 dark:text-green-400';
  if (score >= 60) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
};

/**
 * Get sort configuration based on selected sort option
 */
export const getSortConfig = (option: SortOption): { column: string; ascending: boolean } => {
  switch (option) {
    case 'oldest':
      return { column: 'created_at', ascending: true };
    case 'recently_updated':
      return { column: 'updated_at', ascending: false };
    case 'least_recently_updated':
      return { column: 'updated_at', ascending: true };
    case 'newest':
    default:
      return { column: 'created_at', ascending: false };
  }
};

/**
 * Format card date for display
 * Shows relative time for recent updates, absolute date for creation
 */
export const formatCardDate = (createdAt: string, updatedAt?: string): { label: string; text: string } => {
  try {
    const created = new Date(createdAt);
    const updated = updatedAt ? new Date(updatedAt) : null;

    // If updated_at exists and is different from created_at (more than 1 minute difference)
    if (updated && Math.abs(updated.getTime() - created.getTime()) > 60000) {
      return {
        label: 'Updated',
        text: formatDistanceToNow(updated, { addSuffix: true })
      };
    }

    // Fall back to created_at with absolute date format
    return {
      label: 'Created',
      text: format(created, 'MMM d, yyyy')
    };
  } catch {
    // Handle invalid dates gracefully
    return {
      label: 'Created',
      text: 'Unknown'
    };
  }
};

/**
 * Format relative time for history entries
 */
export const formatHistoryTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString();
};
