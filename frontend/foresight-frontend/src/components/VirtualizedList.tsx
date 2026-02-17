/**
 * VirtualizedList Component
 *
 * A reusable virtualized list component for efficiently rendering large lists
 * with variable item heights. Built on @tanstack/react-virtual.
 *
 * Features:
 * - Dynamic item height measurement
 * - Keyboard navigation support (arrow keys, home, end)
 * - Loading and empty state handling
 * - Scroll to item functionality
 * - Focus management for accessibility
 */

import React, {
  useRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  forwardRef,
} from "react";
import { useVirtualizer, VirtualItem } from "@tanstack/react-virtual";
import { cn } from "../lib/utils";

/**
 * Props for the VirtualizedList component
 */
export interface VirtualizedListProps<T> {
  /** Array of items to render */
  items: T[];
  /** Function to render each item */
  renderItem: (
    item: T,
    index: number,
    virtualItem: VirtualItem,
  ) => React.ReactNode;
  /** Estimated height of each item in pixels (used for initial layout) */
  estimatedSize?: number;
  /** Number of items to render outside the visible area */
  overscan?: number;
  /** Key extractor function for items */
  getItemKey?: (item: T, index: number) => string | number;
  /** Callback when an item is clicked */
  onItemClick?: (item: T, index: number) => void;
  /** Callback for keyboard navigation - called when focused item changes */
  onFocusedIndexChange?: (index: number) => void;
  /** Enable keyboard navigation (arrow keys, home, end) */
  enableKeyboardNavigation?: boolean;
  /** Currently focused item index (controlled) */
  focusedIndex?: number;
  /** Whether the list is in a loading state */
  isLoading?: boolean;
  /** Custom loading component */
  loadingComponent?: React.ReactNode;
  /** Custom empty state component */
  emptyComponent?: React.ReactNode;
  /** Additional className for the container */
  className?: string;
  /** Additional className for the scrollable container */
  scrollContainerClassName?: string;
  /** Gap between items in pixels */
  gap?: number;
  /** Padding at the start of the list */
  paddingStart?: number;
  /** Padding at the end of the list */
  paddingEnd?: number;
  /** Scroll margin for scrollToIndex */
  scrollMargin?: number;
  /** aria-label for the list */
  ariaLabel?: string;
  /** Test ID for testing */
  testId?: string;
}

/**
 * Ref handle for imperative actions
 */
export interface VirtualizedListHandle {
  /** Scroll to a specific item index */
  scrollToIndex: (
    index: number,
    options?: { align?: "start" | "center" | "end" | "auto" },
  ) => void;
  /** Get the current scroll offset */
  getScrollOffset: () => number;
  /** Set the scroll offset */
  setScrollOffset: (offset: number) => void;
  /** Force re-measurement of all items */
  measure: () => void;
}

/**
 * Default loading component
 */
function DefaultLoadingComponent() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
    </div>
  );
}

/**
 * Default empty state component
 */
function DefaultEmptyComponent() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-500 dark:text-gray-400">
      <p>No items to display</p>
    </div>
  );
}

/**
 * Inner component with generics support
 */
function VirtualizedListInner<T>(
  props: VirtualizedListProps<T>,
  ref: React.ForwardedRef<VirtualizedListHandle>,
) {
  const {
    items,
    renderItem,
    estimatedSize = 100,
    overscan = 5,
    getItemKey,
    onItemClick,
    onFocusedIndexChange,
    enableKeyboardNavigation = false,
    focusedIndex,
    isLoading = false,
    loadingComponent,
    emptyComponent,
    className,
    scrollContainerClassName,
    gap = 0,
    paddingStart = 0,
    paddingEnd = 0,
    scrollMargin = 0,
    ariaLabel,
    testId,
  } = props;

  const parentRef = useRef<HTMLDivElement>(null);
  const internalFocusedIndex = useRef<number>(focusedIndex ?? -1);

  // TanStack Virtual tracks option identity (including `getItemKey`) and can
  // trigger a rerender via `onChange` during render if these change. Ensure we
  // provide stable function references to avoid render-loop crashes (#301).
  const getScrollElement = useCallback(() => parentRef.current, []);
  const estimateSizeFn = useCallback(() => estimatedSize, [estimatedSize]);
  const getVirtualizerItemKey = useCallback(
    (index: number) => {
      const item = items[index];
      return item !== undefined ? (getItemKey?.(item, index) ?? index) : index;
    },
    [getItemKey, items],
  );

  // Update internal focused index when controlled value changes
  useEffect(() => {
    if (focusedIndex !== undefined) {
      internalFocusedIndex.current = focusedIndex;
    }
  }, [focusedIndex]);

  // Initialize the virtualizer
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement,
    estimateSize: estimateSizeFn,
    overscan,
    getItemKey: getItemKey ? getVirtualizerItemKey : undefined,
    gap,
    paddingStart,
    paddingEnd,
    scrollMargin,
  });

  // Expose imperative handle
  useImperativeHandle(
    ref,
    () => ({
      scrollToIndex: (index, options) => {
        virtualizer.scrollToIndex(index, {
          align: options?.align ?? "auto",
          behavior: "smooth",
        });
      },
      getScrollOffset: () => virtualizer.scrollOffset ?? 0,
      setScrollOffset: (offset) => {
        if (parentRef.current) {
          parentRef.current.scrollTop = offset;
        }
      },
      measure: () => virtualizer.measure(),
    }),
    [virtualizer],
  );

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (!enableKeyboardNavigation || items.length === 0) return;

      let newIndex = internalFocusedIndex.current;
      let handled = false;

      switch (event.key) {
        case "ArrowDown":
        case "j":
          newIndex = Math.min(
            internalFocusedIndex.current + 1,
            items.length - 1,
          );
          handled = true;
          break;
        case "ArrowUp":
        case "k":
          newIndex = Math.max(internalFocusedIndex.current - 1, 0);
          handled = true;
          break;
        case "Home":
          newIndex = 0;
          handled = true;
          break;
        case "End":
          newIndex = items.length - 1;
          handled = true;
          break;
        case "Enter":
        case " ": {
          const focusedItem = items[internalFocusedIndex.current];
          if (
            internalFocusedIndex.current >= 0 &&
            onItemClick &&
            focusedItem !== undefined
          ) {
            onItemClick(focusedItem, internalFocusedIndex.current);
            handled = true;
          }
          break;
        }
      }

      if (handled) {
        event.preventDefault();
        event.stopPropagation();

        if (newIndex !== internalFocusedIndex.current && newIndex >= 0) {
          internalFocusedIndex.current = newIndex;
          onFocusedIndexChange?.(newIndex);
          virtualizer.scrollToIndex(newIndex, { align: "auto" });
        }
      }
    },
    [
      enableKeyboardNavigation,
      items,
      onItemClick,
      onFocusedIndexChange,
      virtualizer,
    ],
  );

  // Handle item click
  const handleItemClick = useCallback(
    (item: T, index: number) => {
      internalFocusedIndex.current = index;
      onFocusedIndexChange?.(index);
      onItemClick?.(item, index);
    },
    [onItemClick, onFocusedIndexChange],
  );

  // Loading state
  if (isLoading) {
    return (
      <div className={cn("w-full", className)} data-testid={testId}>
        {loadingComponent ?? <DefaultLoadingComponent />}
      </div>
    );
  }

  // Empty state
  if (items.length === 0) {
    return (
      <div className={cn("w-full", className)} data-testid={testId}>
        {emptyComponent ?? <DefaultEmptyComponent />}
      </div>
    );
  }

  const virtualItems = virtualizer.getVirtualItems();

  return (
    <div
      className={cn("w-full", className)}
      data-testid={testId}
      onKeyDown={enableKeyboardNavigation ? handleKeyDown : undefined}
      tabIndex={enableKeyboardNavigation ? 0 : undefined}
      role="list"
      aria-label={ariaLabel}
    >
      {/* Scrollable container */}
      <div
        ref={parentRef}
        className={cn("h-full w-full overflow-auto", scrollContainerClassName)}
      >
        {/* Virtual content container */}
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {/* Render visible items */}
          {virtualItems.map((virtualItem) => {
            const item = items[virtualItem.index]!;
            const isFocused =
              focusedIndex !== undefined
                ? virtualItem.index === focusedIndex
                : virtualItem.index === internalFocusedIndex.current;

            return (
              <div
                key={virtualItem.key}
                data-index={virtualItem.index}
                ref={virtualizer.measureElement}
                role="listitem"
                aria-selected={isFocused}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualItem.start}px)`,
                }}
                onClick={() => handleItemClick(item, virtualItem.index)}
              >
                {renderItem(item, virtualItem.index, virtualItem)}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/**
 * VirtualizedList Component
 *
 * A high-performance virtualized list that only renders visible items.
 * Supports variable item heights, keyboard navigation, and imperative actions.
 *
 * @example
 * ```tsx
 * const listRef = useRef<VirtualizedListHandle>(null);
 *
 * <VirtualizedList
 *   ref={listRef}
 *   items={cards}
 *   renderItem={(card, index) => <CardItem card={card} />}
 *   estimatedSize={200}
 *   enableKeyboardNavigation
 *   onItemClick={(card) => navigate(`/signals/${card.slug}`)}
 * />
 * ```
 */
export const VirtualizedList = forwardRef(VirtualizedListInner) as <T>(
  props: VirtualizedListProps<T> & {
    ref?: React.ForwardedRef<VirtualizedListHandle>;
  },
) => React.ReactElement;

export default VirtualizedList;
