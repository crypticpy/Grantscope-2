/**
 * BulkExportModal Component
 *
 * A modal that displays pre-export validation for bulk brief exports.
 * Shows card readiness status and allows users to configure export options.
 *
 * Features:
 * - Shows all cards in Brief column with their brief status
 * - Visual indication of ready vs. not-ready cards
 * - Format selection (PPTX via Gamma or PDF)
 * - Drag-to-reorder card sequence (uses Kanban order by default)
 * - City of Austin branded styling
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  X,
  Download,
  Loader2,
  CheckCircle,
  AlertCircle,
  Presentation,
  FileText,
  Sparkles,
  GripVertical,
  ArrowUpDown,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '../lib/utils';
import type {
  BulkBriefStatusResponse,
  BulkBriefCardStatus,
} from '../lib/workstream-api';

// =============================================================================
// Types
// =============================================================================

export interface BulkExportModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Workstream name for display */
  workstreamName: string;
  /** Status data from API */
  statusData: BulkBriefStatusResponse | null;
  /** Whether status is loading */
  isLoading: boolean;
  /** Error message if status fetch failed */
  error?: string | null;
  /** Callback when user confirms export */
  onExport: (format: 'pptx' | 'pdf', cardOrder: string[]) => void;
  /** Whether export is in progress */
  isExporting?: boolean;
}

// =============================================================================
// Constants
// =============================================================================

const COA_COLORS = {
  logoBlue: '#44499C',
  logoGreen: '#009F4D',
  fadedWhite: '#f7f6f5',
  darkBlue: '#22254E',
  lightBlue: '#dcf2fd',
  lightGreen: '#dff0e3',
  red: '#F83125',
  darkGray: '#636262',
  amber: '#F59E0B',
};

// =============================================================================
// Component
// =============================================================================

export const BulkExportModal: React.FC<BulkExportModalProps> = ({
  isOpen,
  onClose,
  workstreamName,
  statusData,
  isLoading,
  error,
  onExport,
  isExporting = false,
}) => {
  const [selectedFormat, setSelectedFormat] = useState<'pptx' | 'pdf'>('pptx');
  const [cardOrder, setCardOrder] = useState<string[]>([]);

  // Initialize card order from status data
  useEffect(() => {
    if (statusData?.card_statuses) {
      const readyCards = statusData.card_statuses
        .filter((c) => c.has_brief && c.brief_status === 'completed')
        .sort((a, b) => a.position - b.position)
        .map((c) => c.card_id);
      setCardOrder(readyCards);
    }
  }, [statusData]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isExporting) {
        onClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, isExporting, onClose]);

  // Prevent background scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const handleExport = useCallback(() => {
    if (cardOrder.length > 0) {
      onExport(selectedFormat, cardOrder);
    }
  }, [selectedFormat, cardOrder, onExport]);

  if (!isOpen) return null;

  const readyCount = statusData?.cards_ready ?? 0;
  const totalCount = statusData?.total_cards ?? 0;
  const allReady = readyCount === totalCount && totalCount > 0;
  const canExport = cardOrder.length > 0 && !isExporting;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bulk-export-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={!isExporting ? onClose : undefined}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        className={cn(
          'relative w-full max-w-2xl mx-4',
          'bg-white dark:bg-[#1a1d40] rounded-xl shadow-2xl',
          'border border-gray-200 dark:border-gray-800',
          'transform transition-all duration-200',
          'max-h-[90vh] overflow-hidden flex flex-col'
        )}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b border-gray-200 dark:border-gray-800"
          style={{ backgroundColor: COA_COLORS.fadedWhite }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="p-2 rounded-lg"
                style={{ backgroundColor: COA_COLORS.lightBlue }}
              >
                <Presentation
                  className="h-5 w-5"
                  style={{ color: COA_COLORS.logoBlue }}
                />
              </div>
              <div>
                <h2
                  id="bulk-export-title"
                  className="text-lg font-semibold"
                  style={{ color: COA_COLORS.darkBlue }}
                >
                  Export Portfolio
                </h2>
                <p className="text-sm text-gray-500">{workstreamName}</p>
              </div>
            </div>
            {!isExporting && (
              <button
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                aria-label="Close modal"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2
                className="h-8 w-8 animate-spin mb-4"
                style={{ color: COA_COLORS.logoBlue }}
              />
              <p className="text-gray-500">Loading brief status...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <AlertCircle
                className="h-12 w-12 mb-4"
                style={{ color: COA_COLORS.red }}
              />
              <p className="text-gray-700 dark:text-gray-300 font-medium mb-2">
                Failed to load briefs
              </p>
              <p className="text-gray-500 text-sm">{error}</p>
            </div>
          ) : (
            <>
              {/* Status Summary */}
              <div
                className={cn(
                  'flex items-center gap-3 p-4 rounded-lg mb-6',
                  allReady
                    ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                    : 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800'
                )}
              >
                {allReady ? (
                  <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0" />
                )}
                <div>
                  <p
                    className={cn(
                      'font-medium',
                      allReady
                        ? 'text-green-700 dark:text-green-300'
                        : 'text-amber-700 dark:text-amber-300'
                    )}
                  >
                    {readyCount} of {totalCount} briefs ready
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {allReady
                      ? 'All briefs are complete and ready for export.'
                      : 'Only cards with completed briefs will be included.'}
                  </p>
                </div>
              </div>

              {/* Card List */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Cards to Include
                  </h3>
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <ArrowUpDown className="h-3.5 w-3.5" />
                    <span>Kanban order</span>
                  </div>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {(statusData?.card_statuses ?? [])
                    .slice()
                    .sort((a, b) => a.position - b.position)
                    .map((card, index) => (
                      <CardStatusRow
                        key={card.card_id}
                        card={card}
                        index={index + 1}
                      />
                    ))}
                </div>
              </div>

              {/* Format Selection */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Export Format
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <FormatOption
                    format="pptx"
                    title="PowerPoint"
                    description="AI-generated slides via Gamma.app"
                    icon={Presentation}
                    isSelected={selectedFormat === 'pptx'}
                    onSelect={() => setSelectedFormat('pptx')}
                    isPowered
                  />
                  <FormatOption
                    format="pdf"
                    title="PDF Document"
                    description="Detailed written report"
                    icon={FileText}
                    isSelected={selectedFormat === 'pdf'}
                    onSelect={() => setSelectedFormat('pdf')}
                  />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500">
              {cardOrder.length > 0 && (
                <span>
                  {cardOrder.length} card{cardOrder.length !== 1 ? 's' : ''} will
                  be exported
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={onClose}
                disabled={isExporting}
                className={cn(
                  'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                  'border border-gray-300 dark:border-gray-600',
                  'text-gray-700 dark:text-gray-300',
                  'hover:bg-gray-100 dark:hover:bg-gray-700',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                Cancel
              </button>
              <button
                onClick={handleExport}
                disabled={!canExport}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                  'text-white',
                  canExport
                    ? 'hover:opacity-90'
                    : 'opacity-50 cursor-not-allowed'
                )}
                style={{
                  backgroundColor: canExport
                    ? COA_COLORS.logoBlue
                    : COA_COLORS.darkGray,
                }}
              >
                {isExporting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Exporting...</span>
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    <span>Export Portfolio</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// Sub-components
// =============================================================================

interface CardStatusRowProps {
  card: BulkBriefCardStatus;
  index: number;
}

function CardStatusRow({ card, index }: CardStatusRowProps) {
  const isReady = card.has_brief && card.brief_status === 'completed';

  return (
    <div
      className={cn(
        'flex items-center gap-3 px-3 py-2.5 rounded-lg',
        'border',
        isReady
          ? 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700'
          : 'bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700 opacity-60'
      )}
    >
      <div className="flex items-center gap-2 flex-shrink-0">
        <GripVertical className="h-4 w-4 text-gray-300" />
        <span className="text-xs font-medium text-gray-400 w-4">{index}</span>
      </div>

      <div className="flex-1 min-w-0">
        <p
          className={cn(
            'text-sm font-medium truncate',
            isReady
              ? 'text-gray-900 dark:text-white'
              : 'text-gray-500 dark:text-gray-400'
          )}
        >
          {card.card_name}
        </p>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        {isReady ? (
          <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
            <CheckCircle className="h-3.5 w-3.5" />
            Ready
          </span>
        ) : card.has_brief ? (
          <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {card.brief_status || 'Generating'}
          </span>
        ) : (
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <AlertCircle className="h-3.5 w-3.5" />
            No brief
          </span>
        )}
      </div>
    </div>
  );
}

interface FormatOptionProps {
  format: 'pptx' | 'pdf';
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  isSelected: boolean;
  onSelect: () => void;
  isPowered?: boolean;
}

function FormatOption({
  title,
  description,
  icon: Icon,
  isSelected,
  onSelect,
  isPowered = false,
}: FormatOptionProps) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'flex flex-col items-start p-4 rounded-lg border-2 transition-all text-left',
        isSelected
          ? 'border-[#44499C] bg-[#44499C]/5'
          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon
          className={cn(
            'h-5 w-5',
            isSelected ? 'text-[#44499C]' : 'text-gray-400'
          )}
        />
        <span
          className={cn(
            'font-medium',
            isSelected
              ? 'text-[#44499C] dark:text-[#7c7fd4]'
              : 'text-gray-700 dark:text-gray-300'
          )}
        >
          {title}
        </span>
        {isPowered && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300">
            <Sparkles className="h-2.5 w-2.5" />
            AI
          </span>
        )}
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
    </button>
  );
}

export default BulkExportModal;
