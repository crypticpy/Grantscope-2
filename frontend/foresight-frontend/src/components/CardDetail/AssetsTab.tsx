/**
 * AssetsTab Component
 *
 * Displays a history of all generated assets for a card including:
 * - Executive briefs (all versions)
 * - Deep research reports
 * - PDF exports
 * - PowerPoint exports
 *
 * Features:
 * - Chronological list with timestamps
 * - Download counts (when available)
 * - Re-download functionality
 * - Asset type filtering
 * - Dark mode support
 */

import React, { useState, useMemo, useCallback } from 'react';
import {
  FileText,
  Presentation,
  Download,
  Calendar,
  Clock,
  Search,
  Filter,
  ChevronDown,
  ExternalLink,
  Sparkles,
  FileSearch,
  History,
  Loader2,
} from 'lucide-react';
import { cn } from '../../lib/utils';

// =============================================================================
// Types
// =============================================================================

export type AssetType = 'brief' | 'research' | 'pdf_export' | 'pptx_export';

export interface Asset {
  /** Unique identifier */
  id: string;
  /** Type of asset */
  type: AssetType;
  /** Display title */
  title: string;
  /** When the asset was created */
  created_at: string;
  /** Version number (for briefs) */
  version?: number;
  /** File size in bytes */
  file_size?: number;
  /** Number of times downloaded */
  download_count?: number;
  /** Whether AI was used to generate this */
  ai_generated?: boolean;
  /** AI model used (if applicable) */
  ai_model?: string;
  /** Status of the asset */
  status?: 'ready' | 'generating' | 'failed';
  /** URL to download (if available) */
  download_url?: string;
  /** Additional metadata */
  metadata?: Record<string, unknown>;
}

export interface AssetsTabProps {
  /** Card ID */
  cardId: string;
  /** Workstream ID (if in workstream context) */
  workstreamId?: string;
  /** List of assets */
  assets: Asset[];
  /** Whether assets are loading */
  isLoading?: boolean;
  /** Error message if load failed */
  error?: string | null;
  /** Callback to download an asset */
  onDownload?: (asset: Asset) => void;
  /** Callback to regenerate an asset */
  onRegenerate?: (assetType: AssetType) => void;
  /** Callback to view asset details */
  onViewDetails?: (asset: Asset) => void;
  /** Callback to refresh assets list */
  onRefresh?: () => void;
}

// =============================================================================
// Constants
// =============================================================================

// City of Austin brand colors
const COA_COLORS = {
  logoBlue: '#44499C',
  logoGreen: '#009F4D',
  fadedWhite: '#f7f6f5',
  lightBlue: '#dcf2fd',
  lightGreen: '#dff0e3',
  darkGray: '#636262',
};

const ASSET_TYPE_CONFIG: Record<
  AssetType,
  {
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    color: string;
    bgColor: string;
  }
> = {
  brief: {
    icon: FileText,
    label: 'Executive Brief',
    color: COA_COLORS.logoBlue,
    bgColor: COA_COLORS.lightBlue,
  },
  research: {
    icon: FileSearch,
    label: 'Deep Research',
    color: COA_COLORS.logoGreen,
    bgColor: COA_COLORS.lightGreen,
  },
  pdf_export: {
    icon: FileText,
    label: 'PDF Export',
    color: '#DC2626',
    bgColor: '#FEE2E2',
  },
  pptx_export: {
    icon: Presentation,
    label: 'PowerPoint',
    color: '#EA580C',
    bgColor: '#FFEDD5',
  },
};

// =============================================================================
// Helper Functions
// =============================================================================

function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return 'Unknown';
  }
}

function formatTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function _getRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDate(dateString);
  } catch {
    return '';
  }
}

// =============================================================================
// Subcomponents
// =============================================================================

interface AssetCardProps {
  asset: Asset;
  onDownload?: (asset: Asset) => void;
  onViewDetails?: (asset: Asset) => void;
}

const AssetCard: React.FC<AssetCardProps> = ({
  asset,
  onDownload,
  onViewDetails,
}) => {
  const config = ASSET_TYPE_CONFIG[asset.type];
  const Icon = config.icon;
  const isGenerating = asset.status === 'generating';

  return (
    <div
      className={cn(
        'group relative p-4 rounded-lg border transition-all duration-200',
        'bg-white dark:bg-dark-surface',
        'border-gray-200 dark:border-gray-700',
        'hover:border-gray-300 dark:hover:border-gray-600',
        'hover:shadow-md'
      )}
    >
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div
          className="flex-shrink-0 p-2.5 rounded-lg"
          style={{ backgroundColor: config.bgColor }}
        >
          {isGenerating ? (
            <Loader2
              className="h-5 w-5 animate-spin"
              style={{ color: config.color }}
            />
          ) : (
            <Icon className="h-5 w-5" style={{ color: config.color }} />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h4 className="font-medium text-gray-900 dark:text-white truncate">
                {asset.title}
              </h4>
              <div className="flex items-center gap-2 mt-1">
                <span
                  className="text-xs font-medium px-2 py-0.5 rounded-full"
                  style={{
                    backgroundColor: config.bgColor,
                    color: config.color,
                  }}
                >
                  {config.label}
                </span>
                {asset.version && (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    v{asset.version}
                  </span>
                )}
                {asset.ai_generated && (
                  <span className="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                    <Sparkles className="h-3 w-3" />
                    AI
                  </span>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {onViewDetails && (
                <button
                  onClick={() => onViewDetails(asset)}
                  className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  title="View details"
                >
                  <ExternalLink className="h-4 w-4 text-gray-500" />
                </button>
              )}
              {onDownload && asset.status === 'ready' && (
                <button
                  onClick={() => onDownload(asset)}
                  className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  title="Download"
                >
                  <Download className="h-4 w-4 text-gray-500" />
                </button>
              )}
            </div>
          </div>

          {/* Metadata */}
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500 dark:text-gray-400">
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {formatDate(asset.created_at)}
            </span>
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatTime(asset.created_at)}
            </span>
            {asset.file_size && (
              <span>{formatFileSize(asset.file_size)}</span>
            )}
            {asset.download_count !== undefined && asset.download_count > 0 && (
              <span className="inline-flex items-center gap-1">
                <Download className="h-3 w-3" />
                {asset.download_count}
              </span>
            )}
          </div>

          {/* Status indicator */}
          {isGenerating && (
            <div className="mt-2 text-xs text-amber-600 dark:text-amber-400">
              Generating...
            </div>
          )}
          {asset.status === 'failed' && (
            <div className="mt-2 text-xs text-red-600 dark:text-red-400">
              Generation failed
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// Main Component
// =============================================================================

export const AssetsTab: React.FC<AssetsTabProps> = ({
  cardId: _cardId,
  workstreamId: _workstreamId,
  assets,
  isLoading = false,
  error = null,
  onDownload,
  onRegenerate: _onRegenerate,
  onViewDetails,
  onRefresh,
}) => {
  const [filterType, setFilterType] = useState<AssetType | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  // Filter assets
  const filteredAssets = useMemo(() => {
    let result = [...assets];

    // Type filter
    if (filterType !== 'all') {
      result = result.filter((a) => a.type === filterType);
    }

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (a) =>
          a.title.toLowerCase().includes(query) ||
          a.type.toLowerCase().includes(query)
      );
    }

    // Sort by date (newest first)
    result.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    return result;
  }, [assets, filterType, searchQuery]);

  // Group assets by date
  const groupedAssets = useMemo(() => {
    const groups: Record<string, Asset[]> = {};

    filteredAssets.forEach((asset) => {
      const date = formatDate(asset.created_at);
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(asset);
    });

    return groups;
  }, [filteredAssets]);

  const handleFilterChange = useCallback((type: AssetType | 'all') => {
    setFilterType(type);
    setShowFilters(false);
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400 mb-4" />
        <p className="text-gray-500 dark:text-gray-400">Loading assets...</p>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="text-red-500 mb-4">
          <FileText className="h-12 w-12" />
        </div>
        <p className="text-gray-900 dark:text-white font-medium mb-2">
          Failed to load assets
        </p>
        <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">{error}</p>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
          >
            Try again
          </button>
        )}
      </div>
    );
  }

  // Empty state
  if (assets.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div
          className="p-4 rounded-full mb-4"
          style={{ backgroundColor: COA_COLORS.lightBlue }}
        >
          <History className="h-8 w-8" style={{ color: COA_COLORS.logoBlue }} />
        </div>
        <p className="text-gray-900 dark:text-white font-medium mb-2">
          No assets yet
        </p>
        <p className="text-gray-500 dark:text-gray-400 text-sm text-center max-w-sm">
          Generated content like executive briefs, research reports, and exports
          will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with search and filters */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search assets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={cn(
              'w-full pl-9 pr-4 py-2 text-sm rounded-lg',
              'border border-gray-200 dark:border-gray-700',
              'bg-white dark:bg-dark-surface',
              'text-gray-900 dark:text-white',
              'placeholder-gray-500 dark:placeholder-gray-400',
              'focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            )}
          />
        </div>

        {/* Filter dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'inline-flex items-center gap-2 px-3 py-2 text-sm rounded-lg',
              'border border-gray-200 dark:border-gray-700',
              'bg-white dark:bg-dark-surface',
              'text-gray-700 dark:text-gray-300',
              'hover:bg-gray-50 dark:hover:bg-gray-700',
              'transition-colors'
            )}
          >
            <Filter className="h-4 w-4" />
            {filterType === 'all' ? 'All Types' : ASSET_TYPE_CONFIG[filterType].label}
            <ChevronDown
              className={cn(
                'h-4 w-4 transition-transform',
                showFilters && 'rotate-180'
              )}
            />
          </button>

          {showFilters && (
            <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-dark-surface rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-10">
              <button
                onClick={() => handleFilterChange('all')}
                className={cn(
                  'w-full px-4 py-2 text-sm text-left',
                  'hover:bg-gray-100 dark:hover:bg-gray-700',
                  filterType === 'all' && 'bg-gray-100 dark:bg-gray-700'
                )}
              >
                All Types
              </button>
              {Object.entries(ASSET_TYPE_CONFIG).map(([type, config]) => (
                <button
                  key={type}
                  onClick={() => handleFilterChange(type as AssetType)}
                  className={cn(
                    'w-full px-4 py-2 text-sm text-left flex items-center gap-2',
                    'hover:bg-gray-100 dark:hover:bg-gray-700',
                    filterType === type && 'bg-gray-100 dark:bg-gray-700'
                  )}
                >
                  <config.icon className="h-4 w-4" style={{ color: config.color }} />
                  {config.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Refresh button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            className={cn(
              'p-2 rounded-lg',
              'border border-gray-200 dark:border-gray-700',
              'bg-white dark:bg-dark-surface',
              'text-gray-500 dark:text-gray-400',
              'hover:bg-gray-50 dark:hover:bg-gray-700',
              'transition-colors'
            )}
            title="Refresh"
          >
            <History className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Results count */}
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {filteredAssets.length} asset{filteredAssets.length !== 1 ? 's' : ''}
        {filterType !== 'all' && ` • Filtered by ${ASSET_TYPE_CONFIG[filterType].label}`}
      </p>

      {/* Asset list grouped by date */}
      {Object.entries(groupedAssets).map(([date, dateAssets]) => (
        <div key={date} className="space-y-2">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 sticky top-0 bg-white dark:bg-gray-900 py-1">
            {date}
          </h3>
          <div className="space-y-2">
            {dateAssets.map((asset) => (
              <AssetCard
                key={asset.id}
                asset={asset}
                onDownload={onDownload}
                onViewDetails={onViewDetails}
              />
            ))}
          </div>
        </div>
      ))}

      {/* No results after filtering */}
      {filteredAssets.length === 0 && assets.length > 0 && (
        <div className="text-center py-8">
          <Search className="h-8 w-8 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 dark:text-gray-400">
            No assets match your search
          </p>
        </div>
      )}
    </div>
  );
};

export default AssetsTab;
