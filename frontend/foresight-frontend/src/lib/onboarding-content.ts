/**
 * Onboarding Content Definitions
 *
 * Centralized content for all onboarding, tooltip, and empty-state experiences.
 * Keeping content separate from components makes it easy to update copy
 * without touching rendering logic.
 */

// ---------------------------------------------------------------------------
// Stat explanations (used by InfoTooltip on dashboard stats)
// ---------------------------------------------------------------------------

export const STAT_EXPLANATIONS: Record<string, string> = {
  totalOpportunities:
    "The total number of grant opportunities in the system, discovered by AI from federal, state, and foundation sources.",
  newThisWeek:
    "Opportunities added in the last 7 days. New grants are discovered automatically through scheduled scans.",
  following:
    "Grants you've bookmarked by clicking the heart icon. These appear in your 'My Opportunities' page.",
  programs:
    "Programs are personalized workspaces for tracking grants related to a specific focus area, like 'Youth Services' or 'Infrastructure.'",
  deadlinesThisWeek:
    "Grants with application deadlines in the next 7 days. Don't miss these!",
  pipelineValue:
    "The combined funding amount of all active grant opportunities. This shows the total potential funding available.",
  qualityDistribution:
    "Shows how many grants have been verified. High quality means multiple sources confirm the grant details.",
};

// ---------------------------------------------------------------------------
// Filter explanations (used by InfoTooltip on Discover page filters)
// ---------------------------------------------------------------------------

export const FILTER_EXPLANATIONS: Record<string, string> = {
  strategicPillar:
    "Austin's strategic priority areas. Each grant is tagged with the city priority it best supports.",
  maturityStage:
    "How far along a grant opportunity is in the review process, from initial discovery to fully vetted.",
  pipelineStatus:
    "Where an opportunity stands in the grant pipeline: Discovered, Evaluating, Applying, Submitted, Awarded, Active, or Closed.",
  horizon:
    "When the funding would likely be available. H1 = now to 2 years, H2 = 2-5 years, H3 = 5+ years.",
  semanticSearch:
    "AI-powered search that finds grants related to your meaning, not just matching words. Try describing what your program does.",
  qualityTier:
    "How thoroughly a grant has been verified. 'High' means multiple sources confirm the information.",
  grantType:
    "The source of funding: Federal (US government), State (Texas), Foundation (private), or Local.",
  grantCategory:
    "The subject area the grant funds, like Health & Social Services or Public Safety.",
  impactScore:
    "How much this grant could affect Austin residents and city operations (0-100).",
  relevanceScore:
    "How closely this grant aligns with Austin's strategic priorities (0-100).",
  noveltyScore: "How new or recently discovered this opportunity is (0-100).",
  deadlineRange: "Filter grants by when their application deadline falls.",
  fundingRange: "Filter by how much money the grant provides.",
  sortBy:
    "Change how results are ordered. Try 'Deadline (Soonest)' to see what's closing soon.",
};

// ---------------------------------------------------------------------------
// Empty state guidance
// ---------------------------------------------------------------------------

export interface EmptyStateGuidance {
  title: string;
  description: string;
  steps: string[];
  tipText?: string;
  learnMoreLink?: string;
  learnMoreLabel?: string;
}

export const EMPTY_STATE_GUIDANCE: Record<string, EmptyStateGuidance> = {
  signals: {
    title: "Build Your Grant Watchlist",
    description: "Track the grants that matter to your department.",
    steps: [
      "Visit the Discover page to browse grant opportunities",
      "Click the heart icon on any grant to follow it",
      "Followed grants appear here so you can track them over time",
    ],
    tipText:
      "Following a grant means you'll always see it here and be alerted about deadline changes.",
  },
  workstreams: {
    title: "Organize Your Grant Search",
    description:
      "A program groups grants around a focus area, like 'Public Safety Grants' or 'Youth Services Funding'. GrantScope automatically finds matching opportunities and adds them to your review board.",
    steps: [
      "Name your program",
      "Set keywords and filters",
      "GrantScope fills your board automatically",
    ],
    learnMoreLink: "/guide/workstreams",
    learnMoreLabel: "Learn more about programs",
  },
  workstreamFeed: {
    title: "No Matching Opportunities Yet",
    description:
      "This program's filters might be too narrow, or no grants match yet.",
    steps: [
      "Try broadening your search terms or removing some filters",
      "GrantScope scans for new grants daily -- check back soon",
      "Adjust your program's focus area in the settings",
    ],
    tipText:
      "New grants are discovered automatically. Your program will fill up over time.",
  },
  discoveryQueue: {
    title: "All Caught Up!",
    description:
      "You've reviewed all pending discoveries. GrantScope is always scanning for new opportunities -- check back soon!",
    steps: [],
  },
};

// ---------------------------------------------------------------------------
// Page intro banners (first-time feature introductions)
// ---------------------------------------------------------------------------

export interface PageIntro {
  heading: string;
  body: string;
  tipText: string;
}

export const PAGE_INTROS: Record<"discover" | "ask" | "programs", PageIntro> = {
  discover: {
    heading: "This is your grant library",
    body: "Every grant opportunity GrantScope finds appears here. Use the search bar or filters to narrow down what's relevant to you.",
    tipText:
      "Try searching for what your program does, like 'youth mentoring' or 'park improvements'",
  },
  ask: {
    heading: "Ask anything about grants",
    body: "GrantScope's AI can answer questions about specific grants, compare opportunities, explain eligibility requirements, and help you understand the funding landscape.",
    tipText: "Try one of the suggested questions below, or type your own",
  },
  programs: {
    heading: "Track grants in programs",
    body: "Programs are like personalized folders for grants. Create one for each focus area and GrantScope will automatically find and organize matching opportunities.",
    tipText:
      "Start with a broad focus area like 'Community Health' -- you can always narrow it later",
  },
};

// ---------------------------------------------------------------------------
// Onboarding dialog content
// ---------------------------------------------------------------------------

export const ONBOARDING_FEATURES = [
  {
    icon: "Compass" as const,
    title: "Discover Grants",
    description:
      "Browse hundreds of federal, state, and foundation grant opportunities",
  },
  {
    icon: "Sparkles" as const,
    title: "Ask AI",
    description:
      "Get instant answers about grants, eligibility, deadlines, and more",
  },
  {
    icon: "FolderOpen" as const,
    title: "Track Programs",
    description:
      "Organize grants into programs and track them through a review workflow",
  },
  {
    icon: "FileText" as const,
    title: "Apply with AI",
    description:
      "Our wizard walks you through every step of the application process",
  },
];

export const QUICK_START_ACTIONS = [
  {
    label: "Browse grant opportunities",
    description:
      "Explore the library of grants from federal, state, and foundation sources",
    href: "/discover",
    icon: "Compass" as const,
  },
  {
    label: "Ask a question about grants",
    description:
      "Get AI-powered answers about eligibility, deadlines, and more",
    href: "/ask",
    icon: "Sparkles" as const,
  },
  {
    label: "Apply for a grant I found",
    description:
      "Our wizard guides you from requirements to professional proposal",
    href: "/apply",
    icon: "FileText" as const,
  },
];

// ---------------------------------------------------------------------------
// Getting started checklist
// ---------------------------------------------------------------------------

export interface ChecklistItem {
  id: string;
  label: string;
  description: string;
  href: string;
  /** When true, completion is detected by data (not localStorage) */
  dataDetected?: boolean;
}

export const GETTING_STARTED_ITEMS: ChecklistItem[] = [
  {
    id: "explore-library",
    label: "Explore the grant library",
    description: "Browse available grant opportunities",
    href: "/discover",
  },
  {
    id: "ask-question",
    label: "Ask GrantScope a question",
    description: "Try the AI-powered grant assistant",
    href: "/ask",
  },
  {
    id: "follow-opportunity",
    label: "Follow an opportunity",
    description: "Click the heart icon on any grant to track it",
    href: "/discover",
    dataDetected: true,
  },
  {
    id: "create-program",
    label: "Create a program",
    description: "Organize grants into a focused workspace",
    href: "/workstreams",
    dataDetected: true,
  },
  {
    id: "start-application",
    label: "Start a grant application",
    description: "Our AI wizard helps you through every step",
    href: "/apply",
  },
];
