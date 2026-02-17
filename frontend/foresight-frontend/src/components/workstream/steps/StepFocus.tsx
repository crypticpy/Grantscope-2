/**
 * StepFocus - Readiness Assessment (Step 3)
 *
 * AI-powered questionnaire about staff capacity, past grants,
 * matching funds, and organizational readiness. Assessment is optional.
 */

import { useState } from "react";
import { Loader2, Sparkles, ChevronRight, CheckCircle2 } from "lucide-react";
import { cn } from "../../../lib/utils";
import { API_BASE_URL } from "../../../lib/config";

interface ReadinessScore {
  overall_score: number;
  factors: Array<{
    name: string;
    score: number;
    description: string;
  }>;
  recommendations: string[];
}

interface StepFocusProps {
  readinessScore: ReadinessScore | null;
  onReadinessScoreChange: (score: ReadinessScore | null) => void;
}

const QUESTIONS = [
  {
    id: "staff_capacity",
    label: "Do you have staff dedicated to grant writing and management?",
    placeholder:
      "e.g., We have 2 full-time grant coordinators and access to the city's central grants office...",
  },
  {
    id: "past_grants",
    label:
      "What grants has your department applied for or received in the past?",
    placeholder:
      "e.g., We received a $2M COPS grant in 2024 and applied for FEMA preparedness funding...",
  },
  {
    id: "matching_funds",
    label:
      "Can your department provide matching funds or in-kind contributions?",
    placeholder:
      "e.g., We can provide up to 25% match from our operating budget and in-kind staff time...",
  },
  {
    id: "financial_systems",
    label:
      "Does your department have financial systems for tracking grant funds?",
    placeholder:
      "e.g., We use the city's financial management system with dedicated grant fund codes...",
  },
  {
    id: "reporting_capability",
    label: "Can your department meet federal/state reporting requirements?",
    placeholder:
      "e.g., We have quarterly reporting processes in place for existing grants...",
  },
  {
    id: "partnerships",
    label:
      "What partnerships does your department have that support grant activities?",
    placeholder:
      "e.g., We partner with UT Austin, local nonprofits, and the regional COG...",
  },
];

export function StepFocus({
  readinessScore,
  onReadinessScoreChange,
}: StepFocusProps) {
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [isAssessing, setIsAssessing] = useState(false);
  const [assessmentError, setAssessmentError] = useState<string | null>(null);

  const hasAnyResponse = Object.values(responses).some((v) => v.trim());

  const handleAssessReadiness = async () => {
    if (!hasAnyResponse) return;

    setIsAssessing(true);
    setAssessmentError(null);

    try {
      const token = localStorage.getItem("gs2_token");
      if (!token) {
        setAssessmentError("Not authenticated. Please log in and try again.");
        return;
      }

      const response = await fetch(
        `${API_BASE_URL}/api/v1/ai/readiness-assessment`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ responses }),
        },
      );

      if (!response.ok) {
        throw new Error("Failed to assess readiness");
      }

      const data: ReadinessScore = await response.json();
      onReadinessScoreChange(data);
    } catch (error) {
      console.error("Readiness assessment failed:", error);
      setAssessmentError(
        "Assessment failed. You can skip this step and try again later.",
      );
    } finally {
      setIsAssessing(false);
    }
  };

  const getScoreColor = (score: number): string => {
    if (score >= 80) return "text-green-600 dark:text-green-400";
    if (score >= 60) return "text-amber-600 dark:text-amber-400";
    return "text-red-600 dark:text-red-400";
  };

  const getScoreBgColor = (score: number): string => {
    if (score >= 80)
      return "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700";
    if (score >= 60)
      return "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-700";
    return "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-700";
  };

  const getScoreBarColor = (score: number): string => {
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-amber-500";
    return "bg-red-500";
  };

  return (
    <div className="space-y-6">
      {/* Inline help */}
      <div className="bg-brand-light-blue/30 dark:bg-brand-blue/10 rounded-lg p-4 border border-brand-blue/20">
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          Answer a few questions about your department's grant readiness. This
          helps the AI recommend appropriate opportunities and identify areas
          for improvement. All questions are optional -- you can skip this step
          entirely.
        </p>
      </div>

      {/* Readiness Score Result (shown when assessment is complete) */}
      {readinessScore && (
        <div
          className={cn(
            "rounded-lg p-5 border",
            getScoreBgColor(readinessScore.overall_score),
          )}
        >
          <div className="flex items-center gap-4 mb-4">
            <div className="text-center">
              <div
                className={cn(
                  "text-3xl font-bold",
                  getScoreColor(readinessScore.overall_score),
                )}
              >
                {readinessScore.overall_score}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                out of 100
              </div>
            </div>
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
                Grant Readiness Score
              </h4>
              <div className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500",
                    getScoreBarColor(readinessScore.overall_score),
                  )}
                  style={{
                    width: `${readinessScore.overall_score}%`,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Factor breakdown */}
          {readinessScore.factors.length > 0 && (
            <div className="space-y-2 mb-4">
              <p className="text-xs font-medium text-gray-600 dark:text-gray-300">
                Factor Breakdown:
              </p>
              {readinessScore.factors.map((factor) => (
                <div key={factor.name} className="flex items-center gap-2">
                  <span className="text-xs text-gray-700 dark:text-gray-300 w-32 truncate">
                    {factor.name}
                  </span>
                  <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        getScoreBarColor(factor.score),
                      )}
                      style={{ width: `${factor.score}%` }}
                    />
                  </div>
                  <span
                    className={cn(
                      "text-xs font-medium w-8 text-right",
                      getScoreColor(factor.score),
                    )}
                  >
                    {factor.score}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Recommendations */}
          {readinessScore.recommendations.length > 0 && (
            <div className="border-t border-gray-200 dark:border-gray-600 pt-3">
              <p className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-2">
                Recommendations:
              </p>
              <ul className="space-y-1">
                {readinessScore.recommendations.map((rec, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-xs text-gray-700 dark:text-gray-300"
                  >
                    <ChevronRight className="h-3 w-3 mt-0.5 text-gray-400 flex-shrink-0" />
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            type="button"
            onClick={() => onReadinessScoreChange(null)}
            className="mt-3 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 underline"
          >
            Re-assess readiness
          </button>
        </div>
      )}

      {/* Questionnaire (hidden when score is shown) */}
      {!readinessScore && (
        <>
          <div className="space-y-5">
            {QUESTIONS.map((question) => (
              <div key={question.id}>
                <label
                  htmlFor={`readiness-${question.id}`}
                  className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
                >
                  {question.label}
                </label>
                <textarea
                  id={`readiness-${question.id}`}
                  value={responses[question.id] || ""}
                  onChange={(e) =>
                    setResponses((prev) => ({
                      ...prev,
                      [question.id]: e.target.value,
                    }))
                  }
                  placeholder={question.placeholder}
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400 resize-none"
                />
              </div>
            ))}
          </div>

          {/* Assessment error */}
          {assessmentError && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-md">
              <p className="text-sm text-red-800 dark:text-red-300">
                {assessmentError}
              </p>
            </div>
          )}

          {/* Assess button */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleAssessReadiness}
              disabled={!hasAnyResponse || isAssessing}
              className={cn(
                "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors",
                hasAnyResponse && !isAssessing
                  ? "bg-purple-600 hover:bg-purple-700 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed",
              )}
            >
              {isAssessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {isAssessing ? "Assessing..." : "Assess My Readiness"}
            </button>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Optional -- you can skip this step
            </span>
          </div>

          {/* Completed questions indicator */}
          {hasAnyResponse && (
            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
              <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
              {Object.values(responses).filter((v) => v.trim()).length} of{" "}
              {QUESTIONS.length} questions answered
            </div>
          )}
        </>
      )}
    </div>
  );
}
