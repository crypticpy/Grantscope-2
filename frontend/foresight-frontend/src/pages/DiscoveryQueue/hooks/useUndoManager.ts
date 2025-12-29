import { useState, useCallback, useRef, useEffect } from 'react';
import type { PendingCard } from '../../../lib/discovery-api';
import { UNDO_TIMEOUT_MS, type UndoAction } from '../types';

/**
 * Return type for useUndoManager hook
 */
export interface UseUndoManagerReturn {
  /** Current undo stack */
  undoStack: UndoAction[];
  /** Push an action onto the undo stack */
  pushToUndoStack: (action: UndoAction) => void;
  /** Undo the most recent action, returns the action that was undone */
  undoLastAction: () => UndoAction | null;
  /** Check if there are any undoable actions */
  canUndo: () => boolean;
  /** Get the most recent undoable action */
  getLastUndoableAction: () => UndoAction | null;
  /** Whether the toast is visible */
  toastVisible: boolean;
  /** Time remaining on toast countdown */
  toastTimeRemaining: number;
  /** Show the undo toast */
  showToast: () => void;
  /** Dismiss the toast manually */
  dismissToast: () => void;
  /** Handle undo from toast (undoes and dismisses) */
  handleUndoFromToast: () => void;
}

/**
 * Hook for managing undo functionality with toast notifications
 *
 * Features:
 * - LIFO undo stack with time-based expiration
 * - Toast notification with countdown timer
 * - Auto-cleanup of expired actions
 *
 * @param onCardRestored - Callback when a card is restored via undo
 * @returns Undo management state and handlers
 */
export function useUndoManager(
  onCardRestored?: (card: PendingCard) => void
): UseUndoManagerReturn {
  // Undo stack - stores recent actions for undo functionality (LIFO order)
  const [undoStack, setUndoStack] = useState<UndoAction[]>([]);

  // Toast state - tracks visibility and countdown timer
  const [toastVisible, setToastVisible] = useState(false);
  const [toastTimeRemaining, setToastTimeRemaining] = useState(UNDO_TIMEOUT_MS);
  const toastTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /**
   * Push an action onto the undo stack
   * Stores the card data so it can be restored if user undoes the action
   */
  const pushToUndoStack = useCallback((action: UndoAction) => {
    setUndoStack((prev) => {
      // Remove any expired actions (older than UNDO_TIMEOUT_MS)
      const now = Date.now();
      const validActions = prev.filter(
        (a) => now - a.timestamp < UNDO_TIMEOUT_MS
      );
      // Add the new action at the end (most recent)
      return [...validActions, action];
    });
  }, []);

  /**
   * Undo the most recent action (LIFO)
   * Returns the action that was undone, or null if no valid action to undo
   */
  const undoLastAction = useCallback((): UndoAction | null => {
    let undoneAction: UndoAction | null = null;

    setUndoStack((prev) => {
      if (prev.length === 0) return prev;

      const now = Date.now();
      // Find the most recent action that's still within the undo window (iterate backwards)
      let lastValidIndex = -1;
      for (let i = prev.length - 1; i >= 0; i--) {
        if (now - prev[i].timestamp < UNDO_TIMEOUT_MS) {
          lastValidIndex = i;
          break;
        }
      }

      if (lastValidIndex === -1) return [];

      // Get the action to undo
      undoneAction = prev[lastValidIndex];

      // Return stack without the undone action
      return prev.slice(0, lastValidIndex);
    });

    // If we found a valid action to undo, notify caller
    if (undoneAction && onCardRestored) {
      onCardRestored(undoneAction.card);
    }

    return undoneAction;
  }, [onCardRestored]);

  /**
   * Check if there are any undoable actions within the time window
   */
  const canUndo = useCallback((): boolean => {
    const now = Date.now();
    return undoStack.some((a) => now - a.timestamp < UNDO_TIMEOUT_MS);
  }, [undoStack]);

  /**
   * Get the most recent undoable action (for displaying in toast)
   */
  const getLastUndoableAction = useCallback((): UndoAction | null => {
    const now = Date.now();
    // Find the most recent action within the undo window
    for (let i = undoStack.length - 1; i >= 0; i--) {
      if (now - undoStack[i].timestamp < UNDO_TIMEOUT_MS) {
        return undoStack[i];
      }
    }
    return null;
  }, [undoStack]);

  /**
   * Show toast with countdown timer
   */
  const showToast = useCallback(() => {
    // Clear any existing timer
    if (toastTimerRef.current) {
      clearInterval(toastTimerRef.current);
    }

    // Show toast and reset timer
    setToastVisible(true);
    setToastTimeRemaining(UNDO_TIMEOUT_MS);

    // Start countdown timer (update every 100ms for smooth animation)
    const startTime = Date.now();
    toastTimerRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, UNDO_TIMEOUT_MS - elapsed);
      setToastTimeRemaining(remaining);

      if (remaining <= 0) {
        setToastVisible(false);
        if (toastTimerRef.current) {
          clearInterval(toastTimerRef.current);
          toastTimerRef.current = null;
        }
      }
    }, 100);
  }, []);

  /**
   * Dismiss toast manually
   */
  const dismissToast = useCallback(() => {
    setToastVisible(false);
    if (toastTimerRef.current) {
      clearInterval(toastTimerRef.current);
      toastTimerRef.current = null;
    }
  }, []);

  /**
   * Handle undo action from toast
   */
  const handleUndoFromToast = useCallback(() => {
    undoLastAction();
    dismissToast();
  }, [undoLastAction, dismissToast]);

  // Cleanup toast timer on unmount
  useEffect(() => {
    return () => {
      if (toastTimerRef.current) {
        clearInterval(toastTimerRef.current);
      }
    };
  }, []);

  return {
    undoStack,
    pushToUndoStack,
    undoLastAction,
    canUndo,
    getLastUndoableAction,
    toastVisible,
    toastTimeRemaining,
    showToast,
    dismissToast,
    handleUndoFromToast,
  };
}

export default useUndoManager;
