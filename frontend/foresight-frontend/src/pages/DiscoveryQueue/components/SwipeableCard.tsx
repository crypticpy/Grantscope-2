import React, { useState, useCallback } from 'react';
import { useDrag } from '@use-gesture/react';
import { CheckCircle, XCircle } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { SWIPE_CONFIG } from '../types';

/**
 * Props for SwipeableCard component
 */
export interface SwipeableCardProps {
  /** Unique identifier for the card */
  cardId: string;
  /** Callback when card is swiped left - receives cardId for stable reference pattern */
  onSwipeLeft: (cardId: string) => void;
  /** Callback when card is swiped right - receives cardId for stable reference pattern */
  onSwipeRight: (cardId: string) => void;
  /** Whether swipe gestures are disabled */
  disabled?: boolean;
  /** Card content */
  children: React.ReactNode;
  /** Additional CSS classes */
  className?: string;
  /** Inline styles */
  style?: React.CSSProperties;
  /** Tab index for keyboard navigation */
  tabIndex?: number;
  /** Callback when card is clicked - receives cardId for stable reference pattern */
  onClick?: (cardId: string) => void;
  /** Ref callback for the card element */
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
  if (prevProps.style !== nextProps.style) return false;

  // Compare children by reference
  if (prevProps.children !== nextProps.children) return false;

  return true;
}

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
export const SwipeableCard = React.memo(function SwipeableCard({
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

export default SwipeableCard;
