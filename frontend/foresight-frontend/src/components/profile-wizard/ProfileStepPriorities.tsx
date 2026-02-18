import { useState, useEffect } from "react";
import { Star, SkipForward, ArrowLeft } from "lucide-react";
import {
  getPrioritiesRef,
  type PriorityRef,
  type ProfileData,
} from "@/lib/profile-api";
import { top25Priorities as fallbackPriorities } from "@/data/taxonomy";

interface Props {
  data: ProfileData;
  onUpdate: (partial: Partial<ProfileData>) => Promise<void>;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
  saving: boolean;
}

const HELP_OPTIONS = [
  { value: "discovery", label: "Finding relevant grants" },
  { value: "scoring", label: "Evaluating grant fit" },
  { value: "proposals", label: "Writing proposals" },
  { value: "compliance", label: "Compliance & reporting" },
  { value: "tracking", label: "Tracking trends & signals" },
];

const FREQUENCY_OPTIONS = [
  { value: "daily", label: "Daily digest" },
  { value: "weekly", label: "Weekly summary" },
  { value: "biweekly", label: "Every two weeks" },
  { value: "monthly", label: "Monthly roundup" },
];

export default function ProfileStepPriorities({
  data,
  onUpdate,
  onNext,
  onBack,
  onSkip,
  saving,
}: Props) {
  const [prioritiesList, setPrioritiesList] = useState<PriorityRef[]>([]);
  const [selectedPriorities, setSelectedPriorities] = useState<string[]>(
    data.priorities || [],
  );
  const [customPriorities, setCustomPriorities] = useState(
    data.custom_priorities || "",
  );
  const [helpWanted, setHelpWanted] = useState<string[]>(
    data.help_wanted || [],
  );
  const [updateFrequency, setUpdateFrequency] = useState(
    data.update_frequency || "",
  );

  useEffect(() => {
    getPrioritiesRef()
      .then(setPrioritiesList)
      .catch(() => {
        setPrioritiesList(
          fallbackPriorities.map((p) => ({
            id: p.id,
            name: p.title,
            description: "",
            category: p.pillarCode,
          })),
        );
      });
  }, []);

  const togglePriority = (id: string) => {
    setSelectedPriorities((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id],
    );
  };

  const toggleHelp = (value: string) => {
    setHelpWanted((prev) =>
      prev.includes(value) ? prev.filter((h) => h !== value) : [...prev, value],
    );
  };

  const handleNext = async () => {
    await onUpdate({
      priorities:
        selectedPriorities.length > 0 ? selectedPriorities : undefined,
      custom_priorities: customPriorities || undefined,
      help_wanted: helpWanted.length > 0 ? helpWanted : undefined,
      update_frequency: updateFrequency || undefined,
    });
    onNext();
  };

  return (
    <div className="p-6 space-y-6">
      {/* Motivation */}
      <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-200/50 dark:border-amber-800/30 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Star className="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-white">
              Almost done!
            </p>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              Your priorities help us rank grant opportunities and tailor
              notifications to what matters most to you.
            </p>
          </div>
        </div>
      </div>

      {/* CMO Top 25 Priorities */}
      {prioritiesList.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            CMO Top 25 Priorities{" "}
            <span className="text-xs text-gray-400">
              (select all that apply)
            </span>
          </label>
          <div className="max-h-48 overflow-y-auto space-y-1.5 border border-gray-200 dark:border-gray-600 rounded-lg p-3">
            {prioritiesList.map((p) => (
              <button
                key={p.id}
                onClick={() => togglePriority(p.id)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-all ${
                  selectedPriorities.includes(p.id)
                    ? "bg-brand-blue/10 text-brand-blue font-medium dark:bg-brand-blue/20"
                    : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                }`}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Custom Priorities */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Other Priorities or Focus Areas
        </label>
        <textarea
          value={customPriorities}
          onChange={(e) => setCustomPriorities(e.target.value)}
          rows={2}
          placeholder="Any other priorities or areas of focus not listed above..."
          className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2.5 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue outline-none resize-none"
        />
      </div>

      {/* Help Wanted */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          What kind of help do you want?
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {HELP_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => toggleHelp(opt.value)}
              className={`text-left px-3 py-2.5 rounded-lg border text-sm transition-all ${
                helpWanted.includes(opt.value)
                  ? "border-brand-blue bg-brand-blue/5 text-brand-blue font-medium dark:bg-brand-blue/15"
                  : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Update Frequency */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          How often do you want updates?
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {FREQUENCY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setUpdateFrequency(opt.value)}
              className={`px-3 py-2 text-sm rounded-lg border transition-all ${
                updateFrequency === opt.value
                  ? "border-brand-blue bg-brand-blue/5 text-brand-blue font-medium dark:bg-brand-blue/15"
                  : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-100 dark:border-gray-700">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back
          </button>
          <button
            onClick={onSkip}
            className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <SkipForward className="h-3.5 w-3.5" /> Skip for now
          </button>
        </div>
        <button
          onClick={handleNext}
          disabled={saving}
          className="px-5 py-2.5 bg-brand-blue text-white text-sm font-medium rounded-lg hover:bg-brand-blue/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? "Saving..." : "Continue"}
        </button>
      </div>
    </div>
  );
}
