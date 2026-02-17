/**
 * DiscoveryQueueCard Component
 *
 * A memoized card component for the DiscoveryQueue page.
 * Displays a pending discovery card with swipe gestures, selection,
 * and action buttons for approval, rejection, editing, and dismissal.
 *
 * Features:
 * - Memoized with React.memo to prevent unnecessary re-renders
 * - SwipeableCard integration for touch gestures
 * - Selection checkbox for bulk actions
 * - Action buttons with mobile-optimized touch targets
 * - Dropdown menu for additional actions
 * - Responsive design for mobile and desktop
 */

import React, { memo, useState } from "react";
import { Link } from "react-router-dom";
import { useDrag } from "@use-gesture/react";
import {
  CheckCircle,
  XCircle,
  Edit3,
  Clock,
  MoreHorizontal,
} from "lucide-react";
import { PillarBadge } from "./PillarBadge";
import { HorizonBadge } from "./HorizonBadge";
import { StageBadge } from "./StageBadge";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Tooltip } from "./ui/Tooltip";
import { cn } from "../lib/utils";
import { type PendingCard, type DismissReason } from "../lib/discovery-api";
import { Zap } from "lucide-react";

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

  if (diffHours < 1) return "Just now";
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString();
};

/**
 * Get impact score level and styling
 */
function getImpactLevel(score: number): {
  level: "high" | "medium" | "low";
  label: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
} {
  if (score >= 70) {
    return {
      level: "high",
      label: "High Impact",
      description:
        "This discovery could significantly influence strategy or decision-making.",
      color: "text-purple-600 dark:text-purple-400",
      bgColor: "bg-purple-100 dark:bg-purple-900/30",
      borderColor: "border-purple-300 dark:border-purple-700",
    };
  }
  if (score >= 40) {
    return {
      level: "medium",
      label: "Moderate Impact",
      description:
        "This discovery has notable strategic relevance and may influence planning.",
      color: "text-indigo-600 dark:text-indigo-400",
      bgColor: "bg-indigo-100 dark:bg-indigo-900/30",
      borderColor: "border-indigo-300 dark:border-indigo-700",
    };
  }
  return {
    level: "low",
    label: "Lower Impact",
    description:
      "This discovery provides background information with limited immediate strategic value.",
    color: "text-slate-600 dark:text-slate-400",
    bgColor: "bg-slate-100 dark:bg-slate-900/30",
    borderColor: "border-slate-300 dark:border-slate-700",
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
        <div className={cn("p-1.5 rounded-md", impactInfo.bgColor)}>
          <Zap className={cn("h-4 w-4", impactInfo.color)} />
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
              "h-full rounded-full transition-all duration-200",
              impactInfo.level === "high" && "bg-purple-500 dark:bg-purple-400",
              impactInfo.level === "medium" &&
                "bg-indigo-500 dark:bg-indigo-400",
              impactInfo.level === "low" && "bg-slate-500 dark:bg-slate-400",
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
  size = "sm",
}: {
  score: number;
  size?: "sm" | "md";
}) {
  const impactInfo = getImpactLevel(score);

  const sizeClasses =
    size === "sm" ? "px-1.5 py-0.5 text-xs gap-1" : "px-2 py-1 text-sm gap-1.5";

  const iconSize = size === "sm" ? 10 : 12;

  return (
    <Tooltip
      content={<ImpactScoreTooltipContent score={score} />}
      side="top"
      align="center"
      contentClassName="p-3"
    >
      <span
        className={cn(
          "inline-flex items-center rounded-full font-medium border cursor-pointer",
          impactInfo.bgColor,
          impactInfo.color,
          impactInfo.borderColor,
          sizeClasses,
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
 * SwipeableCard wrapper component for touch gesture support
 * Handles swipe left (dismiss) and swipe right (follow) gestures
 */
interface SwipeableCardWrapperProps {
  cardId: string;
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
  disabled?: boolean;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  tabIndex?: number;
  onClick?: () => void;
  cardRef?: (el: HTMLDivElement | null) => void;
  isMobile?: boolean;
}

function SwipeableCardWrapper({
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
}: SwipeableCardWrapperProps) {
  const [swipeOffset, setSwipeOffset] = useState(0);
  const [isSwiping, setIsSwiping] = useState(false);
  const [swipeDirection, setSwipeDirection] = useState<"left" | "right" | null>(
    null,
  );
  const [willTrigger, setWillTrigger] = useState(false);

  // Use mobile or desktop distance threshold
  const swipeDistance = isMobile
    ? SWIPE_CONFIG.mobileDistance
    : SWIPE_CONFIG.desktopDistance;

  const bind = useDrag(
    ({
      movement: [mx, my],
      dragging,
      tap,
      velocity: [vx],
      direction: [dx],
    }) => {
      // Ignore taps - let regular click handlers work
      if (tap) return;

      // Don't process gestures when disabled (e.g., during loading)
      if (disabled) return;

      // Calculate swipe angle to filter out vertical scrolling attempts
      const absX = Math.abs(mx);
      const absY = Math.abs(my);
      const angle = Math.atan2(absY, absX) * (180 / Math.PI);

      // If angle is too steep (vertical gesture), don't track as swipe
      if (
        angle > SWIPE_CONFIG.maxAngle &&
        absX < SWIPE_CONFIG.feedbackThreshold
      ) {
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
          setSwipeDirection("left");
          setWillTrigger(Math.abs(mx) >= swipeDistance);
        } else if (mx > SWIPE_CONFIG.feedbackThreshold) {
          setSwipeDirection("right");
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
      if (meetsDistanceThreshold || meetsVelocityThreshold) {
        if (dx < 0 && mx < 0) {
          onSwipeLeft();
        } else if (dx > 0 && mx > 0) {
          onSwipeRight();
        }
      }
    },
    {
      filterTaps: true,
      axis: "lock",
      pointer: { touch: true },
      threshold: 10,
    },
  );

  // Calculate swipe visual feedback styles
  const getSwipeStyles = (): React.CSSProperties => {
    if (!isSwiping || Math.abs(swipeOffset) < SWIPE_CONFIG.feedbackThreshold) {
      return {};
    }

    const progress = Math.min(Math.abs(swipeOffset) / swipeDistance, 1);
    const intensity = progress * 0.4;

    if (swipeOffset < -SWIPE_CONFIG.feedbackThreshold) {
      return {
        boxShadow: willTrigger
          ? `inset -6px 0 0 0 rgba(239, 68, 68, 0.5), 0 0 20px rgba(239, 68, 68, 0.2)`
          : `inset -4px 0 0 0 rgba(239, 68, 68, ${intensity})`,
        backgroundColor: willTrigger ? "rgba(239, 68, 68, 0.05)" : undefined,
      };
    } else if (swipeOffset > SWIPE_CONFIG.feedbackThreshold) {
      return {
        boxShadow: willTrigger
          ? `inset 6px 0 0 0 rgba(34, 197, 94, 0.5), 0 0 20px rgba(34, 197, 94, 0.2)`
          : `inset 4px 0 0 0 rgba(34, 197, 94, ${intensity})`,
        backgroundColor: willTrigger ? "rgba(34, 197, 94, 0.05)" : undefined,
      };
    }
    return {};
  };

  // Render swipe direction indicator overlays
  const renderSwipeIndicators = () => {
    if (!isSwiping || !swipeDirection) return null;

    const progress = Math.min(Math.abs(swipeOffset) / swipeDistance, 1);
    const opacity = 0.3 + progress * 0.5;

    return (
      <>
        {/* Left swipe indicator (dismiss) */}
        {swipeDirection === "left" && (
          <div
            className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none z-10"
            style={{ opacity }}
          >
            <span
              className={cn(
                "text-xs font-medium transition-all duration-200",
                willTrigger
                  ? "text-red-600 dark:text-red-400"
                  : "text-red-400 dark:text-red-500",
              )}
            >
              {willTrigger ? "Release to dismiss" : "Dismiss"}
            </span>
            <div
              className={cn(
                "p-1.5 rounded-full transition-all duration-200",
                willTrigger
                  ? "bg-red-500 text-white scale-110"
                  : "bg-red-100 dark:bg-red-900/30 text-red-500 dark:text-red-400",
              )}
            >
              <XCircle className="h-4 w-4" />
            </div>
          </div>
        )}

        {/* Right swipe indicator (follow/approve) */}
        {swipeDirection === "right" && (
          <div
            className="absolute left-2 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none z-10"
            style={{ opacity }}
          >
            <div
              className={cn(
                "p-1.5 rounded-full transition-all duration-200",
                willTrigger
                  ? "bg-green-500 text-white scale-110"
                  : "bg-green-100 dark:bg-green-900/30 text-green-500 dark:text-green-400",
              )}
            >
              <CheckCircle className="h-4 w-4" />
            </div>
            <span
              className={cn(
                "text-xs font-medium transition-all duration-200",
                willTrigger
                  ? "text-green-600 dark:text-green-400"
                  : "text-green-400 dark:text-green-500",
              )}
            >
              {willTrigger ? "Release to approve" : "Approve"}
            </span>
          </div>
        )}
      </>
    );
  };

  return (
    <div
      {...bind()}
      ref={cardRef}
      tabIndex={tabIndex}
      onClick={onClick}
      className={cn(className, "relative")}
      style={{
        ...style,
        touchAction: "pan-y pinch-zoom",
        transform: isSwiping
          ? `translateX(${swipeOffset * SWIPE_CONFIG.damping}px)`
          : undefined,
        transition: isSwiping
          ? "none"
          : "transform 0.2s ease-out, box-shadow 0.2s ease-out",
        ...getSwipeStyles(),
      }}
    >
      {renderSwipeIndicators()}
      {children}
    </div>
  );
}

/**
 * Props for the DiscoveryQueueCard component
 */
export interface DiscoveryQueueCardProps {
  /** The pending card data */
  card: PendingCard;
  /** Whether we're on mobile device */
  isMobile: boolean;
  /** Whether the card is focused via keyboard navigation */
  isFocused: boolean;
  /** Whether the card is selected for bulk actions */
  isSelected: boolean;
  /** Whether the card is in a loading state (action in progress) */
  isLoading: boolean;
  /** Whether the dropdown menu is open */
  isDropdownOpen: boolean;
  /** Callback when swiped right (approve) */
  onSwipeRight: () => void;
  /** Callback when swiped left (dismiss) */
  onSwipeLeft: () => void;
  /** Callback when card is clicked */
  onCardClick: () => void;
  /** Ref callback for the card element */
  onCardRef: (el: HTMLDivElement | null) => void;
  /** Callback to toggle selection */
  onToggleSelection: () => void;
  /** Callback to approve the card */
  onApprove: () => void;
  /** Callback to reject/dismiss the card */
  onReject: () => void;
  /** Callback to open/close the dropdown */
  onToggleDropdown: () => void;
  /** Callback to dismiss with a specific reason */
  onDismissWithReason: (reason: DismissReason) => void;
  /** Callback to defer the card */
  onDefer: () => void;
}

/**
 * DiscoveryQueueCard Component
 *
 * A memoized card component for displaying pending discovery cards.
 * Optimized for virtualized rendering with proper memoization.
 */
export const DiscoveryQueueCard = memo(function DiscoveryQueueCard({
  card,
  isMobile,
  isFocused,
  isSelected,
  isLoading,
  isDropdownOpen,
  onSwipeRight,
  onSwipeLeft,
  onCardClick,
  onCardRef,
  onToggleSelection,
  onApprove,
  onReject,
  onToggleDropdown,
  onDismissWithReason,
  onDefer,
}: DiscoveryQueueCardProps) {
  const stageNumber = parseStageNumber(card.stage_id);

  return (
    <SwipeableCardWrapper
      cardId={card.id}
      isMobile={isMobile}
      cardRef={onCardRef}
      onSwipeRight={onSwipeRight}
      onSwipeLeft={onSwipeLeft}
      disabled={isLoading}
      tabIndex={isFocused ? 0 : -1}
      onClick={onCardClick}
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6 border-l-4 transition-all duration-200",
        isFocused
          ? "border-l-brand-blue ring-2 ring-brand-blue/50 shadow-lg"
          : isSelected
            ? "border-l-brand-blue ring-2 ring-brand-blue/20"
            : "border-transparent hover:border-l-brand-blue",
        isLoading && "opacity-60",
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
            onChange={onToggleSelection}
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
                  <PillarBadge
                    pillarId={card.pillar_id}
                    showIcon={!isMobile}
                    size="sm"
                  />
                  <HorizonBadge horizon={card.horizon} size="sm" />
                  {stageNumber !== null && (
                    <StageBadge
                      stage={stageNumber}
                      size="sm"
                      variant="minimal"
                    />
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
              onClick={(e) => {
                e.stopPropagation();
                onApprove();
              }}
              disabled={isLoading}
              className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 px-3 sm:px-3 py-2 sm:py-1.5 rounded-md text-xs sm:text-sm font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50 disabled:opacity-50 transition-colors active:scale-95"
              title="Approve this opportunity"
            >
              <CheckCircle className="h-5 w-5 sm:h-4 sm:w-4 sm:mr-1.5" />
              <span className="hidden sm:inline ml-1.5">Approve</span>
            </button>

            <Link
              to={`/signals/${card.slug}?mode=edit`}
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
                onReject();
              }}
              disabled={isLoading}
              className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 px-3 sm:px-3 py-2 sm:py-1.5 rounded-md text-xs sm:text-sm font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900/50 disabled:opacity-50 transition-colors active:scale-95"
              title="Reject this opportunity"
            >
              <XCircle className="h-5 w-5 sm:h-4 sm:w-4 sm:mr-1.5" />
              <span className="hidden sm:inline ml-1.5">Reject</span>
            </button>

            {/* More Options Dropdown - 44px touch target */}
            <div className="relative ml-auto sm:ml-0">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleDropdown();
                }}
                className="flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 sm:p-1.5 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:scale-95"
                title="More options"
                aria-label="More options"
              >
                <MoreHorizontal className="h-5 w-5 sm:h-4 sm:w-4" />
              </button>

              {isDropdownOpen && (
                <div className="absolute right-0 mt-1 w-48 sm:w-48 bg-white dark:bg-dark-surface-elevated rounded-md shadow-lg border border-gray-200 dark:border-gray-600 py-1 z-10">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDismissWithReason("duplicate");
                    }}
                    className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                  >
                    Mark as Duplicate
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDismissWithReason("out_of_scope");
                    }}
                    className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                  >
                    Out of Scope
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDismissWithReason("low_quality");
                    }}
                    className="w-full min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 active:bg-gray-200 dark:active:bg-gray-500"
                  >
                    Low Quality
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDefer();
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
    </SwipeableCardWrapper>
  );
});

export default DiscoveryQueueCard;
