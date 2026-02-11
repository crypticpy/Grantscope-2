/**
 * Tooltip Component
 *
 * A base tooltip wrapper using @radix-ui/react-tooltip with:
 * - Consistent styling matching the app theme
 * - Hover trigger on desktop
 * - Click trigger on mobile (via Popover fallback)
 * - Configurable delay and positioning
 */

import * as React from 'react';
import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import * as PopoverPrimitive from '@radix-ui/react-popover';
import { cn } from '../../lib/utils';
import { useIsMobile } from '../../hooks/use-mobile';

// Re-export provider for app-level setup
export const TooltipProvider = TooltipPrimitive.Provider;

export interface TooltipProps {
  /** The trigger element */
  children: React.ReactNode;
  /** Tooltip content - can be string or React node */
  content: React.ReactNode;
  /** Side of the trigger to show tooltip */
  side?: 'top' | 'right' | 'bottom' | 'left';
  /** Alignment along the side */
  align?: 'start' | 'center' | 'end';
  /** Delay before showing (desktop only) */
  delayDuration?: number;
  /** Additional className for content wrapper */
  contentClassName?: string;
  /** Whether tooltip is disabled */
  disabled?: boolean;
  /** Control open state externally */
  open?: boolean;
  /** Callback when open state changes */
  onOpenChange?: (open: boolean) => void;
  /** Offset from trigger element */
  sideOffset?: number;
}

/**
 * Tooltip component that automatically switches between
 * hover (desktop) and click (mobile) triggers
 */
export function Tooltip({
  children,
  content,
  side = 'top',
  align = 'center',
  delayDuration = 300,
  contentClassName,
  disabled = false,
  open,
  onOpenChange,
  sideOffset = 4,
}: TooltipProps) {
  const isMobile = useIsMobile();

  if (disabled || !content) {
    return <>{children}</>;
  }

  // Mobile: Use Popover for click-to-open behavior
  if (isMobile) {
    return (
      <PopoverPrimitive.Root open={open} onOpenChange={onOpenChange}>
        <PopoverPrimitive.Trigger asChild>{children}</PopoverPrimitive.Trigger>
        <PopoverPrimitive.Portal>
          <PopoverPrimitive.Content
            side={side}
            align={align}
            sideOffset={sideOffset}
            className={cn(
              'z-50 max-w-xs overflow-hidden rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 shadow-md',
              'animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
              'data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
              'dark:border-gray-700 dark:bg-dark-surface dark:text-gray-100',
              contentClassName
            )}
          >
            {content}
          </PopoverPrimitive.Content>
        </PopoverPrimitive.Portal>
      </PopoverPrimitive.Root>
    );
  }

  // Desktop: Use Tooltip for hover behavior
  return (
    <TooltipPrimitive.Root
      delayDuration={delayDuration}
      open={open}
      onOpenChange={onOpenChange}
    >
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          align={align}
          sideOffset={sideOffset}
          className={cn(
            'z-50 max-w-xs overflow-hidden rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 shadow-md',
            'animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
            'data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
            'dark:border-gray-700 dark:bg-dark-surface dark:text-gray-100',
            contentClassName
          )}
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-white dark:fill-gray-800" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

/**
 * Simple tooltip with just text content
 */
export interface SimpleTooltipProps {
  children: React.ReactNode;
  text: string;
  side?: 'top' | 'right' | 'bottom' | 'left';
  delayDuration?: number;
}

export function SimpleTooltip({
  children,
  text,
  side = 'top',
  delayDuration = 300,
}: SimpleTooltipProps) {
  return (
    <Tooltip content={text} side={side} delayDuration={delayDuration}>
      {children}
    </Tooltip>
  );
}

/**
 * Wrapper component for app-level tooltip provider setup.
 * Include this at the root of your app to enable tooltips.
 */
export function TooltipProviderWrapper({
  children,
  delayDuration = 300,
  skipDelayDuration = 300,
}: {
  children: React.ReactNode;
  delayDuration?: number;
  skipDelayDuration?: number;
}) {
  return (
    <TooltipPrimitive.Provider
      delayDuration={delayDuration}
      skipDelayDuration={skipDelayDuration}
    >
      {children}
    </TooltipPrimitive.Provider>
  );
}

export default Tooltip;
