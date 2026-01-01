/**
 * WorkstreamKanban Page
 *
 * Displays an interactive Kanban board for a workstream, allowing users to:
 * - View cards organized by research workflow status
 * - Drag and drop cards between columns
 * - Navigate to card detail pages
 * - Auto-populate the board with matching cards
 * - Export workstream reports (PDF/PPTX)
 * - Edit workstream filters
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  RefreshCw,
  Settings,
  Download,
  Plus,
  Loader2,
  FileText,
  Presentation,
  ChevronDown,
  Sparkles,
  Tag,
  Filter,
  CheckCircle2,
  XCircle,
  Search,
  X,
  Radar,
} from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { cn } from '../lib/utils';
import { logger } from '../lib/logger';
import {
  KanbanBoard,
  KanbanErrorBoundary,
  type KanbanStatus,
  type WorkstreamCard,
  type CardActionCallbacks,
  KANBAN_COLUMNS,
} from '../components/kanban';
import {
  useQuickUpdate,
  useCardExport,
  useCheckUpdates,
  useBriefGeneration,
} from '../components/kanban/actions';
import { BriefPreviewModal } from '../components/kanban/BriefPreviewModal';
import { ExportProgressModal } from '../components/ExportProgressModal';
import { BulkExportModal } from '../components/BulkExportModal';
import { useExportWithProgress } from '../hooks/useExportWithProgress';
import {
  fetchWorkstreamCards,
  updateWorkstreamCard,
  removeCardFromWorkstream,
  triggerDeepDive,
  autoPopulateWorkstream,
  fetchResearchStatus,
  getBulkBriefStatus,
  exportBulkBriefs,
  startWorkstreamScan,
  getWorkstreamScanStatus,
  type WorkstreamResearchStatus,
  type BulkBriefStatusResponse,
  type WorkstreamScanStatusResponse,
} from '../lib/workstream-api';
import { PillarBadgeGroup } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge } from '../components/StageBadge';
import { WorkstreamForm, type Workstream } from '../components/WorkstreamForm';

// ============================================================================
// Types
// ============================================================================

/**
 * Toast notification type for user feedback.
 */
interface ToastNotification {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Toast notification component for displaying temporary feedback messages.
 */
function Toast({
  notification,
  onDismiss,
}: {
  notification: ToastNotification;
  onDismiss: (id: string) => void;
}) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(notification.id);
    }, 4000);
    return () => clearTimeout(timer);
  }, [notification.id, onDismiss]);

  const iconClass = 'h-5 w-5 flex-shrink-0';
  const icons = {
    success: <CheckCircle2 className={cn(iconClass, 'text-green-500')} />,
    error: <XCircle className={cn(iconClass, 'text-red-500')} />,
    info: <Sparkles className={cn(iconClass, 'text-brand-blue')} />,
  };

  const bgClass = {
    success: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700',
    error: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-700',
    info: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-700',
  };

  return (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300',
        bgClass[notification.type]
      )}
      role="alert"
    >
      {icons[notification.type]}
      <p className="text-sm font-medium text-gray-900 dark:text-white">
        {notification.message}
      </p>
      <button
        onClick={() => onDismiss(notification.id)}
        className="ml-auto p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
        aria-label="Dismiss notification"
      >
        <XCircle className="h-4 w-4 text-gray-500 dark:text-gray-400" />
      </button>
    </div>
  );
}

/**
 * Container for toast notifications, positioned at the bottom of the screen.
 */
function ToastContainer({
  notifications,
  onDismiss,
}: {
  notifications: ToastNotification[];
  onDismiss: (id: string) => void;
}) {
  if (notifications.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
      {notifications.map((notification) => (
        <Toast
          key={notification.id}
          notification={notification}
          onDismiss={onDismiss}
        />
      ))}
    </div>
  );
}

/**
 * Status badge for active/inactive workstream
 */
function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        isActive
          ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400'
          : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
      )}
    >
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

/**
 * Keyword tag display for filter summary
 */
function KeywordTag({ keyword }: { keyword: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-brand-light-blue dark:bg-brand-blue/20 text-brand-dark-blue dark:text-brand-light-blue border border-brand-blue/30 dark:border-brand-blue/40">
      <Tag className="h-3 w-3" />
      {keyword}
    </span>
  );
}

/**
 * Stage range display for multiple stages
 */
function StageRangeDisplay({ stageIds }: { stageIds: string[] }) {
  if (stageIds.length === 0) return null;

  const stageNumbers = stageIds
    .map((id) => parseInt(id, 10))
    .filter((n) => !isNaN(n))
    .sort((a, b) => a - b);

  if (stageNumbers.length === 0) return null;

  if (stageNumbers.length <= 2) {
    return (
      <div className="flex items-center gap-1 flex-wrap">
        {stageNumbers.map((stage) => (
          <StageBadge
            key={stage}
            stage={stage}
            size="sm"
            showName={false}
            variant="minimal"
          />
        ))}
      </div>
    );
  }

  const isConsecutive = stageNumbers.every(
    (n, i) => i === 0 || n === stageNumbers[i - 1] + 1
  );

  if (isConsecutive) {
    return (
      <span className="text-sm text-gray-600 dark:text-gray-400">
        Stages {stageNumbers[0]} - {stageNumbers[stageNumbers.length - 1]}
      </span>
    );
  }

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {stageNumbers.map((stage) => (
        <StageBadge
          key={stage}
          stage={stage}
          size="sm"
          showName={false}
          variant="minimal"
        />
      ))}
    </div>
  );
}

/**
 * Stats bar displaying card counts per Kanban column
 */
function StatsBar({ cards }: { cards: Record<KanbanStatus, WorkstreamCard[]> }) {
  const totalCards = Object.values(cards).reduce(
    (sum, columnCards) => sum + columnCards.length,
    0
  );

  return (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 mb-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            Total Cards:
          </span>
          <span className="text-lg font-bold text-brand-blue">{totalCards}</span>
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          {KANBAN_COLUMNS.map((column) => {
            const count = cards[column.id]?.length || 0;
            return (
              <div
                key={column.id}
                className="flex items-center gap-1.5 text-sm"
                title={column.description}
              >
                <span className="text-gray-600 dark:text-gray-400">
                  {column.title}:
                </span>
                <span className="font-semibold text-gray-900 dark:text-white">
                  {count}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/**
 * Workstream Form Modal wrapper
 */
function FormModal({
  workstream,
  onSuccess,
  onCancel,
}: {
  workstream: Workstream;
  onSuccess: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-gray-600/50 dark:bg-black/60 flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto my-8">
        <div className="sticky top-0 bg-white dark:bg-[#2d3166] border-b border-gray-200 dark:border-gray-700 px-6 py-4 rounded-t-lg">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white">
            Edit Workstream Filters
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Update the filters and settings for this workstream.
          </p>
        </div>
        <div className="px-6 py-4">
          <WorkstreamForm
            workstream={workstream}
            onSuccess={onSuccess}
            onCancel={onCancel}
          />
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * WorkstreamKanban - Main page component for the workstream Kanban board.
 *
 * Displays an interactive Kanban board that allows users to manage cards
 * through the research workflow stages via drag-and-drop.
 */
const WorkstreamKanban: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuthContext();

  // Workstream and card state
  const [workstream, setWorkstream] = useState<Workstream | null>(null);
  const [cards, setCards] = useState<Record<KanbanStatus, WorkstreamCard[]>>({
    inbox: [],
    screening: [],
    research: [],
    brief: [],
    watching: [],
    archived: [],
  });

  // Loading states
  const [loading, setLoading] = useState(true);
  const [cardsLoading, setCardsLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [autoPopulating, setAutoPopulating] = useState(false);

  // Workstream scan state
  const [scanning, setScanning] = useState(false);
  const [_scanStatus, setScanStatus] = useState<WorkstreamScanStatusResponse | null>(null);
  const scanPollRef = useRef<NodeJS.Timeout | null>(null);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [showEditModal, setShowEditModal] = useState(false);

  // Export state
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exportLoading, setExportLoading] = useState<'pdf' | 'pptx' | null>(null);

  // Toast notifications
  const [toasts, setToasts] = useState<ToastNotification[]>([]);
  const toastIdRef = useRef(0);

  // Brief preview modal state
  const [briefModalCard, setBriefModalCard] = useState<WorkstreamCard | null>(null);
  const [showBriefModal, setShowBriefModal] = useState(false);

  // Bulk export modal state
  const [showBulkExportModal, setShowBulkExportModal] = useState(false);
  const [bulkExportStatus, setBulkExportStatus] = useState<BulkBriefStatusResponse | null>(null);
  const [bulkExportLoading, setBulkExportLoading] = useState(false);
  const [bulkExportError, setBulkExportError] = useState<string | null>(null);
  const [isBulkExporting, setIsBulkExporting] = useState(false);

  // Search/filter state for kanban board
  const [searchQuery, setSearchQuery] = useState('');
  const [filterPillar, setFilterPillar] = useState<string | null>(null);

  // Research status tracking
  const [researchStatuses, setResearchStatuses] = useState<Map<string, WorkstreamResearchStatus>>(new Map());
  const researchPollRef = useRef<NodeJS.Timeout | null>(null);

  // ============================================================================
  // Toast Helper Functions
  // ============================================================================

  /**
   * Show a toast notification.
   */
  const showToast = useCallback(
    (type: ToastNotification['type'], message: string) => {
      const id = `toast-${toastIdRef.current++}`;
      setToasts((prev) => [...prev, { id, type, message }]);
    },
    []
  );

  /**
   * Dismiss a toast notification.
   */
  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // ============================================================================
  // Auth Token Helper
  // ============================================================================

  /**
   * Get the authentication token from Supabase session.
   */
  const getAuthToken = useCallback(async (): Promise<string | null> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token || null;
  }, []);

  // ============================================================================
  // Column-Specific Action Hooks
  // ============================================================================

  // Use a ref to hold startResearchPolling to avoid circular dependencies
  const startResearchPollingRef = useRef<() => void>(() => {});

  const { triggerQuickUpdate } = useQuickUpdate(getAuthToken, id || '', {
    onSuccess: () => {
      showToast('success', 'Quick update started');
      // Start polling for research status updates
      startResearchPollingRef.current();
    },
    onError: (_, error) => showToast('error', error.message),
  });

  const { exportCard } = useCardExport(getAuthToken, {
    onSuccess: (_, format) =>
      showToast('success', `${format.toUpperCase()} export started`),
    onError: (_, format, error) =>
      showToast('error', `Failed to export ${format.toUpperCase()}: ${error.message}`),
  });

  const { checkForUpdates } = useCheckUpdates(getAuthToken, id || '', {
    onSuccess: () => showToast('success', 'Update check started'),
    onError: (_, error) => showToast('error', error.message),
  });

  const {
    triggerBriefGeneration,
    isCardGenerating,
    getCardBrief,
    getCardError,
  } = useBriefGeneration(getAuthToken, id || '', {
    onGenerating: () => showToast('info', 'Generating executive brief...'),
    onSuccess: (cardId, _brief) => {
      showToast('success', 'Executive brief generated');
      // Find the card to show the modal
      for (const columnCards of Object.values(cards)) {
        const card = columnCards.find((c) => c.card.id === cardId);
        if (card) {
          setBriefModalCard(card);
          setShowBriefModal(true);
          break;
        }
      }
    },
    onError: (_, error) => showToast('error', `Brief generation failed: ${error.message}`),
  });

  // Export with progress modal hook
  const {
    state: exportState,
    exportBrief: exportBriefWithProgress,
    closeModal: closeExportModal,
    retryExport,
    downloadExport,
  } = useExportWithProgress(getAuthToken);

  // ============================================================================
  // Data Loading
  // ============================================================================

  /**
   * Load workstream details from Supabase.
   */
  const loadWorkstream = useCallback(async () => {
    if (!id || !user) return;

    try {
      const { data, error: fetchError } = await supabase
        .from('workstreams')
        .select('*')
        .eq('id', id)
        .single();

      if (fetchError) {
        console.error('Error loading workstream:', fetchError);
        setError(
          'Failed to load workstream. It may not exist or you may not have access.'
        );
        return;
      }

      // Verify ownership
      if (data.user_id !== user.id) {
        setError('You do not have access to this workstream.');
        return;
      }

      setWorkstream(data);
    } catch (err) {
      console.error('Error loading workstream:', err);
      setError('An unexpected error occurred.');
    }
  }, [id, user]);

  /**
   * Load Kanban cards for the workstream.
   */
  const loadCards = useCallback(async () => {
    if (!id) return;

    const token = await getAuthToken();
    if (!token) {
      showToast('error', 'Authentication required');
      return;
    }

    try {
      setCardsLoading(true);
      const groupedCards = await fetchWorkstreamCards(token, id);
      setCards(groupedCards);
    } catch (err) {
      console.error('Error loading cards:', err);
      showToast('error', 'Failed to load cards');
    } finally {
      setCardsLoading(false);
    }
  }, [id, getAuthToken, showToast]);

  /**
   * Initial data load on mount.
   */
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await loadWorkstream();
      setLoading(false);
    };
    loadData();
  }, [loadWorkstream]);

  /**
   * Load cards once workstream is loaded, then auto-populate with new matches.
   */
  useEffect(() => {
    if (!workstream || !id) return;

    const loadAndAutoPopulate = async () => {
      // 1. Load existing cards
      await loadCards();

      // 2. Auto-populate inbox with new matching cards (silently, non-blocking)
      try {
        const token = await getAuthToken();
        if (!token) return;

        const result = await autoPopulateWorkstream(token, id, 20);
        if (result.added > 0) {
          showToast(
            'info',
            `${result.added} new card${result.added !== 1 ? 's' : ''} added to inbox`
          );
          // Refresh cards to include the new additions
          await loadCards();
        }
      } catch (err) {
        // Silent fail - auto-populate is an enhancement, not critical
        logger.warn('Auto-populate on load failed:', err);
      }
    };

    loadAndAutoPopulate();
  }, [workstream, id, loadCards, getAuthToken, showToast]);

  /**
   * Fetch and update research status for cards in this workstream.
   * Called on initial load and periodically while there are active tasks.
   */
  const fetchAndUpdateResearchStatus = useCallback(async () => {
    if (!id) return;

    const token = await getAuthToken();
    if (!token) return;

    try {
      const { tasks } = await fetchResearchStatus(token, id);
      
      // Build a map of card_id -> research status
      const statusMap = new Map<string, WorkstreamResearchStatus>();
      for (const task of tasks) {
        statusMap.set(task.card_id, task);
      }
      
      setResearchStatuses(statusMap);
      
      // If there are any active tasks (queued or processing), keep polling
      const hasActiveTasks = tasks.some(
        t => t.status === 'queued' || t.status === 'processing'
      );
      
      return hasActiveTasks;
    } catch (err) {
      console.error('Error fetching research status:', err);
      return false;
    }
  }, [id, getAuthToken]);

  /**
   * Start polling for research status updates.
   */
  const startResearchPolling = useCallback(() => {
    // Clear any existing interval
    if (researchPollRef.current) {
      clearInterval(researchPollRef.current);
    }

    // Poll every 5 seconds while there are active tasks
    const poll = async () => {
      const hasActiveTasks = await fetchAndUpdateResearchStatus();
      if (!hasActiveTasks && researchPollRef.current) {
        clearInterval(researchPollRef.current);
        researchPollRef.current = null;
      }
    };

    // Initial fetch
    poll();

    // Start interval
    researchPollRef.current = setInterval(poll, 5000);
  }, [fetchAndUpdateResearchStatus]);

  // Keep the ref updated with the latest startResearchPolling function
  useEffect(() => {
    startResearchPollingRef.current = startResearchPolling;
  }, [startResearchPolling]);

  /**
   * Fetch research status after cards are loaded.
   */
  useEffect(() => {
    if (workstream && id && Object.values(cards).flat().length > 0) {
      startResearchPolling();
    }

    return () => {
      if (researchPollRef.current) {
        clearInterval(researchPollRef.current);
      }
    };
  }, [workstream, id, cards, startResearchPolling]);

  /**
   * Merge research statuses into cards for rendering.
   * Creates enriched cards with research_status field populated.
   */
  const cardsWithResearchStatus = useMemo(() => {
    const enriched: Record<KanbanStatus, WorkstreamCard[]> = {
      inbox: [],
      screening: [],
      research: [],
      brief: [],
      watching: [],
      archived: [],
    };

    for (const [status, columnCards] of Object.entries(cards)) {
      enriched[status as KanbanStatus] = columnCards.map((card) => {
        const researchStatus = researchStatuses.get(card.card_id);
        if (researchStatus) {
          return {
            ...card,
            research_status: {
              status: researchStatus.status,
              task_type: researchStatus.task_type,
              task_id: researchStatus.task_id,
              started_at: researchStatus.started_at,
              completed_at: researchStatus.completed_at,
            },
          };
        }
        return card;
      });
    }

    return enriched;
  }, [cards, researchStatuses]);

  // ============================================================================
  // Event Handlers
  // ============================================================================

  /**
   * Handle card move (drag and drop).
   * Implements optimistic update with rollback on error.
   */
  const handleCardMove = useCallback(
    async (cardId: string, newStatus: KanbanStatus, newPosition: number) => {
      if (!id) return;

      const token = await getAuthToken();
      if (!token) {
        showToast('error', 'Authentication required');
        return;
      }

      // Find the source column and card
      let sourceStatus: KanbanStatus | null = null;
      let sourceCard: WorkstreamCard | null = null;

      for (const [status, columnCards] of Object.entries(cards)) {
        const card = columnCards.find((c) => c.id === cardId);
        if (card) {
          sourceStatus = status as KanbanStatus;
          sourceCard = card;
          break;
        }
      }

      if (!sourceStatus || !sourceCard) return;

      // Optimistic update
      const previousCards = { ...cards };

      setCards((prev) => {
        const updated = { ...prev };

        // Remove from source column
        updated[sourceStatus as KanbanStatus] = updated[
          sourceStatus as KanbanStatus
        ].filter((c) => c.id !== cardId);

        // Update card status and insert at new position
        const movedCard = { ...sourceCard!, status: newStatus };
        const targetCards = [...updated[newStatus]];
        targetCards.splice(newPosition, 0, movedCard);
        updated[newStatus] = targetCards;

        return updated;
      });

      // API call - use sourceCard.id (workstream_card junction ID)
      // All workstream card endpoints use the junction table ID, not the underlying card UUID
      try {
        await updateWorkstreamCard(token, id, sourceCard.id, {
          status: newStatus,
          position: newPosition,
        });
        showToast('success', 'Card moved successfully');
      } catch (err: unknown) {
        // Rollback on error
        const errorMessage = err instanceof Error ? err.message : 'Unknown error';
        console.error('Error moving card:', errorMessage);
        setCards(previousCards);
        showToast('error', 'Failed to move card. Changes reverted.');
      }
    },
    [id, cards, getAuthToken, showToast]
  );

  /**
   * Handle card click - navigate to card detail page.
   */
  const handleCardClick = useCallback(
    (card: WorkstreamCard) => {
      navigate(`/cards/${card.card.slug}`);
    },
    [navigate]
  );

  /**
   * Handle notes update for a card.
   */
  const handleNotesUpdate = useCallback(
    async (cardId: string, notes: string) => {
      if (!id) return;

      const token = await getAuthToken();
      if (!token) {
        showToast('error', 'Authentication required');
        return;
      }

      try {
        await updateWorkstreamCard(token, id, cardId, { notes });

        // Update local state
        setCards((prev) => {
          const updated = { ...prev };
          for (const status of Object.keys(updated) as KanbanStatus[]) {
            updated[status] = updated[status].map((card) =>
              card.id === cardId ? { ...card, notes } : card
            );
          }
          return updated;
        });

        showToast('success', 'Notes saved');
      } catch (err) {
        console.error('Error updating notes:', err);
        showToast('error', 'Failed to save notes');
      }
    },
    [id, getAuthToken, showToast]
  );

  /**
   * Handle deep dive request for a card.
   */
  const handleDeepDive = useCallback(
    async (cardId: string) => {
      if (!id) return;

      const token = await getAuthToken();
      if (!token) {
        showToast('error', 'Authentication required');
        return;
      }

      try {
        await triggerDeepDive(token, id, cardId);
        showToast('success', 'Deep dive analysis started');
        // Start polling for research status updates
        startResearchPollingRef.current();
      } catch (err) {
        console.error('Error triggering deep dive:', err);
        showToast('error', 'Failed to start deep dive analysis');
      }
    },
    [id, getAuthToken, showToast]
  );

  /**
   * Handle card removal from workstream.
   */
  const handleRemoveCard = useCallback(
    async (cardId: string) => {
      if (!id) return;

      const token = await getAuthToken();
      if (!token) {
        showToast('error', 'Authentication required');
        return;
      }

      // Optimistic update
      const previousCards = { ...cards };

      setCards((prev) => {
        const updated = { ...prev };
        for (const status of Object.keys(updated) as KanbanStatus[]) {
          updated[status] = updated[status].filter((card) => card.id !== cardId);
        }
        return updated;
      });

      try {
        await removeCardFromWorkstream(token, id, cardId);
        showToast('success', 'Card removed from workstream');
      } catch (err) {
        console.error('Error removing card:', err);
        setCards(previousCards);
        showToast('error', 'Failed to remove card');
      }
    },
    [id, cards, getAuthToken, showToast]
  );

  /**
   * Handle moving a card to a different column via menu.
   */
  const handleMoveToColumn = useCallback(
    async (cardId: string, status: KanbanStatus) => {
      if (!id) return;

      const token = await getAuthToken();
      if (!token) {
        showToast('error', 'Authentication required');
        return;
      }

      // Find the card and its current position
      let sourceCard: WorkstreamCard | null = null;
      let sourceStatus: KanbanStatus | null = null;

      for (const [s, columnCards] of Object.entries(cards)) {
        const card = columnCards.find((c) => c.id === cardId);
        if (card) {
          sourceCard = card;
          sourceStatus = s as KanbanStatus;
          break;
        }
      }

      if (!sourceCard || !sourceStatus || sourceStatus === status) return;

      // Optimistic update
      const previousCards = { ...cards };
      const targetPosition = cards[status].length;

      setCards((prev) => {
        const updated = { ...prev };

        // Remove from source column
        updated[sourceStatus!] = updated[sourceStatus!].filter(
          (c) => c.id !== cardId
        );

        // Add to target column at the end
        const movedCard = { ...sourceCard!, status, position: targetPosition };
        updated[status] = [...updated[status], movedCard];

        return updated;
      });

      try {
        await updateWorkstreamCard(token, id, cardId, {
          status,
          position: targetPosition,
        });
        showToast('success', 'Card moved successfully');
      } catch (err) {
        console.error('Error moving card:', err);
        setCards(previousCards);
        showToast('error', 'Failed to move card');
      }
    },
    [id, cards, getAuthToken, showToast]
  );

  /**
   * Handle quick update action (screening column).
   */
  const handleQuickUpdate = useCallback(
    async (cardId: string) => {
      await triggerQuickUpdate(cardId);
    },
    [triggerQuickUpdate]
  );

  /**
   * Handle export action (brief column).
   */
  const handleExport = useCallback(
    async (cardId: string, format: 'pdf' | 'pptx') => {
      await exportCard(cardId, format);
    },
    [exportCard]
  );

  /**
   * Handle check updates action (watching column).
   */
  const handleCheckUpdates = useCallback(
    async (cardId: string) => {
      await checkForUpdates(cardId);
    },
    [checkForUpdates]
  );

  /**
   * Handle generate brief action (brief column).
   * Opens the brief modal and triggers generation.
   */
  const handleGenerateBrief = useCallback(
    async (workstreamCardId: string, cardId: string) => {
      // Find the card for the modal
      for (const columnCards of Object.values(cards)) {
        const card = columnCards.find((c) => c.id === workstreamCardId);
        if (card) {
          setBriefModalCard(card);
          setShowBriefModal(true);
          break;
        }
      }
      // Trigger generation (uses cardId, the actual card UUID)
      await triggerBriefGeneration(cardId);
    },
    [cards, triggerBriefGeneration]
  );

  /**
   * Handle brief modal close.
   */
  const handleBriefModalClose = useCallback(() => {
    setShowBriefModal(false);
    setBriefModalCard(null);
  }, []);

  /**
   * Handle export from brief modal.
   * Uses progress modal for PPTX (Gamma-powered), direct download for PDF.
   */
  const handleBriefExport = useCallback(
    async (format: 'pdf' | 'pptx') => {
      if (briefModalCard && id) {
        // Get card name for the progress modal
        const cardName = briefModalCard.card.name || 'Executive Brief';
        
        // Use progress modal for exports (especially PPTX which uses Gamma)
        await exportBriefWithProgress(
          id,
          briefModalCard.card.id,
          format,
          cardName
        );
      }
    },
    [briefModalCard, id, exportBriefWithProgress]
  );

  /**
   * Handle brief export from card actions menu in Brief column.
   * Uses progress modal for PPTX (Gamma-powered), direct download for PDF.
   */
  const handleBriefExportFromCard = useCallback(
    async (cardId: string, format: 'pdf' | 'pptx') => {
      if (!id) return;
      
      // Find the card to get its name
      let cardName = 'Executive Brief';
      for (const columnCards of Object.values(cards)) {
        const card = columnCards.find((c) => c.card.id === cardId);
        if (card) {
          cardName = card.card.name || cardName;
          break;
        }
      }
      
      // Use progress modal for exports
      await exportBriefWithProgress(id, cardId, format, cardName);
    },
    [id, cards, exportBriefWithProgress]
  );

  // ============================================================================
  // Bulk Export Handlers
  // ============================================================================

  /**
   * Open the bulk export modal and fetch brief status.
   */
  const handleOpenBulkExport = useCallback(async () => {
    if (!id) return;

    setShowBulkExportModal(true);
    setBulkExportLoading(true);
    setBulkExportError(null);

    try {
      const token = await getAuthToken();
      if (!token) {
        setBulkExportError('Authentication required');
        return;
      }

      const status = await getBulkBriefStatus(token, id);
      setBulkExportStatus(status);
    } catch (err) {
      console.error('Error fetching bulk brief status:', err);
      setBulkExportError(err instanceof Error ? err.message : 'Failed to load brief status');
    } finally {
      setBulkExportLoading(false);
    }
  }, [id, getAuthToken]);

  /**
   * Close the bulk export modal and reset state.
   */
  const handleCloseBulkExport = useCallback(() => {
    if (isBulkExporting) return; // Prevent closing during export
    setShowBulkExportModal(false);
    setBulkExportStatus(null);
    setBulkExportError(null);
  }, [isBulkExporting]);

  /**
   * Execute the bulk export.
   */
  const handleExecuteBulkExport = useCallback(
    async (format: 'pptx' | 'pdf', cardOrder: string[]) => {
      if (!id) return;

      setIsBulkExporting(true);

      try {
        const token = await getAuthToken();
        if (!token) {
          showToast('error', 'Authentication required');
          return;
        }

        showToast('info', `Generating ${format.toUpperCase()} portfolio...`);

        const result = await exportBulkBriefs(token, id, format, cardOrder);

        if (result.status === 'success' || result.status === 'completed') {
          // Handle Gamma URL for PPTX
          if (result.pptx_url) {
            window.open(result.pptx_url, '_blank');
            showToast('success', 'Portfolio presentation opened in new tab');
          } else {
            showToast('success', 'Portfolio export completed');
          }
          setShowBulkExportModal(false);
        } else if (result.error) {
          showToast('error', result.error);
        }
      } catch (err) {
        console.error('Bulk export error:', err);
        showToast('error', err instanceof Error ? err.message : 'Export failed');
      } finally {
        setIsBulkExporting(false);
      }
    },
    [id, getAuthToken, showToast]
  );

  /**
   * Card action callbacks for KanbanBoard.
   */
  const cardActions: CardActionCallbacks = {
    onNotesUpdate: handleNotesUpdate,
    onDeepDive: handleDeepDive,
    onRemove: handleRemoveCard,
    onMoveToColumn: handleMoveToColumn,
    onQuickUpdate: handleQuickUpdate,
    onExport: handleExport,
    onExportBrief: handleBriefExportFromCard,
    onCheckUpdates: handleCheckUpdates,
    onGenerateBrief: handleGenerateBrief,
  };

  /**
   * Filter cards based on search query and pillar filter.
   * Uses cardsWithResearchStatus to include research indicators.
   */
  const filteredCards = React.useMemo(() => {
    // If no filters active, return cards with research status
    if (!searchQuery.trim() && !filterPillar) {
      return cardsWithResearchStatus;
    }

    const filtered: Record<KanbanStatus, WorkstreamCard[]> = {
      inbox: [],
      screening: [],
      research: [],
      brief: [],
      watching: [],
      archived: [],
    };

    const query = searchQuery.toLowerCase().trim();

    for (const [status, columnCards] of Object.entries(cardsWithResearchStatus)) {
      filtered[status as KanbanStatus] = columnCards.filter((card) => {
        // Check pillar filter
        if (filterPillar && card.card.pillar_id !== filterPillar) {
          return false;
        }

        // Check search query
        if (query) {
          const cardText = [
            card.card.name || '',
            card.card.summary || '',
            card.notes || '',
          ].join(' ').toLowerCase();

          if (!cardText.includes(query)) {
            return false;
          }
        }

        return true;
      });
    }

    return filtered;
  }, [cardsWithResearchStatus, searchQuery, filterPillar]);

  /**
   * Get unique pillars from all cards for filter dropdown.
   */
  const availablePillars = React.useMemo(() => {
    const pillarSet = new Set<string>();
    for (const columnCards of Object.values(cards)) {
      for (const card of columnCards) {
        if (card.card.pillar_id) {
          pillarSet.add(card.card.pillar_id);
        }
      }
    }
    return Array.from(pillarSet).sort();
  }, [cards]);

  /**
   * Clear all search/filter state.
   */
  const clearFilters = useCallback(() => {
    setSearchQuery('');
    setFilterPillar(null);
  }, []);

  /**
   * Refresh cards.
   */
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadCards();
    setRefreshing(false);
    showToast('success', 'Cards refreshed');
  }, [loadCards, showToast]);

  /**
   * Auto-populate workstream with matching cards.
   */
  const handleAutoPopulate = useCallback(async () => {
    if (!id) return;

    const token = await getAuthToken();
    if (!token) {
      showToast('error', 'Authentication required');
      return;
    }

    try {
      setAutoPopulating(true);
      const result = await autoPopulateWorkstream(token, id);

      if (result.added > 0) {
        showToast(
          'success',
          `Added ${result.added} card${result.added !== 1 ? 's' : ''} to inbox`
        );
        // Reload cards to show the new ones
        await loadCards();
      } else {
        showToast('info', 'No new matching cards found');
      }
    } catch (err) {
      console.error('Error auto-populating:', err);
      showToast('error', 'Failed to auto-populate workstream');
    } finally {
      setAutoPopulating(false);
    }
  }, [id, getAuthToken, loadCards, showToast]);

  /**
   * Start a targeted scan for the workstream.
   */
  const handleStartScan = useCallback(async () => {
    if (!id) return;

    const token = await getAuthToken();
    if (!token) {
      showToast('error', 'Authentication required');
      return;
    }

    try {
      setScanning(true);
      const response = await startWorkstreamScan(token, id);
      setScanStatus({
        scan_id: response.scan_id,
        workstream_id: response.workstream_id,
        status: response.status,
        created_at: new Date().toISOString(),
      });
      showToast('info', response.message);

      // Track polling attempts for timeout (10 min max = 200 polls at 3s each)
      const MAX_POLL_ATTEMPTS = 200;
      let pollAttempts = 0;
      const scanId = response.scan_id;

      // Start polling for scan completion
      const pollScanStatus = async () => {
        pollAttempts++;

        // Timeout after max attempts
        if (pollAttempts > MAX_POLL_ATTEMPTS) {
          setScanning(false);
          showToast('error', 'Scan timed out. Check back later for results.');
          if (scanPollRef.current) {
            clearInterval(scanPollRef.current);
            scanPollRef.current = null;
          }
          return;
        }

        try {
          // Re-fetch token on each poll to handle expiration
          const freshToken = await getAuthToken();
          if (!freshToken) {
            setScanning(false);
            showToast('error', 'Session expired. Please refresh the page.');
            if (scanPollRef.current) {
              clearInterval(scanPollRef.current);
              scanPollRef.current = null;
            }
            return;
          }

          const status = await getWorkstreamScanStatus(freshToken, id, scanId);
          setScanStatus(status);

          if (status.status === 'completed') {
            setScanning(false);
            const cardsAdded = status.results?.cards_added_to_workstream ?? 0;
            const cardsCreated = status.results?.cards_created ?? 0;
            if (cardsAdded > 0 || cardsCreated > 0) {
              showToast(
                'success',
                `Scan complete! ${cardsCreated} new card${cardsCreated !== 1 ? 's' : ''} created, ${cardsAdded} added to inbox`
              );
              await loadCards();
            } else {
              showToast('info', 'Scan complete - no new cards found');
            }
            if (scanPollRef.current) {
              clearInterval(scanPollRef.current);
              scanPollRef.current = null;
            }
          } else if (status.status === 'failed') {
            setScanning(false);
            showToast('error', status.error_message || 'Scan failed');
            if (scanPollRef.current) {
              clearInterval(scanPollRef.current);
              scanPollRef.current = null;
            }
          }
        } catch (err) {
          console.error('Error polling scan status:', err);
          // Don't stop polling on transient errors, but log them
        }
      };

      // Poll every 3 seconds
      scanPollRef.current = setInterval(pollScanStatus, 3000);
      // Also poll immediately
      pollScanStatus();

    } catch (err: unknown) {
      setScanning(false);
      const message = err instanceof Error ? err.message : 'Failed to start scan';
      if (message.includes('Rate limit')) {
        showToast('error', 'Scan limit reached (2 per day). Try again tomorrow.');
      } else if (message.includes('already in progress')) {
        showToast('error', 'A scan is already running. Please wait for it to complete.');
      } else if (message.includes('keywords or pillars')) {
        showToast('error', 'Add keywords or pillars to this workstream to enable scanning.');
      } else {
        showToast('error', message);
      }
    }
  }, [id, getAuthToken, showToast, loadCards]);

  // Cleanup scan polling on unmount
  useEffect(() => {
    return () => {
      if (scanPollRef.current) {
        clearInterval(scanPollRef.current);
      }
    };
  }, []);

  /**
   * Handle form modal success.
   */
  const handleFormSuccess = useCallback(() => {
    setShowEditModal(false);
    loadWorkstream();
    showToast('success', 'Workstream updated');
  }, [loadWorkstream, showToast]);

  /**
   * Handle form modal cancel.
   */
  const handleFormCancel = useCallback(() => {
    setShowEditModal(false);
  }, []);

  /**
   * Export workstream report.
   */
  const handleWorkstreamExport = useCallback(
    async (format: 'pdf' | 'pptx') => {
      if (!workstream || !id) return;

      try {
        setExportLoading(format);
        setShowExportMenu(false);

        const token = await getAuthToken();
        if (!token) {
          throw new Error('Authentication required');
        }

        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const exportUrl = `${apiUrl}/api/v1/workstreams/${id}/export/${format}`;

        const response = await fetch(exportUrl, {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `Export failed: ${response.status}`
          );
        }

        // Get filename from Content-Disposition header or generate one
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `${workstream.name.replace(/[^a-zA-Z0-9-_]/g, '_')}.${format}`;
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(
            /filename="?([^"]+)"?/
          );
          if (filenameMatch) {
            filename = filenameMatch[1];
          }
        }

        // Create blob and download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        showToast('success', `${format.toUpperCase()} export started`);
      } catch (err) {
        console.error('Export failed:', err);
        showToast(
          'error',
          err instanceof Error ? err.message : 'Export failed'
        );
      } finally {
        setExportLoading(null);
      }
    },
    [workstream, id, getAuthToken, showToast]
  );

  // ============================================================================
  // Render States
  // ============================================================================

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-brand-blue" />
          <p className="text-gray-600 dark:text-gray-400">
            Loading workstream...
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <div className="text-red-500 dark:text-red-400 mb-4">
            <Filter className="mx-auto h-12 w-12" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Error
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">{error}</p>
          <Link
            to="/workstreams"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Workstreams
          </Link>
        </div>
      </div>
    );
  }

  // Workstream not found
  if (!workstream) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <Filter className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
          <h3 className="mt-2 text-lg font-medium text-gray-900 dark:text-white">
            Workstream not found
          </h3>
          <p className="mt-1 text-gray-600 dark:text-gray-400">
            The workstream you're looking for doesn't exist or has been deleted.
          </p>
          <div className="mt-6">
            <Link
              to="/workstreams"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Workstreams
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ============================================================================
  // Main Render
  // ============================================================================

  return (
    <div className="min-h-screen dark:bg-brand-dark-blue">
      <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header Section */}
        <div className="mb-6">
          {/* Back button */}
          <Link
            to="/workstreams"
            className="inline-flex items-center text-sm text-gray-600 dark:text-gray-400 hover:text-brand-blue transition-colors mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Workstreams
          </Link>

          {/* Title and Actions */}
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2 flex-wrap">
                <h1 className="text-2xl md:text-3xl font-bold text-brand-dark-blue dark:text-white truncate">
                  {workstream.name}
                </h1>
                <StatusBadge isActive={workstream.is_active} />
              </div>
              {workstream.description && (
                <p className="text-gray-600 dark:text-gray-400 max-w-3xl">
                  {workstream.description}
                </p>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* Scan for Updates Button */}
              <button
                onClick={handleStartScan}
                disabled={scanning}
                className={cn(
                  'inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] transition-colors',
                  scanning && 'opacity-75 cursor-not-allowed'
                )}
                title="Scan web sources for new content matching this workstream (2/day limit)"
              >
                {scanning ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Radar className="h-4 w-4 mr-2" />
                )}
                {scanning ? 'Scanning...' : 'Scan for Updates'}
              </button>

              {/* Auto-Populate Button */}
              <button
                onClick={handleAutoPopulate}
                disabled={autoPopulating}
                className={cn(
                  'inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-green hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-green dark:focus:ring-offset-[#2d3166] transition-colors',
                  autoPopulating && 'opacity-75 cursor-not-allowed'
                )}
                title="Find and add matching cards from existing database"
              >
                {autoPopulating ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4 mr-2" />
                )}
                Auto-populate
              </button>

              {/* Refresh Button */}
              <button
                onClick={handleRefresh}
                disabled={refreshing || cardsLoading}
                className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-[#3d4176] hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] transition-colors"
                title="Refresh cards"
              >
                <RefreshCw
                  className={cn(
                    'h-4 w-4',
                    (refreshing || cardsLoading) && 'animate-spin'
                  )}
                />
              </button>

              {/* Export Dropdown */}
              <div className="relative">
                <button
                  onClick={() => setShowExportMenu(!showExportMenu)}
                  disabled={exportLoading !== null}
                  className={cn(
                    'inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-[#3d4176] hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] transition-colors',
                    exportLoading !== null && 'opacity-75 cursor-not-allowed'
                  )}
                  title="Export workstream report"
                >
                  {exportLoading !== null ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4 mr-2" />
                  )}
                  Export
                  <ChevronDown
                    className={cn(
                      'h-4 w-4 ml-1 transition-transform',
                      showExportMenu && 'rotate-180'
                    )}
                  />
                </button>

                {showExportMenu && (
                  <>
                    {/* Backdrop */}
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setShowExportMenu(false)}
                    />
                    <div className="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white dark:bg-[#3d4176] ring-1 ring-black ring-opacity-5 z-20">
                      <div
                        className="py-1"
                        role="menu"
                        aria-orientation="vertical"
                      >
                        <button
                          onClick={() => handleWorkstreamExport('pdf')}
                          className="w-full text-left px-4 py-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#4d5186] flex items-center gap-3 transition-colors"
                          role="menuitem"
                        >
                          <FileText className="h-5 w-5 text-red-500" />
                          <div>
                            <div className="font-medium">PDF Report</div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              Printable document format
                            </div>
                          </div>
                        </button>
                        <button
                          onClick={() => handleWorkstreamExport('pptx')}
                          className="w-full text-left px-4 py-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#4d5186] flex items-center gap-3 transition-colors"
                          role="menuitem"
                        >
                          <Presentation className="h-5 w-5 text-orange-500" />
                          <div>
                            <div className="font-medium">PowerPoint</div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              Presentation slides
                            </div>
                          </div>
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Edit Filters Button */}
              <button
                onClick={() => setShowEditModal(true)}
                className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-[#3d4176] hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] transition-colors"
                title="Edit workstream filters"
              >
                <Settings className="h-4 w-4 mr-2" />
                Edit Filters
              </button>
            </div>
          </div>
        </div>

        {/* Filter Summary */}
        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 mb-6">
          <h2 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
            Active Filters
          </h2>
          <div className="flex items-center gap-6 flex-wrap text-sm">
            {/* Pillars */}
            {workstream.pillar_ids && workstream.pillar_ids.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-gray-600 dark:text-gray-400">
                  Pillars:
                </span>
                <PillarBadgeGroup
                  pillarIds={workstream.pillar_ids}
                  size="sm"
                  maxVisible={4}
                />
              </div>
            )}

            {/* Horizon */}
            {workstream.horizon && workstream.horizon !== 'ALL' && (
              <div className="flex items-center gap-2">
                <span className="text-gray-600 dark:text-gray-400">
                  Horizon:
                </span>
                <HorizonBadge
                  horizon={workstream.horizon as 'H1' | 'H2' | 'H3'}
                  size="sm"
                />
              </div>
            )}

            {/* Stages */}
            {workstream.stage_ids && workstream.stage_ids.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-gray-600 dark:text-gray-400">
                  Stages:
                </span>
                <StageRangeDisplay stageIds={workstream.stage_ids} />
              </div>
            )}

            {/* Keywords */}
            {workstream.keywords && workstream.keywords.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-gray-600 dark:text-gray-400">
                  Keywords:
                </span>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {workstream.keywords.slice(0, 3).map((keyword) => (
                    <KeywordTag key={keyword} keyword={keyword} />
                  ))}
                  {workstream.keywords.length > 3 && (
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      +{workstream.keywords.length - 3} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* No filters */}
            {(!workstream.pillar_ids || workstream.pillar_ids.length === 0) &&
              (!workstream.horizon || workstream.horizon === 'ALL') &&
              (!workstream.stage_ids || workstream.stage_ids.length === 0) &&
              (!workstream.keywords || workstream.keywords.length === 0) && (
                <p className="text-gray-500 dark:text-gray-400 italic">
                  No filters configured
                </p>
              )}
          </div>
        </div>

        {/* Stats Bar */}
        <StatsBar cards={cards} />

        {/* Search and Filter Bar */}
        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 mb-6">
          <div className="flex items-center gap-4 flex-wrap">
            {/* Search Input */}
            <div className="flex-1 min-w-[200px] relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search cards by name or notes..."
                className="w-full pl-9 pr-8 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm bg-white dark:bg-[#3d4176] text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  aria-label="Clear search"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {/* Pillar Filter */}
            {availablePillars.length > 0 && (
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-gray-400" />
                <select
                  value={filterPillar || ''}
                  onChange={(e) => setFilterPillar(e.target.value || null)}
                  className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm bg-white dark:bg-[#3d4176] text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue"
                >
                  <option value="">All Pillars</option>
                  {availablePillars.map((pillarId) => (
                    <option key={pillarId} value={pillarId}>
                      {pillarId}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Clear Filters Button */}
            {(searchQuery || filterPillar) && (
              <button
                onClick={clearFilters}
                className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
              >
                <X className="h-4 w-4" />
                Clear filters
              </button>
            )}

            {/* Filter Results Count */}
            {(searchQuery || filterPillar) && (
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Showing {Object.values(filteredCards).flat().length} of {Object.values(cards).flat().length} cards
              </span>
            )}
          </div>
        </div>

        {/* Kanban Board */}
        {cardsLoading && Object.values(cards).every((c) => c.length === 0) ? (
          <div className="flex items-center justify-center py-16">
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="h-8 w-8 animate-spin text-brand-blue" />
              <p className="text-gray-600 dark:text-gray-400">
                Loading cards...
              </p>
            </div>
          </div>
        ) : (
          <KanbanErrorBoundary
            onError={(error) => {
              console.error('Kanban board error:', error);
              showToast('error', 'An error occurred in the Kanban board');
            }}
          >
            <KanbanBoard
              cards={filteredCards}
              workstreamId={id!}
              onCardMove={handleCardMove}
              onCardClick={handleCardClick}
              cardActions={cardActions}
              onBulkExport={handleOpenBulkExport}
            />
          </KanbanErrorBoundary>
        )}

        {/* Edit Filters Modal */}
        {showEditModal && workstream && (
          <FormModal
            workstream={workstream}
            onSuccess={handleFormSuccess}
            onCancel={handleFormCancel}
          />
        )}

        {/* Brief Preview Modal */}
        <BriefPreviewModal
          isOpen={showBriefModal}
          onClose={handleBriefModalClose}
          brief={
            briefModalCard
              ? (() => {
                  const brief = getCardBrief(briefModalCard.card.id);
                  if (!brief) return null;
                  // Transform API brief to modal brief format
                  return {
                    id: brief.id,
                    card_id: brief.card_id,
                    title: briefModalCard.card.name,
                    executive_summary: brief.summary || '',
                    content_markdown: brief.content_markdown || '',
                    created_at: brief.created_at,
                  };
                })()
              : null
          }
          isGenerating={briefModalCard ? isCardGenerating(briefModalCard.card.id) : false}
          error={briefModalCard ? getCardError(briefModalCard.card.id)?.message || null : null}
          onExportPdf={() => handleBriefExport('pdf')}
          onExportPptx={() => handleBriefExport('pptx')}
          cardName={briefModalCard?.card.name || ''}
          onRetry={
            briefModalCard
              ? () => triggerBriefGeneration(briefModalCard.card.id)
              : undefined
          }
        />

        {/* Export Progress Modal */}
        <ExportProgressModal
          isOpen={exportState.showModal}
          onClose={closeExportModal}
          status={exportState.status}
          format={exportState.format || 'pptx'}
          progress={exportState.progress}
          statusMessage={exportState.statusMessage}
          errorMessage={exportState.errorMessage}
          downloadUrl={exportState.downloadUrl || undefined}
          filename={exportState.filename || undefined}
          onDownload={downloadExport}
          onRetry={retryExport}
          itemName={exportState.itemName || undefined}
          isGammaPowered={exportState.isGammaPowered}
          estimatedTimeSeconds={exportState.estimatedTimeSeconds}
        />

        {/* Bulk Export Modal */}
        <BulkExportModal
          isOpen={showBulkExportModal}
          onClose={handleCloseBulkExport}
          workstreamName={workstream?.name || 'Workstream'}
          statusData={bulkExportStatus}
          isLoading={bulkExportLoading}
          error={bulkExportError}
          onExport={handleExecuteBulkExport}
          isExporting={isBulkExporting}
        />

        {/* Toast Notifications */}
        <ToastContainer notifications={toasts} onDismiss={dismissToast} />
      </div>
    </div>
  );
};

export default WorkstreamKanban;
