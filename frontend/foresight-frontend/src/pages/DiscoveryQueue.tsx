import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useHotkeys } from 'react-hotkeys-hook';
import {
  Search,
  Filter,
  CheckCircle,
  XCircle,
  Edit3,
  Clock,
  Inbox,
  ChevronDown,
  RefreshCw,
  AlertTriangle,
  Sparkles,
  MoreHorizontal,
} from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { PillarBadge } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge } from '../components/StageBadge';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import {
  fetchPendingReviewCards,
  reviewCard,
  bulkReviewCards,
  dismissCard,
  type PendingCard,
  type ReviewAction,
  type DismissReason,
} from '../lib/discovery-api';

interface Pillar {
  id: string;
  name: string;
  color: string;
}

type ConfidenceFilter = 'all' | 'high' | 'medium' | 'low';

/**
 * Parse stage number from stage_id string
 */
const parseStageNumber = (stageId: string): number | null => {
  const match = stageId.match(/^(\d+)/);
  return match ? parseInt(match[1], 10) : null;
};

/**
 * Format date for display
 */
const formatDiscoveredDate = (dateString: string): string => {
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
const filterByConfidence = (cards: PendingCard[], filter: ConfidenceFilter): PendingCard[] => {
  if (filter === 'all') return cards;
  return cards.filter((card) => {
    if (filter === 'high') return card.ai_confidence >= 0.9;
    if (filter === 'medium') return card.ai_confidence >= 0.7 && card.ai_confidence < 0.9;
    return card.ai_confidence < 0.7;
  });
};

const DiscoveryQueue: React.FC = () => {
  const { user } = useAuthContext();
  const [cards, setCards] = useState<PendingCard[]>([]);
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const loadData = useCallback(async () => {
    if (!user) return;

    try {
      setLoading(true);
      setError(null);

      // Get auth token
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
  const handleReviewAction = async (cardId: string, action: ReviewAction) => {
    if (!user) return;

    try {
      setActionLoading(cardId);
      setOpenDropdown(null);

      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) throw new Error('Not authenticated');

      await reviewCard(token, cardId, action);

      // Remove card from list on success
      setCards((prev) => prev.filter((c) => c.id !== cardId));
      setSelectedCards((prev) => {
        const next = new Set(prev);
        next.delete(cardId);
        return next;
      });
    } catch (err) {
      console.error('Error reviewing card:', err);
      setError(err instanceof Error ? err.message : 'Failed to review card');
    } finally {
      setActionLoading(null);
    }
  };

  /**
   * Handle card dismissal
   */
  const handleDismiss = async (cardId: string, reason?: DismissReason) => {
    if (!user) return;

    try {
      setActionLoading(cardId);
      setOpenDropdown(null);

      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) throw new Error('Not authenticated');

      await dismissCard(token, cardId, reason);

      // Remove card from list on success
      setCards((prev) => prev.filter((c) => c.id !== cardId));
      setSelectedCards((prev) => {
        const next = new Set(prev);
        next.delete(cardId);
        return next;
      });
    } catch (err) {
      console.error('Error dismissing card:', err);
      setError(err instanceof Error ? err.message : 'Failed to dismiss card');
    } finally {
      setActionLoading(null);
    }
  };

  /**
   * Handle bulk action
   */
  const handleBulkAction = async (action: ReviewAction) => {
    if (!user || selectedCards.size === 0) return;

    try {
      setActionLoading('bulk');

      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) throw new Error('Not authenticated');

      const cardIds = Array.from(selectedCards);
      await bulkReviewCards(token, cardIds, action);

      // Remove processed cards from list
      setCards((prev) => prev.filter((c) => !selectedCards.has(c.id)));
      setSelectedCards(new Set());
    } catch (err) {
      console.error('Error bulk reviewing cards:', err);
      setError(err instanceof Error ? err.message : 'Failed to bulk review cards');
    } finally {
      setActionLoading(null);
    }
  };

  /**
   * Toggle card selection
   */
  const toggleCardSelection = (cardId: string) => {
    setSelectedCards((prev) => {
      const next = new Set(prev);
      if (next.has(cardId)) {
        next.delete(cardId);
      } else {
        next.add(cardId);
      }
      return next;
    });
  };

  /**
   * Select all visible cards
   */
  const selectAllVisible = () => {
    const visibleIds = filteredCards.map((c) => c.id);
    setSelectedCards(new Set(visibleIds));
  };

  /**
   * Clear selection
   */
  const clearSelection = () => {
    setSelectedCards(new Set());
  };

  // Filter cards
  const filteredCards = React.useMemo(() => {
    let result = cards;

    // Apply search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(
        (card) =>
          card.name.toLowerCase().includes(term) ||
          card.summary.toLowerCase().includes(term)
      );
    }

    // Apply pillar filter
    if (selectedPillar) {
      result = result.filter((card) => card.pillar_id === selectedPillar);
    }

    // Apply confidence filter
    result = filterByConfidence(result, confidenceFilter);

    return result;
  }, [cards, searchTerm, selectedPillar, confidenceFilter]);

  // Stats
  const stats = React.useMemo(() => {
    const high = cards.filter((c) => c.ai_confidence >= 0.9).length;
    const medium = cards.filter((c) => c.ai_confidence >= 0.7 && c.ai_confidence < 0.9).length;
    const low = cards.filter((c) => c.ai_confidence < 0.7).length;
    return { total: cards.length, high, medium, low };
  }, [cards]);

  // Get the currently focused card (if any)
  const focusedCardId = focusedCardIndex >= 0 && focusedCardIndex < filteredCards.length
    ? filteredCards[focusedCardIndex].id
    : null;

  /**
   * Navigate to next card (j key)
   */
  const navigateNext = useCallback(() => {
    if (filteredCards.length === 0) return;

    setFocusedCardIndex((prev) => {
      const nextIndex = prev < filteredCards.length - 1 ? prev + 1 : 0;
      // Scroll the card into view
      const card = filteredCards[nextIndex];
      if (card) {
        const element = cardRefs.current.get(card.id);
        element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return nextIndex;
    });
  }, [filteredCards]);

  /**
   * Navigate to previous card (k key)
   */
  const navigatePrevious = useCallback(() => {
    if (filteredCards.length === 0) return;

    setFocusedCardIndex((prev) => {
      const nextIndex = prev > 0 ? prev - 1 : filteredCards.length - 1;
      // Scroll the card into view
      const card = filteredCards[nextIndex];
      if (card) {
        const element = cardRefs.current.get(card.id);
        element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return nextIndex;
    });
  }, [filteredCards]);

  // Keyboard shortcuts for navigation
  useHotkeys('j', navigateNext, { preventDefault: true }, [navigateNext]);
  useHotkeys('k', navigatePrevious, { preventDefault: true }, [navigatePrevious]);

  /**
   * Follow/approve the focused card (f key)
   * Only works when a card is focused and not in a form field
   */
  useHotkeys(
    'f',
    () => {
      if (focusedCardId && !actionLoading) {
        handleReviewAction(focusedCardId, 'approve');
      }
    },
    { preventDefault: true },
    [focusedCardId, actionLoading, handleReviewAction]
  );

  /**
   * Dismiss the focused card (d key)
   * Only works when a card is focused and not in a form field
   */
  useHotkeys(
    'd',
    () => {
      if (focusedCardId && !actionLoading) {
        handleDismiss(focusedCardId, 'irrelevant');
      }
    },
    { preventDefault: true },
    [focusedCardId, actionLoading, handleDismiss]
  );

  // Reset focus when filtered cards change
  useEffect(() => {
    if (focusedCardIndex >= filteredCards.length) {
      setFocusedCardIndex(filteredCards.length > 0 ? 0 : -1);
    }
  }, [filteredCards.length, focusedCardIndex]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white flex items-center gap-3">
              <Sparkles className="h-8 w-8 text-brand-blue" />
              Discovery Queue
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Review AI-discovered cards before they're added to the intelligence library.
            </p>
          </div>
          <button
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-[#3d4176] hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Stats Chips */}
        <div className="mt-4 flex items-center gap-3 flex-wrap">
          <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
            <Inbox className="h-4 w-4 mr-1.5" />
            {stats.total} Pending
          </span>
          {stats.high > 0 && (
            <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
              <CheckCircle className="h-4 w-4 mr-1.5" />
              {stats.high} High Confidence
            </span>
          )}
          {stats.medium > 0 && (
            <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">
              <AlertTriangle className="h-4 w-4 mr-1.5" />
              {stats.medium} Medium
            </span>
          )}
          {stats.low > 0 && (
            <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300">
              <XCircle className="h-4 w-4 mr-1.5" />
              {stats.low} Low
            </span>
          )}
        </div>
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
      <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Search */}
          <div className="lg:col-span-2">
            <label htmlFor="search" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <input
                type="text"
                id="search"
                className="pl-10 block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                placeholder="Search pending cards..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          {/* Pillar Filter */}
          <div>
            <label htmlFor="pillar" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Strategic Pillar
            </label>
            <select
              id="pillar"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
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
              AI Confidence
            </label>
            <select
              id="confidence"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
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
        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Showing {filteredCards.length} of {cards.length} cards
            </p>
            {filteredCards.length > 0 && (
              <button
                onClick={selectedCards.size === filteredCards.length ? clearSelection : selectAllVisible}
                className="text-sm text-brand-blue hover:text-brand-dark-blue dark:hover:text-brand-light-blue transition-colors"
              >
                {selectedCards.size === filteredCards.length ? 'Deselect All' : 'Select All'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Bulk Actions Bar */}
      {showBulkActions && (
        <div className="mb-6 p-4 bg-brand-light-blue dark:bg-brand-blue/20 border border-brand-blue/20 rounded-lg flex items-center justify-between">
          <span className="text-sm font-medium text-brand-dark-blue dark:text-brand-light-blue">
            {selectedCards.size} card{selectedCards.size !== 1 ? 's' : ''} selected
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleBulkAction('approve')}
              disabled={actionLoading === 'bulk'}
              className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              <CheckCircle className="h-4 w-4 mr-1.5" />
              Approve All
            </button>
            <button
              onClick={() => handleBulkAction('reject')}
              disabled={actionLoading === 'bulk'}
              className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              <XCircle className="h-4 w-4 mr-1.5" />
              Reject All
            </button>
            <button
              onClick={clearSelection}
              className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              Cancel
            </button>
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
          <Inbox className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
            {cards.length === 0 ? 'Discovery Queue Empty' : 'No Matching Cards'}
          </h3>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-sm mx-auto">
            {cards.length === 0
              ? 'All pending discoveries have been reviewed. Check back later for new AI-discovered cards.'
              : 'Try adjusting your filters to see more cards.'}
          </p>
          {cards.length === 0 && (
            <Link
              to="/discover"
              className="mt-6 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
            >
              Browse Intelligence Library
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {filteredCards.map((card, index) => {
            const stageNumber = parseStageNumber(card.stage_id);
            const isSelected = selectedCards.has(card.id);
            const isLoading = actionLoading === card.id;
            const isDropdownOpen = openDropdown === card.id;
            const isFocused = focusedCardId === card.id;

            return (
              <div
                key={card.id}
                ref={(el) => {
                  if (el) {
                    cardRefs.current.set(card.id, el);
                  } else {
                    cardRefs.current.delete(card.id);
                  }
                }}
                tabIndex={isFocused ? 0 : -1}
                onClick={() => setFocusedCardIndex(index)}
                className={`bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 border-l-4 transition-all duration-200 ${
                  isFocused
                    ? 'border-l-brand-blue ring-2 ring-brand-blue/50 shadow-lg'
                    : isSelected
                      ? 'border-l-brand-blue ring-2 ring-brand-blue/20'
                      : 'border-transparent hover:border-l-brand-blue'
                } ${isLoading ? 'opacity-60' : ''}`}
              >
                <div className="flex items-start gap-4">
                  {/* Checkbox */}
                  <div className="flex-shrink-0 pt-1">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleCardSelection(card.id)}
                      className="h-4 w-4 text-brand-blue border-gray-300 dark:border-gray-600 rounded focus:ring-brand-blue"
                      aria-label={`Select ${card.name}`}
                    />
                  </div>

                  {/* Card Content */}
                  <div className="flex-1 min-w-0">
                    {/* Header Row */}
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div className="flex-1">
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                          {card.name}
                        </h3>
                        <div className="mt-2 flex items-center gap-2 flex-wrap">
                          <PillarBadge pillarId={card.pillar_id} showIcon size="sm" />
                          <HorizonBadge horizon={card.horizon} size="sm" />
                          {stageNumber !== null && (
                            <StageBadge stage={stageNumber} size="sm" variant="minimal" />
                          )}
                          <ConfidenceBadge confidence={card.ai_confidence} size="sm" />
                        </div>
                      </div>

                      {/* Discovered Date */}
                      <div className="flex-shrink-0 text-right">
                        <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                          <Clock className="h-3 w-3" />
                          <span>{formatDiscoveredDate(card.discovered_at)}</span>
                        </div>
                        {card.source_type && (
                          <div className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                            via {card.source_type}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Summary */}
                    <p className="text-gray-600 dark:text-gray-400 mb-4 line-clamp-2">
                      {card.summary}
                    </p>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleReviewAction(card.id, 'approve')}
                        disabled={isLoading}
                        className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50 disabled:opacity-50 transition-colors"
                        title="Approve this card"
                      >
                        <CheckCircle className="h-4 w-4 mr-1.5" />
                        Approve
                      </button>

                      <Link
                        to={`/cards/${card.slug}?mode=edit`}
                        className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors"
                        title="Edit and approve"
                      >
                        <Edit3 className="h-4 w-4 mr-1.5" />
                        Edit
                      </Link>

                      <button
                        onClick={() => handleDismiss(card.id, 'irrelevant')}
                        disabled={isLoading}
                        className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900/50 disabled:opacity-50 transition-colors"
                        title="Reject this card"
                      >
                        <XCircle className="h-4 w-4 mr-1.5" />
                        Reject
                      </button>

                      {/* More Options Dropdown */}
                      <div className="relative">
                        <button
                          onClick={() => setOpenDropdown(isDropdownOpen ? null : card.id)}
                          className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                          title="More options"
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </button>

                        {isDropdownOpen && (
                          <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-[#3d4176] rounded-md shadow-lg border border-gray-200 dark:border-gray-600 py-1 z-10">
                            <button
                              onClick={() => handleDismiss(card.id, 'duplicate')}
                              className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                            >
                              Mark as Duplicate
                            </button>
                            <button
                              onClick={() => handleDismiss(card.id, 'out_of_scope')}
                              className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                            >
                              Out of Scope
                            </button>
                            <button
                              onClick={() => handleDismiss(card.id, 'low_quality')}
                              className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                            >
                              Low Quality
                            </button>
                            <button
                              onClick={() => handleReviewAction(card.id, 'defer')}
                              className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                            >
                              Defer for Later
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Close dropdowns when clicking outside */}
      {openDropdown && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => setOpenDropdown(null)}
        />
      )}
    </div>
  );
};

export default DiscoveryQueue;
