import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useHotkeys } from 'react-hotkeys-hook';
import { useDrag } from '@use-gesture/react';
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
  Zap,
  Undo2,
  X,
} from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { useIsMobile } from '../hooks/use-mobile';
import { PillarBadge } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge } from '../components/StageBadge';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { Tooltip } from '../components/ui/Tooltip';
import { cn } from '../lib/utils';
import { parseStageNumber } from '../lib/stage-utils';
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
 * Undo action types for tracking user actions
 */
type UndoActionType = 'approve' | 'reject' | 'dismiss' | 'defer';

/**
 * Represents an action that can be undone
 * Stores the action type, affected card, and timestamp for time-limited undo
 */
interface UndoAction {
  type: UndoActionType;
  card: PendingCard;
  timestamp: number;
  /** Optional dismiss reason if action was a dismissal */
  dismissReason?: DismissReason;
}

/**
 * Maximum time window (in ms) during which an action can be undone
 */
const UNDO_TIMEOUT_MS = 5000;

/**
 * Minimum interval (in ms) between keyboard actions to prevent double-execution
 * from rapid key presses
 */
const ACTION_DEBOUNCE_MS = 300;

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

/**
 * Get impact score level and styling
 */
function getImpactLevel(score: number): {
  level: 'high' | 'medium' | 'low';
  label: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
} {
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

/**
 * Tooltip content for impact score
 */
function ImpactScoreTooltipContent({ score }: { score: number }) {
  const impactInfo = getImpactLevel(score);

  return (
    <div className="space-y-3 min-w-[200px] max-w-[260px]">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className={cn('p-1.5 rounded-md', impactInfo.bgColor)}>
          <Zap className={cn('h-4 w-4', impactInfo.color)} />
        </div>
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {impactInfo.label}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Impact Score: {score}/100
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
        {impactInfo.description}
      </p>

      {/* Score bar */}
      <div>
        <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              impactInfo.level === 'high' && 'bg-purple-500 dark:bg-purple-400',
              impactInfo.level === 'medium' && 'bg-indigo-500 dark:bg-indigo-400',
              impactInfo.level === 'low' && 'bg-slate-500 dark:bg-slate-400'
            )}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>
    </div>
  );
}

/**
 * Impact score indicator badge for at-a-glance display
 */
function ImpactScoreBadge({
  score,
  size = 'sm',
}: {
  score: number;
  size?: 'sm' | 'md';
}) {
  const impactInfo = getImpactLevel(score);

  const sizeClasses = size === 'sm'
    ? 'px-1.5 py-0.5 text-xs gap-1'
    : 'px-2 py-1 text-sm gap-1.5';

  const iconSize = size === 'sm' ? 10 : 12;

  return (
    <Tooltip
      content={<ImpactScoreTooltipContent score={score} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      <span
        className={cn(
          'inline-flex items-center rounded-full font-medium border cursor-pointer',
          impactInfo.bgColor,
          impactInfo.color,
          impactInfo.borderColor,
          sizeClasses
        )}
        role="status"
        aria-label={`${impactInfo.label}: ${score}/100`}
      >
        <Zap className="shrink-0" size={iconSize} />
        <span>{score}</span>
      </span>
    </Tooltip>
  );
}

/**
 * Mobile-optimized swipe configuration constants
 * Higher thresholds on mobile prevent accidental triggers during vertical scrolling
 */
const SWIPE_CONFIG = {
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

/**
 * SwipeableCard wrapper component for touch gesture support
 * Handles swipe left (dismiss) and swipe right (follow) gestures
 *
 * Mobile Optimizations:
 * - Higher swipe distance threshold prevents accidental triggers
 * - Angle detection distinguishes swipes from vertical scrolling
 * - Enhanced visual feedback with direction icons
 * - Threshold indicators show when swipe will trigger
 *
 * Memoization:
 * - Wrapped with React.memo to prevent unnecessary re-renders
 * - Custom comparison function compares primitive props by value
 * - Callback refs compared by reference (should be stable via useCallback at call site)
 * - onSwipeLeft/onSwipeRight accept cardId parameter for stable callback pattern
 */
interface SwipeableCardProps {
  cardId: string;
  /** Callback when card is swiped left - receives cardId for stable reference pattern */
  onSwipeLeft: (cardId: string) => void;
  /** Callback when card is swiped right - receives cardId for stable reference pattern */
  onSwipeRight: (cardId: string) => void;
  disabled?: boolean;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  tabIndex?: number;
  /** Callback when card is clicked - receives cardId for stable reference pattern */
  onClick?: (cardId: string) => void;
  cardRef?: (el: HTMLDivElement | null) => void;
  /** Whether we're on a mobile device (affects swipe thresholds) */
  isMobile?: boolean;
}

/**
 * Custom comparison function for SwipeableCard memoization
 * Compares props to determine if re-render is needed
 */
function areSwipeableCardPropsEqual(
  prevProps: SwipeableCardProps,
  nextProps: SwipeableCardProps
): boolean {
  // Compare primitive props by value
  if (prevProps.cardId !== nextProps.cardId) return false;
  if (prevProps.disabled !== nextProps.disabled) return false;
  if (prevProps.className !== nextProps.className) return false;
  if (prevProps.tabIndex !== nextProps.tabIndex) return false;
  if (prevProps.isMobile !== nextProps.isMobile) return false;

  // Compare callbacks by reference
  // These should be stable if wrapped with useCallback at the call site
  if (prevProps.onSwipeLeft !== nextProps.onSwipeLeft) return false;
  if (prevProps.onSwipeRight !== nextProps.onSwipeRight) return false;
  if (prevProps.onClick !== nextProps.onClick) return false;
  if (prevProps.cardRef !== nextProps.cardRef) return false;

  // Compare style object by reference (shallow)
  // If style objects are recreated, they'll cause re-renders
  // Consider using useMemo for style objects at call site
  if (prevProps.style !== nextProps.style) return false;

  // Compare children by reference
  // React children are typically new references on each render
  // but this is expected behavior - parent changes cause child re-renders
  if (prevProps.children !== nextProps.children) return false;

  return true;
}

const SwipeableCard = React.memo(function SwipeableCard({
  cardId,
  onSwipeLeft,
  onSwipeRight,
  disabled = false,
  children,
  className,
  style,
  tabIndex,
  onClick,
  cardRef,
  isMobile = false,
}: SwipeableCardProps) {
  const [swipeOffset, setSwipeOffset] = useState(0);
  const [isSwiping, setIsSwiping] = useState(false);
  const [swipeDirection, setSwipeDirection] = useState<'left' | 'right' | null>(null);
  const [willTrigger, setWillTrigger] = useState(false);

  // Use mobile or desktop distance threshold
  const swipeDistance = isMobile ? SWIPE_CONFIG.mobileDistance : SWIPE_CONFIG.desktopDistance;

  const bind = useDrag(
    ({ movement: [mx, my], dragging, tap, velocity: [vx], direction: [dx] }) => {
      // Ignore taps - let regular click handlers work
      if (tap) return;

      // Don't process gestures when disabled (e.g., during loading)
      if (disabled) return;

      // Calculate swipe angle to filter out vertical scrolling attempts
      // Only process if the gesture is mostly horizontal
      const absX = Math.abs(mx);
      const absY = Math.abs(my);
      const angle = Math.atan2(absY, absX) * (180 / Math.PI);

      // If angle is too steep (vertical gesture), don't track as swipe
      if (angle > SWIPE_CONFIG.maxAngle && absX < SWIPE_CONFIG.feedbackThreshold) {
        if (isSwiping) {
          setIsSwiping(false);
          setSwipeOffset(0);
          setSwipeDirection(null);
          setWillTrigger(false);
        }
        return;
      }

      // Update visual feedback during drag
      if (dragging) {
        setIsSwiping(true);
        setSwipeOffset(mx);

        // Determine direction
        if (mx < -SWIPE_CONFIG.feedbackThreshold) {
          setSwipeDirection('left');
          setWillTrigger(Math.abs(mx) >= swipeDistance);
        } else if (mx > SWIPE_CONFIG.feedbackThreshold) {
          setSwipeDirection('right');
          setWillTrigger(mx >= swipeDistance);
        } else {
          setSwipeDirection(null);
          setWillTrigger(false);
        }
        return;
      }

      // Reset visual state when drag ends
      setIsSwiping(false);
      setSwipeOffset(0);
      setSwipeDirection(null);
      setWillTrigger(false);

      // Check if swipe meets distance and velocity thresholds
      const meetsDistanceThreshold = Math.abs(mx) >= swipeDistance;
      const meetsVelocityThreshold = Math.abs(vx) >= SWIPE_CONFIG.velocity;

      // Trigger action if either threshold is met
      // Pass cardId to callbacks for stable reference pattern
      if (meetsDistanceThreshold || meetsVelocityThreshold) {
        if (dx < 0 && mx < 0) {
          onSwipeLeft(cardId);
        } else if (dx > 0 && mx > 0) {
          onSwipeRight(cardId);
        }
      }
    },
    {
      filterTaps: true, // Distinguish clicks from drags
      axis: 'lock', // Lock to first detected axis, helps with scroll vs swipe
      pointer: { touch: true }, // Optimize for touch
      threshold: 10, // Minimum movement before tracking starts
    }
  );

  // Calculate swipe visual feedback styles
  const getSwipeStyles = (): React.CSSProperties => {
    if (!isSwiping || Math.abs(swipeOffset) < SWIPE_CONFIG.feedbackThreshold) {
      return {};
    }

    // Calculate normalized intensity (0-1) based on progress toward trigger threshold
    const progress = Math.min(Math.abs(swipeOffset) / swipeDistance, 1);
    const intensity = progress * 0.4; // Max 40% opacity

    if (swipeOffset < -SWIPE_CONFIG.feedbackThreshold) {
      // Swiping left - dismiss (red indicator)
      return {
        boxShadow: willTrigger
          ? `inset -6px 0 0 0 rgba(239, 68, 68, 0.5), 0 0 20px rgba(239, 68, 68, 0.2)`
          : `inset -4px 0 0 0 rgba(239, 68, 68, ${intensity})`,
        backgroundColor: willTrigger ? 'rgba(239, 68, 68, 0.05)' : undefined,
      };
    } else if (swipeOffset > SWIPE_CONFIG.feedbackThreshold) {
      // Swiping right - follow (green indicator)
      return {
        boxShadow: willTrigger
          ? `inset 6px 0 0 0 rgba(34, 197, 94, 0.5), 0 0 20px rgba(34, 197, 94, 0.2)`
          : `inset 4px 0 0 0 rgba(34, 197, 94, ${intensity})`,
        backgroundColor: willTrigger ? 'rgba(34, 197, 94, 0.05)' : undefined,
      };
    }
    return {};
  };

  // Render swipe direction indicator overlays
  const renderSwipeIndicators = () => {
    if (!isSwiping || !swipeDirection) return null;

    const progress = Math.min(Math.abs(swipeOffset) / swipeDistance, 1);
    const opacity = 0.3 + (progress * 0.5); // 30% to 80% opacity

    return (
      <>
        {/* Left swipe indicator (dismiss) */}
        {swipeDirection === 'left' && (
          <div
            className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none z-10"
            style={{ opacity }}
          >
            <span className={cn(
              'text-xs font-medium transition-all',
              willTrigger ? 'text-red-600 dark:text-red-400' : 'text-red-400 dark:text-red-500'
            )}>
              {willTrigger ? 'Release to dismiss' : 'Dismiss'}
            </span>
            <div className={cn(
              'p-1.5 rounded-full transition-all',
              willTrigger
                ? 'bg-red-500 text-white scale-110'
                : 'bg-red-100 dark:bg-red-900/30 text-red-500 dark:text-red-400'
            )}>
              <XCircle className="h-4 w-4" />
            </div>
          </div>
        )}

        {/* Right swipe indicator (follow/approve) */}
        {swipeDirection === 'right' && (
          <div
            className="absolute left-2 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none z-10"
            style={{ opacity }}
          >
            <div className={cn(
              'p-1.5 rounded-full transition-all',
              willTrigger
                ? 'bg-green-500 text-white scale-110'
                : 'bg-green-100 dark:bg-green-900/30 text-green-500 dark:text-green-400'
            )}>
              <CheckCircle className="h-4 w-4" />
            </div>
            <span className={cn(
              'text-xs font-medium transition-all',
              willTrigger ? 'text-green-600 dark:text-green-400' : 'text-green-400 dark:text-green-500'
            )}>
              {willTrigger ? 'Release to approve' : 'Approve'}
            </span>
          </div>
        )}
      </>
    );
  };

  // Create a stable click handler that passes cardId to the onClick callback
  const handleClick = useCallback(() => {
    onClick?.(cardId);
  }, [onClick, cardId]);

  return (
    <div
      {...bind()}
      ref={cardRef}
      tabIndex={tabIndex}
      onClick={handleClick}
      className={cn(className, 'relative')}
      style={{
        ...style,
        touchAction: 'pan-y pinch-zoom', // Allow vertical scroll and pinch zoom
        transform: isSwiping ? `translateX(${swipeOffset * SWIPE_CONFIG.damping}px)` : undefined,
        transition: isSwiping ? 'none' : 'transform 0.2s ease-out, box-shadow 0.2s ease-out',
        ...getSwipeStyles(),
      }}
    >
      {renderSwipeIndicators()}
      {children}
    </div>
  );
}, areSwipeableCardPropsEqual);

/**
 * Get human-readable action description for toast
 */
function getActionDescription(action: UndoAction): { verb: string; icon: React.ReactNode } {
  switch (action.type) {
    case 'approve':
      return { verb: 'approved', icon: <CheckCircle className="h-4 w-4 text-green-500" /> };
    case 'reject':
      return { verb: 'rejected', icon: <XCircle className="h-4 w-4 text-red-500" /> };
    case 'dismiss':
      return { verb: 'dismissed', icon: <XCircle className="h-4 w-4 text-gray-500" /> };
    case 'defer':
      return { verb: 'deferred', icon: <Clock className="h-4 w-4 text-amber-500" /> };
  }
}

/**
 * UndoToast Component
 * Displays a toast notification with an undo button after actions
 * Auto-dismisses after UNDO_TIMEOUT_MS with a visual countdown
 *
 * Memoization:
 * - Wrapped with React.memo to prevent unnecessary re-renders
 * - onUndo and onDismiss callbacks should be memoized at call site (via useCallback)
 * - timeRemaining will change frequently, but other props remain stable
 */
interface UndoToastProps {
  action: UndoAction;
  onUndo: () => void;
  onDismiss: () => void;
  timeRemaining: number; // ms remaining until auto-dismiss
}

const UndoToast = React.memo(function UndoToast({ action, onUndo, onDismiss, timeRemaining }: UndoToastProps) {
  const { verb, icon } = getActionDescription(action);
  const progressPercent = Math.max(0, (timeRemaining / UNDO_TIMEOUT_MS) * 100);

  // Truncate card name based on screen size (shorter on mobile)
  const maxLength = typeof window !== 'undefined' && window.innerWidth < 640 ? 20 : 40;
  const cardName = action.card.name.length > maxLength
    ? `${action.card.name.substring(0, maxLength - 3)}...`
    : action.card.name;

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        'fixed bottom-4 sm:bottom-6 left-3 right-3 sm:left-1/2 sm:right-auto sm:-translate-x-1/2 z-50',
        'flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg shadow-lg',
        'bg-white dark:bg-[#3d4176] border border-gray-200 dark:border-gray-600',
        'animate-in slide-in-from-bottom-4 fade-in duration-200'
      )}
    >
      {/* Icon */}
      {icon}

      {/* Message */}
      <span className="text-xs sm:text-sm text-gray-700 dark:text-gray-200 flex-1 min-w-0 truncate">
        <span className="font-medium">&quot;{cardName}&quot;</span> {verb}
      </span>

      {/* Undo Button - min 44px touch target */}
      <button
        onClick={onUndo}
        className={cn(
          'inline-flex items-center justify-center gap-1 sm:gap-1.5 px-3 sm:px-3 py-2.5 sm:py-1.5',
          'min-h-[44px] min-w-[44px]',
          'text-xs sm:text-sm font-medium rounded-md transition-colors flex-shrink-0',
          'bg-brand-blue/10 text-brand-blue hover:bg-brand-blue/20',
          'dark:bg-brand-blue/20 dark:hover:bg-brand-blue/30',
          'active:scale-95'
        )}
      >
        <Undo2 className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
        Undo
      </button>

      {/* Close Button - min 44px touch target */}
      <button
        onClick={onDismiss}
        className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors flex-shrink-0 active:scale-95"
        aria-label="Dismiss notification"
      >
        <X className="h-5 w-5" />
      </button>

      {/* Progress bar showing time remaining */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200 dark:bg-gray-600 rounded-b-lg overflow-hidden">
        <div
          className="h-full bg-brand-blue transition-all duration-100 ease-linear"
          style={{ width: `${progressPercent}%` }}
        />
      </div>
    </div>
  );
});

const DiscoveryQueue: React.FC = () => {
  const { user } = useAuthContext();
  const isMobile = useIsMobile();
  const [cards, setCards] = useState<PendingCard[]>([]);
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Progress tracking - stores initial count when queue was loaded
  const [initialCardCount, setInitialCardCount] = useState<number>(0);

  // Undo stack - tracks recent actions for undo functionality (LIFO order)
  const [undoStack, setUndoStack] = useState<UndoAction[]>([]);

  // Toast state - tracks visibility and countdown timer
  const [toastVisible, setToastVisible] = useState(false);
  const [toastTimeRemaining, setToastTimeRemaining] = useState(UNDO_TIMEOUT_MS);
  const toastTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  // Cache for stable ref callbacks per card ID - prevents new function references on each render
  const cardRefCallbacksCache = useRef<Map<string, (el: HTMLDivElement | null) => void>>(new Map());

  // Debounce ref to prevent rapid keyboard input from double-executing actions
  const lastActionTimeRef = useRef<number>(0);

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
      // Set initial count for progress tracking (only if we have cards)
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

    // If we found a valid action to undo, restore the card to the list
    if (undoneAction) {
      setCards((prevCards) => {
        // Check if card already exists (prevent duplicates)
        if (prevCards.some((c) => c.id === undoneAction!.card.id)) {
          return prevCards;
        }
        // Add the card back to the list
        return [...prevCards, undoneAction!.card];
      });
    }

    return undoneAction;
  }, []);

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

  /**
   * Handle card review action
   */
  const handleReviewAction = useCallback(async (cardId: string, action: ReviewAction) => {
    if (!user) return;

    // Find the card before we remove it (needed for undo)
    const cardToAction = cards.find((c) => c.id === cardId);
    if (!cardToAction) return;

    try {
      setActionLoading(cardId);
      setOpenDropdown(null);

      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) throw new Error('Not authenticated');

      await reviewCard(token, cardId, action);

      // Push to undo stack before removing (map ReviewAction to UndoActionType)
      const undoActionType: UndoActionType = action === 'approve' ? 'approve' : action === 'reject' ? 'reject' : 'defer';
      pushToUndoStack({
        type: undoActionType,
        card: cardToAction,
        timestamp: Date.now(),
      });

      // Remove card from list on success
      setCards((prev) => prev.filter((c) => c.id !== cardId));
      setSelectedCards((prev) => {
        const next = new Set(prev);
        next.delete(cardId);
        return next;
      });

      // Show undo toast
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

    // Find the card before we remove it (needed for undo)
    const cardToDismiss = cards.find((c) => c.id === cardId);
    if (!cardToDismiss) return;

    try {
      setActionLoading(cardId);
      setOpenDropdown(null);

      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) throw new Error('Not authenticated');

      await dismissCard(token, cardId, reason);

      // Push to undo stack before removing
      pushToUndoStack({
        type: 'dismiss',
        card: cardToDismiss,
        timestamp: Date.now(),
        dismissReason: reason,
      });

      // Remove card from list on success
      setCards((prev) => prev.filter((c) => c.id !== cardId));
      setSelectedCards((prev) => {
        const next = new Set(prev);
        next.delete(cardId);
        return next;
      });

      // Show undo toast
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
   * Used by SwipeableCard - accepts cardId parameter for stable reference pattern
   * This prevents creating new function references per card per render
   */
  const handleSwipeApprove = useCallback((cardId: string) => {
    handleReviewAction(cardId, 'approve');
  }, [handleReviewAction]);

  /**
   * Stable callback for swipe-left action (dismiss as irrelevant)
   * Used by SwipeableCard - accepts cardId parameter for stable reference pattern
   * This prevents creating new function references per card per render
   */
  const handleSwipeDismiss = useCallback((cardId: string) => {
    handleDismiss(cardId, 'irrelevant');
  }, [handleDismiss]);

  /**
   * Stable callback for card click action (set focused card)
   * Used by SwipeableCard - accepts cardId parameter for stable reference pattern
   * This prevents creating new function references per card per render
   * Looks up the index from filteredCards at click time to handle filter changes correctly
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

      // Remove processed cards from list
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

  // Progress tracking stats
  const progressStats = React.useMemo(() => {
    const reviewed = initialCardCount - cards.length;
    const total = initialCardCount;
    const percentage = total > 0 ? (reviewed / total) * 100 : 0;
    return { reviewed, total, percentage };
  }, [cards.length, initialCardCount]);

  // Get the currently focused card (if any)
  const focusedCardId = focusedCardIndex >= 0 && focusedCardIndex < filteredCards.length
    ? filteredCards[focusedCardIndex].id
    : null;

  /**
   * Check if enough time has passed since the last action to allow a new one.
   * This prevents rapid keyboard input from causing double-execution.
   * Returns true if action should proceed, false if it should be debounced.
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

  // Keyboard shortcuts for navigation (disabled in form fields)
  useHotkeys('j', navigateNext, {
    preventDefault: true,
    enableOnFormTags: false,
  }, [navigateNext]);
  useHotkeys('k', navigatePrevious, {
    preventDefault: true,
    enableOnFormTags: false,
  }, [navigatePrevious]);

  /**
   * Follow/approve the focused card (f key)
   * Only works when a card is focused and not in a form field
   * Debounced to prevent rapid double-execution
   */
  useHotkeys(
    'f',
    () => {
      if (focusedCardId && !actionLoading && canExecuteAction()) {
        handleReviewAction(focusedCardId, 'approve');
      }
    },
    {
      preventDefault: true,
      enableOnFormTags: false,
    },
    [focusedCardId, actionLoading, handleReviewAction, canExecuteAction]
  );

  /**
   * Dismiss the focused card (d key)
   * Only works when a card is focused and not in a form field
   * Debounced to prevent rapid double-execution
   */
  useHotkeys(
    'd',
    () => {
      if (focusedCardId && !actionLoading && canExecuteAction()) {
        handleDismiss(focusedCardId, 'irrelevant');
      }
    },
    {
      preventDefault: true,
      enableOnFormTags: false,
    },
    [focusedCardId, actionLoading, handleDismiss, canExecuteAction]
  );

  /**
   * Undo last action (z key)
   * Only works when there's an undoable action
   * Debounced to prevent accidental double-undo
   */
  useHotkeys(
    'z',
    () => {
      if (toastVisible && canUndo() && canExecuteAction()) {
        handleUndoFromToast();
      }
    },
    {
      preventDefault: true,
      enableOnFormTags: false,
    },
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
   * Returns a stable callback that updates the cardRefs Map for a specific card ID.
   * Uses a persistent cache (cardRefCallbacksCache) to ensure the same callback instance
   * is returned for the same card ID across renders, preventing unnecessary re-renders
   * of SwipeableCard components.
   *
   * The returned function handles both mount (el !== null) and unmount (el === null) cases.
   */
  const getCardRefCallback = useCallback((cardId: string) => {
    // Check cache first - return existing callback if available
    let callback = cardRefCallbacksCache.current.get(cardId);
    if (!callback) {
      // Create and cache a new callback for this card ID
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

        {/* Stats Chips - horizontally scrollable on mobile */}
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

      {/* Keyboard Shortcuts Hint - hidden on mobile (touch users swipe instead) */}
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

      {/* Mobile Swipe Hint - shown on mobile only */}
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
              {/* Empty queue - all cards reviewed */}
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
              {/* No cards match current filters */}
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
        <div className="space-y-3 sm:space-y-4">
          {filteredCards.map((card) => {
            const stageNumber = parseStageNumber(card.stage_id);
            const isSelected = selectedCards.has(card.id);
            const isLoading = actionLoading === card.id;
            const isDropdownOpen = openDropdown === card.id;
            const isFocused = focusedCardId === card.id;

            return (
              <SwipeableCard
                key={card.id}
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
                  {/* Checkbox - wrapped in 44px touch target */}
                  <label
                    className="flex-shrink-0 flex items-center justify-center min-h-[44px] min-w-[44px] -m-2 cursor-pointer"
                    aria-label={`Select ${card.name}`}
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
                    {/* Header Row - stack on mobile */}
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-4 mb-2 sm:mb-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-base sm:text-lg font-medium text-gray-900 dark:text-white line-clamp-2 sm:line-clamp-none">
                          {card.name}
                        </h3>
                        {/* Badges - horizontally scrollable on mobile */}
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

                      {/* Discovered Date - inline on mobile */}
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

                    {/* Action Buttons - min 44px touch targets on mobile */}
                    <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                      <button
                        onClick={() => handleReviewAction(card.id, 'approve')}
                        disabled={isLoading}
                        className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 px-3 sm:px-3 py-2 sm:py-1.5 rounded-md text-xs sm:text-sm font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50 disabled:opacity-50 transition-colors active:scale-95"
                        title="Approve this card"
                      >
                        <CheckCircle className="h-5 w-5 sm:h-4 sm:w-4 sm:mr-1.5" />
                        <span className="hidden sm:inline ml-1.5">Approve</span>
                      </button>

                      <Link
                        to={`/cards/${card.slug}?mode=edit`}
                        className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 px-3 sm:px-3 py-2 sm:py-1.5 rounded-md text-xs sm:text-sm font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors active:scale-95"
                        title="Edit and approve"
                      >
                        <Edit3 className="h-5 w-5 sm:h-4 sm:w-4 sm:mr-1.5" />
                        <span className="hidden sm:inline ml-1.5">Edit</span>
                      </Link>

                      <button
                        onClick={() => handleDismiss(card.id, 'irrelevant')}
                        disabled={isLoading}
                        className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 px-3 sm:px-3 py-2 sm:py-1.5 rounded-md text-xs sm:text-sm font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900/50 disabled:opacity-50 transition-colors active:scale-95"
                        title="Reject this card"
                      >
                        <XCircle className="h-5 w-5 sm:h-4 sm:w-4 sm:mr-1.5" />
                        <span className="hidden sm:inline ml-1.5">Reject</span>
                      </button>

                      {/* More Options Dropdown - 44px touch target */}
                      <div className="relative ml-auto sm:ml-0">
                        <button
                          onClick={() => setOpenDropdown(isDropdownOpen ? null : card.id)}
                          className="flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 sm:p-1.5 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:scale-95"
                          title="More options"
                          aria-label="More options"
                        >
                          <MoreHorizontal className="h-5 w-5 sm:h-4 sm:w-4" />
                        </button>

                        {isDropdownOpen && (
                          <div className="absolute right-0 mt-1 w-48 sm:w-48 bg-white dark:bg-[#3d4176] rounded-md shadow-lg border border-gray-200 dark:border-gray-600 py-1 z-10">
                            <button
                              onClick={() => handleDismiss(card.id, 'duplicate')}
                              className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                            >
                              Mark as Duplicate
                            </button>
                            <button
                              onClick={() => handleDismiss(card.id, 'out_of_scope')}
                              className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                            >
                              Out of Scope
                            </button>
                            <button
                              onClick={() => handleDismiss(card.id, 'low_quality')}
                              className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                            >
                              Low Quality
                            </button>
                            <button
                              onClick={() => handleReviewAction(card.id, 'defer')}
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
