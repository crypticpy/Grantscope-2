import { useState, useEffect } from "react";
import { Target, SkipForward, ArrowLeft } from "lucide-react";
import {
  getGrantCategoriesRef,
  getPillarsRef,
  type GrantCategoryRef,
  type PillarRef,
  type ProfileData,
} from "@/lib/profile-api";
import {
  grantCategories as fallbackCategories,
  pillars as fallbackPillars,
} from "@/data/taxonomy";

interface Props {
  data: ProfileData;
  onUpdate: (partial: Partial<ProfileData>) => Promise<void>;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
  saving: boolean;
}

const EXPERIENCE_LEVELS = [
  {
    value: "none",
    label: "No experience",
    desc: "Haven't applied for grants yet",
  },
  { value: "beginner", label: "Beginner", desc: "Applied for 1-2 grants" },
  {
    value: "intermediate",
    label: "Intermediate",
    desc: "Successfully won a few grants",
  },
  {
    value: "experienced",
    label: "Experienced",
    desc: "Regular grant applicant",
  },
  {
    value: "expert",
    label: "Expert",
    desc: "Lead grant strategy for my department",
  },
];

export default function ProfileStepGrants({
  data,
  onUpdate,
  onNext,
  onBack,
  onSkip,
  saving,
}: Props) {
  const [categories, setCategories] = useState<GrantCategoryRef[]>([]);
  const [pillarsList, setPillarsList] = useState<PillarRef[]>([]);
  const [grantExperience, setGrantExperience] = useState(
    data.grant_experience || "",
  );
  const [selectedCategories, setSelectedCategories] = useState<string[]>(
    data.grant_categories || [],
  );
  const [selectedPillars, setSelectedPillars] = useState<string[]>(
    data.strategic_pillars || [],
  );
  const [fundingMin, setFundingMin] = useState(
    data.funding_range_min?.toString() || "",
  );
  const [fundingMax, setFundingMax] = useState(
    data.funding_range_max?.toString() || "",
  );

  useEffect(() => {
    getGrantCategoriesRef()
      .then(setCategories)
      .catch(() => {
        setCategories(
          fallbackCategories.map((c) => ({
            id: c.code,
            name: c.name,
            description: c.description,
            color: c.color,
            icon: c.icon,
          })),
        );
      });
    getPillarsRef()
      .then(setPillarsList)
      .catch(() => {
        setPillarsList(
          fallbackPillars.map((p) => ({
            id: p.code,
            name: p.name,
            description: p.description,
            code: p.code,
            color: p.color,
          })),
        );
      });
  }, []);

  const toggleCategory = (id: string) => {
    setSelectedCategories((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id],
    );
  };

  const togglePillar = (id: string) => {
    setSelectedPillars((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id],
    );
  };

  const handleNext = async () => {
    await onUpdate({
      grant_experience: grantExperience || undefined,
      grant_categories:
        selectedCategories.length > 0 ? selectedCategories : undefined,
      strategic_pillars:
        selectedPillars.length > 0 ? selectedPillars : undefined,
      funding_range_min: fundingMin ? parseInt(fundingMin, 10) : undefined,
      funding_range_max: fundingMax ? parseInt(fundingMax, 10) : undefined,
    });
    onNext();
  };

  return (
    <div className="p-6 space-y-6">
      {/* Motivation */}
      <div className="bg-purple-50 dark:bg-purple-900/10 border border-purple-200/50 dark:border-purple-800/30 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Target className="h-5 w-5 text-purple-600 dark:text-purple-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-white">
              Your grant interests
            </p>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              This directly powers your discovery queue — we'll prioritize
              grants matching your categories, pillars, and funding range.
            </p>
          </div>
        </div>
      </div>

      {/* Grant Experience */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Grant Experience Level
        </label>
        <div className="space-y-2">
          {EXPERIENCE_LEVELS.map((level) => (
            <button
              key={level.value}
              onClick={() => setGrantExperience(level.value)}
              className={`w-full text-left px-4 py-3 rounded-lg border transition-all ${
                grantExperience === level.value
                  ? "border-brand-blue bg-brand-blue/5 dark:bg-brand-blue/15"
                  : "border-gray-200 dark:border-gray-600 hover:border-gray-300"
              }`}
            >
              <p
                className={`text-sm font-medium ${
                  grantExperience === level.value
                    ? "text-brand-blue"
                    : "text-gray-700 dark:text-gray-300"
                }`}
              >
                {level.label}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {level.desc}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Grant Categories */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Grant Categories of Interest
        </label>
        <div className="grid grid-cols-2 gap-2">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => toggleCategory(cat.id)}
              className={`text-left px-3 py-2.5 rounded-lg border text-sm transition-all ${
                selectedCategories.includes(cat.id)
                  ? "border-brand-blue bg-brand-blue/5 text-brand-blue font-medium dark:bg-brand-blue/15"
                  : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300"
              }`}
            >
              {cat.name}
            </button>
          ))}
        </div>
      </div>

      {/* Strategic Pillars */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Strategic Pillars Your Work Aligns With
        </label>
        <div className="grid grid-cols-2 gap-2">
          {pillarsList.map((p) => (
            <button
              key={p.id}
              onClick={() => togglePillar(p.id)}
              className={`text-left px-3 py-2.5 rounded-lg border text-sm transition-all ${
                selectedPillars.includes(p.id)
                  ? "border-brand-blue bg-brand-blue/5 text-brand-blue font-medium dark:bg-brand-blue/15"
                  : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300"
              }`}
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      {/* Funding Range */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
          Typical Funding Range You Pursue
        </label>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 dark:text-gray-400">
              Minimum ($)
            </label>
            <input
              type="number"
              value={fundingMin}
              onChange={(e) => setFundingMin(e.target.value)}
              placeholder="e.g. 50000"
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 dark:text-gray-400">
              Maximum ($)
            </label>
            <input
              type="number"
              value={fundingMax}
              onChange={(e) => setFundingMax(e.target.value)}
              placeholder="e.g. 500000"
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue outline-none"
            />
          </div>
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
