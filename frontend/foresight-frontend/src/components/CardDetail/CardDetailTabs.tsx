/**
 * CardDetailTabs Component
 *
 * Tab navigation component for the CardDetail page.
 * Displays a horizontal tab bar with icons for navigating between
 * Overview, Sources, Timeline, Notes, and Related sections.
 *
 * Features:
 * - Responsive design with horizontal scroll on mobile
 * - Keyboard navigation support (Tab, Enter, Space, Arrow keys)
 * - ARIA attributes for accessibility
 * - Dark mode support
 * - Active tab styling with brand colors
 *
 * @module CardDetail
 */

import React, { useCallback, useRef, type KeyboardEvent } from "react";
import {
  Eye,
  FileText,
  Calendar,
  TrendingUp,
  GitBranch,
  FolderOpen,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { CardDetailTab } from "./types";

/**
 * Tab definition object
 */
export interface TabDefinition {
  /** Unique tab identifier */
  id: CardDetailTab;
  /** Display name for the tab */
  name: string;
  /** Lucide icon component for the tab */
  icon: LucideIcon;
}

/**
 * Default tab definitions for CardDetail
 */
export const DEFAULT_TABS: readonly TabDefinition[] = [
  { id: "overview", name: "Overview", icon: Eye },
  { id: "sources", name: "Sources", icon: FileText },
  { id: "timeline", name: "Timeline", icon: Calendar },
  { id: "notes", name: "Notes", icon: TrendingUp },
  { id: "related", name: "Related", icon: GitBranch },
  { id: "chat", name: "Chat", icon: MessageSquare },
  { id: "assets", name: "Assets", icon: FolderOpen },
] as const;

/**
 * Props for the CardDetailTabs component
 */
export interface CardDetailTabsProps {
  /** Currently active tab */
  activeTab: CardDetailTab;
  /** Callback when a tab is selected */
  onTabChange: (tab: CardDetailTab) => void;
  /** Optional custom tab definitions (defaults to DEFAULT_TABS) */
  tabs?: readonly TabDefinition[];
  /** Optional custom className for the container */
  className?: string;
}

/**
 * CardDetailTabs renders a horizontal tab navigation bar.
 *
 * This component is designed to be accessible and responsive:
 * - Uses proper ARIA roles (tablist, tab, aria-selected)
 * - Supports keyboard navigation (Arrow keys, Enter, Space)
 * - Horizontally scrollable on small screens
 * - Dark mode compatible
 *
 * @example
 * ```tsx
 * const [activeTab, setActiveTab] = useState<CardDetailTab>('overview');
 *
 * <CardDetailTabs
 *   activeTab={activeTab}
 *   onTabChange={setActiveTab}
 * />
 * ```
 *
 * @example With custom tabs
 * ```tsx
 * const customTabs = [
 *   { id: 'overview', name: 'Overview', icon: Eye },
 *   { id: 'sources', name: 'Sources', icon: FileText },
 * ];
 *
 * <CardDetailTabs
 *   activeTab={activeTab}
 *   onTabChange={setActiveTab}
 *   tabs={customTabs}
 * />
 * ```
 */
export const CardDetailTabs: React.FC<CardDetailTabsProps> = ({
  activeTab,
  onTabChange,
  tabs = DEFAULT_TABS,
  className = "",
}) => {
  const tabListRef = useRef<HTMLElement>(null);

  /**
   * Handle keyboard navigation between tabs
   * Supports: ArrowLeft, ArrowRight, Home, End, Enter, Space
   */
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
      const tabCount = tabs.length;

      switch (event.key) {
        case "ArrowLeft": {
          event.preventDefault();
          const prevIndex =
            currentIndex === 0 ? tabCount - 1 : currentIndex - 1;
          const prevTab = tabs[prevIndex];
          if (prevTab) onTabChange(prevTab.id);
          // Focus the previous tab button
          const buttons =
            tabListRef.current?.querySelectorAll('button[role="tab"]');
          (buttons?.[prevIndex] as HTMLButtonElement)?.focus();
          break;
        }
        case "ArrowRight": {
          event.preventDefault();
          const nextIndex =
            currentIndex === tabCount - 1 ? 0 : currentIndex + 1;
          const nextTab = tabs[nextIndex];
          if (nextTab) onTabChange(nextTab.id);
          // Focus the next tab button
          const buttons =
            tabListRef.current?.querySelectorAll('button[role="tab"]');
          (buttons?.[nextIndex] as HTMLButtonElement)?.focus();
          break;
        }
        case "Home": {
          event.preventDefault();
          const firstTab = tabs[0];
          if (firstTab) onTabChange(firstTab.id);
          const buttons =
            tabListRef.current?.querySelectorAll('button[role="tab"]');
          (buttons?.[0] as HTMLButtonElement)?.focus();
          break;
        }
        case "End": {
          event.preventDefault();
          const lastTab = tabs[tabCount - 1];
          if (lastTab) onTabChange(lastTab.id);
          const buttons =
            tabListRef.current?.querySelectorAll('button[role="tab"]');
          (buttons?.[tabCount - 1] as HTMLButtonElement)?.focus();
          break;
        }
        // Enter and Space are handled by the button's onClick
      }
    },
    [tabs, onTabChange],
  );

  return (
    <div
      className={cn(
        "border-b border-gray-200 dark:border-gray-700 mb-6 sm:mb-8 -mx-4 px-4 sm:mx-0 sm:px-0",
        className,
      )}
    >
      <nav
        ref={tabListRef}
        className="-mb-px flex space-x-4 sm:space-x-8 overflow-x-auto scrollbar-hide"
        role="tablist"
        aria-label="Opportunity detail sections"
      >
        {tabs.map((tab, index) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${tab.id}`}
              tabIndex={isActive ? 0 : -1}
              className={cn(
                // Base styles
                "py-2 px-1 border-b-2 font-medium text-sm flex items-center",
                "whitespace-nowrap transition-colors flex-shrink-0",
                // Touch-friendly minimum tap target
                "min-h-[44px]",
                // Active state
                isActive
                  ? "border-brand-blue text-brand-blue"
                  : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300",
                // Focus ring for keyboard navigation
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900",
              )}
            >
              <Icon className="h-4 w-4 mr-2" aria-hidden="true" />
              {tab.name}
            </button>
          );
        })}
      </nav>
    </div>
  );
};

export default CardDetailTabs;
