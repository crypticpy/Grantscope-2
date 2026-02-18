import { useState, useEffect } from "react";
import { Building2, SkipForward } from "lucide-react";
import {
  getDepartments,
  type DepartmentRef,
  type ProfileData,
} from "@/lib/profile-api";
import { departments as fallbackDepartments } from "@/data/taxonomy";

interface Props {
  data: ProfileData;
  onUpdate: (partial: Partial<ProfileData>) => Promise<void>;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
  saving: boolean;
}

export default function ProfileStepIdentity({
  data,
  onUpdate,
  onNext,
  onSkip,
  saving,
}: Props) {
  const [departments, setDepartments] = useState<DepartmentRef[]>([]);
  const [departmentId, setDepartmentId] = useState(data.department_id || "");
  const [displayName, setDisplayName] = useState(data.display_name || "");
  const [title, setTitle] = useState(data.title || "");
  const [bio, setBio] = useState(data.bio || "");
  const [loadingDepts, setLoadingDepts] = useState(true);

  useEffect(() => {
    getDepartments()
      .then(setDepartments)
      .catch(() => {
        // Use frontend taxonomy fallback
        setDepartments(
          fallbackDepartments.map((d) => ({
            id: d.id,
            name: d.name,
            abbreviation: d.abbreviation,
            category_ids: d.categoryIds,
          })),
        );
      })
      .finally(() => setLoadingDepts(false));
  }, []);

  const canProceed = departmentId && displayName;

  const handleNext = async () => {
    if (!canProceed) return;
    await onUpdate({
      department_id: departmentId,
      display_name: displayName,
      title: title || undefined,
      bio: bio || undefined,
    });
    onNext();
  };

  return (
    <div className="p-6 space-y-6">
      {/* Motivation banner */}
      <div className="bg-brand-blue/5 dark:bg-brand-blue/10 border border-brand-blue/15 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Building2 className="h-5 w-5 text-brand-blue flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-white">
              Why this matters
            </p>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              Your department and role help us surface grants that match your
              team's mission and capabilities. We'll score opportunities against
              your specific context.
            </p>
          </div>
        </div>
      </div>

      {/* Department */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Department <span className="text-red-500">*</span>
        </label>
        <select
          value={departmentId}
          onChange={(e) => setDepartmentId(e.target.value)}
          disabled={loadingDepts}
          className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2.5 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue outline-none"
        >
          <option value="">Select your department...</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} ({d.abbreviation})
            </option>
          ))}
        </select>
      </div>

      {/* Display Name */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Your Name <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="e.g. Chris Martinez"
          className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2.5 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue outline-none"
        />
      </div>

      {/* Job Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Job Title
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Grants Manager, Program Director"
          className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2.5 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue outline-none"
        />
      </div>

      {/* Bio */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Brief Bio <span className="text-xs text-gray-400">(optional)</span>
        </label>
        <textarea
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          rows={3}
          placeholder="e.g. I manage federal and state grant applications for Austin Public Health's chronic disease prevention programs."
          className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2.5 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue outline-none resize-none"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-100 dark:border-gray-700">
        <button
          onClick={onSkip}
          className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        >
          <SkipForward className="h-3.5 w-3.5" />
          Skip for now
        </button>
        <button
          onClick={handleNext}
          disabled={!canProceed || saving}
          className="px-5 py-2.5 bg-brand-blue text-white text-sm font-medium rounded-lg hover:bg-brand-blue/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? "Saving..." : "Continue"}
        </button>
      </div>
    </div>
  );
}
