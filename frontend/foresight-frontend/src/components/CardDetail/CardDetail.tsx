/**
 * CardDetail Component
 *
 * A refactored, modular component that displays comprehensive card/trend details.
 * This component orchestrates top-level state management and data flow,
 * delegating rendering to focused sub-components.
 *
 * Original: 1829 lines -> Refactored: ~290 lines
 *
 * Features:
 * - Modular composition of sub-components
 * - Centralized state management for data loading
 * - Research task triggering and polling
 * - Tab-based navigation (Overview, Sources, Timeline, Notes, Related)
 * - Dark mode support
 * - Responsive design
 *
 * @module CardDetail
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Eye, FileText, Calendar, TrendingUp, GitBranch, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { supabase } from '../../App';
import { useAuthContext } from '../../hooks/useAuthContext';
import { cn } from '../../lib/utils';

// CardDetail sub-components
import { CardDetailHeader } from './CardDetailHeader';
import { CardActionButtons } from './CardActionButtons';
import {
  CardDescription,
  CardClassification,
  ResearchHistoryPanel,
  ImpactMetricsPanel,
  MaturityScorePanel,
  ActivityStatsPanel,
} from './tabs/OverviewTab';
import { SourcesTab } from './tabs/SourcesTab';
import { TimelineTab } from './tabs/TimelineTab';
import { NotesTab } from './tabs/NotesTab';

// Visualization Components
import { ScoreTimelineChart } from '../visualizations/ScoreTimelineChart';
import { ConceptNetworkDiagram } from '../visualizations/ConceptNetworkDiagram';

// Types and utilities
import type { Card, ResearchTask, Source, TimelineEvent, Note, CardDetailTab } from './types';
import { API_BASE_URL } from './utils';

// API Functions
import {
  getScoreHistory,
  getStageHistory,
  getRelatedCards,
  type ScoreHistory,
  type StageHistory,
  type RelatedCard,
} from '../../lib/discovery-api';

/**
 * Props for the CardDetail component
 */
export interface CardDetailProps {
  /** Optional custom className for the container */
  className?: string;
}

/**
 * CardDetail displays comprehensive information about a card/trend.
 *
 * This is the main orchestrator component that:
 * - Loads and manages all card-related data
 * - Handles research task triggering and status polling
 * - Manages user interactions (following, notes)
 * - Renders sub-components in a tabbed layout
 */
export const CardDetail: React.FC<CardDetailProps> = ({ className = '' }) => {
  const { slug } = useParams<{ slug: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();

  // Core card data
  const [card, setCard] = useState<Card | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [isFollowing, setIsFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<CardDetailTab>('overview');
  const [newNote, setNewNote] = useState('');

  // Research state
  const [researchTask, setResearchTask] = useState<ResearchTask | null>(null);
  const [isResearching, setIsResearching] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [showReport, setShowReport] = useState(false);
  const [reportCopied, setReportCopied] = useState(false);
  const [researchHistory, setResearchHistory] = useState<ResearchTask[]>([]);

  // Trend visualization state
  const [scoreHistory, setScoreHistory] = useState<ScoreHistory[]>([]);
  const [stageHistory, setStageHistory] = useState<StageHistory[]>([]);
  const [scoreHistoryLoading, setScoreHistoryLoading] = useState(false);
  const [stageHistoryLoading, setStageHistoryLoading] = useState(false);
  const [scoreHistoryError, setScoreHistoryError] = useState<string | null>(null);

  // Related cards state
  const [relatedCards, setRelatedCards] = useState<RelatedCard[]>([]);
  const [relatedCardsLoading, setRelatedCardsLoading] = useState(false);
  const [relatedCardsError, setRelatedCardsError] = useState<string | null>(null);

  // Get auth token for API requests
  const getAuthToken = useCallback(async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token;
  }, []);

  // Load card detail from database
  const loadCardDetail = useCallback(async () => {
    if (!slug) return;
    try {
      const { data: cardData } = await supabase
        .from('cards')
        .select('*')
        .eq('slug', slug)
        .eq('status', 'active')
        .single();

      if (cardData) {
        setCard(cardData);

        // Load related data in parallel
        const [sourcesRes, timelineRes, notesRes, researchRes] = await Promise.all([
          supabase.from('sources').select('*').eq('card_id', cardData.id).order('relevance_score', { ascending: false }),
          supabase.from('card_timeline').select('*').eq('card_id', cardData.id).order('created_at', { ascending: false }),
          supabase.from('card_notes').select('*').eq('card_id', cardData.id).or(`user_id.eq.${user?.id},is_private.eq.false`).order('created_at', { ascending: false }),
          supabase.from('research_tasks').select('*').eq('card_id', cardData.id).eq('status', 'completed').order('completed_at', { ascending: false }).limit(10),
        ]);

        setSources(sourcesRes.data || []);
        setTimeline(timelineRes.data || []);
        setNotes(notesRes.data || []);
        setResearchHistory(researchRes.data || []);
      }
    } finally {
      setLoading(false);
    }
  }, [slug, user?.id]);

  // Load score/stage history and related cards
  const loadScoreHistory = useCallback(async () => {
    if (!card?.id) return;
    setScoreHistoryLoading(true);
    setScoreHistoryError(null);
    try {
      const token = await getAuthToken();
      if (token) {
        const response = await getScoreHistory(token, card.id);
        setScoreHistory(response.history);
      }
    } catch (error: unknown) {
      setScoreHistoryError(error instanceof Error ? error.message : 'Failed to load');
    } finally {
      setScoreHistoryLoading(false);
    }
  }, [card?.id, getAuthToken]);

  const loadStageHistory = useCallback(async () => {
    if (!card?.id) return;
    setStageHistoryLoading(true);
    try {
      const token = await getAuthToken();
      if (token) {
        const response = await getStageHistory(token, card.id);
        setStageHistory(response.history);
      }
    } finally {
      setStageHistoryLoading(false);
    }
  }, [card?.id, getAuthToken]);

  const loadRelatedCards = useCallback(async () => {
    if (!card?.id) return;
    setRelatedCardsLoading(true);
    setRelatedCardsError(null);
    try {
      const token = await getAuthToken();
      if (token) {
        const response = await getRelatedCards(token, card.id);
        setRelatedCards(response.related_cards);
      }
    } catch (error: unknown) {
      setRelatedCardsError(error instanceof Error ? error.message : 'Failed to load');
    } finally {
      setRelatedCardsLoading(false);
    }
  }, [card?.id, getAuthToken]);

  // Check following status
  const checkIfFollowing = useCallback(async () => {
    if (!user || !card?.id) return;
    try {
      const { data } = await supabase.from('card_follows').select('id').eq('user_id', user.id).eq('card_id', card.id).maybeSingle();
      setIsFollowing(!!data);
    } catch {
      setIsFollowing(false);
    }
  }, [user, card?.id]);

  // Toggle follow status
  const toggleFollow = useCallback(async () => {
    if (!user || !card) return;
    try {
      if (isFollowing) {
        await supabase.from('card_follows').delete().eq('user_id', user.id).eq('card_id', card.id);
        setIsFollowing(false);
      } else {
        await supabase.from('card_follows').insert({ user_id: user.id, card_id: card.id, priority: 'medium' });
        setIsFollowing(true);
      }
    } catch (error) {
      console.error('Error toggling follow:', error);
    }
  }, [user, card, isFollowing]);

  // Add note
  const addNote = useCallback(async () => {
    if (!user || !card || !newNote.trim()) return;
    try {
      const { data } = await supabase.from('card_notes').insert({ user_id: user.id, card_id: card.id, content: newNote, is_private: false }).select().single();
      if (data) {
        setNotes([data, ...notes]);
        setNewNote('');
      }
    } catch (error) {
      console.error('Error adding note:', error);
    }
  }, [user, card, newNote, notes]);

  // Poll for research task status
  const pollTaskStatus = useCallback(async (taskId: string) => {
    const token = await getAuthToken();
    if (!token) return;

    const poll = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/research/${taskId}`, { headers: { Authorization: `Bearer ${token}` } });
        if (!response.ok) throw new Error('Failed to get task status');
        const task: ResearchTask = await response.json();
        setResearchTask(task);

        if (task.status === 'completed') {
          setIsResearching(false);
          loadCardDetail();
        } else if (task.status === 'failed') {
          setIsResearching(false);
          setResearchError(task.error_message || 'Research failed');
        } else {
          setTimeout(poll, 2000);
        }
      } catch {
        setIsResearching(false);
        setResearchError('Failed to check research status');
      }
    };
    poll();
  }, [getAuthToken, loadCardDetail]);

  // Trigger research
  const triggerResearch = useCallback(async (taskType: 'update' | 'deep_research') => {
    if (!card || isResearching) return;
    setIsResearching(true);
    setResearchError(null);
    setResearchTask(null);

    try {
      const token = await getAuthToken();
      if (!token) throw new Error('Not authenticated');

      const response = await fetch(`${API_BASE_URL}/api/v1/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ card_id: card.id, task_type: taskType }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start research');
      }

      const task = await response.json();
      setResearchTask(task);
      pollTaskStatus(task.id);
    } catch (error: unknown) {
      setResearchError(error instanceof Error ? error.message : 'Failed to start research');
      setIsResearching(false);
    }
  }, [card, isResearching, getAuthToken, pollTaskStatus]);

  // Handle related card click
  const handleRelatedCardClick = useCallback((cardId: string, cardSlug: string) => {
    if (cardSlug) navigate(`/cards/${cardSlug}`);
  }, [navigate]);

  // Effects
  useEffect(() => { if (slug) loadCardDetail(); }, [slug, loadCardDetail]);
  useEffect(() => { if (card?.id && user) checkIfFollowing(); }, [card?.id, user, checkIfFollowing]);
  useEffect(() => { if (card?.id) { loadScoreHistory(); loadStageHistory(); loadRelatedCards(); } }, [card?.id, loadScoreHistory, loadStageHistory, loadRelatedCards]);

  // Computed values
  const canDeepResearch = card && (card.deep_research_count_today ?? 0) < 2;

  // Tab definitions
  const tabs = [
    { id: 'overview' as const, name: 'Overview', icon: Eye },
    { id: 'sources' as const, name: 'Sources', icon: FileText },
    { id: 'timeline' as const, name: 'Timeline', icon: Calendar },
    { id: 'notes' as const, name: 'Notes', icon: TrendingUp },
    { id: 'related' as const, name: 'Related', icon: GitBranch },
  ];

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-brand-blue" />
      </div>
    );
  }

  // Not found state
  if (!card) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Card not found</h1>
          <Link to="/discover" className="text-brand-blue hover:text-brand-dark-blue mt-4 inline-block transition-colors">
            Back to Discover
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8', className)}>
      {/* Header with action buttons */}
      <CardDetailHeader card={card}>
        <CardActionButtons
          card={card}
          isFollowing={isFollowing}
          isResearching={isResearching}
          researchTask={researchTask}
          canDeepResearch={canDeepResearch ?? false}
          onTriggerResearch={triggerResearch}
          onToggleFollow={toggleFollow}
          getAuthToken={getAuthToken}
        />
      </CardDetailHeader>

      {/* Research Status Banner */}
      {(isResearching || researchError || researchTask?.status === 'completed') && (
        <ResearchStatusBanner
          isResearching={isResearching}
          researchError={researchError}
          researchTask={researchTask}
          showReport={showReport}
          reportCopied={reportCopied}
          onToggleReport={() => setShowReport(!showReport)}
          onCopyReport={() => { navigator.clipboard.writeText(researchTask?.result_summary?.report_preview || ''); setReportCopied(true); setTimeout(() => setReportCopied(false), 2000); }}
          onDismissError={() => setResearchError(null)}
          onDismissTask={() => setResearchTask(null)}
        />
      )}

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6 sm:mb-8 -mx-4 px-4 sm:mx-0 sm:px-0">
        <nav className="-mb-px flex space-x-4 sm:space-x-8 overflow-x-auto scrollbar-hide" role="tablist">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                role="tab"
                aria-selected={activeTab === tab.id}
                className={cn(
                  'py-2 px-1 border-b-2 font-medium text-sm flex items-center whitespace-nowrap transition-colors flex-shrink-0',
                  activeTab === tab.id
                    ? 'border-brand-blue text-brand-blue'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
                )}
              >
                <Icon className="h-4 w-4 mr-2" />
                {tab.name}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 lg:gap-8">
          <div className="lg:col-span-2 space-y-4 sm:space-y-6">
            <CardDescription description={card.description} />
            <CardClassification card={card} stageHistory={stageHistory} stageHistoryLoading={stageHistoryLoading} />
            <ScoreTimelineChart data={scoreHistory} title="Score History" height={350} loading={scoreHistoryLoading} error={scoreHistoryError} onRetry={loadScoreHistory} />
            <ResearchHistoryPanel researchHistory={researchHistory} />
          </div>
          <div className="space-y-4 sm:space-y-6">
            <ImpactMetricsPanel impactScore={card.impact_score} relevanceScore={card.relevance_score} velocityScore={card.velocity_score} noveltyScore={card.novelty_score} opportunityScore={card.opportunity_score} riskScore={card.risk_score} />
            <MaturityScorePanel maturityScore={card.maturity_score} stageId={card.stage_id} />
            <ActivityStatsPanel sourcesCount={sources.length} timelineCount={timeline.length} notesCount={notes.length} scoreHistory={scoreHistory} scoreHistoryLoading={scoreHistoryLoading} createdAt={card.created_at} updatedAt={card.updated_at} deepResearchAt={card.deep_research_at} />
          </div>
        </div>
      )}

      {activeTab === 'sources' && <SourcesTab sources={sources} />}
      {activeTab === 'timeline' && <TimelineTab timeline={timeline} />}
      {activeTab === 'notes' && <NotesTab notes={notes} newNoteValue={newNote} onNewNoteChange={setNewNote} onAddNote={addNote} />}
      {activeTab === 'related' && (
        <ConceptNetworkDiagram
          sourceCardId={card.id}
          sourceCardName={card.name}
          sourceCardSummary={card.summary}
          sourceCardHorizon={card.horizon}
          relatedCards={relatedCards}
          height={600}
          loading={relatedCardsLoading}
          error={relatedCardsError}
          onRetry={loadRelatedCards}
          onCardClick={handleRelatedCardClick}
          showMinimap
          showBackground
          title="Related Trends Network"
        />
      )}
    </div>
  );
};

// ============================================================================
// ResearchStatusBanner - Inline component for research status display
// TODO: Extract to ResearchStatusBanner.tsx in subtask 2.4
// ============================================================================

interface ResearchStatusBannerProps {
  isResearching: boolean;
  researchError: string | null;
  researchTask: ResearchTask | null;
  showReport: boolean;
  reportCopied: boolean;
  onToggleReport: () => void;
  onCopyReport: () => void;
  onDismissError: () => void;
  onDismissTask: () => void;
}

const ResearchStatusBanner: React.FC<ResearchStatusBannerProps> = ({
  isResearching,
  researchError,
  researchTask,
  showReport,
  reportCopied,
  onToggleReport,
  onCopyReport,
  onDismissError,
  onDismissTask,
}) => {
  const { Check, Copy, ChevronDown, ChevronUp, FileText: FileTextIcon } = require('lucide-react');

  return (
    <div className={cn(
      'mb-6 rounded-lg border overflow-hidden',
      isResearching && 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800',
      researchError && 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800',
      researchTask?.status === 'completed' && !isResearching && 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
    )}>
      <div className="p-4">
        <div className="flex items-center gap-3">
          {isResearching && (
            <>
              <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
              <div>
                <p className="font-medium text-blue-800 dark:text-blue-200">
                  {researchTask?.task_type === 'deep_research' ? 'Deep research in progress...' : 'Updating sources...'}
                </p>
                <p className="text-sm text-blue-600 dark:text-blue-300">This may take a minute. You can continue browsing.</p>
              </div>
            </>
          )}
          {researchError && (
            <>
              <div className="h-5 w-5 rounded-full bg-red-500 text-white flex items-center justify-center text-xs font-bold">!</div>
              <div>
                <p className="font-medium text-red-800 dark:text-red-200">Research failed</p>
                <p className="text-sm text-red-600 dark:text-red-300">{researchError}</p>
              </div>
              <button onClick={onDismissError} className="ml-auto text-red-600 hover:text-red-800 text-sm">Dismiss</button>
            </>
          )}
          {researchTask?.status === 'completed' && !isResearching && !researchError && (
            <>
              <div className="h-5 w-5 rounded-full bg-green-500 text-white flex items-center justify-center text-xs">&#10003;</div>
              <div className="flex-1">
                <p className="font-medium text-green-800 dark:text-green-200">Research completed!</p>
                <p className="text-sm text-green-600 dark:text-green-300">
                  Discovered {researchTask.result_summary?.sources_found || 0} sources
                  {researchTask.result_summary?.sources_relevant && ` → ${researchTask.result_summary.sources_relevant} relevant`}
                  {' → '}added {researchTask.result_summary?.sources_added || 0} new
                </p>
              </div>
              <div className="flex items-center gap-2">
                {researchTask.result_summary?.report_preview && (
                  <button onClick={onToggleReport} className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-green-700 bg-green-100 hover:bg-green-200 rounded-md transition-colors">
                    <FileTextIcon className="h-4 w-4 mr-1.5" />
                    {showReport ? 'Hide' : 'View'} Report
                    {showReport ? <ChevronUp className="h-4 w-4 ml-1" /> : <ChevronDown className="h-4 w-4 ml-1" />}
                  </button>
                )}
                <button onClick={onDismissTask} className="text-green-600 hover:text-green-800 text-sm">Dismiss</button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Collapsible Research Report */}
      {researchTask?.status === 'completed' && showReport && researchTask.result_summary?.report_preview && (
        <div className="border-t border-green-200 dark:border-green-800 bg-white dark:bg-gray-900">
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <FileTextIcon className="h-4 w-4" />
                Research Report
              </h4>
              <button onClick={onCopyReport} className="inline-flex items-center px-2 py-1 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 dark:text-gray-300 dark:bg-gray-800 dark:hover:bg-gray-700 rounded transition-colors">
                {reportCopied ? <><Check className="h-3 w-3 mr-1 text-green-600" />Copied!</> : <><Copy className="h-3 w-3 mr-1" />Copy Report</>}
              </button>
            </div>
            <div className="prose prose-sm dark:prose-invert max-w-none max-h-[70vh] sm:max-h-[500px] overflow-y-auto p-3 sm:p-4 bg-gray-50 dark:bg-gray-800 rounded-lg break-words">
              <ReactMarkdown>{researchTask.result_summary.report_preview}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CardDetail;
