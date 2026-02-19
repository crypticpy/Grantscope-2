import React, { useState, useEffect, useRef, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Heart,
  TrendingUp,
  Eye,
  Plus,
  Filter,
  Star,
  Sparkles,
  ArrowRight,
  Clock,
  DollarSign,
  BookOpen,
  ExternalLink,
  FileText,
} from "lucide-react";
import { useAuthContext } from "../hooks/useAuthContext";
import { PillarBadge } from "../components/PillarBadge";
import { HorizonBadge } from "../components/HorizonBadge";
import { StageBadge } from "../components/StageBadge";
import { Top25Badge } from "../components/Top25Badge";
import { QualityBadge } from "../components/QualityBadge";
import { VelocityBadge, type VelocityTrend } from "../components/VelocityBadge";
import { PatternInsightsSection } from "../components/PatternInsightsSection";
import { AskGrantScopeBar } from "../components/Chat/AskGrantScopeBar";
import { parseStageNumber } from "../lib/stage-utils";
import { logger } from "../lib/logger";
import { getDeadlineUrgency } from "../data/taxonomy";
import { OnboardingDialog } from "../components/onboarding/OnboardingDialog";
import { GettingStartedChecklist } from "../components/onboarding/GettingStartedChecklist";
import { DashboardNudge } from "../components/onboarding/DashboardNudge";
import { InfoTooltip } from "../components/onboarding/InfoTooltip";
import {
  hasCompletedOnboarding,
  markOnboardingComplete,
  isGettingStartedDismissed,
  dismissGettingStarted,
  markStepCompleted,
  hasSkippedProfileWizard,
} from "../lib/onboarding-state";
import { STAT_EXPLANATIONS } from "../lib/onboarding-content";
import { API_BASE_URL } from "../lib/config";
import { MyApplications } from "../components/dashboard/MyApplications";
import type { BaseCard } from "../types/card";

type Card = BaseCard;

interface FollowingCard {
  id: string;
  priority: string;
  cards: Card;
}

/** Fetch the consolidated dashboard payload from the backend. */
async function fetchDashboardData(token: string) {
  const res = await fetch(`${API_BASE_URL}/api/v1/me/dashboard`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Dashboard API ${res.status}`);
  return res.json();
}

/**
 * Animates a number from 0 to the target value over the given duration (ms)
 * using requestAnimationFrame for smooth 60fps rendering.
 */
function useCountUp(target: number, duration = 500): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    if (target === 0) {
      setValue(0);
      return;
    }
    const start = performance.now();
    const animate = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      // Use ease-out curve for a more natural feel
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration]);

  return value;
}

const getPriorityColor = (priority: string) => {
  const colors: Record<string, string> = {
    high: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    medium:
      "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
    low: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  };
  return (
    colors[priority] ||
    "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
  );
};

const getPriorityBorder = (priority: string) => {
  const borders: Record<string, string> = {
    high: "border-l-red-500",
    medium: "border-l-amber-500",
    low: "border-l-emerald-500",
  };
  return borders[priority] || "border-l-gray-300";
};

const getPriorityGradient = (priority: string) => {
  const gradients: Record<string, string> = {
    high: "from-red-50 dark:from-red-900/10",
    medium: "from-amber-50 dark:from-amber-900/10",
    low: "from-emerald-50 dark:from-emerald-900/10",
  };
  return gradients[priority] || "from-gray-50 dark:from-gray-800/50";
};

const Dashboard: React.FC = () => {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const token = localStorage.getItem("gs2_token") || "";
  const [showOnboarding, setShowOnboarding] = useState(
    () => !hasCompletedOnboarding(),
  );
  const [showChecklist, setShowChecklist] = useState(
    () => !isGettingStartedDismissed(),
  );
  const [recentCards, setRecentCards] = useState<Card[]>([]);
  const [followingCards, setFollowingCards] = useState<FollowingCard[]>([]);
  const [upcomingDeadlineCards, setUpcomingDeadlineCards] = useState<Card[]>(
    [],
  );
  const [loading, setLoading] = useState(true);
  const [pendingReviewCount, setPendingReviewCount] = useState(0);
  const [stats, setStats] = useState({
    totalCards: 0,
    newThisWeek: 0,
    following: 0,
    workstreams: 0,
    deadlinesThisWeek: 0,
    pipelineValue: 0,
  });
  const [qualityDistribution, setQualityDistribution] = useState({
    high: 0,
    moderate: 0,
    low: 0,
  });

  // Animated stat card values
  const animatedTotalCards = useCountUp(stats.totalCards);
  const animatedNewThisWeek = useCountUp(stats.newThisWeek);
  const animatedFollowing = useCountUp(stats.following);
  const animatedWorkstreams = useCountUp(stats.workstreams);
  const animatedDeadlinesThisWeek = useCountUp(stats.deadlinesThisWeek);
  const animatedPipelineValue = useCountUp(stats.pipelineValue);

  const handleChecklistStepClick = useCallback(
    (href: string) => {
      if (href === "/discover") markStepCompleted("explore-library");
      if (href === "/ask") markStepCompleted("ask-question");
      if (href === "/apply") markStepCompleted("start-application");
      navigate(href);
    },
    [navigate],
  );

  const handleDismissChecklist = useCallback(() => {
    dismissGettingStarted();
    setShowChecklist(false);
  }, []);

  // Redirect to profile setup on first login if profile is incomplete
  useEffect(() => {
    if (user && !user.profile_completed_at && !hasSkippedProfileWizard()) {
      navigate("/profile-setup");
    }
  }, [user, navigate]);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const token = localStorage.getItem("gs2_token");
      if (!token) {
        setLoading(false);
        return;
      }

      const data = await fetchDashboardData(token);

      setRecentCards(data.recent_cards ?? []);

      // Backend returns following cards as flat card dicts with follow_id/follow_priority
      const transformedFollowing: FollowingCard[] = (
        data.following_cards ?? []
      ).map((c: Card & { follow_id?: string; follow_priority?: string }) => ({
        id: c.follow_id ?? c.id,
        priority: c.follow_priority ?? "medium",
        cards: c,
      }));
      setFollowingCards(transformedFollowing);

      setUpcomingDeadlineCards(data.upcoming_deadlines ?? []);

      const s = data.stats ?? {};
      setStats({
        totalCards: s.total_cards ?? 0,
        newThisWeek: s.new_this_week ?? 0,
        following: s.following ?? 0,
        workstreams: s.workstreams ?? 0,
        deadlinesThisWeek: s.deadlines_this_week ?? 0,
        pipelineValue: Math.round(s.pipeline_value ?? 0),
      });
      setPendingReviewCount(s.pending_review ?? 0);

      const q = data.quality_distribution ?? {};
      setQualityDistribution({
        high: q.high ?? 0,
        moderate: q.moderate ?? 0,
        low: q.low ?? 0,
      });
    } catch (error) {
      logger.warn("Error loading dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header skeleton */}
        <div className="mb-8">
          <div
            className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-lg h-9 w-72"
            style={{ animationDelay: "0ms" }}
          />
          <div
            className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-lg h-5 w-96 mt-2"
            style={{ animationDelay: "50ms" }}
          />
        </div>

        {/* Ask GrantScope Bar skeleton */}
        <div
          className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-xl h-12 mb-8"
          style={{ animationDelay: "100ms" }}
        />

        {/* Stat cards skeleton — 6 cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6 mb-8">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-xl h-28"
              style={{ animationDelay: `${150 + i * 50}ms` }}
            />
          ))}
        </div>

        {/* Quality distribution bar skeleton */}
        <div className="flex items-center justify-between mb-8">
          <div
            className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-lg h-5 w-64"
            style={{ animationDelay: "400ms" }}
          />
          <div
            className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-lg h-5 w-48"
            style={{ animationDelay: "450ms" }}
          />
        </div>

        {/* Pattern Insights skeleton */}
        <div className="mb-8">
          <div
            className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-lg h-6 w-48 mb-4"
            style={{ animationDelay: "500ms" }}
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-xl h-48"
                style={{ animationDelay: `${550 + i * 50}ms` }}
              />
            ))}
          </div>
        </div>

        {/* Following Signals skeleton */}
        <div className="mb-8">
          <div
            className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-lg h-6 w-56 mb-4"
            style={{ animationDelay: "700ms" }}
          />
          <div className="grid gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-xl h-24"
                style={{ animationDelay: `${750 + i * 50}ms` }}
              />
            ))}
          </div>
        </div>

        {/* Recent Intelligence skeleton */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div
              className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-lg h-6 w-48"
              style={{ animationDelay: "900ms" }}
            />
            <div
              className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-lg h-9 w-24"
              style={{ animationDelay: "950ms" }}
            />
          </div>
          <div className="grid gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-xl h-32"
                style={{ animationDelay: `${1000 + i * 50}ms` }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const isNewUser = stats.following === 0 && stats.workstreams === 0;
  const userName = user?.email?.split("@")[0];

  const greetingTitle = (() => {
    if (isNewUser && !hasCompletedOnboarding()) {
      return `Welcome to GrantScope2${userName ? `, ${userName}` : ""}!`;
    }
    return `Welcome back${userName ? `, ${userName}` : ""}!`;
  })();

  const greetingSubtitle = (() => {
    if (isNewUser && !hasCompletedOnboarding()) {
      return "Let's find the right grants for your programs.";
    }
    if (
      stats.totalCards === 0 &&
      stats.following === 0 &&
      stats.workstreams === 0
    ) {
      return "Ready to discover some grant opportunities?";
    }
    return "Here's what's happening in your grant pipeline.";
  })();

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Onboarding Dialog (first-time users) */}
      <OnboardingDialog
        open={showOnboarding}
        onClose={() => {
          markOnboardingComplete();
          setShowOnboarding(false);
        }}
      />

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">
          {greetingTitle}
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          {greetingSubtitle}
        </p>
      </div>

      {/* Ask GrantScope Bar */}
      <AskGrantScopeBar className="mb-8" />

      {/* Getting Started Checklist (new users) */}
      {showChecklist && (
        <GettingStartedChecklist
          stats={{
            following: stats.following ?? 0,
            workstreams: stats.workstreams ?? 0,
          }}
          onStepClick={handleChecklistStepClick}
          onDismiss={handleDismissChecklist}
          className="mb-6"
        />
      )}

      {/* Contextual nudge */}
      <DashboardNudge
        stats={{
          following: stats.following,
          workstreams: stats.workstreams,
        }}
        profileCompleted={!!user?.profile_completed_at}
        className="mb-6"
      />

      {/* Pending Review Alert */}
      {pendingReviewCount > 0 && (
        <div className="mb-8">
          <Link
            to="/discover/queue"
            className="block bg-gradient-to-r from-brand-blue/10 to-brand-green/10 dark:from-brand-blue/20 dark:to-brand-green/20 border border-brand-blue/20 dark:border-brand-blue/30 rounded-xl p-4 hover:from-brand-blue/15 hover:to-brand-green/15 dark:hover:from-brand-blue/25 dark:hover:to-brand-green/25 transition-all duration-200 group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 p-2 bg-brand-blue/20 dark:bg-brand-blue/30 rounded-full">
                  <Sparkles className="h-5 w-5 text-brand-blue" />
                </div>
                <div>
                  <h3 className="font-semibold text-brand-dark-blue dark:text-white">
                    {pendingReviewCount} New Discovery
                    {pendingReviewCount !== 1 ? "ies" : ""} Pending Review
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    AI has found new grant opportunities. Review and approve
                    them to add to your library.
                  </p>
                </div>
              </div>
              <div className="flex-shrink-0 flex items-center gap-1 text-brand-blue group-hover:translate-x-1 transition-transform">
                <span className="text-sm font-medium">Review Now</span>
                <ArrowRight className="h-4 w-4" />
              </div>
            </div>
          </Link>
        </div>
      )}

      {/* Apply for a Grant CTA */}
      <div className="mb-8">
        <Link
          to="/apply"
          className="block bg-gradient-to-r from-brand-blue/10 to-extended-purple/10 dark:from-brand-blue/20 dark:to-extended-purple/20 border border-brand-blue/20 dark:border-brand-blue/30 rounded-xl p-4 hover:from-brand-blue/15 hover:to-extended-purple/15 dark:hover:from-brand-blue/25 dark:hover:to-extended-purple/25 transition-all duration-200 group"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0 p-2 bg-brand-blue/20 dark:bg-brand-blue/30 rounded-full">
                <FileText className="h-5 w-5 text-brand-blue" />
              </div>
              <div>
                <h3 className="font-semibold text-brand-dark-blue dark:text-white">
                  Ready to apply for a grant?
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Our AI-powered wizard walks you through every step — from
                  understanding requirements to generating a professional
                  proposal.
                </p>
              </div>
            </div>
            <div className="flex-shrink-0 flex items-center gap-1 text-brand-blue group-hover:translate-x-1 transition-transform">
              <span className="text-sm font-medium">Start Application</span>
              <ArrowRight className="h-4 w-4" />
            </div>
          </div>
        </Link>
      </div>

      {/* My Applications */}
      <MyApplications token={token} />

      {/* Stats Cards - Clickable KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-8">
        <Link
          to="/discover"
          aria-label={`Total Opportunities: ${stats.totalCards}`}
          className="bg-white dark:bg-dark-surface rounded-xl shadow px-4 py-5 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group text-center"
        >
          <Eye className="h-6 w-6 text-brand-blue mx-auto mb-2 group-hover:scale-110 transition-transform" />
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 flex items-center justify-center gap-0.5 mb-1">
            Opportunities
            <InfoTooltip content={STAT_EXPLANATIONS.totalOpportunities} />
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white tabular-nums">
            {animatedTotalCards.toLocaleString()}
          </p>
        </Link>

        <Link
          to="/discover?filter=new"
          aria-label={`New This Week: ${stats.newThisWeek}`}
          className="bg-white dark:bg-dark-surface rounded-xl shadow px-4 py-5 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group text-center"
        >
          <TrendingUp className="h-6 w-6 text-brand-green mx-auto mb-2 group-hover:scale-110 transition-transform" />
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 flex items-center justify-center gap-0.5 mb-1">
            New This Week
            <InfoTooltip content={STAT_EXPLANATIONS.newThisWeek} />
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white tabular-nums">
            {animatedNewThisWeek.toLocaleString()}
          </p>
        </Link>

        <Link
          to="/discover?filter=following"
          aria-label={`Following: ${stats.following}`}
          className="bg-white dark:bg-dark-surface rounded-xl shadow px-4 py-5 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group text-center"
        >
          <Heart className="h-6 w-6 text-extended-purple mx-auto mb-2 group-hover:scale-110 transition-transform" />
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 flex items-center justify-center gap-0.5 mb-1">
            Following
            <InfoTooltip content={STAT_EXPLANATIONS.following} />
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white tabular-nums">
            {animatedFollowing.toLocaleString()}
          </p>
        </Link>

        <Link
          to="/workstreams"
          aria-label={`Programs: ${stats.workstreams}`}
          className="bg-white dark:bg-dark-surface rounded-xl shadow px-4 py-5 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group text-center"
        >
          <Filter className="h-6 w-6 text-extended-orange mx-auto mb-2 group-hover:scale-110 transition-transform" />
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 flex items-center justify-center gap-0.5 mb-1">
            Programs
            <InfoTooltip content={STAT_EXPLANATIONS.programs} />
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white tabular-nums">
            {animatedWorkstreams.toLocaleString()}
          </p>
        </Link>

        <Link
          to="/discover?filter=deadline"
          aria-label={`Deadlines This Week: ${stats.deadlinesThisWeek}`}
          className="bg-white dark:bg-dark-surface rounded-xl shadow px-4 py-5 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-95 active:shadow-inner cursor-pointer group text-center"
        >
          <Clock className="h-6 w-6 text-red-500 mx-auto mb-2 group-hover:scale-110 transition-transform" />
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 flex items-center justify-center gap-0.5 mb-1">
            Deadlines
            <InfoTooltip content={STAT_EXPLANATIONS.deadlinesThisWeek} />
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white tabular-nums">
            {animatedDeadlinesThisWeek.toLocaleString()}
          </p>
        </Link>

        <div
          aria-label={`Pipeline Value: $${stats.pipelineValue.toLocaleString()}`}
          className="bg-white dark:bg-dark-surface rounded-xl shadow px-4 py-5 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg group text-center"
          title={`$${stats.pipelineValue.toLocaleString()}`}
        >
          <DollarSign className="h-6 w-6 text-emerald-500 mx-auto mb-2 group-hover:scale-110 transition-transform" />
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 flex items-center justify-center gap-0.5 mb-1">
            Pipeline
            <InfoTooltip content={STAT_EXPLANATIONS.pipelineValue} />
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white tabular-nums">
            {animatedPipelineValue >= 1_000_000
              ? `$${(animatedPipelineValue / 1_000_000).toFixed(1)}M`
              : animatedPipelineValue >= 1_000
                ? `$${(animatedPipelineValue / 1_000).toFixed(0)}K`
                : `$${animatedPipelineValue.toLocaleString()}`}
          </p>
        </div>
      </div>

      {/* Quality Distribution & Methodology Link */}
      <div className="flex items-center justify-between mb-8">
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400"
        >
          <span className="flex items-center gap-1.5 font-medium text-gray-700 dark:text-gray-300">
            Quality Distribution
            <InfoTooltip content={STAT_EXPLANATIONS.qualityDistribution} />
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            {qualityDistribution.high} High
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
            {qualityDistribution.moderate} Moderate
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500"></span>
            {qualityDistribution.low} Needs Verification
          </span>
        </div>
        <Link
          to="/methodology"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-brand-blue dark:hover:text-brand-blue transition-colors"
        >
          <BookOpen className="h-4 w-4" />
          How does GrantScope2 work?
        </Link>
      </div>

      {/* Upcoming Deadlines */}
      {upcomingDeadlineCards.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="h-5 w-5 text-red-500" />
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Upcoming Deadlines
            </h2>
          </div>
          <div className="bg-white dark:bg-dark-surface rounded-xl shadow divide-y divide-gray-100 dark:divide-gray-700/50">
            {upcomingDeadlineCards.map((card) => {
              const urgency = card.deadline
                ? getDeadlineUrgency(card.deadline)
                : undefined;
              const deadlineDate = card.deadline
                ? new Date(card.deadline)
                : null;
              return (
                <Link
                  key={card.id}
                  to={`/signals/${card.slug}`}
                  className="flex items-center justify-between px-5 py-3.5 hover:bg-gray-50 dark:hover:bg-dark-surface-hover transition-colors group first:rounded-t-xl last:rounded-b-xl"
                >
                  <div className="flex-1 min-w-0 mr-4">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate group-hover:text-brand-blue transition-colors">
                      {card.name}
                    </p>
                    {card.grantor && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                        {card.grantor}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    {deadlineDate && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {deadlineDate.toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </span>
                    )}
                    {urgency && (
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                        style={{
                          backgroundColor: urgency.colorLight,
                          color: urgency.color,
                        }}
                      >
                        {urgency.name}
                      </span>
                    )}
                    <ExternalLink className="h-3.5 w-3.5 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* AI-Detected Patterns */}
      <PatternInsightsSection className="mb-8" />

      {/* Following Cards */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Your Followed Opportunities
          </h2>
        </div>
        {followingCards.length > 0 ? (
          <div className="grid gap-4">
            {followingCards.slice(0, 3).map((following, index) => {
              const stageNum = parseStageNumber(following.cards.stage_id);
              return (
                <div
                  key={following.id}
                  style={{
                    animationDelay: `${Math.min(index, 5) * 50}ms`,
                    animationFillMode: "both",
                  }}
                  className={`animate-in fade-in slide-in-from-bottom-2 duration-300 bg-gradient-to-r ${getPriorityGradient(following.priority)} to-white dark:to-[#2d3166] rounded-xl shadow p-6 border-l-4 ${getPriorityBorder(following.priority)} transition-all duration-200 hover:-translate-y-1 hover:shadow-lg`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <Star className="h-4 w-4 text-amber-500 fill-amber-500 flex-shrink-0" />
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                          <Link
                            to={`/signals/${following.cards.slug}`}
                            state={{ from: "/" }}
                            className="hover:text-brand-blue transition-colors"
                          >
                            {following.cards.name}
                          </Link>
                        </h3>
                        <PillarBadge
                          pillarId={following.cards.pillar_id}
                          showIcon={true}
                          size="sm"
                        />
                        <HorizonBadge
                          horizon={following.cards.horizon}
                          size="sm"
                        />
                        {stageNum && (
                          <StageBadge
                            stage={stageNum}
                            size="sm"
                            showName={false}
                            variant="minimal"
                          />
                        )}
                        <VelocityBadge
                          trend={
                            following.cards.velocity_trend as VelocityTrend
                          }
                          score={following.cards.velocity_score}
                        />
                        {following.cards.top25_relevance &&
                          following.cards.top25_relevance.length > 0 && (
                            <Top25Badge
                              priorities={following.cards.top25_relevance}
                              size="sm"
                              showCount={true}
                            />
                          )}
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getPriorityColor(following.priority)}`}
                        >
                          {following.priority}
                        </span>
                      </div>
                      <p className="text-gray-600 dark:text-gray-300 mb-3">
                        {following.cards.summary}
                      </p>
                      <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-brand-blue"></span>
                          Impact: {following.cards.impact_score}/100
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-extended-purple"></span>
                          Relevance: {following.cards.relevance_score}/100
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-8 bg-white dark:bg-dark-surface rounded-lg shadow">
            <Heart className="h-8 w-8 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              No followed opportunities yet
            </p>
            <ol className="text-xs text-gray-500 dark:text-gray-400 space-y-1 mb-3 text-left max-w-xs mx-auto">
              <li>
                1. Go to the{" "}
                <button
                  onClick={() => navigate("/discover")}
                  className="text-brand-blue hover:underline"
                >
                  Discover page
                </button>
              </li>
              <li>2. Find a grant that interests you</li>
              <li>3. Click the heart icon to follow it</li>
            </ol>
            <p className="text-xs text-gray-400 dark:text-gray-500 italic mb-4">
              Following a grant adds it to your personal watchlist so you never
              miss a deadline.
            </p>
            <div>
              <Link
                to="/discover"
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
              >
                <Eye className="h-4 w-4 mr-2" />
                Discover Opportunities
                <ArrowRight className="h-4 w-4 ml-2" />
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* Recent Cards */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Recent Opportunities
          </h2>
          <Link
            to="/discover"
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-brand-blue bg-brand-light-blue hover:bg-brand-blue hover:text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue transition-colors"
          >
            <Plus className="h-4 w-4 mr-1" />
            View All
          </Link>
        </div>
        <div className="grid gap-4">
          {recentCards.map((card, index) => {
            const stageNum = parseStageNumber(card.stage_id);
            return (
              <div
                key={card.id}
                style={{
                  animationDelay: `${Math.min(index, 5) * 50}ms`,
                  animationFillMode: "both",
                }}
                className="animate-in fade-in slide-in-from-bottom-2 duration-300 bg-white dark:bg-dark-surface rounded-xl shadow p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                        <Link
                          to={`/signals/${card.slug}`}
                          state={{ from: "/" }}
                          className="hover:text-brand-blue transition-colors"
                        >
                          {card.name}
                        </Link>
                      </h3>
                      <QualityBadge
                        score={card.signal_quality_score}
                        size="sm"
                      />
                      <PillarBadge
                        pillarId={card.pillar_id}
                        showIcon={true}
                        size="sm"
                      />
                      <HorizonBadge horizon={card.horizon} size="sm" />
                      {stageNum && (
                        <StageBadge
                          stage={stageNum}
                          size="sm"
                          showName={false}
                          variant="minimal"
                        />
                      )}
                      <VelocityBadge
                        trend={card.velocity_trend as VelocityTrend}
                        score={card.velocity_score}
                      />
                      {card.top25_relevance &&
                        card.top25_relevance.length > 0 && (
                          <Top25Badge
                            priorities={card.top25_relevance}
                            size="sm"
                            showCount={true}
                          />
                        )}
                    </div>
                    <p className="text-gray-600 dark:text-gray-300 mb-3">
                      {card.summary}
                    </p>
                    <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                      <span>Impact: {card.impact_score}/100</span>
                      <span>Relevance: {card.relevance_score}/100</span>
                      <span>Velocity: {card.velocity_score}/100</span>
                    </div>
                  </div>
                  <div className="ml-4 flex-shrink-0">
                    <Link
                      to={`/signals/${card.slug}`}
                      state={{ from: "/" }}
                      className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 dark:text-gray-200 bg-white dark:bg-dark-surface-elevated hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue transition-colors"
                    >
                      View Details
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
