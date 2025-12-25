import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Heart, Calendar, ExternalLink, FileText, TrendingUp, Eye, Info, RefreshCw, Search, Loader2, ChevronDown, ChevronUp, Copy, Check, Download, FileSpreadsheet, Presentation } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { cn } from '../lib/utils';
import { Tooltip } from '../components/ui/Tooltip';

// Badge Components
import { PillarBadge } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge, StageProgress } from '../components/StageBadge';
import { AnchorBadge } from '../components/AnchorBadge';
import { Top25Badge, Top25List } from '../components/Top25Badge';

// Taxonomy helpers
import { getGoalByCode, type Goal } from '../data/taxonomy';

interface Card {
  id: string;
  name: string;
  slug: string;
  summary: string;
  description: string;
  pillar_id: string;
  goal_id: string;
  anchor_id?: string;
  stage_id: string;
  horizon: 'H1' | 'H2' | 'H3';
  novelty_score: number;
  maturity_score: number;
  impact_score: number;
  relevance_score: number;
  velocity_score: number;
  risk_score: number;
  opportunity_score: number;
  top25_relevance?: string[];
  created_at: string;
  updated_at: string;
  deep_research_at?: string;
  deep_research_count_today?: number;
}

interface ResearchTask {
  id: string;
  task_type: 'update' | 'deep_research';
  status: 'queued' | 'processing' | 'completed' | 'failed';
  result_summary?: {
    sources_found?: number;
    sources_relevant?: number;
    sources_added?: number;
    cards_matched?: string[];
    cards_created?: string[];
    entities_extracted?: number;
    cost_estimate?: number;
    report_preview?: string;  // Full research report text
  };
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

interface Source {
  id: string;
  title: string;
  url: string;
  // Database fields
  ai_summary?: string;
  key_excerpts?: string[];
  publication?: string;
  full_text?: string;
  relevance_to_card?: number;
  api_source?: string;
  ingested_at?: string;
  // Legacy fields (may be null)
  summary?: string;
  source_type?: string;
  author?: string;
  publisher?: string;
  published_date?: string;
  relevance_score?: number;
}

interface TimelineEvent {
  id: string;
  event_type: string;
  title: string;
  description: string;
  created_at: string;
  metadata?: {
    sources_found?: number;
    sources_relevant?: number;
    sources_added?: number;
    entities_extracted?: number;
    cost?: number;
    detailed_report?: string;
  };
}

interface Note {
  id: string;
  content: string;
  is_private: boolean;
  created_at: string;
}

/**
 * Parse stage number from stage_id string
 * Handles formats like "1_concept", "3_prototype", etc.
 */
const parseStageNumber = (stageId: string): number | null => {
  if (!stageId) return null;
  const match = stageId.match(/^(\d+)/);
  return match ? parseInt(match[1], 10) : null;
};

/**
 * Get score color classes based on score value
 * WCAG 2.1 AA compliant - minimum 4.5:1 contrast ratio for text
 */
const getScoreColorClasses = (score: number): { bg: string; text: string; border: string } => {
  if (score >= 80) {
    return {
      bg: 'bg-green-100 dark:bg-green-900/40',
      text: 'text-green-800 dark:text-green-200',
      border: 'border-green-400 dark:border-green-600'
    };
  }
  if (score >= 60) {
    return {
      bg: 'bg-amber-100 dark:bg-amber-900/40',
      text: 'text-amber-800 dark:text-amber-200',
      border: 'border-amber-400 dark:border-amber-600'
    };
  }
  if (score >= 40) {
    return {
      bg: 'bg-orange-100 dark:bg-orange-900/40',
      text: 'text-orange-800 dark:text-orange-200',
      border: 'border-orange-400 dark:border-orange-600'
    };
  }
  return {
    bg: 'bg-red-100 dark:bg-red-900/40',
    text: 'text-red-800 dark:text-red-200',
    border: 'border-red-400 dark:border-red-600'
  };
};

/**
 * Metric definitions with descriptions for tooltips
 */
const metricDefinitions: Record<string, { label: string; description: string }> = {
  impact: {
    label: 'Impact',
    description: 'Potential magnitude of effect on City operations, services, or residents',
  },
  relevance: {
    label: 'Relevance',
    description: 'How closely this aligns with current City priorities and strategic goals',
  },
  velocity: {
    label: 'Velocity',
    description: 'Speed of development and adoption in the broader ecosystem',
  },
  novelty: {
    label: 'Novelty',
    description: 'How new or unprecedented this signal is compared to existing knowledge',
  },
  opportunity: {
    label: 'Opportunity',
    description: 'Potential benefits and positive outcomes if adopted or leveraged',
  },
  risk: {
    label: 'Risk',
    description: 'Potential negative consequences or challenges to consider',
  },
};

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const CardDetail: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { user } = useAuthContext();
  const [card, setCard] = useState<Card | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [isFollowing, setIsFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'sources' | 'timeline' | 'notes'>('overview');
  const [newNote, setNewNote] = useState('');

  // Research state
  const [researchTask, setResearchTask] = useState<ResearchTask | null>(null);
  const [isResearching, setIsResearching] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [showReport, setShowReport] = useState(false);
  const [reportCopied, setReportCopied] = useState(false);

  // Research history state
  const [researchHistory, setResearchHistory] = useState<ResearchTask[]>([]);
  const [expandedReportId, setExpandedReportId] = useState<string | null>(null);

  // Timeline expanded reports
  const [expandedTimelineId, setExpandedTimelineId] = useState<string | null>(null);

  // Export state
  const [showExportDropdown, setShowExportDropdown] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (slug) {
      loadCardDetail();
    }
  }, [slug]);

  // Check following status after card is loaded
  useEffect(() => {
    if (card?.id && user) {
      checkIfFollowing();
    }
  }, [card?.id, user]);

  const loadCardDetail = async () => {
    try {
      // Load card
      const { data: cardData } = await supabase
        .from('cards')
        .select('*')
        .eq('slug', slug)
        .eq('status', 'active')
        .single();

      if (cardData) {
        setCard(cardData);

        // Load sources
        const { data: sourcesData } = await supabase
          .from('sources')
          .select('*')
          .eq('card_id', cardData.id)
          .order('relevance_score', { ascending: false });

        // Load timeline
        const { data: timelineData } = await supabase
          .from('card_timeline')
          .select('*')
          .eq('card_id', cardData.id)
          .order('created_at', { ascending: false });

        // Load notes
        const { data: notesData } = await supabase
          .from('card_notes')
          .select('*')
          .eq('card_id', cardData.id)
          .or(`user_id.eq.${user?.id},is_private.eq.false`)
          .order('created_at', { ascending: false });

        // Load research history (completed tasks only)
        const { data: researchData } = await supabase
          .from('research_tasks')
          .select('*')
          .eq('card_id', cardData.id)
          .eq('status', 'completed')
          .order('completed_at', { ascending: false })
          .limit(10);

        setSources(sourcesData || []);
        setTimeline(timelineData || []);
        setNotes(notesData || []);
        setResearchHistory(researchData || []);
      }
    } catch (error) {
      console.error('Error loading card detail:', error);
    } finally {
      setLoading(false);
    }
  };

  const checkIfFollowing = async () => {
    if (!user || !card?.id) return;

    try {
      const { data } = await supabase
        .from('card_follows')
        .select('id')
        .eq('user_id', user.id)
        .eq('card_id', card.id)
        .maybeSingle();  // Use maybeSingle to avoid 406 error when no row exists

      setIsFollowing(!!data);
    } catch (error) {
      setIsFollowing(false);
    }
  };

  const toggleFollow = async () => {
    if (!user || !card) return;

    try {
      if (isFollowing) {
        await supabase
          .from('card_follows')
          .delete()
          .eq('user_id', user.id)
          .eq('card_id', card.id);
        setIsFollowing(false);
      } else {
        await supabase
          .from('card_follows')
          .insert({
            user_id: user.id,
            card_id: card.id,
            priority: 'medium'
          });
        setIsFollowing(true);
      }
    } catch (error) {
      console.error('Error toggling follow:', error);
    }
  };

  const addNote = async () => {
    if (!user || !card || !newNote.trim()) return;

    try {
      const { data } = await supabase
        .from('card_notes')
        .insert({
          user_id: user.id,
          card_id: card.id,
          content: newNote,
          is_private: false
        })
        .select()
        .single();

      if (data) {
        setNotes([data, ...notes]);
        setNewNote('');
      }
    } catch (error) {
      console.error('Error adding note:', error);
    }
  };

  // Get auth token for API requests
  const getAuthToken = useCallback(async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token;
  }, []);

  // Trigger research (update or deep_research)
  const triggerResearch = async (taskType: 'update' | 'deep_research') => {
    if (!card || isResearching) return;

    setIsResearching(true);
    setResearchError(null);
    setResearchTask(null);

    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          card_id: card.id,
          task_type: taskType,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start research');
      }

      const task = await response.json();
      setResearchTask(task);

      // Start polling for task status
      pollTaskStatus(task.id);
    } catch (error: any) {
      console.error('Error triggering research:', error);
      setResearchError(error.message || 'Failed to start research');
      setIsResearching(false);
    }
  };

  // Poll for task status until complete
  const pollTaskStatus = useCallback(async (taskId: string) => {
    const token = await getAuthToken();
    if (!token) return;

    const poll = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/research/${taskId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error('Failed to get task status');
        }

        const task: ResearchTask = await response.json();
        setResearchTask(task);

        if (task.status === 'completed') {
          setIsResearching(false);
          // Reload card detail to get updated data
          loadCardDetail();
        } else if (task.status === 'failed') {
          setIsResearching(false);
          setResearchError(task.error_message || 'Research failed');
        } else {
          // Still processing, poll again in 2 seconds
          setTimeout(poll, 2000);
        }
      } catch (error: any) {
        console.error('Error polling task status:', error);
        setIsResearching(false);
        setResearchError('Failed to check research status');
      }
    };

    poll();
  }, [getAuthToken]);

  // Check if deep research is available (rate limit)
  const canDeepResearch = card && (card.deep_research_count_today ?? 0) < 2;

  // Format relative time for smart timestamp display
  const formatRelativeTime = (dateStr: string | undefined): string => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));

    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  // Handle export to different formats
  const handleExport = async (format: 'pdf' | 'pptx' | 'csv') => {
    if (!card || isExporting) return;

    setIsExporting(true);
    setExportError(null);
    setShowExportDropdown(false);

    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(
        `${API_BASE_URL}/api/v1/cards/${card.id}/export/${format}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Export failed: ${response.statusText}`);
      }

      // Create blob from response and trigger download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${card.slug}-export.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error: any) {
      setExportError(error.message || 'Failed to export card');
    } finally {
      setIsExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-brand-blue"></div>
      </div>
    );
  }

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

  // Parse stage number from stage_id
  const stageNumber = parseStageNumber(card.stage_id);

  // Get goal information
  const goal: Goal | undefined = card.goal_id ? getGoalByCode(card.goal_id) : undefined;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <Link
          to="/discover"
          className="inline-flex items-center text-sm text-gray-500 dark:text-gray-400 hover:text-brand-blue mb-4 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Discover
        </Link>

        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Title and Primary Badges */}
            <div className="flex flex-col sm:flex-row sm:items-center flex-wrap gap-3 mb-4">
              <h1 className="text-2xl sm:text-3xl font-bold text-brand-dark-blue dark:text-white break-words">{card.name}</h1>
              <div className="flex items-center gap-2 flex-wrap">
                <PillarBadge
                  pillarId={card.pillar_id}
                  goalId={card.goal_id}
                  showIcon
                  size="md"
                />
                <HorizonBadge
                  horizon={card.horizon}
                  showIcon
                  size="md"
                />
                {card.top25_relevance && card.top25_relevance.length > 0 && (
                  <Top25Badge
                    priorities={card.top25_relevance}
                    showCount
                    size="md"
                  />
                )}
              </div>
            </div>

            {/* Summary */}
            <p className="text-base sm:text-lg text-gray-600 dark:text-gray-300 mb-4 break-words">{card.summary}</p>

            {/* Quick Info Row */}
            <div className="flex items-center flex-wrap gap-2 sm:gap-4 text-sm">
              {stageNumber && (
                <StageBadge
                  stage={stageNumber}
                  variant="badge"
                  showName
                  size="sm"
                />
              )}
              {card.anchor_id && (
                <AnchorBadge
                  anchor={card.anchor_id}
                  size="sm"
                  abbreviated
                />
              )}
              <span className="text-gray-500">
                Created: {new Date(card.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>

          {/* Action buttons - horizontal scroll on mobile, wrap on larger screens */}
          <div className="flex items-center gap-2 sm:gap-3 overflow-x-auto pb-2 lg:pb-0 lg:overflow-visible lg:flex-wrap lg:justify-end -mx-4 px-4 sm:mx-0 sm:px-0">
            {/* Research buttons */}
            <Tooltip
              content={
                <div className="max-w-[200px]">
                  <p className="font-medium">Quick Update</p>
                  <p className="text-xs text-gray-500">Find 5-10 new sources and refresh card data</p>
                </div>
              }
              side="bottom"
            >
              <button
                onClick={() => triggerResearch('update')}
                disabled={isResearching}
                className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95"
              >
                {isResearching && researchTask?.task_type === 'update' ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                Update
              </button>
            </Tooltip>

            <Tooltip
              content={
                <div className="max-w-[200px]">
                  <p className="font-medium">Deep Research</p>
                  <p className="text-xs text-gray-500">
                    Comprehensive research with 15+ sources and metrics update
                    {!canDeepResearch && <span className="block text-amber-500 mt-1">Daily limit reached (2/day)</span>}
                  </p>
                </div>
              }
              side="bottom"
            >
              <button
                onClick={() => triggerResearch('deep_research')}
                disabled={isResearching || !canDeepResearch}
                className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-3 py-2 border border-brand-blue rounded-md shadow-sm text-sm font-medium text-white bg-brand-blue hover:bg-brand-dark-blue disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95"
              >
                {isResearching && researchTask?.task_type === 'deep_research' ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Search className="h-4 w-4 mr-2" />
                )}
                Deep Research
              </button>
            </Tooltip>

            {/* Export Dropdown */}
            <div className="relative">
              <Tooltip
                content={
                  <div className="max-w-[200px]">
                    <p className="font-medium">Export Card</p>
                    <p className="text-xs text-gray-500">Download this card in various formats for sharing and analysis</p>
                  </div>
                }
                side="bottom"
              >
                <button
                  onClick={() => setShowExportDropdown(!showExportDropdown)}
                  disabled={isExporting}
                  className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95"
                >
                  {isExporting ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4 mr-2" />
                  )}
                  Export
                  <ChevronDown className="h-4 w-4 ml-1" />
                </button>
              </Tooltip>

              {/* Dropdown Menu */}
              {showExportDropdown && (
                <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-[#3d4176] rounded-md shadow-lg border border-gray-200 dark:border-gray-600 py-1 z-20">
                  <button
                    onClick={() => handleExport('pdf')}
                    className="w-full flex items-center min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:bg-gray-200 dark:active:bg-gray-600"
                  >
                    <FileText className="h-4 w-4 mr-3 text-red-500" />
                    Export as PDF
                  </button>
                  <button
                    onClick={() => handleExport('pptx')}
                    className="w-full flex items-center min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:bg-gray-200 dark:active:bg-gray-600"
                  >
                    <Presentation className="h-4 w-4 mr-3 text-orange-500" />
                    Export as PowerPoint
                  </button>
                  <button
                    onClick={() => handleExport('csv')}
                    className="w-full flex items-center min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:bg-gray-200 dark:active:bg-gray-600"
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-3 text-green-500" />
                    Export as CSV
                  </button>
                </div>
              )}
            </div>

            <button
              onClick={toggleFollow}
              className={`inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-4 py-2 border rounded-md shadow-sm text-sm font-medium transition-colors active:scale-95 ${
                isFollowing
                  ? 'border-red-300 text-red-700 bg-red-50 hover:bg-red-100'
                  : 'border-gray-300 text-gray-700 bg-white hover:bg-gray-50'
              }`}
            >
              <Heart className={`h-4 w-4 mr-2 ${isFollowing ? 'fill-current' : ''}`} />
              {isFollowing ? 'Following' : 'Follow'}
            </button>
          </div>
        </div>
      </div>

      {/* Export Error Banner */}
      {exportError && (
        <div className="mb-6 rounded-lg border bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800 p-4">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 rounded-full bg-red-500 text-white flex items-center justify-center text-xs font-bold">!</div>
            <div>
              <p className="font-medium text-red-800 dark:text-red-200">Export failed</p>
              <p className="text-sm text-red-600 dark:text-red-300">{exportError}</p>
            </div>
            <button
              onClick={() => setExportError(null)}
              className="ml-auto text-red-600 hover:text-red-800 text-sm"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Research Status Banner */}
      {(isResearching || researchError || researchTask?.status === 'completed') && (
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
                    <p className="text-sm text-blue-600 dark:text-blue-300">
                      This may take a minute. You can continue browsing.
                    </p>
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
                  <button
                    onClick={() => setResearchError(null)}
                    className="ml-auto text-red-600 hover:text-red-800 text-sm"
                  >
                    Dismiss
                  </button>
                </>
              )}
              {researchTask?.status === 'completed' && !isResearching && !researchError && (
                <>
                  <div className="h-5 w-5 rounded-full bg-green-500 text-white flex items-center justify-center text-xs">✓</div>
                  <div className="flex-1">
                    <p className="font-medium text-green-800 dark:text-green-200">Research completed!</p>
                    <p className="text-sm text-green-600 dark:text-green-300">
                      Discovered {researchTask.result_summary?.sources_found || 0} sources
                      {researchTask.result_summary?.sources_relevant &&
                        ` → ${researchTask.result_summary.sources_relevant} relevant`}
                      {' → '}added {researchTask.result_summary?.sources_added || 0} new
                      {researchTask.result_summary?.entities_extracted && researchTask.result_summary.entities_extracted > 0 &&
                        ` • ${researchTask.result_summary.entities_extracted} entities extracted`}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {researchTask.result_summary?.report_preview && (
                      <button
                        onClick={() => setShowReport(!showReport)}
                        className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-green-700 bg-green-100 hover:bg-green-200 rounded-md transition-colors"
                      >
                        <FileText className="h-4 w-4 mr-1.5" />
                        {showReport ? 'Hide' : 'View'} Report
                        {showReport ? <ChevronUp className="h-4 w-4 ml-1" /> : <ChevronDown className="h-4 w-4 ml-1" />}
                      </button>
                    )}
                    <button
                      onClick={() => setResearchTask(null)}
                      className="text-green-600 hover:text-green-800 text-sm"
                    >
                      Dismiss
                    </button>
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
                    <FileText className="h-4 w-4" />
                    Research Report
                  </h4>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(researchTask.result_summary?.report_preview || '');
                      setReportCopied(true);
                      setTimeout(() => setReportCopied(false), 2000);
                    }}
                    className="inline-flex items-center px-2 py-1 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 dark:text-gray-300 dark:bg-gray-800 dark:hover:bg-gray-700 rounded transition-colors"
                  >
                    {reportCopied ? (
                      <>
                        <Check className="h-3 w-3 mr-1 text-green-600" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 mr-1" />
                        Copy Report
                      </>
                    )}
                  </button>
                </div>
                <div className="prose prose-sm dark:prose-invert max-w-none max-h-[70vh] sm:max-h-[500px] overflow-y-auto overflow-x-hidden p-3 sm:p-4 bg-gray-50 dark:bg-gray-800 rounded-lg break-words">
                  <ReactMarkdown
                    components={{
                      // Style links
                      a: ({ node, ...props }) => (
                        <a {...props} className="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer" />
                      ),
                      // Style headings
                      h1: ({ node, ...props }) => <h1 {...props} className="text-xl font-bold text-gray-900 dark:text-white mt-4 mb-2" />,
                      h2: ({ node, ...props }) => <h2 {...props} className="text-lg font-semibold text-gray-900 dark:text-white mt-3 mb-2" />,
                      h3: ({ node, ...props }) => <h3 {...props} className="text-base font-semibold text-gray-800 dark:text-gray-100 mt-2 mb-1" />,
                      // Style paragraphs
                      p: ({ node, ...props }) => <p {...props} className="text-gray-700 dark:text-gray-300 mb-3 leading-relaxed" />,
                      // Style lists
                      ul: ({ node, ...props }) => <ul {...props} className="list-disc list-inside mb-3 space-y-1" />,
                      ol: ({ node, ...props }) => <ol {...props} className="list-decimal list-inside mb-3 space-y-1" />,
                      li: ({ node, ...props }) => <li {...props} className="text-gray-700 dark:text-gray-300" />,
                      // Style code
                      code: ({ node, ...props }) => <code {...props} className="bg-gray-200 dark:bg-gray-700 px-1 py-0.5 rounded text-sm" />,
                      // Style blockquotes
                      blockquote: ({ node, ...props }) => (
                        <blockquote {...props} className="border-l-4 border-blue-500 pl-4 italic text-gray-600 dark:text-gray-400 my-3" />
                      ),
                    }}
                  >
                    {researchTask.result_summary.report_preview}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tabs - horizontally scrollable on mobile */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6 sm:mb-8 -mx-4 px-4 sm:mx-0 sm:px-0">
        <nav className="-mb-px flex space-x-4 sm:space-x-8 overflow-x-auto scrollbar-hide" role="tablist">
          {[
            { id: 'overview', name: 'Overview', icon: Eye },
            { id: 'sources', name: 'Sources', icon: FileText },
            { id: 'timeline', name: 'Timeline', icon: Calendar },
            { id: 'notes', name: 'Notes', icon: TrendingUp },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                role="tab"
                aria-selected={activeTab === tab.id}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center whitespace-nowrap transition-colors flex-shrink-0 ${
                  activeTab === tab.id
                    ? 'border-brand-blue text-brand-blue'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
                }`}
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
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-4 sm:space-y-6">
            {/* Description */}
            <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6">
              <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">Description</h2>
              <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words text-sm sm:text-base">{card.description}</p>
            </div>

            {/* Classification Section */}
            <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6">
              <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4">Classification</h2>
              <div className="space-y-3 sm:space-y-4">
                {/* Pillar & Goal */}
                <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4">
                  <div className="w-auto sm:w-24 text-xs sm:text-sm font-medium text-gray-500 shrink-0">Pillar</div>
                  <div className="flex-1">
                    <PillarBadge
                      pillarId={card.pillar_id}
                      goalId={card.goal_id}
                      showIcon
                      size="md"
                    />
                  </div>
                </div>

                {/* Goal */}
                {goal && (
                  <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4">
                    <div className="w-auto sm:w-24 text-xs sm:text-sm font-medium text-gray-500 shrink-0">Goal</div>
                    <div className="flex-1">
                      <span className="inline-flex items-center flex-wrap gap-2 text-sm text-gray-700 dark:text-gray-300">
                        <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                          {goal.code}
                        </span>
                        <span className="break-words">{goal.name}</span>
                      </span>
                    </div>
                  </div>
                )}

                {/* Anchor */}
                <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4">
                  <div className="w-auto sm:w-24 text-xs sm:text-sm font-medium text-gray-500 shrink-0">Anchor</div>
                  <div className="flex-1">
                    {card.anchor_id ? (
                      <AnchorBadge
                        anchor={card.anchor_id}
                        size="md"
                      />
                    ) : (
                      <span className="text-sm text-gray-400 italic">Not assigned</span>
                    )}
                  </div>
                </div>

                {/* Stage */}
                <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4">
                  <div className="w-auto sm:w-24 text-xs sm:text-sm font-medium text-gray-500 shrink-0">Stage</div>
                  <div className="flex-1 space-y-2">
                    {stageNumber ? (
                      <>
                        <StageBadge
                          stage={stageNumber}
                          variant="badge"
                          showName
                          size="md"
                        />
                        <div className="max-w-full sm:max-w-full sm:max-w-xs">
                          <StageProgress stage={stageNumber} showLabels />
                        </div>
                      </>
                    ) : (
                      <span className="text-sm text-gray-400 italic">Not assigned</span>
                    )}
                  </div>
                </div>

                {/* Horizon */}
                <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4">
                  <div className="w-auto sm:w-24 text-xs sm:text-sm font-medium text-gray-500 shrink-0">Horizon</div>
                  <div className="flex-1">
                    <HorizonBadge
                      horizon={card.horizon}
                      showIcon
                      size="md"
                    />
                  </div>
                </div>

                {/* Top 25 */}
                <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4">
                  <div className="w-auto sm:w-24 text-xs sm:text-sm font-medium text-gray-500 shrink-0">Top 25</div>
                  <div className="flex-1">
                    {card.top25_relevance && card.top25_relevance.length > 0 ? (
                      <Top25List
                        priorities={card.top25_relevance}
                        maxVisible={3}
                      />
                    ) : (
                      <span className="text-sm text-gray-400 italic">Not aligned with Top 25 priorities</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Research History */}
            {researchHistory.length > 0 && (
              <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6">
                <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4 flex items-center gap-2">
                  <Search className="h-5 w-5 text-brand-blue" />
                  Research History
                </h2>
                <div className="space-y-4">
                  {researchHistory.map((task) => (
                    <div
                      key={task.id}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
                    >
                      {/* Task header - always visible */}
                      <button
                        onClick={() => setExpandedReportId(expandedReportId === task.id ? null : task.id)}
                        className="w-full px-3 sm:px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors min-h-[48px] touch-manipulation"
                      >
                        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
                          <span className={cn(
                            'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                            task.task_type === 'deep_research'
                              ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
                              : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                          )}>
                            {task.task_type === 'deep_research' ? 'Deep Research' : 'Update'}
                          </span>
                          <span className="text-xs sm:text-sm text-gray-600 dark:text-gray-300">
                            {task.completed_at
                              ? new Date(task.completed_at).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric',
                                  year: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit'
                                })
                              : 'Unknown date'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between sm:justify-end gap-2 sm:gap-3">
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {task.result_summary?.sources_found || 0} found
                            {task.result_summary?.sources_added ? ` → ${task.result_summary.sources_added} added` : ''}
                          </span>
                          {expandedReportId === task.id ? (
                            <ChevronUp className="h-5 w-5 sm:h-4 sm:w-4 text-gray-400" />
                          ) : (
                            <ChevronDown className="h-5 w-5 sm:h-4 sm:w-4 text-gray-400" />
                          )}
                        </div>
                      </button>

                      {/* Expanded report content */}
                      {expandedReportId === task.id && task.result_summary?.report_preview && (
                        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
                          <div className="flex items-center justify-between mb-3">
                            <h4 className="font-medium text-gray-900 dark:text-white text-sm">Research Report</h4>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard.writeText(task.result_summary?.report_preview || '');
                              }}
                              className="inline-flex items-center px-2 py-1 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 dark:text-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 rounded transition-colors"
                            >
                              <Copy className="h-3 w-3 mr-1" />
                              Copy
                            </button>
                          </div>
                          <div className="prose prose-sm dark:prose-invert max-w-none max-h-[60vh] sm:max-h-[400px] overflow-y-auto overflow-x-hidden p-3 bg-gray-50 dark:bg-gray-800 rounded-lg break-words">
                            <ReactMarkdown
                              components={{
                                a: ({ node, ...props }) => (
                                  <a {...props} className="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer" />
                                ),
                                h1: ({ node, ...props }) => <h1 {...props} className="text-lg font-bold text-gray-900 dark:text-white mt-3 mb-2" />,
                                h2: ({ node, ...props }) => <h2 {...props} className="text-base font-semibold text-gray-900 dark:text-white mt-2 mb-1" />,
                                h3: ({ node, ...props }) => <h3 {...props} className="text-sm font-semibold text-gray-800 dark:text-gray-100 mt-2 mb-1" />,
                                p: ({ node, ...props }) => <p {...props} className="text-gray-700 dark:text-gray-300 mb-2 text-sm leading-relaxed" />,
                                ul: ({ node, ...props }) => <ul {...props} className="list-disc list-inside mb-2 space-y-0.5" />,
                                ol: ({ node, ...props }) => <ol {...props} className="list-decimal list-inside mb-2 space-y-0.5" />,
                                li: ({ node, ...props }) => <li {...props} className="text-gray-700 dark:text-gray-300 text-sm" />,
                                code: ({ node, ...props }) => <code {...props} className="bg-gray-200 dark:bg-gray-700 px-1 py-0.5 rounded text-xs" />,
                                blockquote: ({ node, ...props }) => (
                                  <blockquote {...props} className="border-l-4 border-blue-500 pl-3 italic text-gray-600 dark:text-gray-400 my-2 text-sm" />
                                ),
                              }}
                            >
                              {task.result_summary.report_preview}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Sidebar - Scores (stacks below main content on mobile) */}
          <div className="space-y-4 sm:space-y-6">
            {/* Impact Metrics */}
            <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Impact Metrics</h3>
                <Tooltip
                  content={
                    <div className="space-y-1">
                      <p className="font-medium">Score Interpretation</p>
                      <p className="text-xs text-gray-500">
                        Scores range from 0-100, with higher scores indicating stronger signals.
                      </p>
                    </div>
                  }
                  side="left"
                >
                  <button className="p-1 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100">
                    <Info className="h-4 w-4" />
                  </button>
                </Tooltip>
              </div>
              <div className="space-y-3">
                {[
                  { key: 'impact', score: card.impact_score },
                  { key: 'relevance', score: card.relevance_score },
                  { key: 'velocity', score: card.velocity_score },
                  { key: 'novelty', score: card.novelty_score },
                  { key: 'opportunity', score: card.opportunity_score },
                  { key: 'risk', score: card.risk_score },
                ].map((metric) => {
                  const definition = metricDefinitions[metric.key];
                  const colors = getScoreColorClasses(metric.score);

                  return (
                    <div key={metric.key} className="flex items-center justify-between">
                      <Tooltip
                        content={
                          <div className="max-w-[200px]">
                            <p className="font-medium mb-1">{definition.label}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">{definition.description}</p>
                          </div>
                        }
                        side="left"
                      >
                        <span className="text-sm text-gray-700 dark:text-gray-200 cursor-help border-b border-dotted border-gray-400 dark:border-gray-500">
                          {definition.label}
                        </span>
                      </Tooltip>
                      <span
                        className={cn(
                          'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border',
                          colors.bg,
                          colors.text,
                          colors.border
                        )}
                      >
                        {metric.score}/100
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Maturity Score */}
            <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6">
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Maturity</h3>
                <Tooltip
                  content={
                    <div className="space-y-2 max-w-full sm:max-w-xs">
                      <div className="font-semibold text-gray-900 dark:text-white">Maturity Score</div>
                      <p className="text-sm text-gray-600 dark:text-gray-300">
                        Indicates how developed and established this technology or trend is. Higher scores mean more mature,
                        proven solutions with established best practices and widespread adoption.
                      </p>
                      <div className="text-xs text-gray-500 dark:text-gray-400 pt-1 border-t border-gray-200 dark:border-gray-600">
                        <div className="flex justify-between"><span>0-30:</span><span>Early/Experimental</span></div>
                        <div className="flex justify-between"><span>31-60:</span><span>Emerging/Developing</span></div>
                        <div className="flex justify-between"><span>61-80:</span><span>Established</span></div>
                        <div className="flex justify-between"><span>81-100:</span><span>Mature/Mainstream</span></div>
                      </div>
                    </div>
                  }
                  side="top"
                  contentClassName="p-3"
                >
                  <Info className="h-4 w-4 text-gray-400 hover:text-brand-blue cursor-help transition-colors" />
                </Tooltip>
              </div>
              <div className="text-center">
                <Tooltip
                  content={
                    <span>
                      {card.maturity_score >= 81 ? 'Mature & Mainstream - Well-established with proven track record' :
                       card.maturity_score >= 61 ? 'Established - Gaining broad adoption and validation' :
                       card.maturity_score >= 31 ? 'Emerging - Actively developing with growing interest' :
                       'Early Stage - Experimental or recently introduced'}
                    </span>
                  }
                  side="bottom"
                >
                  <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-brand-light-blue dark:bg-slate-700 border-4 border-brand-blue/30 dark:border-brand-blue/50 mb-2 cursor-help">
                    <span className="text-2xl font-bold text-brand-dark-blue dark:text-white">{card.maturity_score}</span>
                  </div>
                </Tooltip>
                <p className="text-sm text-gray-500 dark:text-gray-400">Maturity Score</p>
              </div>
              {stageNumber && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <div className="text-center">
                    <StageBadge
                      stage={stageNumber}
                      variant="progress"
                      size="md"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Quick Stats */}
            <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Activity</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Sources</span>
                  <span className="font-medium text-gray-900 dark:text-white">{sources.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Timeline Events</span>
                  <span className="font-medium text-gray-900 dark:text-white">{timeline.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Notes</span>
                  <span className="font-medium text-gray-900 dark:text-white">{notes.length}</span>
                </div>

                {/* Timestamps Section */}
                <div className="pt-3 mt-3 border-t border-gray-200 dark:border-gray-700 space-y-2">
                  <Tooltip
                    content={<span>Created: {new Date(card.created_at).toLocaleString()}</span>}
                    side="left"
                  >
                    <div className="flex justify-between cursor-help">
                      <span className="text-gray-500 dark:text-gray-400">Created</span>
                      <span className="font-medium text-gray-900 dark:text-white">
                        {formatRelativeTime(card.created_at)}
                      </span>
                    </div>
                  </Tooltip>

                  <Tooltip
                    content={<span>Updated: {new Date(card.updated_at).toLocaleString()}</span>}
                    side="left"
                  >
                    <div className="flex justify-between cursor-help">
                      <span className="text-gray-500 dark:text-gray-400">Last Updated</span>
                      <span className="font-medium text-gray-900 dark:text-white">
                        {formatRelativeTime(card.updated_at)}
                      </span>
                    </div>
                  </Tooltip>

                  <Tooltip
                    content={
                      card.deep_research_at
                        ? <span>Deep Research: {new Date(card.deep_research_at).toLocaleString()}</span>
                        : <span>No deep research performed yet</span>
                    }
                    side="left"
                  >
                    <div className="flex justify-between cursor-help">
                      <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1">
                        <Search className="h-3 w-3" />
                        Deep Research
                      </span>
                      <span className={cn(
                        'font-medium',
                        card.deep_research_at
                          ? 'text-gray-900 dark:text-white'
                          : 'text-gray-400 dark:text-gray-500 italic'
                      )}>
                        {formatRelativeTime(card.deep_research_at)}
                      </span>
                    </div>
                  </Tooltip>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'sources' && (
        <div className="space-y-6">
          {sources.length === 0 ? (
            <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
              <FileText className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No sources yet</h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Sources will appear here as they are discovered and analyzed.
              </p>
            </div>
          ) : (
            sources.map((source) => {
              // Use relevance_to_card (1-5 scale) scaled to 100, or legacy relevance_score
              const relevanceScore = source.relevance_to_card
                ? Math.round(source.relevance_to_card * 20)  // 1-5 scale → 0-100
                : (source.relevance_score || 50);
              const sourceColors = getScoreColorClasses(relevanceScore);
              // Use ai_summary as primary, fallback to legacy summary
              const displaySummary = source.ai_summary || source.summary;
              // Use publication as publisher, fallback to legacy
              const displayPublisher = source.publication || source.publisher;
              // Format date - use ingested_at or published_date, handle nulls
              const displayDate = source.ingested_at || source.published_date;
              const formattedDate = displayDate && new Date(displayDate).getFullYear() > 1970
                ? new Date(displayDate).toLocaleDateString()
                : null;

              return (
                <div key={source.id} className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue">
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
                    <div className="flex-1 min-w-0">
                      {/* Title as link */}
                      {source.url ? (
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-base sm:text-lg font-medium text-brand-blue hover:text-brand-dark-blue hover:underline mb-2 block break-words"
                        >
                          {source.title}
                          <ExternalLink className="h-4 w-4 inline ml-2 opacity-50" />
                        </a>
                      ) : (
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">{source.title}</h3>
                      )}

                      {/* Summary/Synopsis */}
                      {displaySummary && (
                        <p className="text-gray-600 dark:text-gray-300 mb-3 line-clamp-3">{displaySummary}</p>
                      )}

                      {/* Key Excerpts */}
                      {source.key_excerpts && source.key_excerpts.length > 0 && (
                        <div className="mb-3 pl-3 border-l-2 border-gray-200 dark:border-gray-600">
                          <p className="text-sm text-gray-500 dark:text-gray-400 italic line-clamp-2">
                            "{source.key_excerpts[0]}"
                          </p>
                        </div>
                      )}

                      {/* Metadata row */}
                      <div className="flex items-center flex-wrap gap-2 text-sm text-gray-500 dark:text-gray-400">
                        {displayPublisher && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs">
                            {displayPublisher}
                          </span>
                        )}
                        {source.api_source && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 text-xs">
                            via {source.api_source === 'gpt_researcher' ? 'GPT Researcher' : source.api_source}
                          </span>
                        )}
                        {formattedDate && (
                          <span className="text-gray-400 text-xs">
                            {formattedDate}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Relevance score badge */}
                    <div className="sm:ml-4 flex-shrink-0 self-start sm:self-auto">
                      <div className="flex flex-row sm:flex-col items-center sm:items-end gap-2 sm:gap-1">
                        <span
                          className={cn(
                            'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border',
                            sourceColors.bg,
                            sourceColors.text,
                            sourceColors.border
                          )}
                        >
                          {relevanceScore}%
                        </span>
                        <span className="text-[10px] text-gray-400">relevance</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {activeTab === 'timeline' && (
        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow">
          {timeline.length === 0 ? (
            <div className="text-center py-12">
              <Calendar className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No timeline events yet</h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Timeline events will appear here as the card evolves.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {timeline.map((event) => {
                const isDeepResearch = event.event_type === 'deep_research';
                const hasDetailedReport = isDeepResearch && event.metadata?.detailed_report;
                const isExpanded = expandedTimelineId === event.id;

                return (
                  <div key={event.id} className={cn(
                    "p-4 sm:p-6",
                    isDeepResearch && "bg-gradient-to-r from-brand-light-blue/10 to-transparent"
                  )}>
                    <div className="flex items-start">
                      <div className="flex-shrink-0">
                        {isDeepResearch ? (
                          <div className="p-2 rounded-full bg-brand-blue/10">
                            <Search className="h-5 w-5 text-brand-blue" />
                          </div>
                        ) : (
                          <Calendar className="h-5 w-5 text-gray-400" />
                        )}
                      </div>
                      <div className="ml-3 flex-1 min-w-0">
                        <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2">
                          <h3 className={cn(
                            "font-medium text-gray-900 dark:text-white break-words",
                            isDeepResearch ? "text-base" : "text-sm"
                          )}>{event.title}</h3>
                          {isDeepResearch && (
                            <span className="inline-flex items-center px-2 sm:px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gradient-to-r from-brand-blue to-extended-purple text-white shadow-sm w-fit">
                              Strategic Intelligence Report
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">{event.description}</p>

                        {/* Metadata stats for deep research - enhanced display */}
                        {isDeepResearch && event.metadata && (
                          <div className="flex flex-wrap items-center gap-4 mt-3">
                            {event.metadata.sources_found !== undefined && (
                              <div className="flex items-center gap-1.5 text-xs">
                                <div className="w-2 h-2 rounded-full bg-brand-green"></div>
                                <span className="text-gray-600 dark:text-gray-300">
                                  <span className="font-semibold text-gray-900 dark:text-white">{event.metadata.sources_found}</span> sources found
                                </span>
                              </div>
                            )}
                            {event.metadata.sources_added !== undefined && (
                              <div className="flex items-center gap-1.5 text-xs">
                                <div className="w-2 h-2 rounded-full bg-brand-blue"></div>
                                <span className="text-gray-600 dark:text-gray-300">
                                  <span className="font-semibold text-gray-900 dark:text-white">{event.metadata.sources_added}</span> added
                                </span>
                              </div>
                            )}
                            {event.metadata.entities_extracted !== undefined && (
                              <div className="flex items-center gap-1.5 text-xs">
                                <div className="w-2 h-2 rounded-full bg-extended-purple"></div>
                                <span className="text-gray-600 dark:text-gray-300">
                                  <span className="font-semibold text-gray-900 dark:text-white">{event.metadata.entities_extracted}</span> entities
                                </span>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Detailed Report Toggle - enhanced */}
                        {hasDetailedReport && (
                          <div className="mt-4">
                            <button
                              onClick={() => setExpandedTimelineId(isExpanded ? null : event.id)}
                              className={cn(
                                "inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                                isExpanded
                                  ? "bg-brand-blue text-white shadow-md hover:bg-brand-dark-blue"
                                  : "bg-brand-light-blue text-brand-blue hover:bg-brand-blue hover:text-white"
                              )}
                            >
                              <FileText className="h-4 w-4" />
                              {isExpanded ? 'Collapse Strategic Report' : 'View Strategic Intelligence Report'}
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </button>

                            {/* Expanded Report Content - enhanced styling */}
                            {isExpanded && (
                              <div className="mt-4 rounded-xl border-2 border-brand-blue/20 overflow-hidden">
                                {/* Report Header */}
                                <div className="bg-gradient-to-r from-brand-blue to-extended-purple p-3 sm:p-4">
                                  <div className="flex items-center gap-2 sm:gap-3 text-white">
                                    <FileText className="h-5 w-5 sm:h-6 sm:w-6 flex-shrink-0" />
                                    <div className="min-w-0">
                                      <h4 className="font-bold text-base sm:text-lg">Strategic Intelligence Report</h4>
                                      <p className="text-white/80 text-xs sm:text-sm">Generated {new Date(event.created_at).toLocaleDateString()}</p>
                                    </div>
                                  </div>
                                </div>

                                {/* Report Content */}
                                <div className="p-4 sm:p-6 bg-white dark:bg-[#1d2156] max-h-[70vh] sm:max-h-[80vh] overflow-y-auto overflow-x-hidden">
                                  <div className="prose prose-sm dark:prose-invert max-w-none break-words
                                    prose-headings:text-brand-dark-blue dark:prose-headings:text-white
                                    prose-h2:text-base prose-h2:sm:text-lg prose-h2:font-bold prose-h2:border-b prose-h2:border-gray-200 dark:prose-h2:border-gray-700 prose-h2:pb-2 prose-h2:mb-4 prose-h2:mt-6
                                    prose-h3:text-sm prose-h3:sm:text-base prose-h3:font-semibold
                                    prose-strong:text-brand-dark-blue dark:prose-strong:text-brand-light-blue
                                    prose-ul:my-2 prose-li:my-0.5
                                    prose-p:text-gray-700 dark:prose-p:text-gray-300
                                    prose-a:text-brand-blue hover:prose-a:text-brand-dark-blue
                                  ">
                                    <ReactMarkdown>
                                      {event.metadata!.detailed_report!}
                                    </ReactMarkdown>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        )}

                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                          {new Date(event.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {activeTab === 'notes' && (
        <div className="space-y-4 sm:space-y-6">
          {/* Add Note */}
          <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Add Note</h3>
            <div className="space-y-4">
              <textarea
                rows={3}
                className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-white rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                placeholder="Add your thoughts and analysis..."
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
              />
              <button
                onClick={addNote}
                disabled={!newNote.trim()}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Add Note
              </button>
            </div>
          </div>

          {/* Notes List */}
          <div className="space-y-4">
            {notes.length === 0 ? (
              <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
                <TrendingUp className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No notes yet</h3>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Add your first note to start tracking your insights.
                </p>
              </div>
            ) : (
              notes.map((note) => (
                <div key={note.id} className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue">
                  <p className="text-gray-700 dark:text-gray-300 mb-3 break-words">{note.content}</p>
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-sm text-gray-500 dark:text-gray-400">
                    <span className="text-xs sm:text-sm">{new Date(note.created_at).toLocaleString()}</span>
                    {note.is_private && (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200">
                        Private
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Close export dropdown when clicking outside */}
      {showExportDropdown && (
        <div
          className="fixed inset-0 z-10"
          onClick={() => setShowExportDropdown(false)}
        />
      )}
    </div>
  );
};

export default CardDetail;
