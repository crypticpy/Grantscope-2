import { ArrowLeft, Check, Edit2, Sparkles } from "lucide-react";
import { type ProfileData } from "@/lib/profile-api";

interface Props {
  data: ProfileData;
  onComplete: () => Promise<void>;
  onBack: () => void;
  onGoToStep: (step: number) => void;
  saving: boolean;
}

function SectionCard({
  title,
  step,
  onEdit,
  children,
}: {
  title: string;
  step: number;
  onEdit: (step: number) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-900 dark:text-white">
          {title}
        </h3>
        <button
          onClick={() => onEdit(step)}
          className="flex items-center gap-1 text-xs text-brand-blue hover:underline"
        >
          <Edit2 className="h-3 w-3" /> Edit
        </button>
      </div>
      <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
        {children}
      </div>
    </div>
  );
}

const TEAM_SIZE_LABELS: Record<string, string> = {
  "1-5": "1-5 people",
  "6-15": "6-15 people",
  "16-50": "16-50 people",
  "50+": "50+ people",
};

const BUDGET_LABELS: Record<string, string> = {
  under_100k: "Under $100K",
  "100k_500k": "$100K - $500K",
  "500k_1m": "$500K - $1M",
  "1m_5m": "$1M - $5M",
  over_5m: "Over $5M",
};

const EXPERIENCE_LABELS: Record<string, string> = {
  none: "No experience",
  beginner: "Beginner",
  intermediate: "Intermediate",
  experienced: "Experienced",
  expert: "Expert",
};

const FREQUENCY_LABELS: Record<string, string> = {
  daily: "Daily digest",
  weekly: "Weekly summary",
  biweekly: "Every two weeks",
  monthly: "Monthly roundup",
};

export default function ProfileStepReview({
  data,
  onComplete,
  onBack,
  onGoToStep,
  saving,
}: Props) {
  return (
    <div className="p-6 space-y-6">
      {/* Celebration banner */}
      <div className="bg-gradient-to-r from-brand-blue/10 to-brand-green/10 dark:from-brand-blue/15 dark:to-brand-green/15 border border-brand-blue/20 rounded-lg p-5 text-center">
        <Sparkles className="h-8 w-8 text-brand-blue mx-auto mb-2" />
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          You're all set!
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 max-w-md mx-auto">
          Review your profile below. Once you complete setup, we'll personalize
          your grant recommendations, alignment scores, and proposal pre-fills.
        </p>
      </div>

      {/* Sections */}
      <div className="space-y-3">
        {/* Identity */}
        <SectionCard title="About You" step={0} onEdit={onGoToStep}>
          {data.display_name && (
            <p>
              <span className="text-gray-500">Name:</span> {data.display_name}
            </p>
          )}
          {data.department_id && (
            <p>
              <span className="text-gray-500">Department:</span>{" "}
              {data.department || data.department_id}
            </p>
          )}
          {data.title && (
            <p>
              <span className="text-gray-500">Title:</span> {data.title}
            </p>
          )}
          {data.bio && (
            <p>
              <span className="text-gray-500">Bio:</span> {data.bio}
            </p>
          )}
          {!data.display_name && !data.department_id && (
            <p className="text-gray-400 italic">Not filled in yet</p>
          )}
        </SectionCard>

        {/* Program */}
        <SectionCard title="Your Program" step={1} onEdit={onGoToStep}>
          {data.program_name && (
            <p>
              <span className="text-gray-500">Program:</span>{" "}
              {data.program_name}
            </p>
          )}
          {data.program_mission && (
            <p>
              <span className="text-gray-500">Mission:</span>{" "}
              {data.program_mission}
            </p>
          )}
          {data.team_size && (
            <p>
              <span className="text-gray-500">Team:</span>{" "}
              {TEAM_SIZE_LABELS[data.team_size] || data.team_size}
            </p>
          )}
          {data.budget_range && (
            <p>
              <span className="text-gray-500">Budget:</span>{" "}
              {BUDGET_LABELS[data.budget_range] || data.budget_range}
            </p>
          )}
          {!data.program_name && !data.team_size && (
            <p className="text-gray-400 italic">Not filled in yet</p>
          )}
        </SectionCard>

        {/* Grant Interests */}
        <SectionCard title="Grant Interests" step={2} onEdit={onGoToStep}>
          {data.grant_experience && (
            <p>
              <span className="text-gray-500">Experience:</span>{" "}
              {EXPERIENCE_LABELS[data.grant_experience] ||
                data.grant_experience}
            </p>
          )}
          {data.grant_categories && data.grant_categories.length > 0 && (
            <p>
              <span className="text-gray-500">Categories:</span>{" "}
              {data.grant_categories.join(", ")}
            </p>
          )}
          {data.strategic_pillars && data.strategic_pillars.length > 0 && (
            <p>
              <span className="text-gray-500">Pillars:</span>{" "}
              {data.strategic_pillars.join(", ")}
            </p>
          )}
          {(data.funding_range_min != null ||
            data.funding_range_max != null) && (
            <p>
              <span className="text-gray-500">Funding:</span>{" "}
              {data.funding_range_min
                ? `$${data.funding_range_min.toLocaleString()}`
                : "Any"}{" "}
              –{" "}
              {data.funding_range_max
                ? `$${data.funding_range_max.toLocaleString()}`
                : "Any"}
            </p>
          )}
          {!data.grant_experience &&
            (!data.grant_categories || data.grant_categories.length === 0) && (
              <p className="text-gray-400 italic">Not filled in yet</p>
            )}
        </SectionCard>

        {/* Priorities */}
        <SectionCard
          title="Priorities & Preferences"
          step={3}
          onEdit={onGoToStep}
        >
          {data.priorities && data.priorities.length > 0 && (
            <p>
              <span className="text-gray-500">Priorities:</span>{" "}
              {data.priorities.length} selected
            </p>
          )}
          {data.custom_priorities && (
            <p>
              <span className="text-gray-500">Other:</span>{" "}
              {data.custom_priorities}
            </p>
          )}
          {data.help_wanted && data.help_wanted.length > 0 && (
            <p>
              <span className="text-gray-500">Help wanted:</span>{" "}
              {data.help_wanted.join(", ")}
            </p>
          )}
          {data.update_frequency && (
            <p>
              <span className="text-gray-500">Updates:</span>{" "}
              {FREQUENCY_LABELS[data.update_frequency] || data.update_frequency}
            </p>
          )}
          {(!data.priorities || data.priorities.length === 0) &&
            !data.custom_priorities && (
              <p className="text-gray-400 italic">Not filled in yet</p>
            )}
        </SectionCard>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-100 dark:border-gray-700">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back
        </button>
        <button
          onClick={onComplete}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-brand-green text-white text-sm font-medium rounded-lg hover:bg-brand-green/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Check className="h-4 w-4" />
          {saving ? "Completing..." : "Complete Setup"}
        </button>
      </div>
    </div>
  );
}
