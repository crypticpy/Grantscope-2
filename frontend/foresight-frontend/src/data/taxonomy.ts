/**
 * GrantScope Taxonomy Data
 *
 * Complete taxonomy reference for card classification including:
 * - CSP Pillars (6)
 * - CSP Goals (23)
 * - Strategic Anchors (6)
 * - Maturity Stages (8)
 * - Horizons (3)
 * - CMO Top 25 Priorities (24)
 * - STEEP Categories (5)
 */

// ============================================================================
// Type Definitions
// ============================================================================

export interface Pillar {
  code: string;
  name: string;
  description: string;
  color: string;
  colorLight: string;
  colorDark: string;
  icon: string;
}

export interface Goal {
  code: string;
  pillarCode: string;
  name: string;
  description?: string;
}

export interface Anchor {
  name: string;
  description: string;
  icon: string;
}

export interface MaturityStage {
  stage: number;
  name: string;
  horizon: "H1" | "H2" | "H3";
  description: string;
  signals: string;
}

export interface Horizon {
  code: "H1" | "H2" | "H3";
  name: string;
  timeframe: string;
  description: string;
  color: string;
  colorLight: string;
}

export interface Top25Priority {
  id: string;
  title: string;
  pillarCode: string;
}

export interface SteepCategory {
  code: string;
  name: string;
  description: string;
}

export interface TriageScore {
  score: 1 | 3 | 5;
  name: string;
  description: string;
}

export interface GrantCategory {
  code: string;
  name: string;
  description: string;
  color: string;
  colorLight: string;
  colorDark: string;
  icon: string;
}

export interface GrantLifecycleStage {
  id: string;
  name: string;
  description: string;
}

export interface DeadlineUrgency {
  code: string;
  name: string;
  description: string;
  color: string;
  colorLight: string;
  daysThreshold: number;
}

export interface PipelineStatus {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
}

export interface Department {
  id: string;
  name: string;
  abbreviation: string;
  categoryIds: string[];
}

// ============================================================================
// CSP Pillars (6)
// ============================================================================

export const pillars: Pillar[] = [
  {
    code: "CH",
    name: "Community Health & Sustainability",
    description:
      "Public health, parks, climate, preparedness, and animal services",
    color: "#22c55e",
    colorLight: "#dcfce7",
    colorDark: "#166534",
    icon: "Heart",
  },
  {
    code: "EW",
    name: "Economic & Workforce Development",
    description:
      "Economic mobility, small business support, and creative economy",
    color: "#3b82f6",
    colorLight: "#dbeafe",
    colorDark: "#1e40af",
    icon: "Briefcase",
  },
  {
    code: "HG",
    name: "High-Performing Government",
    description:
      "Fiscal integrity, technology, workforce, and community engagement",
    color: "#6366f1",
    colorLight: "#e0e7ff",
    colorDark: "#3730a3",
    icon: "Building2",
  },
  {
    code: "HH",
    name: "Homelessness & Housing",
    description:
      "Complete communities, affordable housing, and homelessness reduction",
    color: "#ec4899",
    colorLight: "#fce7f3",
    colorDark: "#9d174d",
    icon: "Home",
  },
  {
    code: "MC",
    name: "Mobility & Critical Infrastructure",
    description: "Transportation, transit, utilities, and facility management",
    color: "#f59e0b",
    colorLight: "#fef3c7",
    colorDark: "#b45309",
    icon: "Car",
  },
  {
    code: "PS",
    name: "Public Safety",
    description:
      "Community relationships, fair delivery, and disaster preparedness",
    color: "#ef4444",
    colorLight: "#fee2e2",
    colorDark: "#b91c1c",
    icon: "Shield",
  },
];

// ============================================================================
// CSP Goals (23)
// ============================================================================

export const goals: Goal[] = [
  // Community Health & Sustainability (CH)
  {
    code: "CH.1",
    pillarCode: "CH",
    name: "Ensure equitable delivery of core public health services",
  },
  {
    code: "CH.2",
    pillarCode: "CH",
    name: "Preserve equitable access to parks, trails, and recreation",
  },
  {
    code: "CH.3",
    pillarCode: "CH",
    name: "Protect natural resources and mitigate climate change",
  },
  {
    code: "CH.4",
    pillarCode: "CH",
    name: "Increase community preparedness and resiliency",
  },
  {
    code: "CH.5",
    pillarCode: "CH",
    name: "Operate Animal Centers efficiently with high-quality care",
  },

  // Economic & Workforce Development (EW)
  {
    code: "EW.1",
    pillarCode: "EW",
    name: "Equip and empower the community for economic mobility",
  },
  {
    code: "EW.2",
    pillarCode: "EW",
    name: "Promote a resilient economy prioritizing small and BIPOC businesses",
  },
  {
    code: "EW.3",
    pillarCode: "EW",
    name: "Preserve and enrich Austin's creative ecosystem",
  },

  // High-Performing Government (HG)
  {
    code: "HG.1",
    pillarCode: "HG",
    name: "Ensure fiscal integrity and responsibility",
  },
  {
    code: "HG.2",
    pillarCode: "HG",
    name: "Enhance data and technology capabilities",
  },
  {
    code: "HG.3",
    pillarCode: "HG",
    name: "Recruit and retain a talented, diverse workforce",
  },
  {
    code: "HG.4",
    pillarCode: "HG",
    name: "Provide equitable outreach and collaborative engagement",
  },

  // Homelessness & Housing (HH)
  {
    code: "HH.1",
    pillarCode: "HH",
    name: "Support complete communities with accessible necessities",
  },
  {
    code: "HH.2",
    pillarCode: "HH",
    name: "Prioritize development/preservation of affordable housing",
  },
  {
    code: "HH.3",
    pillarCode: "HH",
    name: "Reduce the number of people experiencing homelessness",
  },

  // Mobility & Critical Infrastructure (MC)
  {
    code: "MC.1",
    pillarCode: "MC",
    name: "Prioritize mobility safety and public health",
  },
  {
    code: "MC.2",
    pillarCode: "MC",
    name: "Invest in high-capacity transit and airport expansion",
  },
  {
    code: "MC.3",
    pillarCode: "MC",
    name: "Expand access to sustainable transportation choices",
  },
  {
    code: "MC.4",
    pillarCode: "MC",
    name: "Maintain a portfolio of safe, resilient City facilities",
  },
  {
    code: "MC.5",
    pillarCode: "MC",
    name: "Provide secure, cost-effective utility infrastructure",
  },

  // Public Safety (PS)
  {
    code: "PS.1",
    pillarCode: "PS",
    name: "Build relationships to create a sense of shared responsibility",
  },
  {
    code: "PS.2",
    pillarCode: "PS",
    name: "Ensure fair, evidence-based delivery of public safety/court services",
  },
  {
    code: "PS.3",
    pillarCode: "PS",
    name: "Invest in partnerships to adapt to hazards and disasters",
  },
];

// ============================================================================
// Strategic Anchors (6)
// ============================================================================

export const anchors: Anchor[] = [
  {
    name: "Equity",
    description: "Ensuring fair access and outcomes for all residents",
    icon: "Scale",
  },
  {
    name: "Affordability",
    description: "Keeping Austin accessible for all income levels",
    icon: "DollarSign",
  },
  {
    name: "Innovation",
    description: "Embracing new approaches and technologies",
    icon: "Lightbulb",
  },
  {
    name: "Sustainability & Resiliency",
    description: "Environmental protection and disaster readiness",
    icon: "Leaf",
  },
  {
    name: "Proactive Prevention",
    description: "Addressing issues before they become crises",
    icon: "ShieldCheck",
  },
  {
    name: "Community Trust & Relationships",
    description: "Building strong connections with residents",
    icon: "Users",
  },
];

// ============================================================================
// Maturity Stages (8)
// ============================================================================

export const stages: MaturityStage[] = [
  {
    stage: 1,
    name: "Concept",
    horizon: "H3",
    description: "Academic research, theoretical exploration",
    signals: "arXiv papers, university research",
  },
  {
    stage: 2,
    name: "Emerging",
    horizon: "H3",
    description: "Startups forming, patents filed",
    signals: "VC funding, patent filings",
  },
  {
    stage: 3,
    name: "Prototype",
    horizon: "H2",
    description: "Working demos exist",
    signals: 'Conference demos, "proof of concept"',
  },
  {
    stage: 4,
    name: "Pilot",
    horizon: "H2",
    description: "Real-world testing (private sector)",
    signals: '"Company X announces pilot..."',
  },
  {
    stage: 5,
    name: "Municipal Pilot",
    horizon: "H2",
    description: "Government entity testing",
    signals: '"City of X announces..."',
  },
  {
    stage: 6,
    name: "Early Adoption",
    horizon: "H1",
    description: "Multiple cities implementing",
    signals: "Pattern of announcements",
  },
  {
    stage: 7,
    name: "Mainstream",
    horizon: "H1",
    description: "Widespread adoption",
    signals: '"Cities across the country..."',
  },
  {
    stage: 8,
    name: "Mature",
    horizon: "H1",
    description: "Established, commoditized",
    signals: "Industry standards exist",
  },
];

// ============================================================================
// Horizons (3)
// ============================================================================

export const horizons: Horizon[] = [
  {
    code: "H1",
    name: "Mainstream",
    timeframe: "0-3 years",
    description: "Current system, confirms baseline",
    color: "#22c55e",
    colorLight: "#dcfce7",
  },
  {
    code: "H2",
    name: "Transitional",
    timeframe: "3-7 years",
    description: "Emerging alternatives, pilots",
    color: "#f59e0b",
    colorLight: "#fef3c7",
  },
  {
    code: "H3",
    name: "Transformative",
    timeframe: "7-15+ years",
    description: "Weak signals, novel possibilities",
    color: "#a855f7",
    colorLight: "#f3e8ff",
  },
];

// ============================================================================
// CMO Top 25 Priorities (24 - as per documentation)
// ============================================================================

export const top25Priorities: Top25Priority[] = [
  { id: "top25-01", title: "First ACME Strategic Plan", pillarCode: "EW" },
  {
    id: "top25-02",
    title: "Airline Use & Lease Agreement (Airport)",
    pillarCode: "MC",
  },
  { id: "top25-03", title: "Shared Services Implementation", pillarCode: "HG" },
  { id: "top25-04", title: "2026 Bond Program Development", pillarCode: "HG" },
  { id: "top25-05", title: "Climate Revolving Fund", pillarCode: "CH" },
  {
    id: "top25-06",
    title: "Expedited Site Plan Review Pilot",
    pillarCode: "HG",
  },
  {
    id: "top25-07",
    title: "Development Code/Criteria Streamlining",
    pillarCode: "HG",
  },
  { id: "top25-08", title: "Economic Development Roadmap", pillarCode: "EW" },
  { id: "top25-09", title: "AE Resiliency Plan", pillarCode: "MC" },
  { id: "top25-10", title: "Human Rights Framework", pillarCode: "HG" },
  {
    id: "top25-11",
    title: "Facility Condition Assessment Contract",
    pillarCode: "MC",
  },
  { id: "top25-12", title: "New Fire Labor Agreement", pillarCode: "PS" },
  { id: "top25-13", title: "Rapid Rehousing Program Model", pillarCode: "HH" },
  {
    id: "top25-14",
    title: "10-Year Housing Blueprint Update",
    pillarCode: "HH",
  },
  { id: "top25-15", title: "AHFC 5-Year Strategic Plan", pillarCode: "HH" },
  {
    id: "top25-16",
    title: "Phase 2 Compensation Recalibration",
    pillarCode: "HG",
  },
  {
    id: "top25-17",
    title: "Alternative Parks Funding Strategies",
    pillarCode: "CH",
  },
  { id: "top25-18", title: "Imagine Austin Update", pillarCode: "HG" },
  {
    id: "top25-19",
    title: "Comprehensive Crime Reduction Plan",
    pillarCode: "PS",
  },
  { id: "top25-20", title: "Police OCM Plan (BerryDunn)", pillarCode: "PS" },
  {
    id: "top25-21",
    title: "Light Rail Interlocal Agreement",
    pillarCode: "MC",
  },
  {
    id: "top25-22",
    title: "Citywide Technology Strategic Plan",
    pillarCode: "HG",
  },
  {
    id: "top25-23",
    title: "IT Organizational Alignment (Phase 1)",
    pillarCode: "HG",
  },
  {
    id: "top25-24",
    title: "Austin FIRST EMS Mental Health Pilot",
    pillarCode: "PS",
  },
];

// ============================================================================
// STEEP Categories (5)
// ============================================================================

export const steepCategories: SteepCategory[] = [
  {
    code: "S",
    name: "Social",
    description: "Demographics, culture, lifestyle, public opinion",
  },
  {
    code: "T",
    name: "Technological",
    description: "Innovation, R&D, digital transformation",
  },
  {
    code: "Ec",
    name: "Economic",
    description: "Markets, employment, trade, fiscal policy",
  },
  {
    code: "En",
    name: "Environmental",
    description: "Climate, resources, sustainability",
  },
  {
    code: "P",
    name: "Political",
    description: "Policy, regulation, governance, elections",
  },
];

// ============================================================================
// Triage Scores (3)
// ============================================================================

export const triageScores: TriageScore[] = [
  {
    score: 1,
    name: "Confirming",
    description: "Confirms what we already know (baseline)",
  },
  {
    score: 3,
    name: "Resolving",
    description: "Provides evidence for one of known alternatives",
  },
  {
    score: 5,
    name: "Novel",
    description: "Suggests new possibility not previously considered",
  },
];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get a pillar by its code
 * Supports exact match and common abbreviations
 */
export function getPillarByCode(code: string): Pillar | undefined {
  if (!code) return undefined;
  const upperCode = code.toUpperCase();

  // Direct match
  const direct = pillars.find((p) => p.code === upperCode);
  if (direct) return direct;

  // Handle common abbreviations/mismatches
  const abbreviationMap: Record<string, string> = {
    ES: "CH", // Environmental/Sustainability maps to Community Health & Sustainability
    ENV: "CH",
    HEALTH: "CH",
    ECON: "EW",
    GOV: "HG",
    HOUSING: "HH",
    MOBILITY: "MC",
    INFRA: "MC",
    SAFETY: "PS",
  };

  const mappedCode = abbreviationMap[upperCode];
  if (mappedCode) {
    return pillars.find((p) => p.code === mappedCode);
  }

  return undefined;
}

/**
 * Get a goal by its code
 */
export function getGoalByCode(code: string): Goal | undefined {
  return goals.find((g) => g.code === code);
}

/**
 * Get all goals for a pillar
 */
export function getGoalsByPillar(pillarCode: string): Goal[] {
  return goals.filter((g) => g.pillarCode === pillarCode);
}

/**
 * Get a stage by its number
 */
export function getStageByNumber(stageNum: number): MaturityStage | undefined {
  return stages.find((s) => s.stage === stageNum);
}

/**
 * Get stages by horizon
 */
export function getStagesByHorizon(
  horizon: "H1" | "H2" | "H3",
): MaturityStage[] {
  return stages.filter((s) => s.horizon === horizon);
}

/**
 * Get a horizon by its code
 */
export function getHorizonByCode(
  code: "H1" | "H2" | "H3",
): Horizon | undefined {
  return horizons.find((h) => h.code === code);
}

/**
 * Get an anchor by its name
 * Supports exact match, partial match, and common abbreviations
 */
export function getAnchorByName(name: string): Anchor | undefined {
  if (!name) return undefined;
  const lowerName = name.toLowerCase().trim();

  // Direct match (case-insensitive)
  const direct = anchors.find((a) => a.name.toLowerCase() === lowerName);
  if (direct) return direct;

  // Partial/keyword match
  const keywordMap: Record<string, string> = {
    equity: "Equity",
    afford: "Affordability",
    affordability: "Affordability",
    innov: "Innovation",
    innovation: "Innovation",
    sustain: "Sustainability & Resiliency",
    sustainability: "Sustainability & Resiliency",
    resiliency: "Sustainability & Resiliency",
    resilience: "Sustainability & Resiliency",
    prevent: "Proactive Prevention",
    prevention: "Proactive Prevention",
    proactive: "Proactive Prevention",
    trust: "Community Trust & Relationships",
    community: "Community Trust & Relationships",
    relationship: "Community Trust & Relationships",
  };

  const mappedName = keywordMap[lowerName];
  if (mappedName) {
    return anchors.find((a) => a.name === mappedName);
  }

  // Fuzzy match - check if the anchor name contains the search term
  const fuzzy = anchors.find(
    (a) =>
      a.name.toLowerCase().includes(lowerName) ||
      lowerName.includes(a.name.toLowerCase().split(" ")[0]),
  );
  if (fuzzy) return fuzzy;

  return undefined;
}

/**
 * Get Top 25 priorities by pillar
 */
export function getTop25ByPillar(pillarCode: string): Top25Priority[] {
  return top25Priorities.filter((p) => p.pillarCode === pillarCode);
}

/**
 * Get a Top 25 priority by its title
 */
export function getTop25ByTitle(title: string): Top25Priority | undefined {
  return top25Priorities.find((p) => p.title === title);
}

/**
 * Get a STEEP category by its code
 */
export function getSteepByCode(code: string): SteepCategory | undefined {
  return steepCategories.find((s) => s.code === code);
}

/**
 * Get a triage score definition
 */
export function getTriageScore(score: 1 | 3 | 5): TriageScore | undefined {
  return triageScores.find((t) => t.score === score);
}

/**
 * Get the horizon for a given stage number
 */
export function getHorizonForStage(stageNum: number): Horizon | undefined {
  const stage = getStageByNumber(stageNum);
  if (!stage) return undefined;
  return getHorizonByCode(stage.horizon);
}

/**
 * Map of pillar codes to their associated pillars for quick lookup
 */
export const pillarMap: Record<string, Pillar> = pillars.reduce(
  (acc, pillar) => {
    acc[pillar.code] = pillar;
    return acc;
  },
  {} as Record<string, Pillar>,
);

/**
 * Map of goal codes to their associated goals for quick lookup
 */
export const goalMap: Record<string, Goal> = goals.reduce(
  (acc, goal) => {
    acc[goal.code] = goal;
    return acc;
  },
  {} as Record<string, Goal>,
);

/**
 * Map of stage numbers to stages for quick lookup
 */
export const stageMap: Record<number, MaturityStage> = stages.reduce(
  (acc, stage) => {
    acc[stage.stage] = stage;
    return acc;
  },
  {} as Record<number, MaturityStage>,
);

/**
 * Map of horizon codes to horizons for quick lookup
 */
export const horizonMap: Record<string, Horizon> = horizons.reduce(
  (acc, horizon) => {
    acc[horizon.code] = horizon;
    return acc;
  },
  {} as Record<string, Horizon>,
);

/**
 * Map of anchor names to anchors for quick lookup
 */
export const anchorMap: Record<string, Anchor> = anchors.reduce(
  (acc, anchor) => {
    acc[anchor.name] = anchor;
    return acc;
  },
  {} as Record<string, Anchor>,
);

// ============================================================================
// Grant Categories (8)
// ============================================================================

export const grantCategories: GrantCategory[] = [
  {
    code: "HS",
    name: "Health & Social Services",
    description:
      "Public health, behavioral health, social services, youth development",
    color: "#22c55e",
    colorLight: "#dcfce7",
    colorDark: "#166534",
    icon: "Heart",
  },
  {
    code: "PS",
    name: "Public Safety",
    description: "Law enforcement, fire, EMS, emergency management, justice",
    color: "#ef4444",
    colorLight: "#fee2e2",
    colorDark: "#b91c1c",
    icon: "Shield",
  },
  {
    code: "HD",
    name: "Housing & Development",
    description:
      "Affordable housing, homelessness, community development, planning",
    color: "#ec4899",
    colorLight: "#fce7f3",
    colorDark: "#9d174d",
    icon: "Home",
  },
  {
    code: "IN",
    name: "Infrastructure",
    description:
      "Transportation, water, energy, facilities, telecommunications",
    color: "#f59e0b",
    colorLight: "#fef3c7",
    colorDark: "#b45309",
    icon: "Construction",
  },
  {
    code: "EN",
    name: "Environment",
    description: "Climate, sustainability, parks, conservation, resilience",
    color: "#10b981",
    colorLight: "#d1fae5",
    colorDark: "#065f46",
    icon: "Leaf",
  },
  {
    code: "CE",
    name: "Culture & Education",
    description: "Libraries, museums, arts, education, workforce development",
    color: "#8b5cf6",
    colorLight: "#e0e7ff",
    colorDark: "#3730a3",
    icon: "GraduationCap",
  },
  {
    code: "TG",
    name: "Technology & Government",
    description:
      "IT modernization, data, cybersecurity, innovation, e-government",
    color: "#3b82f6",
    colorLight: "#dbeafe",
    colorDark: "#1e40af",
    icon: "Cpu",
  },
  {
    code: "EQ",
    name: "Equity & Engagement",
    description:
      "Civil rights, accessibility, language access, civic participation",
    color: "#f97316",
    colorLight: "#ede9fe",
    colorDark: "#5b21b6",
    icon: "Users",
  },
];

// ============================================================================
// Grant Lifecycle Stages (5)
// ============================================================================

export const grantLifecycleStages: GrantLifecycleStage[] = [
  {
    id: "forecasted",
    name: "Forecasted",
    description: "Expected to be announced",
  },
  { id: "open", name: "Open", description: "Accepting applications" },
  {
    id: "closing_soon",
    name: "Closing Soon",
    description: "Deadline approaching",
  },
  {
    id: "closed",
    name: "Closed",
    description: "No longer accepting applications",
  },
  { id: "awarded", name: "Awarded", description: "Grants have been awarded" },
];

// ============================================================================
// Deadline Urgency Tiers (3)
// ============================================================================

export const deadlineUrgencyTiers: DeadlineUrgency[] = [
  {
    code: "urgent",
    name: "Urgent",
    description: "Deadline within 2 weeks",
    color: "#ef4444",
    colorLight: "#fee2e2",
    daysThreshold: 14,
  },
  {
    code: "approaching",
    name: "Approaching",
    description: "Deadline within 45 days",
    color: "#f59e0b",
    colorLight: "#fef3c7",
    daysThreshold: 45,
  },
  {
    code: "planning",
    name: "Planning",
    description: "Deadline more than 45 days away",
    color: "#22c55e",
    colorLight: "#dcfce7",
    daysThreshold: 999,
  },
];

// ============================================================================
// Pipeline Statuses (7)
// ============================================================================

export const pipelineStatuses: PipelineStatus[] = [
  {
    id: "discovered",
    name: "Discovered",
    description: "New opportunities found",
    icon: "Search",
    color: "#3b82f6",
  },
  {
    id: "evaluating",
    name: "Evaluating",
    description: "Assessing fit and eligibility",
    icon: "ClipboardCheck",
    color: "#f59e0b",
  },
  {
    id: "applying",
    name: "Applying",
    description: "Preparing application",
    icon: "FileEdit",
    color: "#8b5cf6",
  },
  {
    id: "submitted",
    name: "Submitted",
    description: "Application submitted",
    icon: "Send",
    color: "#6366f1",
  },
  {
    id: "awarded",
    name: "Awarded",
    description: "Grant awarded",
    icon: "Trophy",
    color: "#22c55e",
  },
  {
    id: "declined",
    name: "Declined",
    description: "Application not selected",
    icon: "XCircle",
    color: "#ef4444",
  },
  {
    id: "expired",
    name: "Expired",
    description: "Deadline passed",
    icon: "Clock",
    color: "#9ca3af",
  },
];

// ============================================================================
// Grant Lookup Maps
// ============================================================================

/**
 * Map of grant category codes to their associated categories for quick lookup
 */
export const grantCategoryMap: Record<string, GrantCategory> =
  grantCategories.reduce(
    (acc, cat) => {
      acc[cat.code] = cat;
      return acc;
    },
    {} as Record<string, GrantCategory>,
  );

/**
 * Map of pipeline status IDs to their associated statuses for quick lookup
 */
export const pipelineStatusMap: Record<string, PipelineStatus> =
  pipelineStatuses.reduce(
    (acc, status) => {
      acc[status.id] = status;
      return acc;
    },
    {} as Record<string, PipelineStatus>,
  );

// ============================================================================
// Grant Helper Functions
// ============================================================================

/**
 * Get a grant category by its code
 */
export function getGrantCategoryByCode(
  code: string,
): GrantCategory | undefined {
  return grantCategories.find((c) => c.code === code);
}

/**
 * Get the deadline urgency tier for a given deadline date.
 * Returns undefined if deadline is null or already past.
 */
export function getDeadlineUrgency(
  deadline: Date | string | null,
): DeadlineUrgency | undefined {
  if (!deadline) return undefined;
  const deadlineDate =
    typeof deadline === "string" ? new Date(deadline) : deadline;
  const now = new Date();
  const daysUntil = Math.ceil(
    (deadlineDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
  );
  if (daysUntil < 0) return undefined;
  return deadlineUrgencyTiers.find((tier) => daysUntil <= tier.daysThreshold);
}

/**
 * Get a pipeline status by its ID
 */
export function getPipelineStatusById(id: string): PipelineStatus | undefined {
  return pipelineStatuses.find((s) => s.id === id);
}

// ============================================================================
// City of Austin Departments (subset for local fallback; full list of 43 in DB)
// ============================================================================

export const departments: Department[] = [
  {
    id: "APD",
    name: "Austin Police Department",
    abbreviation: "APD",
    categoryIds: ["PS"],
  },
  {
    id: "AFD",
    name: "Austin Fire Department",
    abbreviation: "AFD",
    categoryIds: ["PS"],
  },
  {
    id: "ATD",
    name: "Austin Transportation Department",
    abbreviation: "ATD",
    categoryIds: ["IN"],
  },
  {
    id: "APH",
    name: "Austin Public Health",
    abbreviation: "APH",
    categoryIds: ["HS"],
  },
  {
    id: "NHCD",
    name: "Housing & Community Development",
    abbreviation: "NHCD",
    categoryIds: ["HD"],
  },
  {
    id: "PARD",
    name: "Parks & Recreation Department",
    abbreviation: "PARD",
    categoryIds: ["HS", "EN"],
  },
  {
    id: "AE",
    name: "Austin Energy",
    abbreviation: "AE",
    categoryIds: ["EN", "IN"],
  },
  {
    id: "AWU",
    name: "Austin Water",
    abbreviation: "AWU",
    categoryIds: ["EN", "IN"],
  },
  {
    id: "EDD",
    name: "Economic Development Department",
    abbreviation: "EDD",
    categoryIds: ["CE", "EQ"],
  },
  {
    id: "CTM",
    name: "Communications & Technology Management",
    abbreviation: "CTM",
    categoryIds: ["TG"],
  },
  {
    id: "OOS",
    name: "Office of Sustainability",
    abbreviation: "OOS",
    categoryIds: ["EN"],
  },
  {
    id: "OTHER",
    name: "Other Department",
    abbreviation: "Other",
    categoryIds: [],
  },
];

/**
 * Get a department by its ID
 */
export function getDepartmentById(id: string): Department | undefined {
  return departments.find((d) => d.id === id);
}
