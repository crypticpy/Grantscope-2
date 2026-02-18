import { useState } from "react";
import { Briefcase, SkipForward, ArrowLeft } from "lucide-react";
import { type ProfileData } from "@/lib/profile-api";

interface Props {
  data: ProfileData;
  onUpdate: (partial: Partial<ProfileData>) => Promise<void>;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
  saving: boolean;
}

const TEAM_SIZES = [
  { value: "1-5", label: "1-5 people" },
  { value: "6-15", label: "6-15 people" },
  { value: "16-50", label: "16-50 people" },
  { value: "50+", label: "50+ people" },
];

const BUDGET_RANGES = [
  { value: "under_100k", label: "Under $100K" },
  { value: "100k_500k", label: "$100K - $500K" },
  { value: "500k_1m", label: "$500K - $1M" },
  { value: "1m_5m", label: "$1M - $5M" },
  { value: "over_5m", label: "Over $5M" },
];

export default function ProfileStepProgram({
  data,
  onUpdate,
  onNext,
  onBack,
  onSkip,
  saving,
}: Props) {
  const [programName, setProgramName] = useState(data.program_name || "");
  const [programMission, setProgramMission] = useState(
    data.program_mission || "",
  );
  const [teamSize, setTeamSize] = useState(data.team_size || "");
  const [budgetRange, setBudgetRange] = useState(data.budget_range || "");

  const handleNext = async () => {
    await onUpdate({
      program_name: programName || undefined,
      program_mission: programMission || undefined,
      team_size: teamSize || undefined,
      budget_range: budgetRange || undefined,
    });
    onNext();
  };

  return (
    <div className="p-6 space-y-6">
      {/* Motivation banner */}
      <div className="bg-brand-green/5 dark:bg-brand-green/10 border border-brand-green/15 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Briefcase className="h-5 w-5 text-brand-green flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-white">
              Tell us about your program
            </p>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              This helps the AI pre-fill proposal sections like staffing plans,
              budget narratives, and organizational capacity when you apply for
              grants.
            </p>
          </div>
        </div>
      </div>

      {/* Program Name */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Program or Division Name
        </label>
        <input
          type="text"
          value={programName}
          onChange={(e) => setProgramName(e.target.value)}
          placeholder="e.g. Chronic Disease Prevention, Watershed Protection"
          className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2.5 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue outline-none"
        />
      </div>

      {/* Mission */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          What does your program do?
        </label>
        <textarea
          value={programMission}
          onChange={(e) => setProgramMission(e.target.value)}
          rows={3}
          placeholder="Briefly describe your program's mission and key activities..."
          className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2.5 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue outline-none resize-none"
        />
      </div>

      {/* Team Size */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Team Size
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {TEAM_SIZES.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTeamSize(opt.value)}
              className={`px-3 py-2 text-sm rounded-lg border transition-all ${
                teamSize === opt.value
                  ? "border-brand-blue bg-brand-blue/5 text-brand-blue font-medium dark:bg-brand-blue/15"
                  : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Budget Range */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Annual Operating Budget
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {BUDGET_RANGES.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setBudgetRange(opt.value)}
              className={`px-3 py-2 text-sm rounded-lg border transition-all ${
                budgetRange === opt.value
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
            <ArrowLeft className="h-3.5 w-3.5" />
            Back
          </button>
          <button
            onClick={onSkip}
            className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <SkipForward className="h-3.5 w-3.5" />
            Skip for now
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
