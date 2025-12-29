import type { PendingCard, DismissReason } from '../../lib/discovery-api';

/**
 * Pillar data structure
 */
export interface Pillar {
  id: string;
  name: string;
  color: string;
}

/**
 * Confidence filter options
 */
export type ConfidenceFilter = 'all' | 'high' | 'medium' | 'low';

/**
 * Undo action types for tracking user actions
 */
export type UndoActionType = 'approve' | 'reject' | 'dismiss' | 'defer';

/**
 * Represents an action that can be undone
 * Stores the action type, affected card, and timestamp for time-limited undo
 */
export interface UndoAction {
  type: UndoActionType;
  card: PendingCard;
  timestamp: number;
  /** Optional dismiss reason if action was a dismissal */
  dismissReason?: DismissReason;
}

/**
 * Maximum time window (in ms) during which an action can be undone
 */
export const UNDO_TIMEOUT_MS = 5000;

/**
 * Minimum interval (in ms) between keyboard actions to prevent double-execution
 * from rapid key presses
 */
export const ACTION_DEBOUNCE_MS = 300;

/**
 * Mobile-optimized swipe configuration constants
 * Higher thresholds on mobile prevent accidental triggers during vertical scrolling
 */
export const SWIPE_CONFIG = {
  /** Minimum swipe distance for mobile (higher to prevent accidental triggers) */
  mobileDistance: 80,
  /** Minimum swipe distance for desktop */
  desktopDistance: 50,
  /** Minimum velocity threshold for swipe detection */
  velocity: 0.3,
  /** Maximum angle from horizontal (in degrees) to count as a swipe */
  maxAngle: 30,
  /** Offset threshold to show visual feedback */
  feedbackThreshold: 25,
  /** Offset threshold to show "will trigger" state */
  triggerThreshold: 60,
  /** Damping factor for card movement (0-1, lower = more resistance) */
  damping: 0.4,
} as const;
