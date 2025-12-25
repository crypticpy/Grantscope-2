/**
 * VirtualizedGrid Component
 *
 * A reusable virtualized grid component for rendering large lists of items in a responsive
 * multi-column layout. Uses @tanstack/react-virtual to only render visible rows, improving
 * performance for 100+ items.
 *
 * The grid virtualizes by row, where each row contains N items based on the column count.
 * Column count is responsive based on container width.
 */

import React, { useRef, useCallback, useState, useEffect, useMemo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { cn } from '../lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface VirtualizedGridProps<T> {
  /** Array of items to render in the grid */
  items: T[];
  /** Function to render each item */
  renderItem: (item: T, index: number) => React.ReactNode;
  /** Function to get a unique key for each item */
  getItemKey: (item: T, index: number) => string | number;
  /** Estimated height of each row in pixels (default: 280) */
  estimatedRowHeight?: number;
  /** Gap between items in pixels (default: 24, matching gap-6) */
  gap?: number;
  /**
   * Column configuration: responsive breakpoints for column counts
   * Default: { sm: 1, md: 2, lg: 3 } matching tailwind grid-cols-1 md:grid-cols-2 lg:grid-cols-3
   */
  columns?: {
    /** Base column count (< md breakpoint) */
    sm?: number;
    /** Column count at md breakpoint (768px+) */
    md?: number;
    /** Column count at lg breakpoint (1024px+) */
    lg?: number;
  };
  /** Additional className for the container */
  className?: string;
  /** Component to render when items array is empty */
  emptyState?: React.ReactNode;
  /** Component to render while loading */
  loadingState?: React.ReactNode;
  /** Whether the grid is in a loading state */
  isLoading?: boolean;
  /** Number of rows to render beyond the visible area (default: 3) */
  overscan?: number;
  /** Callback when scroll position changes */
  onScroll?: (scrollOffset: number) => void;
  /** Initial scroll offset to restore */
  initialScrollOffset?: number;
}

// ============================================================================
// Breakpoints (matching Tailwind defaults)
// ============================================================================

const BREAKPOINTS = {
  md: 768,
  lg: 1024,
} as const;

// ============================================================================
// Hook: useContainerWidth
// ============================================================================

/**
 * Hook to track container width using ResizeObserver
 */
function useContainerWidth(ref: React.RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    // Set initial width
    setWidth(element.offsetWidth);

    // Observe size changes
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const newWidth = entry.contentRect.width;
        setWidth(newWidth);
      }
    });

    resizeObserver.observe(element);

    return () => {
      resizeObserver.disconnect();
    };
  }, [ref]);

  return width;
}

// ============================================================================
// Hook: useColumnCount
// ============================================================================

/**
 * Hook to calculate column count based on container width
 */
function useColumnCount(
  containerWidth: number,
  columns: Required<VirtualizedGridProps<unknown>['columns']>
): number {
  return useMemo(() => {
    if (containerWidth >= BREAKPOINTS.lg) {
      return columns.lg ?? columns.md ?? columns.sm ?? 1;
    }
    if (containerWidth >= BREAKPOINTS.md) {
      return columns.md ?? columns.sm ?? 1;
    }
    return columns.sm ?? 1;
  }, [containerWidth, columns.sm, columns.md, columns.lg]);
}

// ============================================================================
// Main Component
// ============================================================================

export function VirtualizedGrid<T>({
  items,
  renderItem,
  getItemKey,
  estimatedRowHeight = 280,
  gap = 24,
  columns = { sm: 1, md: 2, lg: 3 },
  className,
  emptyState,
  loadingState,
  isLoading = false,
  overscan = 3,
  onScroll,
  initialScrollOffset,
}: VirtualizedGridProps<T>): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const containerWidth = useContainerWidth(containerRef);

  // Ensure columns has all values (with defaults)
  const normalizedColumns = useMemo(() => ({
    sm: columns.sm ?? 1,
    md: columns.md ?? 2,
    lg: columns.lg ?? 3,
  }), [columns.sm, columns.md, columns.lg]);

  const columnCount = useColumnCount(containerWidth, normalizedColumns);

  // Calculate number of rows
  const rowCount = useMemo(() => {
    if (items.length === 0) return 0;
    return Math.ceil(items.length / columnCount);
  }, [items.length, columnCount]);

  // Get items for a specific row
  const getRowItems = useCallback(
    (rowIndex: number): T[] => {
      const startIndex = rowIndex * columnCount;
      const endIndex = Math.min(startIndex + columnCount, items.length);
      return items.slice(startIndex, endIndex);
    },
    [items, columnCount]
  );

  // Initialize virtualizer
  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => containerRef.current,
    estimateSize: () => estimatedRowHeight + gap,
    overscan,
  });

  // Track if initial scroll has been applied
  const hasAppliedInitialScroll = useRef(false);

  // Restore scroll position on mount
  useEffect(() => {
    if (
      initialScrollOffset !== undefined &&
      initialScrollOffset > 0 &&
      !hasAppliedInitialScroll.current &&
      containerRef.current
    ) {
      virtualizer.scrollToOffset(initialScrollOffset);
      hasAppliedInitialScroll.current = true;
    }
  }, [initialScrollOffset, virtualizer]);

  // Handle scroll events
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !onScroll) return;

    const handleScroll = () => {
      onScroll(container.scrollTop);
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [onScroll]);

  // Handle loading state
  if (isLoading && loadingState) {
    return <>{loadingState}</>;
  }

  // Handle empty state
  if (items.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  // Don't render until we have a container width
  if (containerWidth === 0) {
    return (
      <div
        ref={containerRef}
        className={cn('h-full w-full overflow-auto', className)}
        style={{ minHeight: '400px' }}
      />
    );
  }

  const virtualRows = virtualizer.getVirtualItems();

  return (
    <div
      ref={containerRef}
      className={cn('h-full w-full overflow-auto', className)}
    >
      {/* Total height container for scroll height calculation */}
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {/* Virtual rows container - positioned at the start of visible rows */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            transform: `translateY(${virtualRows[0]?.start ?? 0}px)`,
          }}
        >
          {virtualRows.map((virtualRow) => {
            const rowItems = getRowItems(virtualRow.index);
            const isLastRow = virtualRow.index === rowCount - 1;
            const itemsInRow = rowItems.length;

            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  display: 'grid',
                  gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))`,
                  gap: `${gap}px`,
                  paddingBottom: isLastRow ? 0 : `${gap}px`,
                }}
              >
                {rowItems.map((item, indexInRow) => {
                  const globalIndex = virtualRow.index * columnCount + indexInRow;
                  return (
                    <div key={getItemKey(item, globalIndex)}>
                      {renderItem(item, globalIndex)}
                    </div>
                  );
                })}
                {/* Fill empty cells in partial last row to maintain grid alignment */}
                {isLastRow && itemsInRow < columnCount &&
                  Array.from({ length: columnCount - itemsInRow }).map((_, i) => (
                    <div key={`empty-${i}`} aria-hidden="true" />
                  ))
                }
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Helper function to scroll to a specific item index
 */
export function scrollToItemIndex<T>(
  virtualizer: ReturnType<typeof useVirtualizer>,
  itemIndex: number,
  columnCount: number
): void {
  const rowIndex = Math.floor(itemIndex / columnCount);
  virtualizer.scrollToIndex(rowIndex, { align: 'start' });
}

export default VirtualizedGrid;
