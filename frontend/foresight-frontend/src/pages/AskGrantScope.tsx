/**
 * AskGrantScope Page
 *
 * Full-page AI-powered chat interface for natural language queries against
 * the GrantScope intelligence system. Features a conversation sidebar,
 * scope selector, and the reusable ChatPanel component.
 *
 * @module pages/AskGrantScope
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { supabase } from "../App";
import {
  Plus,
  Trash2,
  Globe,
  FolderOpen,
  MessageSquare,
  Menu,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Loader2,
} from "lucide-react";
import { cn } from "../lib/utils";
import { ChatPanel } from "../components/Chat/ChatPanel";
import {
  fetchConversations,
  deleteConversation,
  searchConversations,
} from "../lib/chat-api";
import type { Conversation } from "../lib/chat-api";
import { FeatureIntroBanner } from "../components/onboarding/FeatureIntroBanner";

// ============================================================================
// Types
// ============================================================================

interface Workstream {
  id: string;
  name: string;
}

interface ScopeOption {
  label: string;
  scope: "global" | "workstream";
  scopeId?: string;
}

// ============================================================================
// Helpers
// ============================================================================

/** Groups conversations into "Today", "This Week", and "Older" buckets. */
function groupConversations(conversations: Conversation[]) {
  const now = new Date();
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - startOfWeek.getDay());

  const today: Conversation[] = [];
  const thisWeek: Conversation[] = [];
  const older: Conversation[] = [];

  for (const conv of conversations) {
    const updatedAt = new Date(conv.updated_at);
    if (updatedAt >= startOfToday) {
      today.push(conv);
    } else if (updatedAt >= startOfWeek) {
      thisWeek.push(conv);
    } else {
      older.push(conv);
    }
  }

  return { today, thisWeek, older };
}

/** Returns a human-friendly relative time string. */
function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

/** Returns the pill color classes for a scope type. */
function scopeBadgeClasses(scope: Conversation["scope"]): string {
  switch (scope) {
    case "signal":
      return "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300";
    case "workstream":
      return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300";
    case "global":
    default:
      return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300";
  }
}

/** Label for scope badge pill. */
function scopeLabel(scope: Conversation["scope"]): string {
  switch (scope) {
    case "signal":
      return "Opportunity";
    case "workstream":
      return "Workstream";
    case "global":
    default:
      return "Global";
  }
}

// ============================================================================
// Component
// ============================================================================

export default function AskGrantScope() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Scope state
  const [selectedScope, setSelectedScope] = useState<ScopeOption>({
    label: "All Opportunities",
    scope: "global",
  });
  const [workstreams, setWorkstreams] = useState<Workstream[]>([]);
  const [scopeDropdownOpen, setScopeDropdownOpen] = useState(false);

  // Conversation state — restore from sessionStorage so navigating away and
  // back doesn't lose the active conversation.
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(() => {
    try {
      return sessionStorage.getItem("grantscope:ask:activeConversationId");
    } catch {
      return null;
    }
  });
  const [activeConversationScope, setActiveConversationScope] = useState<
    "global" | "signal" | "workstream" | "wizard"
  >(() => {
    try {
      return (
        (sessionStorage.getItem("grantscope:ask:activeScope") as
          | "global"
          | "signal"
          | "workstream"
          | "wizard") || "global"
      );
    } catch {
      return "global";
    }
  });
  const [activeConversationScopeId, setActiveConversationScopeId] = useState<
    string | undefined
  >(() => {
    try {
      return (
        sessionStorage.getItem("grantscope:ask:activeScopeId") || undefined
      );
    } catch {
      return undefined;
    }
  });
  // When true, ChatPanel should start fresh (not auto-restore)
  const [forceNewChat, setForceNewChat] = useState(false);

  // Mobile sidebar
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Desktop sidebar collapse
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem("grantscope:ask:sidebarCollapsed") === "true";
    } catch {
      return false;
    }
  });

  // Conversation search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Conversation[] | null>(
    null,
  );
  const [isSearching, setIsSearching] = useState(false);

  // Initial query from URL
  const initialQuery = searchParams.get("q") || undefined;

  // ChatPanel remount key — uses a stable session counter instead of
  // activeConversationId so that the null→UUID transition from the streaming
  // done event does NOT cause a full remount. Only explicit user actions
  // (new chat, sidebar click, scope change) increment the counter.
  const chatSessionRef = useRef(0);
  const chatKey = `${chatSessionRef.current}-${selectedScope.scope}-${selectedScope.scopeId || "none"}`;

  // ============================================================================
  // Data Fetching
  // ============================================================================

  /** Load conversation history from the API. */
  const loadConversations = useCallback(async () => {
    try {
      const data = await fetchConversations({ limit: 50 });
      setConversations(data);
    } catch {
      // Non-critical: silently degrade
    }
  }, []);

  /** Load user workstreams from Supabase. */
  const loadWorkstreams = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from("workstreams")
        .select("id, name")
        .order("name", { ascending: true });

      if (!error && data) {
        setWorkstreams(data as Workstream[]);
      }
    } catch {
      // Non-critical
    }
  }, []);

  // Load on mount
  useEffect(() => {
    loadConversations();
    loadWorkstreams();
  }, [loadConversations, loadWorkstreams]);

  // Persist active conversation to sessionStorage
  useEffect(() => {
    try {
      if (activeConversationId) {
        sessionStorage.setItem(
          "grantscope:ask:activeConversationId",
          activeConversationId,
        );
        sessionStorage.setItem(
          "grantscope:ask:activeScope",
          activeConversationScope,
        );
        if (activeConversationScopeId) {
          sessionStorage.setItem(
            "grantscope:ask:activeScopeId",
            activeConversationScopeId,
          );
        } else {
          sessionStorage.removeItem("grantscope:ask:activeScopeId");
        }
      } else {
        sessionStorage.removeItem("grantscope:ask:activeConversationId");
        sessionStorage.removeItem("grantscope:ask:activeScope");
        sessionStorage.removeItem("grantscope:ask:activeScopeId");
      }
    } catch {
      // sessionStorage unavailable
    }
  }, [
    activeConversationId,
    activeConversationScope,
    activeConversationScopeId,
  ]);

  // Persist sidebar collapsed state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(
        "grantscope:ask:sidebarCollapsed",
        String(sidebarCollapsed),
      );
    } catch {
      // localStorage unavailable
    }
  }, [sidebarCollapsed]);

  // Debounced conversation search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await searchConversations(searchQuery.trim(), 20);
        setSearchResults(results);
      } catch {
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // ============================================================================
  // Handlers
  // ============================================================================

  /** Start a new chat, clearing the active conversation and URL params. */
  const handleNewChat = useCallback(() => {
    chatSessionRef.current += 1;
    setActiveConversationId(null);
    setActiveConversationScope("global");
    setActiveConversationScopeId(undefined);
    setForceNewChat(true);
    setSearchParams({});
    setSidebarOpen(false);
  }, [setSearchParams]);

  /** Select a conversation from the sidebar. */
  const handleSelectConversation = useCallback(
    (conv: Conversation) => {
      chatSessionRef.current += 1;
      setActiveConversationId(conv.id);
      setActiveConversationScope(conv.scope);
      setActiveConversationScopeId(conv.scope_id);
      setForceNewChat(false);
      setSearchParams({});
      setSidebarOpen(false);
    },
    [setSearchParams],
  );

  /** Track conversation changes from ChatPanel and refresh sidebar. */
  const handleConversationChange = useCallback(
    (convId: string | null) => {
      if (convId && convId !== activeConversationId) {
        setActiveConversationId(convId);
        setForceNewChat(false);
        // Refresh sidebar so new conversations appear
        loadConversations();
      }
    },
    [activeConversationId, loadConversations],
  );

  /** Delete a conversation. */
  const handleDeleteConversation = useCallback(
    async (e: React.MouseEvent, convId: string) => {
      e.stopPropagation();
      try {
        await deleteConversation(convId);
        setConversations((prev) => prev.filter((c) => c.id !== convId));
        if (activeConversationId === convId) {
          setActiveConversationId(null);
        }
      } catch {
        // Silently fail
      }
    },
    [activeConversationId],
  );

  /** Change the scope. Resets the active conversation. */
  const handleScopeChange = useCallback(
    (option: ScopeOption) => {
      chatSessionRef.current += 1;
      setSelectedScope(option);
      setScopeDropdownOpen(false);
      setActiveConversationId(null);
      setActiveConversationScope(option.scope);
      setActiveConversationScopeId(option.scopeId);
      setSearchParams({});
    },
    [setSearchParams],
  );

  // Determine effective scope for ChatPanel
  const effectiveScope = activeConversationId
    ? activeConversationScope
    : selectedScope.scope;
  const effectiveScopeId = activeConversationId
    ? activeConversationScopeId
    : selectedScope.scopeId;

  // ChatPanel is always mounted so it can auto-restore from Supabase.
  // Its built-in empty state (with suggestions) handles the no-conversation case.

  // Group conversations for sidebar
  const grouped = groupConversations(conversations);

  // Build scope options
  const scopeOptions: ScopeOption[] = [
    { label: "All Opportunities", scope: "global" },
    ...workstreams.map((ws) => ({
      label: ws.name,
      scope: "workstream" as const,
      scopeId: ws.id,
    })),
  ];

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-white dark:bg-dark-surface-deep">
      {/* Header bar */}
      <div
        className={cn(
          "flex items-center justify-between px-4 py-2",
          "border-b border-gray-200 dark:border-gray-700",
          "bg-white dark:bg-dark-surface-deep",
          "shrink-0",
        )}
      >
        <div className="flex items-center gap-2">
          {/* Mobile sidebar toggle */}
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className={cn(
              "md:hidden inline-flex items-center justify-center",
              "w-8 h-8 rounded-lg",
              "text-gray-500 hover:bg-gray-100 dark:hover:bg-dark-surface-hover",
              "transition-colors duration-200",
            )}
            aria-label="Toggle conversation sidebar"
          >
            {sidebarOpen ? (
              <X className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5" aria-hidden="true" />
            )}
          </button>

          {/* Scope selector */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setScopeDropdownOpen(!scopeDropdownOpen)}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-lg",
                "border border-gray-200 dark:border-gray-600",
                "bg-white dark:bg-dark-surface",
                "text-gray-700 dark:text-gray-300",
                "hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue",
                "transition-colors duration-200",
              )}
            >
              {selectedScope.scope === "global" ? (
                <Globe className="h-4 w-4 text-brand-blue" aria-hidden="true" />
              ) : (
                <FolderOpen
                  className="h-4 w-4 text-brand-green"
                  aria-hidden="true"
                />
              )}
              <span className="max-w-[180px] truncate">
                {selectedScope.label}
              </span>
            </button>

            {scopeDropdownOpen && (
              <>
                {/* Backdrop to close dropdown */}
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setScopeDropdownOpen(false)}
                />
                <div
                  className={cn(
                    "absolute left-0 top-full mt-1 z-20",
                    "w-64 max-h-72 overflow-y-auto",
                    "bg-white dark:bg-dark-surface",
                    "border border-gray-200 dark:border-gray-600",
                    "rounded-lg shadow-lg",
                    "py-1",
                    "animate-in fade-in-0 zoom-in-95 duration-200",
                  )}
                >
                  {scopeOptions.map((option) => (
                    <button
                      key={`${option.scope}-${option.scopeId || "global"}`}
                      type="button"
                      onClick={() => handleScopeChange(option)}
                      className={cn(
                        "w-full flex items-center gap-2 px-4 py-2 text-sm text-left",
                        "transition-colors duration-150",
                        selectedScope.scope === option.scope &&
                          selectedScope.scopeId === option.scopeId
                          ? "bg-brand-blue/10 text-brand-blue"
                          : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-surface-hover",
                      )}
                    >
                      {option.scope === "global" ? (
                        <Globe
                          className="h-4 w-4 shrink-0"
                          aria-hidden="true"
                        />
                      ) : (
                        <FolderOpen
                          className="h-4 w-4 shrink-0"
                          aria-hidden="true"
                        />
                      )}
                      <span className="truncate">{option.label}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        <span className="text-xs text-gray-400 dark:text-gray-500 hidden sm:inline">
          Powered by GrantScope AI
        </span>
      </div>

      {/* Main layout */}
      <div className="flex flex-1 min-h-0">
        {/* Sidebar */}
        <aside
          className={cn(
            "shrink-0 border-r border-gray-200 dark:border-gray-700",
            "bg-gray-50 dark:bg-dark-surface-deep",
            "flex flex-col",
            "overflow-hidden",
            // Mobile: absolute overlay — always full width
            "fixed md:relative inset-y-0 left-0 z-30 md:z-auto",
            "md:translate-x-0 transition-all duration-300 ease-in-out",
            // Account for header height on mobile
            "top-16 md:top-0",
            // Mobile: always 280px; Desktop: collapsible
            sidebarOpen
              ? "translate-x-0 w-[280px]"
              : "-translate-x-full md:translate-x-0",
            !sidebarOpen && (sidebarCollapsed ? "md:w-[60px]" : "md:w-[280px]"),
          )}
        >
          {/* Sidebar header: New Chat + collapse toggle */}
          <div className="p-3 shrink-0 flex items-center gap-2">
            <button
              type="button"
              onClick={handleNewChat}
              title={sidebarCollapsed ? "New Chat" : undefined}
              className={cn(
                "inline-flex items-center justify-center gap-2",
                "py-2.5 text-sm font-medium rounded-lg",
                "bg-brand-blue text-white",
                "hover:bg-brand-dark-blue",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
                "transition-colors duration-200",
                sidebarCollapsed ? "w-9 h-9 px-0 flex-shrink-0" : "flex-1 px-4",
              )}
            >
              <Plus className="h-4 w-4 shrink-0" aria-hidden="true" />
              {!sidebarCollapsed && <span>New Chat</span>}
            </button>

            {/* Collapse/expand toggle — desktop only */}
            <button
              type="button"
              onClick={() => setSidebarCollapsed((prev) => !prev)}
              className={cn(
                "hidden md:inline-flex items-center justify-center",
                "w-7 h-7 rounded-md shrink-0",
                "text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300",
                "hover:bg-gray-200 dark:hover:bg-dark-surface-hover",
                "focus:outline-none focus:ring-1 focus:ring-brand-blue",
                "transition-colors duration-150",
              )}
              aria-label={
                sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
              }
            >
              {sidebarCollapsed ? (
                <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
              ) : (
                <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          </div>

          {/* Search bar */}
          {!sidebarCollapsed && (
            <div className="px-3 pb-2">
              <div
                className={cn(
                  "flex items-center gap-2 px-2.5 py-1.5 rounded-lg",
                  "bg-white dark:bg-dark-surface",
                  "border border-gray-200 dark:border-gray-600",
                  "focus-within:ring-2 focus-within:ring-brand-blue focus-within:border-transparent",
                  "transition-all duration-200",
                )}
              >
                <Search
                  className="h-3.5 w-3.5 text-gray-400 shrink-0"
                  aria-hidden="true"
                />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search conversations..."
                  className={cn(
                    "flex-1 bg-transparent text-sm",
                    "text-gray-700 dark:text-gray-300",
                    "placeholder-gray-400 dark:placeholder-gray-500",
                    "focus:outline-none",
                  )}
                  aria-label="Search conversations"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery("")}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    aria-label="Clear search"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Divider */}
          <div className="border-b border-gray-200 dark:border-gray-700 mx-3" />

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto px-2 py-2">
            {searchResults !== null ? (
              /* Search results mode */
              <div>
                {isSearching ? (
                  <div className="text-center py-6">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400 mx-auto" />
                    <p className="text-xs text-gray-400 mt-2">Searching...</p>
                  </div>
                ) : searchResults.length === 0 ? (
                  <div className="text-center py-6 px-3">
                    <p className="text-xs text-gray-400">
                      No conversations found
                    </p>
                  </div>
                ) : (
                  <div className="space-y-0.5">
                    <p className="px-2 py-1 text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Results
                    </p>
                    {searchResults.map((conv) => (
                      <ConversationItem
                        key={conv.id}
                        conversation={conv}
                        isActive={activeConversationId === conv.id}
                        onSelect={handleSelectConversation}
                        onDelete={handleDeleteConversation}
                      />
                    ))}
                  </div>
                )}
              </div>
            ) : (
              /* Normal grouped view */
              <>
                {conversations.length === 0 ? (
                  <div className="text-center py-8 px-3">
                    <MessageSquare
                      className="h-8 w-8 text-gray-300 dark:text-gray-600 mx-auto mb-2"
                      aria-hidden="true"
                    />
                    {!sidebarCollapsed && (
                      <p className="text-xs text-gray-400 dark:text-gray-500">
                        No conversations yet
                      </p>
                    )}
                  </div>
                ) : (
                  <>
                    {grouped.today.length > 0 && (
                      <ConversationGroup
                        label="Today"
                        conversations={grouped.today}
                        activeId={activeConversationId}
                        onSelect={handleSelectConversation}
                        onDelete={handleDeleteConversation}
                        collapsed={sidebarCollapsed}
                      />
                    )}
                    {grouped.thisWeek.length > 0 && (
                      <ConversationGroup
                        label="This Week"
                        conversations={grouped.thisWeek}
                        activeId={activeConversationId}
                        onSelect={handleSelectConversation}
                        onDelete={handleDeleteConversation}
                        collapsed={sidebarCollapsed}
                      />
                    )}
                    {grouped.older.length > 0 && (
                      <ConversationGroup
                        label="Older"
                        conversations={grouped.older}
                        activeId={activeConversationId}
                        onSelect={handleSelectConversation}
                        onDelete={handleDeleteConversation}
                        collapsed={sidebarCollapsed}
                      />
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </aside>

        {/* Mobile sidebar backdrop */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-20 bg-black/30 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* First-use intro banner */}
          <FeatureIntroBanner
            feature="ask"
            className="mx-4 mt-4 mb-2 shrink-0"
          />
          <ChatPanel
            key={chatKey}
            scope={effectiveScope}
            scopeId={effectiveScopeId}
            initialQuery={initialQuery}
            initialConversationId={activeConversationId ?? undefined}
            onConversationChange={handleConversationChange}
            forceNew={forceNewChat}
            className="flex-1"
            placeholder="Ask GrantScope about grants, funding opportunities, and deadlines..."
            emptyStateTitle="What would you like to explore?"
            emptyStateDescription="Ask questions about grants, funding opportunities, eligibility requirements, and more. GrantScope uses AI to synthesize intelligence from your data."
            defaultSuggestedQuestions={[
              "What grants are open for environmental sustainability?",
              "Which deadlines should I prioritize this month?",
              "Summarize eligibility for the latest federal grants",
              "What's the total value of my grant pipeline?",
              "Compare funding opportunities for community health programs",
            ]}
          />
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Conversation Group Sub-component
// ============================================================================

interface ConversationGroupProps {
  label: string;
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (conv: Conversation) => void;
  onDelete: (e: React.MouseEvent, convId: string) => void;
  collapsed?: boolean;
}

function ConversationGroup({
  label,
  conversations,
  activeId,
  onSelect,
  onDelete,
  collapsed,
}: ConversationGroupProps) {
  return (
    <div className="mb-3">
      {!collapsed && (
        <p className="px-2 py-1 text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider">
          {label}
        </p>
      )}
      <div className="space-y-0.5">
        {conversations.map((conv) => (
          <ConversationItem
            key={conv.id}
            conversation={conv}
            isActive={activeId === conv.id}
            onSelect={onSelect}
            onDelete={onDelete}
            collapsed={collapsed}
          />
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Conversation Item Sub-component
// ============================================================================

interface ConversationItemProps {
  conversation: Conversation;
  isActive: boolean;
  onSelect: (conv: Conversation) => void;
  onDelete: (e: React.MouseEvent, convId: string) => void;
  collapsed?: boolean;
}

function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onDelete,
  collapsed,
}: ConversationItemProps) {
  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => onSelect(conversation)}
        title={conversation.title || "Untitled conversation"}
        className={cn(
          "w-full flex items-center justify-center",
          "p-2 rounded-lg",
          "transition-colors duration-150",
          isActive
            ? "bg-brand-blue/10 dark:bg-brand-blue/20"
            : "hover:bg-gray-100 dark:hover:bg-dark-surface-hover",
        )}
      >
        <MessageSquare
          className={cn(
            "h-4 w-4 shrink-0",
            isActive ? "text-brand-blue" : "text-gray-400 dark:text-gray-500",
          )}
          aria-hidden="true"
        />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onSelect(conversation)}
      className={cn(
        "w-full group flex items-start gap-2 px-2 py-2 rounded-lg text-left",
        "transition-colors duration-150",
        isActive
          ? "bg-brand-blue/10 dark:bg-brand-blue/20"
          : "hover:bg-gray-100 dark:hover:bg-dark-surface-hover",
      )}
    >
      <MessageSquare
        className={cn(
          "h-4 w-4 shrink-0 mt-0.5",
          isActive ? "text-brand-blue" : "text-gray-400 dark:text-gray-500",
        )}
        aria-hidden="true"
      />
      <div className="flex-1 min-w-0">
        <p
          className={cn(
            "text-sm truncate",
            isActive
              ? "text-brand-blue font-medium"
              : "text-gray-700 dark:text-gray-300",
          )}
        >
          {conversation.title || "Untitled conversation"}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span
            className={cn(
              "inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium",
              scopeBadgeClasses(conversation.scope),
            )}
          >
            {scopeLabel(conversation.scope)}
          </span>
          <span className="text-[10px] text-gray-400 dark:text-gray-500">
            {relativeTime(conversation.updated_at)}
          </span>
        </div>
      </div>

      {/* Delete button (visible on hover) */}
      <button
        type="button"
        onClick={(e) => onDelete(e, conversation.id)}
        className={cn(
          "shrink-0 p-1 rounded opacity-0 group-hover:opacity-100",
          "text-gray-400 hover:text-red-500",
          "hover:bg-red-50 dark:hover:bg-red-900/20",
          "focus:opacity-100 focus:outline-none focus:ring-1 focus:ring-red-400",
          "transition-all duration-150",
        )}
        aria-label={`Delete conversation: ${conversation.title || "Untitled"}`}
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </button>
  );
}
