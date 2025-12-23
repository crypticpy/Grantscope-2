import React, { useState, useEffect } from 'react';
import { Plus, FolderOpen, Pencil, Trash2, AlertTriangle } from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { WorkstreamForm, type Workstream } from '../components/WorkstreamForm';
import { PillarBadgeGroup } from '../components/PillarBadge';
import { getGoalByCode } from '../data/taxonomy';

// ============================================================================
// Delete Confirmation Modal
// ============================================================================

interface DeleteConfirmModalProps {
  workstream: Workstream;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}

function DeleteConfirmModal({
  workstream,
  onConfirm,
  onCancel,
  isDeleting,
}: DeleteConfirmModalProps) {
  return (
    <div className="fixed inset-0 bg-gray-600/50 dark:bg-black/60 flex items-center justify-center p-4 z-50">
      <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow-xl max-w-md w-full p-6">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 w-10 h-10 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
            <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">
              Delete Workstream
            </h3>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
              Are you sure you want to delete{' '}
              <span className="font-semibold">"{workstream.name}"</span>? This
              action cannot be undone.
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-[#3d4176] border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 transition-colors"
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Workstream Form Modal
// ============================================================================

interface FormModalProps {
  workstream?: Workstream;
  onSuccess: () => void;
  onCancel: () => void;
}

function FormModal({ workstream, onSuccess, onCancel }: FormModalProps) {
  return (
    <div className="fixed inset-0 bg-gray-600/50 dark:bg-black/60 flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto my-8">
        <div className="sticky top-0 bg-white dark:bg-[#2d3166] border-b border-gray-200 dark:border-gray-700 px-6 py-4 rounded-t-lg">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white">
            {workstream ? 'Edit Workstream' : 'Create New Workstream'}
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {workstream
              ? 'Update the filters and settings for this workstream.'
              : 'Define filters to curate a personalized intelligence feed.'}
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
// Workstream Card
// ============================================================================

interface WorkstreamCardProps {
  workstream: Workstream;
  onEdit: () => void;
  onDelete: () => void;
}

function WorkstreamCard({ workstream, onEdit, onDelete }: WorkstreamCardProps) {
  // Format stage IDs for display
  const formatStages = (stageIds: string[]): string => {
    if (stageIds.length === 0) return '';
    const nums = stageIds.map(Number).sort((a, b) => a - b);
    // Check if consecutive range
    if (
      nums.length > 2 &&
      nums[nums.length - 1] - nums[0] === nums.length - 1
    ) {
      return `${nums[0]}-${nums[nums.length - 1]}`;
    }
    return nums.join(', ');
  };

  return (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white truncate">
            {workstream.name}
          </h3>
          {workstream.description && (
            <p className="text-gray-600 dark:text-gray-300 text-sm mt-1 line-clamp-2">
              {workstream.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 ml-4">
          {workstream.is_active ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400">
              Active
            </span>
          ) : (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300">
              Inactive
            </span>
          )}
        </div>
      </div>

      {/* Filter Summary */}
      <div className="space-y-3 text-sm">
        {/* Pillars */}
        {workstream.pillar_ids.length > 0 && (
          <div>
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1.5">
              Pillars
            </span>
            <PillarBadgeGroup
              pillarIds={workstream.pillar_ids}
              size="sm"
              maxVisible={6}
            />
          </div>
        )}

        {/* Goals */}
        {workstream.goal_ids.length > 0 && (
          <div>
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1">
              Goals
            </span>
            <div className="text-gray-600 dark:text-gray-300 text-sm">
              {workstream.goal_ids.length <= 3
                ? workstream.goal_ids
                    .map((id) => {
                      const goal = getGoalByCode(id);
                      return goal ? `${goal.code}` : id;
                    })
                    .join(', ')
                : `${workstream.goal_ids.length} goals selected`}
            </div>
          </div>
        )}

        {/* Stages and Horizon */}
        <div className="flex flex-wrap gap-4">
          {workstream.stage_ids.length > 0 && (
            <div>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1">
                Stages
              </span>
              <span className="text-gray-600 dark:text-gray-300">
                {formatStages(workstream.stage_ids)}
              </span>
            </div>
          )}

          {workstream.horizon && workstream.horizon !== 'ALL' && (
            <div>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1">
                Horizon
              </span>
              <span className="text-gray-600 dark:text-gray-300">{workstream.horizon}</span>
            </div>
          )}
        </div>

        {/* Keywords */}
        {workstream.keywords.length > 0 && (
          <div>
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1.5">
              Keywords
            </span>
            <div className="flex flex-wrap gap-1.5">
              {workstream.keywords.slice(0, 5).map((keyword) => (
                <span
                  key={keyword}
                  className="inline-flex px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs"
                >
                  {keyword}
                </span>
              ))}
              {workstream.keywords.length > 5 && (
                <span className="inline-flex px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 text-xs">
                  +{workstream.keywords.length - 5} more
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Created {new Date(workstream.created_at).toLocaleDateString()}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={onEdit}
              className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-[#3d4176] border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-brand-blue transition-colors"
              aria-label={`Edit ${workstream.name}`}
            >
              <Pencil className="h-3.5 w-3.5 mr-1" />
              Edit
            </button>
            <button
              onClick={onDelete}
              className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-red-700 dark:text-red-400 bg-white dark:bg-[#3d4176] border border-red-300 dark:border-red-500/50 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-red-500 transition-colors"
              aria-label={`Delete ${workstream.name}`}
            >
              <Trash2 className="h-3.5 w-3.5 mr-1" />
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

const Workstreams: React.FC = () => {
  const { user } = useAuthContext();
  const [workstreams, setWorkstreams] = useState<Workstream[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal states
  const [showForm, setShowForm] = useState(false);
  const [editingWorkstream, setEditingWorkstream] = useState<
    Workstream | undefined
  >(undefined);
  const [deletingWorkstream, setDeletingWorkstream] = useState<
    Workstream | undefined
  >(undefined);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    loadWorkstreams();
  }, []);

  const loadWorkstreams = async () => {
    try {
      const { data } = await supabase
        .from('workstreams')
        .select('*')
        .eq('user_id', user?.id)
        .order('created_at', { ascending: false });

      setWorkstreams(data || []);
    } catch (error) {
      console.error('Error loading workstreams:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFormSuccess = () => {
    setShowForm(false);
    setEditingWorkstream(undefined);
    loadWorkstreams();
  };

  const handleFormCancel = () => {
    setShowForm(false);
    setEditingWorkstream(undefined);
  };

  const handleEditClick = (workstream: Workstream) => {
    setEditingWorkstream(workstream);
    setShowForm(true);
  };

  const handleDeleteClick = (workstream: Workstream) => {
    setDeletingWorkstream(workstream);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingWorkstream) return;

    setIsDeleting(true);
    try {
      const { error } = await supabase
        .from('workstreams')
        .delete()
        .eq('id', deletingWorkstream.id)
        .eq('user_id', user?.id);

      if (error) throw error;

      setDeletingWorkstream(undefined);
      loadWorkstreams();
    } catch (error) {
      console.error('Error deleting workstream:', error);
      alert('Failed to delete workstream. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeletingWorkstream(undefined);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-brand-blue"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">Workstreams</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Create custom research streams based on your strategic priorities.
          </p>
        </div>
        <button
          onClick={() => {
            setEditingWorkstream(undefined);
            setShowForm(true);
          }}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue transition-colors"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Workstream
        </button>
      </div>

      {/* Workstreams List */}
      {workstreams.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <FolderOpen className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
            No workstreams yet
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Create your first workstream to start tracking relevant
            intelligence.
          </p>
          <div className="mt-6">
            <button
              onClick={() => {
                setEditingWorkstream(undefined);
                setShowForm(true);
              }}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue transition-colors"
            >
              <Plus className="h-4 w-4 mr-2" />
              Create Workstream
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {workstreams.map((workstream) => (
            <WorkstreamCard
              key={workstream.id}
              workstream={workstream}
              onEdit={() => handleEditClick(workstream)}
              onDelete={() => handleDeleteClick(workstream)}
            />
          ))}
        </div>
      )}

      {/* Form Modal */}
      {showForm && (
        <FormModal
          workstream={editingWorkstream}
          onSuccess={handleFormSuccess}
          onCancel={handleFormCancel}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deletingWorkstream && (
        <DeleteConfirmModal
          workstream={deletingWorkstream}
          onConfirm={handleDeleteConfirm}
          onCancel={handleDeleteCancel}
          isDeleting={isDeleting}
        />
      )}
    </div>
  );
};

export default Workstreams;
