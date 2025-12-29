/**
 * DiscoveryQueue Page
 *
 * A modular page component for reviewing AI-discovered cards before they're
 * added to the intelligence library. Supports keyboard shortcuts, swipe gestures,
 * bulk actions, and undo functionality.
 *
 * @module DiscoveryQueue
 *
 * Directory Structure:
 * - index.tsx - Main page component (this file)
 * - types.ts - TypeScript interfaces and constants
 * - utils.ts - Utility functions (date formatting, filtering, impact levels)
 * - components/ - Reusable UI components
 *   - ImpactScoreBadge.tsx - Impact score indicator with tooltip
 *   - SwipeableCard.tsx - Touch gesture wrapper for mobile swipe actions
 *   - UndoToast.tsx - Undo notification with countdown timer
 * - hooks/ - Custom React hooks
 *   - useUndoManager.ts - Undo stack and toast state management
 *
 * @example
 * ```tsx
 * import DiscoveryQueue from '@/pages/DiscoveryQueue';
 *
 * // In router
 * <Route path="/discover/queue" element={<DiscoveryQueue />} />
 * ```
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useHotkeys } from 'react-hotkeys-hook';
import * as Progress from '@radix-ui/react-progress';
import {
  Search,
  CheckCircle,
  XCircle,
  Edit3,
  Clock,
  Inbox,
  RefreshCw,
  AlertTriangle,
  Sparkles,
  MoreHorizontal,
} from 'lucide-react';
import { supabase } from '../../App';
import { useAuthContext } from '../../hooks/useAuthContext';
import { useIsMobile } from '../../hooks/use-mobile';
import { useScrollRestoration } from '../../hooks/useScrollRestoration';
import { PillarBadge } from '../../components/PillarBadge';
import { HorizonBadge } from '../../components/HorizonBadge';
import { StageBadge } from '../../components/StageBadge';
import { ConfidenceBadge } from '../../components/ConfidenceBadge';
import { cn } from '../../lib/utils';
import { parseStageNumber } from '../../lib/stage-utils';
import { VirtualizedList, VirtualizedListHandle } from '../../components/VirtualizedList';
import {
  fetchPendingReviewCards,
  reviewCard,
  bulkReviewCards,
  dismissCard,
  type PendingCard,
  type ReviewAction,
  type DismissReason,
} from '../../lib/discovery-api';

// Local imports from modular structure
import { ImpactScoreBadge, SwipeableCard, UndoToast } from './components';
import { useUndoManager } from './hooks';
import { formatDiscoveredDate, filterByConfidence } from './utils';
import {
  type Pillar,
  type ConfidenceFilter,
  type UndoActionType,
  ACTION_DEBOUNCE_MS,
} from './types';

/**
 * DiscoveryQueue Page Component
 *
 * Main page for reviewing pending AI-discovered cards. Features:
 * - Virtualized list for performance with large card counts
 * - Keyboard navigation (j/k to navigate, f to follow, d to dismiss, z to undo)
 * - Swipe gestures on mobile (right to approve, left to dismiss)
 * - Bulk selection and actions
 * - Undo functionality with countdown timer
 * - Filtering by pillar, confidence level, and search term
 */
const DiscoveryQueue: React.FC = () => {
  const { user } = useAuthContext();
  const isMobile = useIsMobile();

  // Enable scroll position restoration for navigation
  useScrollRestoration({
    storageKey: 'discovery-queue',
    clearAfterRestore: false,
  });

  const [cards, setCards] = useState<PendingCard[]>([]);
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Progress tracking - stores initial count when queue was loaded
  const [initialCardCount, setInitialCardCount] = useState<number>(0);

  // Undo manager hook - handles undo stack and toast
  const handleCardRestored = useCallback((card: PendingCard) => {
    setCards((prevCards) => {
      // Check if card already exists (prevent duplicates)
      if (prevCards.some((c) => c.id === card.id)) {
        return prevCards;
      }
      // Add the card back to the list
      return [...prevCards, card];
    });
  }, []);

  const {
    pushToUndoStack,
    canUndo,
    getLastUndoableAction,
    toastVisible,
    toastTimeRemaining,
    showToast,
    dismissToast,
    handleUndoFromToast,
  } = useUndoManager(handleCardRestored);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPillar, setSelectedPillar] = useState('');
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>('all');

  // Bulk selection
  const [selectedCards, setSelectedCards] = useState<Set<string>>(new Set());
  const [showBulkActions, setShowBulkActions] = useState(false);

  // Dropdown states
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  // Keyboard navigation state
  const [focusedCardIndex, setFocusedCardIndex] = useState<number>(-1);
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // Cache for stable ref callbacks per card ID
  const cardRefCallbacksCache = useRef<Map<string, (el: HTMLDivElement | null) => void>>(new Map());

  // Virtualized list ref for scroll control
  const virtualizedListRef = useRef<VirtualizedListHandle>(null);

  // Debounce ref to prevent rapid keyboard input
  const lastActionTimeRef = useRef<number>(0);

  const loadData = useCallback(async () => {
    if (!user) return;

    try {
      setLoading(true);
      setError(null);

      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) {
        throw new Error('Not authenticated');
      }

      // Load pillars from Supabase
      const { data: pillarsData } = await supabase
        .from('pillars')
        .select('*')
        .order('name');

      setPillars(pillarsData || []);

      // Load pending cards from backend API
      const pendingCards = await fetchPendingReviewCards(token);
      setCards(pendingCards);
      if (pendingCards.length > 0) {
        setInitialCardCount(pendingCards.length);
      }
    } catch (err) {
      console.error('Error loading discovery queue:', err);
      setError(err instanceof Error ? err.message : 'Failed to load discovery queue');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Update bulk actions visibility when selection changes
  useEffect(() => {
    setShowBulkActions(selectedCards.size > 0);
  }, [selectedCards]);

  /**
   * Handle card review action
   */
  const handleReviewAction = useCallback(async (cardId: string, action: ReviewAction) => {
    if (!user) return;

    const cardToAction = cards.find((c) => c.id === cardId);
    if (!cardToAction) return;

    try {
      setActionLoading(cardId);
      setOpenDropdown(null);

      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) throw new Error('Not authenticated');

      await reviewCard(token, cardId, action);

      // Push to undo stack before removing
      const undoActionType: UndoActionType = action === 'approve' ? 'approve' : action === 'reject' ? 'reject' : 'defer';
      pushToUndoStack({
        type: undoActionType,
        card: cardToAction,
        timestamp: Date.now(),
      });

      // Remove card from list
      setCards((prev) => prev.filter((c) => c.id !== cardId));
      setSelectedCards((prev) => {
        const next = new Set(prev);
        next.delete(cardId);
        return next;
      });

      showToast();
    } catch (err) {
      console.error('Error reviewing card:', err);
      setError(err instanceof Error ? err.message : 'Failed to review card');
    } finally {
      setActionLoading(null);
    }
  }, [user, cards, pushToUndoStack, showToast]);

  /**
   * Handle card dismissal
   */
  const handleDismiss = useCallback(async (cardId: string, reason?: DismissReason) => {
    if (!user) return;

    const cardToDismiss = cards.find((c) => c.id === cardId);
    if (!cardToDismiss) return;

    try {
      setActionLoading(cardId);
      setOpenDropdown(null);

      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) throw new Error('Not authenticated');

      await dismissCard(token, cardId, reason);

      pushToUndoStack({
        type: 'dismiss',
        card: cardToDismiss,
        timestamp: Date.now(),
        dismissReason: reason,
      });

      setCards((prev) => prev.filter((c) => c.id !== cardId));
      setSelectedCards((prev) => {
        const next = new Set(prev);
        next.delete(cardId);
        return next;
      });

      showToast();
    } catch (err) {
      console.error('Error dismissing card:', err);
      setError(err instanceof Error ? err.message : 'Failed to dismiss card');
    } finally {
      setActionLoading(null);
    }
  }, [user, cards, pushToUndoStack, showToast]);

  /**
   * Stable callback for swipe-right action (approve)
   */
  const handleSwipeApprove = useCallback((cardId: string) => {
    handleReviewAction(cardId, 'approve');
  }, [handleReviewAction]);

  /**
   * Stable callback for swipe-left action (dismiss as irrelevant)
   */
  const handleSwipeDismiss = useCallback((cardId: string) => {
    handleDismiss(cardId, 'irrelevant');
  }, [handleDismiss]);

  // Filter cards
  const filteredCards = useMemo(() => {
    let result = cards;

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(
        (card) =>
          card.name.toLowerCase().includes(term) ||
          card.summary.toLowerCase().includes(term)
      );
    }

    if (selectedPillar) {
      result = result.filter((card) => card.pillar_id === selectedPillar);
    }

    result = filterByConfidence(result, confidenceFilter);

    return result;
  }, [cards, searchTerm, selectedPillar, confidenceFilter]);

  /**
   * Stable callback for card click action
   */
  const handleCardClick = useCallback((cardId: string) => {
    const index = filteredCards.findIndex(c => c.id === cardId);
    if (index !== -1) {
      setFocusedCardIndex(index);
    }
  }, [filteredCards]);

  /**
   * Handle bulk action
   */
  const handleBulkAction = useCallback(async (action: ReviewAction) => {
    if (!user || selectedCards.size === 0) return;

    try {
      setActionLoading('bulk');

      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) throw new Error('Not authenticated');

      const cardIds = Array.from(selectedCards);
      await bulkReviewCards(token, cardIds, action);

      setCards((prev) => prev.filter((c) => !selectedCards.has(c.id)));
      setSelectedCards(new Set());
    } catch (err) {
      console.error('Error bulk reviewing cards:', err);
      setError(err instanceof Error ? err.message : 'Failed to bulk review cards');
    } finally {
      setActionLoading(null);
    }
  }, [user, selectedCards]);

  /**
   * Toggle card selection
   */
  const toggleCardSelection = useCallback((cardId: string) => {
    setSelectedCards((prev) => {
      const next = new Set(prev);
      if (next.has(cardId)) {
        next.delete(cardId);
      } else {
        next.add(cardId);
      }
      return next;
    });
  }, []);

  /**
   * Select all visible cards
   */
  const selectAllVisible = useCallback(() => {
    const visibleIds = filteredCards.map((c) => c.id);
    setSelectedCards(new Set(visibleIds));
  }, [filteredCards]);

  /**
   * Clear selection
   */
  const clearSelection = useCallback(() => {
    setSelectedCards(new Set());
  }, []);

  // Stats
  const stats = useMemo(() => {
    const high = cards.filter((c) => c.ai_confidence >= 0.9).length;
    const medium = cards.filter((c) => c.ai_confidence >= 0.7 && c.ai_confidence < 0.9).length;
    const low = cards.filter((c) => c.ai_confidence < 0.7).length;
    return { total: cards.length, high, medium, low };
  }, [cards]);

  // Progress tracking stats
  const progressStats = useMemo(() => {
    const reviewed = initialCardCount - cards.length;
    const total = initialCardCount;
    const percentage = total > 0 ? (reviewed / total) * 100 : 0;
    return { reviewed, total, percentage };
  }, [cards.length, initialCardCount]);

  // Get the currently focused card
  const focusedCardId = focusedCardIndex >= 0 && focusedCardIndex < filteredCards.length
    ? filteredCards[focusedCardIndex].id
    : null;

  /**
   * Check if enough time has passed since the last action
   */
  const canExecuteAction = useCallback((): boolean => {
    const now = Date.now();
    if (now - lastActionTimeRef.current < ACTION_DEBOUNCE_MS) {
      return false;
    }
    lastActionTimeRef.current = now;
    return true;
  }, []);

  /**
   * Navigate to next card (j key)
   */
  const navigateNext = useCallback(() => {
    if (filteredCards.length === 0) return;

    setFocusedCardIndex((prev) => {
      const nextIndex = prev < filteredCards.length - 1 ? prev + 1 : 0;
      virtualizedListRef.current?.scrollToIndex(nextIndex, { align: 'center' });
      return nextIndex;
    });
  }, [filteredCards.length]);

  /**
   * Navigate to previous card (k key)
   */
  const navigatePrevious = useCallback(() => {
    if (filteredCards.length === 0) return;

    setFocusedCardIndex((prev) => {
      const nextIndex = prev > 0 ? prev - 1 : filteredCards.length - 1;
      virtualizedListRef.current?.scrollToIndex(nextIndex, { align: 'center' });
      return nextIndex;
    });
  }, [filteredCards.length]);

  // Stable hotkey options
  const hotkeyOptions = useMemo(() => ({
    preventDefault: true,
    enableOnFormTags: false,
  }), []);

  // Keyboard shortcuts
  useHotkeys('j', navigateNext, hotkeyOptions, [navigateNext]);
  useHotkeys('k', navigatePrevious, hotkeyOptions, [navigatePrevious]);

  useHotkeys(
    'f',
    () => {
      if (focusedCardId && !actionLoading && canExecuteAction()) {
        handleReviewAction(focusedCardId, 'approve');
      }
    },
    hotkeyOptions,
    [focusedCardId, actionLoading, handleReviewAction, canExecuteAction]
  );

  useHotkeys(
    'd',
    () => {
      if (focusedCardId && !actionLoading && canExecuteAction()) {
        handleDismiss(focusedCardId, 'irrelevant');
      }
    },
    hotkeyOptions,
    [focusedCardId, actionLoading, handleDismiss, canExecuteAction]
  );

  useHotkeys(
    'z',
    () => {
      if (toastVisible && canUndo() && canExecuteAction()) {
        handleUndoFromToast();
      }
    },
    hotkeyOptions,
    [toastVisible, canUndo, handleUndoFromToast, canExecuteAction]
  );

  // Reset focus when filtered cards change
  useEffect(() => {
    if (focusedCardIndex >= filteredCards.length) {
      setFocusedCardIndex(filteredCards.length > 0 ? 0 : -1);
    }
  }, [filteredCards.length, focusedCardIndex]);

  /**
   * Ref callback factory for card elements
   */
  const getCardRefCallback = useCallback((cardId: string) => {
    let callback = cardRefCallbacksCache.current.get(cardId);
    if (!callback) {
      callback = (el: HTMLDivElement | null) => {
        if (el) {
          cardRefs.current.set(cardId, el);
        } else {
          cardRefs.current.delete(cardId);
        }
      };
      cardRefCallbacksCache.current.set(cardId, callback);
    }
    return callback;
  }, []);

  if (!user) {
    return <div className="p-8">Loading...</div>;
  }

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl sm:text-3xl font-bold text-brand-dark-blue dark:text-white flex items-center gap-2 sm:gap-3">
              <Sparkles className="h-6 w-6 sm:h-8 sm:w-8 text-brand-blue flex-shrink-0" />
              <span className="truncate">Discovery Queue</span>
            </h1>
            <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600 dark:text-gray-400">
              Review AI-discovered cards before they're added to the intelligence library.
            </p>
          </div>
          <button
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] px-3 sm:px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-[#3d4176] hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue disabled:opacity-50 transition-colors flex-shrink-0 active:scale-95"
          >
            <RefreshCw className={`h-5 w-5 sm:h-4 sm:w-4 ${loading ? 'animate-spin' : ''} ${isMobile ? '' : 'mr-2'}`} />
            {!isMobile && 'Refresh'}
          </button>
        </div>

        {/* Stats Chips */}
        <div className="mt-3 sm:mt-4 -mx-3 px-3 sm:mx-0 sm:px-0 overflow-x-auto scrollbar-hide">
          <div className="flex items-center gap-2 sm:gap-3 flex-nowrap sm:flex-wrap min-w-max sm:min-w-0">
            <span className="inline-flex items-center px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 whitespace-nowrap">
              <Inbox className="h-3.5 w-3.5 sm:h-4 sm:w-4 mr-1 sm:mr-1.5" />
              {stats.total} Pending
            </span>
            {stats.high > 0 && (
              <span className="inline-flex items-center px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 whitespace-nowrap">
                <CheckCircle className="h-3.5 w-3.5 sm:h-4 sm:w-4 mr-1 sm:mr-1.5" />
                {stats.high} High
              </span>
            )}
            {stats.medium > 0 && (
              <span className="inline-flex items-center px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 whitespace-nowrap">
                <AlertTriangle className="h-3.5 w-3.5 sm:h-4 sm:w-4 mr-1 sm:mr-1.5" />
                {stats.medium} Med
              </span>
            )}
            {stats.low > 0 && (
              <span className="inline-flex items-center px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 whitespace-nowrap">
                <XCircle className="h-3.5 w-3.5 sm:h-4 sm:w-4 mr-1 sm:mr-1.5" />
                {stats.low} Low
              </span>
            )}
          </div>
        </div>

        {/* Progress Indicator */}
        {progressStats.total > 0 && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Review Progress
              </span>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {progressStats.reviewed} of {progressStats.total} cards reviewed
              </span>
            </div>
            <Progress.Root
              className="relative h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700"
              value={progressStats.percentage}
            >
              <Progress.Indicator
                className="h-full rounded-full bg-brand-blue transition-transform duration-300 ease-out"
                style={{ transform: `translateX(-${100 - progressStats.percentage}%)` }}
              />
            </Progress.Root>
            {progressStats.percentage === 100 && progressStats.total > 0 && (
              <p className="mt-2 text-sm text-green-600 dark:text-green-400 flex items-center gap-1.5">
                <CheckCircle className="h-4 w-4" />
                All cards reviewed! Great job.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="flex items-center gap-2 text-red-700 dark:text-red-300">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">{error}</span>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6 mb-4 sm:mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {/* Search */}
          <div className="sm:col-span-2 lg:col-span-2">
            <label htmlFor="search" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <input
                type="text"
                id="search"
                className="pl-10 block w-full min-h-[44px] sm:min-h-0 border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue text-base sm:text-sm"
                placeholder="Search pending cards..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          {/* Pillar Filter */}
          <div>
            <label htmlFor="pillar" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Pillar
            </label>
            <select
              id="pillar"
              className="block w-full min-h-[44px] sm:min-h-0 border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue text-base sm:text-sm"
              value={selectedPillar}
              onChange={(e) => setSelectedPillar(e.target.value)}
            >
              <option value="">All Pillars</option>
              {pillars.map((pillar) => (
                <option key={pillar.id} value={pillar.id}>
                  {pillar.name}
                </option>
              ))}
            </select>
          </div>

          {/* Confidence Filter */}
          <div>
            <label htmlFor="confidence" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Confidence
            </label>
            <select
              id="confidence"
              className="block w-full min-h-[44px] sm:min-h-0 border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue text-base sm:text-sm"
              value={confidenceFilter}
              onChange={(e) => setConfidenceFilter(e.target.value as ConfidenceFilter)}
            >
              <option value="all">All Levels</option>
              <option value="high">High (90%+)</option>
              <option value="medium">Medium (70-90%)</option>
              <option value="low">Low (&lt;70%)</option>
            </select>
          </div>
        </div>

        {/* Selection Controls */}
        <div className="mt-3 sm:mt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-4 flex-wrap">
            <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">
              {filteredCards.length} of {cards.length} cards
            </p>
            {filteredCards.length > 0 && (
              <button
                onClick={selectedCards.size === filteredCards.length ? clearSelection : selectAllVisible}
                className="min-h-[44px] px-2 py-2 -my-2 text-xs sm:text-sm text-brand-blue hover:text-brand-dark-blue dark:hover:text-brand-light-blue transition-colors active:scale-95"
              >
                {selectedCards.size === filteredCards.length ? 'Deselect All' : 'Select All'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Keyboard Shortcuts Hint - desktop only */}
      {!isMobile && !showBulkActions && filteredCards.length > 0 && (
        <div className="mb-4 px-4 py-2 bg-gray-50 dark:bg-[#2d3166]/50 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-center gap-6 text-xs text-gray-500 dark:text-gray-400">
            <span className="flex items-center gap-1.5">
              <kbd className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 font-mono text-gray-700 dark:text-gray-300">j</kbd>
              <kbd className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 font-mono text-gray-700 dark:text-gray-300">k</kbd>
              <span>Navigate</span>
            </span>
            <span className="flex items-center gap-1.5">
              <kbd className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 font-mono text-gray-700 dark:text-gray-300">f</kbd>
              <span>Follow</span>
            </span>
            <span className="flex items-center gap-1.5">
              <kbd className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 font-mono text-gray-700 dark:text-gray-300">d</kbd>
              <span>Dismiss</span>
            </span>
            <span className="flex items-center gap-1.5">
              <kbd className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 font-mono text-gray-700 dark:text-gray-300">z</kbd>
              <span>Undo</span>
            </span>
          </div>
        </div>
      )}

      {/* Mobile Swipe Hint */}
      {isMobile && filteredCards.length > 0 && !showBulkActions && (
        <div className="mb-3 px-3 py-2 bg-gray-50 dark:bg-[#2d3166]/50 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-xs text-center text-gray-500 dark:text-gray-400">
            Swipe right to approve • Swipe left to dismiss
          </p>
        </div>
      )}

      {/* Bulk Actions Bar */}
      {showBulkActions && (
        <div className="mb-4 sm:mb-6 p-3 sm:p-4 bg-brand-light-blue dark:bg-brand-blue/20 border border-brand-blue/20 rounded-lg">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <span className="text-sm font-medium text-brand-dark-blue dark:text-brand-light-blue">
              {selectedCards.size} card{selectedCards.size !== 1 ? 's' : ''} selected
            </span>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => handleBulkAction('approve')}
                disabled={actionLoading === 'bulk'}
                className="inline-flex items-center justify-center min-h-[44px] px-3 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors active:scale-95"
              >
                <CheckCircle className="h-4 w-4 sm:h-4 sm:w-4 mr-1.5 sm:mr-1.5" />
                {isMobile ? 'Approve' : 'Approve All'}
              </button>
              <button
                onClick={() => handleBulkAction('reject')}
                disabled={actionLoading === 'bulk'}
                className="inline-flex items-center justify-center min-h-[44px] px-3 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors active:scale-95"
              >
                <XCircle className="h-4 w-4 sm:h-4 sm:w-4 mr-1.5 sm:mr-1.5" />
                {isMobile ? 'Reject' : 'Reject All'}
              </button>
              <button
                onClick={clearSelection}
                className="inline-flex items-center justify-center min-h-[44px] px-3 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:scale-95"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cards */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue"></div>
        </div>
      ) : filteredCards.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
          {cards.length === 0 ? (
            <>
              <div className="mx-auto h-16 w-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <CheckCircle className="h-10 w-10 text-green-500 dark:text-green-400" />
              </div>
              <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
                All Caught Up!
              </h3>
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-sm mx-auto">
                Great work! You&apos;ve reviewed all pending discoveries. Check back later for new AI-discovered cards.
              </p>
              <Link
                to="/discover"
                className="mt-6 inline-flex items-center justify-center min-h-[44px] px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors active:scale-95"
              >
                Browse Intelligence Library
              </Link>
            </>
          ) : (
            <>
              <Inbox className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
                No Matching Cards
              </h3>
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-sm mx-auto">
                No cards match your current filters. Try adjusting your search or filter settings.
              </p>
              <button
                onClick={() => {
                  setSearchTerm('');
                  setSelectedPillar('');
                  setConfidenceFilter('all');
                }}
                className="mt-4 inline-flex items-center justify-center min-h-[44px] px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-200 bg-white dark:bg-[#3d4176] hover:bg-gray-50 dark:hover:bg-[#4d5186] transition-colors active:scale-95"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Clear All Filters
              </button>
            </>
          )}
        </div>
      ) : (
        <VirtualizedList<PendingCard>
          ref={virtualizedListRef}
          items={filteredCards}
          estimatedSize={200}
          gap={isMobile ? 12 : 16}
          overscan={3}
          getItemKey={(card) => card.id}
          focusedIndex={focusedCardIndex}
          onFocusedIndexChange={setFocusedCardIndex}
          ariaLabel="Discovery queue cards"
          scrollContainerClassName="h-[calc(100vh-280px)] sm:h-[calc(100vh-300px)]"
          renderItem={(card) => {
            const stageNumber = parseStageNumber(card.stage_id);
            const isSelected = selectedCards.has(card.id);
            const isLoading = actionLoading === card.id;
            const isDropdownOpen = openDropdown === card.id;
            const isFocused = focusedCardId === card.id;

            return (
              <SwipeableCard
                cardId={card.id}
                isMobile={isMobile}
                cardRef={getCardRefCallback(card.id)}
                onSwipeRight={handleSwipeApprove}
                onSwipeLeft={handleSwipeDismiss}
                disabled={isLoading}
                tabIndex={isFocused ? 0 : -1}
                onClick={handleCardClick}
                className={cn(
                  'bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6 border-l-4 transition-all duration-200',
                  isFocused
                    ? 'border-l-brand-blue ring-2 ring-brand-blue/50 shadow-lg'
                    : isSelected
                      ? 'border-l-brand-blue ring-2 ring-brand-blue/20'
                      : 'border-transparent hover:border-l-brand-blue',
                  isLoading && 'opacity-60'
                )}
              >
                <div className="flex items-start gap-2 sm:gap-4">
                  {/* Checkbox */}
                  <label
                    className="flex-shrink-0 flex items-center justify-center min-h-[44px] min-w-[44px] -m-2 cursor-pointer"
                    aria-label={`Select ${card.name}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleCardSelection(card.id)}
                      className="h-5 w-5 sm:h-4 sm:w-4 text-brand-blue border-gray-300 dark:border-gray-600 rounded focus:ring-brand-blue cursor-pointer"
                    />
                  </label>

                  {/* Card Content */}
                  <div className="flex-1 min-w-0">
                    {/* Header Row */}
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-4 mb-2 sm:mb-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-base sm:text-lg font-medium text-gray-900 dark:text-white line-clamp-2 sm:line-clamp-none">
                          {card.name}
                        </h3>
                        {/* Badges */}
                        <div className="mt-1.5 sm:mt-2 -mx-4 px-4 sm:mx-0 sm:px-0 overflow-x-auto scrollbar-hide">
                          <div className="flex items-center gap-1.5 sm:gap-2 flex-nowrap sm:flex-wrap min-w-max sm:min-w-0">
                            <PillarBadge pillarId={card.pillar_id} showIcon={!isMobile} size="sm" />
                            <HorizonBadge horizon={card.horizon} size="sm" />
                            {stageNumber !== null && (
                              <StageBadge stage={stageNumber} size="sm" variant="minimal" />
                            )}
                            <ConfidenceBadge confidence={card.ai_confidence} size="sm" />
                            <ImpactScoreBadge score={card.impact_score} size="sm" />
                          </div>
                        </div>
                      </div>

                      {/* Discovered Date */}
                      <div className="flex-shrink-0 flex sm:flex-col items-center sm:items-end gap-2 sm:gap-0 sm:text-right text-xs text-gray-500 dark:text-gray-400">
                        <div className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          <span>{formatDiscoveredDate(card.discovered_at)}</span>
                        </div>
                        {card.source_type && (
                          <span className="sm:mt-1 text-gray-400 dark:text-gray-500">
                            via {card.source_type}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Summary */}
                    <p className="text-sm sm:text-base text-gray-600 dark:text-gray-400 mb-3 sm:mb-4 line-clamp-2">
                      {card.summary}
                    </p>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleReviewAction(card.id, 'approve');
                        }}
                        disabled={isLoading}
                        className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 px-3 sm:px-3 py-2 sm:py-1.5 rounded-md text-xs sm:text-sm font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50 disabled:opacity-50 transition-colors active:scale-95"
                        title="Approve this card"
                      >
                        <CheckCircle className="h-5 w-5 sm:h-4 sm:w-4 sm:mr-1.5" />
                        <span className="hidden sm:inline ml-1.5">Approve</span>
                      </button>

                      <Link
                        to={`/cards/${card.slug}?mode=edit`}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 px-3 sm:px-3 py-2 sm:py-1.5 rounded-md text-xs sm:text-sm font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors active:scale-95"
                        title="Edit and approve"
                      >
                        <Edit3 className="h-5 w-5 sm:h-4 sm:w-4 sm:mr-1.5" />
                        <span className="hidden sm:inline ml-1.5">Edit</span>
                      </Link>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDismiss(card.id, 'irrelevant');
                        }}
                        disabled={isLoading}
                        className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 px-3 sm:px-3 py-2 sm:py-1.5 rounded-md text-xs sm:text-sm font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900/50 disabled:opacity-50 transition-colors active:scale-95"
                        title="Reject this card"
                      >
                        <XCircle className="h-5 w-5 sm:h-4 sm:w-4 sm:mr-1.5" />
                        <span className="hidden sm:inline ml-1.5">Reject</span>
                      </button>

                      {/* More Options Dropdown */}
                      <div className="relative ml-auto sm:ml-0">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenDropdown(isDropdownOpen ? null : card.id);
                          }}
                          className="flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 sm:p-1.5 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:scale-95"
                          title="More options"
                          aria-label="More options"
                        >
                          <MoreHorizontal className="h-5 w-5 sm:h-4 sm:w-4" />
                        </button>

                        {isDropdownOpen && (
                          <div className="absolute right-0 mt-1 w-48 sm:w-48 bg-white dark:bg-[#3d4176] rounded-md shadow-lg border border-gray-200 dark:border-gray-600 py-1 z-10">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDismiss(card.id, 'duplicate');
                              }}
                              className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                            >
                              Mark as Duplicate
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDismiss(card.id, 'out_of_scope');
                              }}
                              className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                            >
                              Out of Scope
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDismiss(card.id, 'low_quality');
                              }}
                              className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                            >
                              Low Quality
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleReviewAction(card.id, 'defer');
                              }}
                              className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                            >
                              Defer for Later
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </SwipeableCard>
            );
          }}
        />
      )}

      {/* Close dropdowns when clicking outside */}
      {openDropdown && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => setOpenDropdown(null)}
        />
      )}

      {/* Undo Toast Notification */}
      {toastVisible && getLastUndoableAction() && (
        <UndoToast
          action={getLastUndoableAction()!}
          onUndo={handleUndoFromToast}
          onDismiss={dismissToast}
          timeRemaining={toastTimeRemaining}
        />
      )}
    </div>
  );
};

export default DiscoveryQueue;
