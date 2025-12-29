import type { PendingCard } from '../../lib/discovery-api';
import type { ConfidenceFilter } from './types';

/**
 * Format date for display
 */
export const formatDiscoveredDate = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString();
};

/**
 * Filter cards by confidence level
 */
export const filterByConfidence = (cards: PendingCard[], filter: ConfidenceFilter): PendingCard[] => {
  if (filter === 'all') return cards;
  return cards.filter((card) => {
    if (filter === 'high') return card.ai_confidence >= 0.9;
    if (filter === 'medium') return card.ai_confidence >= 0.7 && card.ai_confidence < 0.9;
    return card.ai_confidence < 0.7;
  });
};

/**
 * Impact level info for styling and display
 */
export interface ImpactLevelInfo {
  level: 'high' | 'medium' | 'low';
  label: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

/**
 * Get impact score level and styling
 */
export function getImpactLevel(score: number): ImpactLevelInfo {
  if (score >= 70) {
    return {
      level: 'high',
      label: 'High Impact',
      description: 'This discovery could significantly influence strategy or decision-making.',
      color: 'text-purple-600 dark:text-purple-400',
      bgColor: 'bg-purple-100 dark:bg-purple-900/30',
      borderColor: 'border-purple-300 dark:border-purple-700',
    };
  }
  if (score >= 40) {
    return {
      level: 'medium',
      label: 'Moderate Impact',
      description: 'This discovery has notable strategic relevance and may influence planning.',
      color: 'text-indigo-600 dark:text-indigo-400',
      bgColor: 'bg-indigo-100 dark:bg-indigo-900/30',
      borderColor: 'border-indigo-300 dark:border-indigo-700',
    };
  }
  return {
    level: 'low',
    label: 'Lower Impact',
    description: 'This discovery provides background information with limited immediate strategic value.',
    color: 'text-slate-600 dark:text-slate-400',
    bgColor: 'bg-slate-100 dark:bg-slate-900/30',
    borderColor: 'border-slate-300 dark:border-slate-700',
  };
}
