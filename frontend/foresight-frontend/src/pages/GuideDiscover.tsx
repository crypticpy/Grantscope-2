import React, { useState } from "react";
import * as Accordion from "@radix-ui/react-accordion";
import { Link } from "react-router-dom";
import {
  Compass,
  ChevronDown,
  ArrowLeft,
  Search,
  Brain,
  Filter,
  Star,
  Eye,
  Grid3X3,
  List,
  Bookmark,
  Clock,
  Rss,
  Newspaper,
  GraduationCap,
  Landmark,
  Cpu,
  ArrowRight,
  Lightbulb,
  CheckCircle,
  BookOpen,
  BarChart3,
  Shield,
  Zap,
  GitCompare,
  Layers,
  SlidersHorizontal,
  History,
  CircleDot,
  Target,
  TrendingUp,
  Sparkles,
  AlertTriangle,
  ThumbsUp,
  ThumbsDown,
  ExternalLink,
} from "lucide-react";
import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Reusable trigger for accordion items. */
const AccordionTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof Accordion.Trigger> & {
    icon?: React.ReactNode;
  }
>(({ children, className, icon, ...props }, ref) => (
  <Accordion.Header className="flex">
    <Accordion.Trigger
      ref={ref}
      className={cn(
        "group flex flex-1 items-center gap-3 py-4 text-left text-lg font-semibold",
        "text-gray-900 dark:text-gray-100 transition-colors",
        "hover:text-brand-blue dark:hover:text-brand-light-blue",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded",
        className,
      )}
      {...props}
    >
      {icon && (
        <span className="flex-shrink-0 text-brand-blue dark:text-brand-light-blue">
          {icon}
        </span>
      )}
      <span className="flex-1">{children}</span>
      <ChevronDown
        className="h-5 w-5 shrink-0 text-gray-400 transition-transform duration-200 group-data-[state=open]:rotate-180"
        aria-hidden
      />
    </Accordion.Trigger>
  </Accordion.Header>
));
AccordionTrigger.displayName = "AccordionTrigger";

/** Reusable content wrapper for accordion items. */
const AccordionContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof Accordion.Content>
>(({ children, className, ...props }, ref) => (
  <Accordion.Content
    ref={ref}
    className={cn(
      "overflow-hidden transition-all duration-200",
      "data-[state=open]:animate-accordion-down data-[state=closed]:animate-accordion-up",
      className,
    )}
    {...props}
  >
    <div className="pb-6 pt-1 pl-10 pr-2 text-gray-700 dark:text-gray-300 leading-relaxed text-[0.938rem]">
      {children}
    </div>
  </Accordion.Content>
));
AccordionContent.displayName = "AccordionContent";

/** Pro tip callout box. */
function ProTip({
  children,
  title = "Pro Tip",
}: {
  children: React.ReactNode;
  title?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="my-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl p-4">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 text-left text-sm font-semibold text-amber-600 dark:text-amber-400 transition-colors hover:text-amber-700 dark:hover:text-amber-300"
      >
        <Lightbulb className="h-4 w-4 flex-shrink-0 text-amber-600 dark:text-amber-400" />
        <span className="flex-1">{title}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <div className="mt-2 text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          {children}
        </div>
      )}
    </div>
  );
}

/** Info callout box (non-collapsible). */
function InfoBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-4 rounded-lg border border-brand-blue/20 bg-brand-light-blue/30 dark:bg-brand-blue/10 px-4 py-3 text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
      {children}
    </div>
  );
}

/** Interactive quick-start step card. */
function QuickStartCard({
  step,
  title,
  description,
  detail,
  icon,
  isActive,
  onClick,
}: {
  step: number;
  title: string;
  description: string;
  detail: string;
  icon: React.ReactNode;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "relative flex flex-col items-start rounded-xl border p-5 text-left transition-all duration-200",
        "hover:shadow-md hover:-translate-y-0.5",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue",
        isActive
          ? "border-brand-blue bg-white dark:bg-dark-surface shadow-md ring-1 ring-brand-blue/20"
          : "border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface/60",
      )}
    >
      <div className="flex items-center gap-3 mb-2">
        <span
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold transition-colors",
            isActive
              ? "bg-brand-blue text-white"
              : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400",
          )}
        >
          {step}
        </span>
        <span
          className={cn(
            "transition-colors",
            isActive
              ? "text-brand-blue dark:text-brand-light-blue"
              : "text-gray-500 dark:text-gray-400",
          )}
        >
          {icon}
        </span>
      </div>
      <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-1">
        {title}
      </h3>
      <p className="text-sm text-gray-600 dark:text-gray-400">{description}</p>
      <div
        className={cn(
          "mt-3 overflow-hidden transition-all duration-300",
          isActive ? "max-h-96 opacity-100" : "max-h-0 opacity-0",
        )}
      >
        <div className="border-t border-gray-200 dark:border-gray-600 pt-3 text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          {detail}
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Score dimension data
// ---------------------------------------------------------------------------

const SCORE_DIMENSIONS = [
  {
    name: "Impact",
    icon: <Target className="h-5 w-5" />,
    color: "text-red-500 dark:text-red-400",
    bgColor: "bg-red-50 dark:bg-red-900/20",
    borderColor: "border-red-200 dark:border-red-800/40",
    description:
      "How significantly could this trend affect City of Austin operations, services, or residents? High scores indicate potential to reshape how departments function or deliver services.",
    example:
      "A new federal mandate on municipal cybersecurity requirements might score 85+.",
  },
  {
    name: "Relevance",
    icon: <CircleDot className="h-5 w-5" />,
    color: "text-brand-blue dark:text-brand-light-blue",
    bgColor: "bg-brand-light-blue/30 dark:bg-brand-blue/10",
    borderColor: "border-brand-blue/20 dark:border-brand-blue/30",
    description:
      "How closely does this opportunity align with Austin's strategic pillars and the CMO's Top 25 Priorities? Higher relevance means direct connection to ongoing city initiatives.",
    example:
      "A transit innovation in a similarly-sized city would score higher than one from a rural context.",
  },
  {
    name: "Velocity",
    icon: <Zap className="h-5 w-5" />,
    color: "text-amber-500 dark:text-amber-400",
    bgColor: "bg-amber-50 dark:bg-amber-900/20",
    borderColor: "border-amber-200 dark:border-amber-800/40",
    description:
      "How quickly is this trend accelerating or changing? Fast-moving opportunities require more urgent attention. Consider adoption rates, funding momentum, and regulatory timelines.",
    example:
      "Rapidly spreading legislation across states would score high on velocity.",
  },
  {
    name: "Novelty",
    icon: <Sparkles className="h-5 w-5" />,
    color: "text-purple-500 dark:text-purple-400",
    bgColor: "bg-purple-50 dark:bg-purple-900/20",
    borderColor: "border-purple-200 dark:border-purple-800/40",
    description:
      "How new or emerging is this opportunity? Novel topics represent genuinely new information that is not yet widely known or discussed in municipal circles.",
    example:
      "A first-of-its-kind pilot program would score higher than an incremental update to existing policy.",
  },
  {
    name: "Opportunity",
    icon: <TrendingUp className="h-5 w-5" />,
    color: "text-brand-green dark:text-brand-green",
    bgColor: "bg-brand-light-green/30 dark:bg-brand-green/10",
    borderColor: "border-brand-green/20 dark:border-brand-green/30",
    description:
      "What is the potential for positive action? Opportunities with high opportunity scores suggest areas where the city could gain an advantage, secure funding, or improve outcomes by acting early.",
    example:
      "A new federal grant program for smart city infrastructure would score high.",
  },
  {
    name: "Risk",
    icon: <Shield className="h-5 w-5" />,
    color: "text-orange-500 dark:text-orange-400",
    bgColor: "bg-orange-50 dark:bg-orange-900/20",
    borderColor: "border-orange-200 dark:border-orange-800/40",
    description:
      "What are the threats if this opportunity is ignored? High-risk scores indicate that inaction could lead to negative consequences -- regulatory penalties, missed deadlines, security vulnerabilities, or loss of public trust.",
    example:
      "An emerging cybersecurity vulnerability affecting municipal systems would score high.",
  },
];

// ---------------------------------------------------------------------------
// Filter type data
// ---------------------------------------------------------------------------

const FILTER_TYPES = [
  {
    name: "Strategic Pillars",
    icon: <Layers className="h-5 w-5" />,
    items: [
      {
        code: "CH",
        label: "Community Health",
        desc: "Public health, wellness, social services",
      },
      {
        code: "MC",
        label: "Mobility",
        desc: "Transportation, transit, infrastructure",
      },
      {
        code: "HS",
        label: "Housing",
        desc: "Affordability, development, homelessness",
      },
      {
        code: "EC",
        label: "Economic",
        desc: "Workforce, business development, innovation",
      },
      {
        code: "ES",
        label: "Environmental",
        desc: "Sustainability, climate, resilience",
      },
      {
        code: "CE",
        label: "Cultural",
        desc: "Arts, equity, community engagement",
      },
    ],
  },
  {
    name: "Time Horizons",
    icon: <Clock className="h-5 w-5" />,
    items: [
      {
        code: "H1",
        label: "Now (0-2 years)",
        desc: "Immediate impacts and near-term changes",
      },
      {
        code: "H2",
        label: "Near (2-5 years)",
        desc: "Medium-term trends requiring planning",
      },
      {
        code: "H3",
        label: "Far (5+ years)",
        desc: "Long-range opportunities and emerging possibilities",
      },
    ],
  },
  {
    name: "Maturity Stages",
    icon: <BarChart3 className="h-5 w-5" />,
    items: [
      { code: "1", label: "Concept", desc: "Early idea or proposal stage" },
      {
        code: "2",
        label: "Exploring",
        desc: "Active research and investigation",
      },
      {
        code: "3",
        label: "Pilot",
        desc: "Small-scale trial or proof of concept",
      },
      {
        code: "4",
        label: "PoC",
        desc: "Proof of concept with measured results",
      },
      { code: "5", label: "Implementing", desc: "Active rollout in progress" },
      {
        code: "6",
        label: "Scaling",
        desc: "Expanding beyond initial deployment",
      },
      { code: "7", label: "Mature", desc: "Established and widely adopted" },
      { code: "8", label: "Declining", desc: "Being phased out or superseded" },
    ],
  },
];

// ---------------------------------------------------------------------------
// Pipeline stages
// ---------------------------------------------------------------------------

const PIPELINE_STAGES = [
  {
    label: "Source Fetch",
    icon: <Rss className="h-5 w-5" />,
    desc: "Content is collected from 5 source categories: news agencies, academic databases, government publications, tech media, and RSS feeds.",
  },
  {
    label: "AI Triage",
    icon: <Brain className="h-5 w-5" />,
    desc: "GPT-4 analyzes each piece of content for relevance to Austin's strategic priorities, filtering out noise and off-topic material.",
  },
  {
    label: "Classification",
    icon: <Layers className="h-5 w-5" />,
    desc: "Relevant content is classified by strategic pillar, maturity stage, and time horizon using AI analysis.",
  },
  {
    label: "Scoring",
    icon: <BarChart3 className="h-5 w-5" />,
    desc: "Multi-factor scoring assigns 0-100 values for Impact, Relevance, Velocity, Novelty, Opportunity, and Risk. A composite Opportunity Quality Index (SQI) is computed.",
  },
  {
    label: "Deduplication",
    icon: <GitCompare className="h-5 w-5" />,
    desc: "Vector embeddings enable semantic similarity matching. Content that is too similar to existing opportunities (above 0.92 threshold) is merged or discarded.",
  },
  {
    label: "Published",
    icon: <CheckCircle className="h-5 w-5" />,
    desc: "Opportunities that pass all checks appear in the Discover library, ready for analysts to explore, follow, and act upon.",
  },
];

// ---------------------------------------------------------------------------
// Source categories
// ---------------------------------------------------------------------------

const SOURCE_CATEGORIES = [
  {
    name: "News",
    icon: <Newspaper className="h-5 w-5" />,
    examples: "Reuters, AP, GCN, GovTech",
    desc: "Breaking news and current events coverage with municipal relevance",
  },
  {
    name: "Academic",
    icon: <GraduationCap className="h-5 w-5" />,
    examples: "arXiv, research journals",
    desc: "Peer-reviewed research and pre-print publications",
  },
  {
    name: "Government",
    icon: <Landmark className="h-5 w-5" />,
    examples: ".gov domains, GAO, NIST",
    desc: "Official government publications, reports, and policy documents",
  },
  {
    name: "Tech Media",
    icon: <Cpu className="h-5 w-5" />,
    examples: "TechCrunch, Wired, The Verge",
    desc: "Technology news, product launches, and innovation coverage",
  },
  {
    name: "RSS Feeds",
    icon: <Rss className="h-5 w-5" />,
    examples: "Hacker News, Ars Technica",
    desc: "Curated feeds from specialized publications and aggregators",
  },
];

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function GuideDiscover() {
  const [activeStep, setActiveStep] = useState(0);
  const [expandedFilter, setExpandedFilter] = useState<string | null>(null);
  const [expandedScore, setExpandedScore] = useState<string | null>(null);

  return (
    <>
      {/* Print styles */}
      <style>{`
        @media print {
          [data-state="closed"] > [role="region"] {
            display: block !important;
            height: auto !important;
          }
          [data-radix-collection-item] svg.lucide-chevron-down {
            display: none !important;
          }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="min-h-screen bg-brand-faded-white dark:bg-brand-dark-blue">
        {/* ---------------------------------------------------------------- */}
        {/* Hero Header */}
        {/* ---------------------------------------------------------------- */}
        <div className="bg-gradient-to-r from-brand-blue via-brand-blue/90 to-brand-green">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
            <Link
              to="/discover"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-white/80 hover:text-white transition-colors mb-6 no-print"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Discover
            </Link>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-12 h-12 rounded-xl bg-white/15 flex items-center justify-center">
                <Compass className="h-6 w-6 text-white" />
              </div>
              <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                How to Use Discover
              </h1>
            </div>
            <p className="text-lg text-white/85 max-w-2xl leading-relaxed">
              Your guide to exploring GrantScope2's intelligence library -- from
              searching and filtering opportunities to building your personal
              watchlist and turning insights into action.
            </p>
          </div>
        </div>

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
          {/* ---------------------------------------------------------------- */}
          {/* Quick Start */}
          {/* ---------------------------------------------------------------- */}
          <section className="mb-14">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              Quick Start
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Four steps to get the most from the intelligence library. Click
              each step to learn more.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <QuickStartCard
                step={1}
                title="Browse"
                description="Open the Discover page and scan the opportunity grid."
                detail="The Discover page loads all published opportunities in a virtual grid. Scroll through to explore, or switch to list view for a denser layout. New and recently updated opportunities are highlighted."
                icon={<Eye className="h-5 w-5" />}
                isActive={activeStep === 0}
                onClick={() => setActiveStep(activeStep === 0 ? -1 : 0)}
              />
              <QuickStartCard
                step={2}
                title="Search"
                description="Use text or AI-powered semantic search."
                detail="Type keywords in the search bar for fast text matching. Toggle the AI Search switch for vector-based semantic search that finds conceptually related opportunities -- even when exact terms do not appear."
                icon={<Search className="h-5 w-5" />}
                isActive={activeStep === 1}
                onClick={() => setActiveStep(activeStep === 1 ? -1 : 1)}
              />
              <QuickStartCard
                step={3}
                title="Filter"
                description="Narrow results by pillar, horizon, stage, and scores."
                detail="Apply multi-dimensional filters to focus on exactly what matters to you. Combine strategic pillars, time horizons, maturity stages, score thresholds, quality tiers, and date ranges for precision results."
                icon={<Filter className="h-5 w-5" />}
                isActive={activeStep === 2}
                onClick={() => setActiveStep(activeStep === 2 ? -1 : 2)}
              />
              <QuickStartCard
                step={4}
                title="Follow"
                description="Follow opportunities to build your watchlist."
                detail="Click the star icon on any opportunity card to add it to your personal watchlist on the My Opportunities page. Followed opportunities surface updates and can be organized into research programs."
                icon={<Star className="h-5 w-5" />}
                isActive={activeStep === 3}
                onClick={() => setActiveStep(activeStep === 3 ? -1 : 3)}
              />
            </div>
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* Accordion Sections */}
          {/* ---------------------------------------------------------------- */}
          <Accordion.Root
            type="multiple"
            defaultValue={[]}
            className="divide-y divide-gray-200 dark:divide-gray-700 border-t border-b border-gray-200 dark:border-gray-700"
          >
            {/* -------------------------------------------------------------- */}
            {/* 1. The Intelligence Library */}
            {/* -------------------------------------------------------------- */}
            <Accordion.Item value="library" id="library">
              <AccordionTrigger icon={<BookOpen className="h-5 w-5" />}>
                The Intelligence Library
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  The Discover page is the central hub for all strategic grant
                  opportunities in GrantScope2. Every opportunity you see here
                  has been automatically discovered, classified, and scored by
                  the AI-powered discovery pipeline running behind the scenes.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                  Where Opportunities Come From
                </h4>
                <p className="mb-4">
                  GrantScope2 continuously monitors hundreds of sources across
                  five categories. Each source category brings a different lens
                  to the strategic landscape:
                </p>

                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-5">
                  {SOURCE_CATEGORIES.map((cat) => (
                    <div
                      key={cat.name}
                      className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-4"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-brand-blue dark:text-brand-light-blue">
                          {cat.icon}
                        </span>
                        <span className="font-semibold text-gray-900 dark:text-white text-sm">
                          {cat.name}
                        </span>
                      </div>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                        {cat.desc}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-500 italic">
                        {cat.examples}
                      </p>
                    </div>
                  ))}
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  What You See on Each Card
                </h4>
                <ul className="list-disc list-inside space-y-1 mb-3">
                  <li>
                    <span className="font-medium">Title and summary</span>{" "}
                    &mdash; a concise description of the opportunity
                  </li>
                  <li>
                    <span className="font-medium">Strategic pillar badge</span>{" "}
                    &mdash; which pillar(s) the opportunity aligns with
                  </li>
                  <li>
                    <span className="font-medium">Quality tier indicator</span>{" "}
                    &mdash; High, Moderate, or Needs Verification
                  </li>
                  <li>
                    <span className="font-medium">Horizon tag</span> &mdash; the
                    time horizon (H1, H2, or H3)
                  </li>
                  <li>
                    <span className="font-medium">Score highlights</span>{" "}
                    &mdash; key scoring dimensions visible at a glance
                  </li>
                  <li>
                    <span className="font-medium">Follow status</span> &mdash;
                    star icon indicates whether you are tracking this
                    opportunity
                  </li>
                </ul>

                <ProTip>
                  Use the quick filter chips at the top of Discover to rapidly
                  scope your view. "New This Week" shows opportunities
                  discovered in the last 7 days, while "Updated This Week"
                  catches recently re-scored or enriched opportunities you may
                  have already seen.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* -------------------------------------------------------------- */}
            {/* 2. Search & AI Search */}
            {/* -------------------------------------------------------------- */}
            <Accordion.Item value="search" id="search">
              <AccordionTrigger icon={<Search className="h-5 w-5" />}>
                Search and AI Search
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  Discover offers two search modes that complement each other.
                  The standard text search is fast and exact; the AI-powered
                  semantic search understands meaning and concepts.
                </p>

                <div className="grid sm:grid-cols-2 gap-4 mb-5">
                  {/* Standard Search */}
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <Search className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                      <h4 className="font-semibold text-gray-900 dark:text-white">
                        Standard Search
                      </h4>
                    </div>
                    <ul className="text-sm space-y-2 text-gray-700 dark:text-gray-300">
                      <li className="flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-brand-green flex-shrink-0 mt-0.5" />
                        <span>
                          Matches exact keywords in titles and summaries
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-brand-green flex-shrink-0 mt-0.5" />
                        <span>
                          Fast, with debounced input for smooth typing
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-brand-green flex-shrink-0 mt-0.5" />
                        <span>
                          Best for known terms, names, or specific topics
                        </span>
                      </li>
                    </ul>
                  </div>

                  {/* AI Search */}
                  <div className="rounded-lg border border-brand-blue/30 bg-brand-light-blue/20 dark:bg-brand-blue/10 dark:border-brand-blue/20 p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <Brain className="h-5 w-5 text-brand-blue dark:text-brand-light-blue" />
                      <h4 className="font-semibold text-gray-900 dark:text-white">
                        AI Search (Semantic)
                      </h4>
                    </div>
                    <ul className="text-sm space-y-2 text-gray-700 dark:text-gray-300">
                      <li className="flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-brand-blue flex-shrink-0 mt-0.5" />
                        <span>
                          Finds conceptually related opportunities using vector
                          embeddings
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-brand-blue flex-shrink-0 mt-0.5" />
                        <span>
                          Understands meaning -- "urban heat" finds "cooling
                          infrastructure"
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-brand-blue flex-shrink-0 mt-0.5" />
                        <span>
                          Best for exploratory queries and discovering
                          connections
                        </span>
                      </li>
                    </ul>
                  </div>
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  How AI Search Works
                </h4>
                <p className="mb-3">
                  When you toggle on AI Search, your query is converted into a
                  high-dimensional vector embedding using the same model that
                  encodes all opportunity content. The system then performs a
                  nearest-neighbor search in vector space, returning
                  opportunities that are semantically similar to your query --
                  even if they use entirely different vocabulary.
                </p>

                <InfoBox>
                  <span className="font-medium">When to use which:</span> Start
                  with standard search when you know exactly what you are
                  looking for. Switch to AI Search when exploring a broad topic,
                  looking for cross-cutting themes, or when standard search
                  returns too few results.
                </InfoBox>

                <ProTip title="Search Tips">
                  For AI Search, phrase your query as a concept or question
                  rather than isolated keywords. "How are cities adapting public
                  transit to autonomous vehicles" will yield richer results than
                  just "autonomous vehicles transit."
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* -------------------------------------------------------------- */}
            {/* 3. Filtering Your View */}
            {/* -------------------------------------------------------------- */}
            <Accordion.Item value="filtering" id="filtering">
              <AccordionTrigger
                icon={<SlidersHorizontal className="h-5 w-5" />}
              >
                Filtering Your View
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  Discover provides multi-dimensional filtering to help you
                  focus on exactly the opportunities that matter for your work.
                  Filters can be combined freely and are preserved in your saved
                  searches.
                </p>

                {/* Interactive filter type explorer */}
                <div className="space-y-3 mb-5">
                  {FILTER_TYPES.map((ft) => (
                    <div
                      key={ft.name}
                      className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface overflow-hidden"
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedFilter(
                            expandedFilter === ft.name ? null : ft.name,
                          )
                        }
                        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-dark-surface-elevated transition-colors"
                      >
                        <span className="text-brand-blue dark:text-brand-light-blue">
                          {ft.icon}
                        </span>
                        <span className="flex-1 font-semibold text-sm text-gray-900 dark:text-white">
                          {ft.name}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {ft.items.length} options
                        </span>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 text-gray-400 transition-transform duration-200",
                            expandedFilter === ft.name && "rotate-180",
                          )}
                        />
                      </button>
                      <div
                        className={cn(
                          "transition-all duration-300 overflow-hidden",
                          expandedFilter === ft.name
                            ? "max-h-[600px] opacity-100"
                            : "max-h-0 opacity-0",
                        )}
                      >
                        <div className="px-4 pb-4 pt-1">
                          <div className="flex flex-wrap gap-2">
                            {ft.items.map((item) => (
                              <div
                                key={item.code}
                                className="rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-dark-surface-elevated px-3 py-2 text-xs"
                              >
                                <span className="font-bold text-brand-blue dark:text-brand-light-blue">
                                  {item.code}
                                </span>
                                <span className="mx-1.5 text-gray-400">|</span>
                                <span className="font-medium text-gray-900 dark:text-white">
                                  {item.label}
                                </span>
                                {item.desc && (
                                  <p className="mt-1 text-gray-500 dark:text-gray-400">
                                    {item.desc}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Score Threshold Sliders
                </h4>
                <p className="mb-3">
                  Use the Impact, Relevance, and Novelty sliders to set minimum
                  score thresholds. Only opportunities meeting or exceeding all
                  thresholds will appear. This is useful for focusing on
                  high-impact or highly novel content.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Quality Tier Filter
                </h4>
                <div className="flex flex-wrap gap-2 mb-4">
                  {[
                    {
                      tier: "High",
                      color:
                        "bg-brand-green/10 text-brand-green border-brand-green/30",
                      desc: "Well-sourced, multiple corroborating references",
                    },
                    {
                      tier: "Moderate",
                      color:
                        "bg-amber-100/60 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400 border-amber-300/40",
                      desc: "Reasonable sourcing with some gaps",
                    },
                    {
                      tier: "Needs Verification",
                      color:
                        "bg-red-100/60 text-red-600 dark:bg-red-900/20 dark:text-red-400 border-red-300/40",
                      desc: "Limited sources, requires analyst review",
                    },
                  ].map((q) => (
                    <div
                      key={q.tier}
                      className={cn(
                        "rounded-md border px-3 py-2 text-xs",
                        q.color,
                      )}
                    >
                      <span className="font-semibold">{q.tier}</span>
                      <span className="ml-1.5 opacity-75">
                        &mdash; {q.desc}
                      </span>
                    </div>
                  ))}
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Quick Filter Chips
                </h4>
                <div className="flex flex-wrap gap-2 mb-4">
                  {[
                    {
                      label: "All Opportunities",
                      icon: <Eye className="h-3.5 w-3.5" />,
                    },
                    {
                      label: "New This Week",
                      icon: <Sparkles className="h-3.5 w-3.5" />,
                    },
                    {
                      label: "Updated This Week",
                      icon: <Clock className="h-3.5 w-3.5" />,
                    },
                  ].map((chip) => (
                    <span
                      key={chip.label}
                      className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 dark:border-gray-600 bg-white dark:bg-dark-surface px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300"
                    >
                      {chip.icon}
                      {chip.label}
                    </span>
                  ))}
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  Quick filter chips appear above the opportunity grid and let
                  you rapidly toggle between common views. "New This Week" and
                  "Updated This Week" surface fresh intelligence without
                  requiring manual date range filtering.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Date Range
                </h4>
                <p className="mb-1">
                  Constrain results to a specific creation or update window
                  using the date range picker. This is particularly useful for
                  reviewing what appeared during a specific period (e.g., a
                  council session or planning cycle).
                </p>

                <ProTip>
                  Combine filters strategically: set pillar to "MC" (Mobility),
                  horizon to "H1" (Now), and quality to "High" to see only the
                  most credible near-term transportation opportunities. Save
                  this combination for quick access later.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* -------------------------------------------------------------- */}
            {/* 4. Working with Signals */}
            {/* -------------------------------------------------------------- */}
            <Accordion.Item value="working" id="working">
              <AccordionTrigger icon={<Grid3X3 className="h-5 w-5" />}>
                Working with Opportunities
              </AccordionTrigger>
              <AccordionContent>
                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Grid and List Views
                </h4>
                <div className="grid sm:grid-cols-2 gap-4 mb-5">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Grid3X3 className="h-5 w-5 text-brand-blue dark:text-brand-light-blue" />
                      <span className="font-semibold text-sm text-gray-900 dark:text-white">
                        Grid View
                      </span>
                      <span className="ml-auto text-xs text-gray-500 dark:text-gray-400 italic">
                        default
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Cards arranged in a responsive grid. Best for visual
                      scanning and when you want to compare card badges, scores,
                      and pillar indicators at a glance.
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <List className="h-5 w-5 text-brand-blue dark:text-brand-light-blue" />
                      <span className="font-semibold text-sm text-gray-900 dark:text-white">
                        List View
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Compact rows with key metadata visible inline. Ideal for
                      scanning large result sets quickly and when working with
                      more data-dense analysis workflows.
                    </p>
                  </div>
                </div>
                <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
                  Both views use virtualized rendering -- only the opportunities
                  currently visible in your viewport are rendered, keeping the
                  page fast even with thousands of results.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Following and Unfollowing
                </h4>
                <p className="mb-3">
                  Click the{" "}
                  <Star className="inline-block h-4 w-4 text-amber-500" /> star
                  icon on any card to follow that opportunity. Following uses
                  optimistic updates -- the star fills immediately while the
                  request processes in the background. To unfollow, click the
                  star again.
                </p>
                <p className="mb-4">
                  Followed opportunities appear on your{" "}
                  <Link
                    to="/signals"
                    className="font-medium text-brand-blue dark:text-brand-light-blue hover:underline"
                  >
                    My Opportunities
                  </Link>{" "}
                  page, where you can organize, prioritize, and route them into
                  research programs.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Card Comparison Mode
                </h4>
                <p className="mb-3">
                  Need to evaluate two opportunities side by side? Activate
                  comparison mode by clicking the compare icon (
                  <GitCompare className="inline-block h-4 w-4 text-gray-500" />)
                  on any card. Select a second card to open the full comparison
                  view, which displays both opportunities with their complete
                  metadata, scores, and classifications aligned for easy visual
                  comparison.
                </p>

                <InfoBox>
                  <span className="font-medium">Navigating to detail:</span>{" "}
                  Click any opportunity's title or the "View" action to open its
                  full detail page, where you can see the complete analysis, all
                  source references, related opportunities, and the full scoring
                  breakdown.
                </InfoBox>

                <ProTip>
                  Comparison mode is especially useful for understanding why two
                  seemingly similar opportunities were scored differently.
                  Compare their source quality, recency, and pillar alignment to
                  see what drives the difference.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* -------------------------------------------------------------- */}
            {/* 5. Saved Searches */}
            {/* -------------------------------------------------------------- */}
            <Accordion.Item value="saved" id="saved">
              <AccordionTrigger icon={<Bookmark className="h-5 w-5" />}>
                Saved Searches
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  When you find a useful combination of search terms and
                  filters, save it for instant recall. Saved searches preserve
                  your full configuration: search text, AI search toggle, all
                  active filters, score thresholds, and sort order.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  How to Save a Search
                </h4>
                <ol className="list-decimal list-inside space-y-1.5 mb-4 text-sm">
                  <li>Configure your desired search and filter combination</li>
                  <li>
                    Click the{" "}
                    <Bookmark className="inline-block h-3.5 w-3.5 text-gray-500" />{" "}
                    bookmark icon in the search bar area
                  </li>
                  <li>Give your saved search a descriptive name</li>
                  <li>
                    Click "Save" -- your configuration is stored and accessible
                    from the Saved Searches sidebar
                  </li>
                </ol>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Managing Saved Searches
                </h4>
                <p className="mb-3">
                  Open the Saved Searches sidebar to see all your saved
                  configurations. From there you can:
                </p>
                <ul className="list-disc list-inside space-y-1 mb-4 text-sm">
                  <li>
                    <span className="font-medium">Load</span> &mdash; apply a
                    saved search to restore its full configuration
                  </li>
                  <li>
                    <span className="font-medium">Edit</span> &mdash; rename or
                    update the saved configuration
                  </li>
                  <li>
                    <span className="font-medium">Delete</span> &mdash; remove
                    saved searches you no longer need
                  </li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Search History
                </h4>
                <p className="mb-3">
                  GrantScope2 also keeps a history of your recent searches. Open
                  the Search History panel (
                  <History className="inline-block h-3.5 w-3.5 text-gray-500" />
                  ) to browse, restore, or clear past search sessions. This is
                  useful for retracing your research path or revisiting a query
                  you ran earlier in the day.
                </p>

                <ProTip title="When to Use Saved Searches">
                  Create saved searches for recurring analysis tasks. For
                  example, save a "Weekly Environmental Scan" with pillar set to
                  ES, quality to High, and date range to the last 7 days. Load
                  it each Monday for a consistent review workflow.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* -------------------------------------------------------------- */}
            {/* 6. The Discovery Pipeline */}
            {/* -------------------------------------------------------------- */}
            <Accordion.Item value="pipeline" id="pipeline">
              <AccordionTrigger icon={<Rss className="h-5 w-5" />}>
                The Discovery Pipeline
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-5">
                  Understanding how opportunities arrive in Discover helps you
                  interpret their quality and coverage. Here is the automated
                  pipeline that runs behind the scenes:
                </p>

                {/* Visual pipeline diagram */}
                <div className="relative mb-6">
                  <div className="space-y-0">
                    {PIPELINE_STAGES.map((stage, idx) => (
                      <div
                        key={stage.label}
                        className="relative flex items-start gap-4"
                      >
                        {/* Vertical connector line */}
                        {idx < PIPELINE_STAGES.length - 1 && (
                          <div className="absolute left-[19px] top-10 bottom-0 w-0.5 bg-gray-200 dark:bg-gray-700" />
                        )}
                        {/* Stage dot / icon */}
                        <div
                          className={cn(
                            "relative z-10 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border-2",
                            idx === PIPELINE_STAGES.length - 1
                              ? "border-brand-green bg-brand-green/10 text-brand-green"
                              : "border-brand-blue/40 bg-brand-light-blue/30 dark:bg-brand-blue/10 text-brand-blue dark:text-brand-light-blue",
                          )}
                        >
                          {stage.icon}
                        </div>
                        {/* Stage content */}
                        <div className="pb-6 pt-1.5">
                          <h4 className="font-semibold text-gray-900 dark:text-white text-sm">
                            {stage.label}
                          </h4>
                          <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5 leading-relaxed">
                            {stage.desc}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                  Source Categories in Detail
                </h4>
                <div className="overflow-x-auto mb-4">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-gray-300 dark:border-gray-600">
                        <th className="text-left py-2 pr-4 font-semibold text-gray-900 dark:text-gray-100">
                          Category
                        </th>
                        <th className="text-left py-2 pr-4 font-semibold text-gray-900 dark:text-gray-100">
                          Key Sources
                        </th>
                        <th className="text-left py-2 font-semibold text-gray-900 dark:text-gray-100">
                          Content Type
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      <tr>
                        <td className="py-2 pr-4 font-medium">News</td>
                        <td className="py-2 pr-4">Reuters, AP, GCN, GovTech</td>
                        <td className="py-2">
                          Breaking news, policy changes, event coverage
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-medium">Academic</td>
                        <td className="py-2 pr-4">arXiv, research journals</td>
                        <td className="py-2">
                          Peer-reviewed research, pre-prints, white papers
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-medium">Government</td>
                        <td className="py-2 pr-4">.gov domains, GAO, NIST</td>
                        <td className="py-2">
                          Official reports, regulations, guidelines
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-medium">Tech Media</td>
                        <td className="py-2 pr-4">
                          TechCrunch, Wired, The Verge
                        </td>
                        <td className="py-2">
                          Technology developments, product launches
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-medium">RSS</td>
                        <td className="py-2 pr-4">Hacker News, Ars Technica</td>
                        <td className="py-2">
                          Community-curated tech and science discussion
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <InfoBox>
                  <span className="font-medium">Deduplication explained:</span>{" "}
                  When multiple sources report on the same topic, GrantScope2
                  uses vector embeddings to detect semantic overlap. Content
                  above a 0.92 similarity threshold is either merged into an
                  existing opportunity (adding source diversity) or discarded,
                  keeping the library clean and non-redundant.
                </InfoBox>

                <ProTip>
                  The pipeline runs on a configurable schedule. If you notice a
                  gap in coverage for a specific topic area, consider creating a
                  user-generated opportunity or requesting a manual discovery
                  run through the admin settings.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* -------------------------------------------------------------- */}
            {/* 7. Score Dimensions */}
            {/* -------------------------------------------------------------- */}
            <Accordion.Item value="scores" id="scores">
              <AccordionTrigger icon={<BarChart3 className="h-5 w-5" />}>
                Understanding Score Dimensions
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  Every opportunity receives six independent scores on a 0-100
                  scale. These scores are computed by AI analysis and combined
                  into a composite Opportunity Quality Index (OQI). Click on any
                  dimension below to learn what it measures and how it is
                  calculated.
                </p>

                {/* Interactive score dimension cards */}
                <div className="grid sm:grid-cols-2 gap-3 mb-5">
                  {SCORE_DIMENSIONS.map((dim) => (
                    <button
                      key={dim.name}
                      type="button"
                      onClick={() =>
                        setExpandedScore(
                          expandedScore === dim.name ? null : dim.name,
                        )
                      }
                      className={cn(
                        "rounded-lg border text-left transition-all duration-200",
                        "hover:shadow-sm",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue",
                        expandedScore === dim.name
                          ? cn(dim.borderColor, dim.bgColor, "shadow-sm")
                          : "border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface",
                      )}
                    >
                      <div className="flex items-center gap-3 px-4 py-3">
                        <span className={dim.color}>{dim.icon}</span>
                        <span className="flex-1 font-semibold text-sm text-gray-900 dark:text-white">
                          {dim.name}
                        </span>
                        <span className="text-xs text-gray-400">0-100</span>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 text-gray-400 transition-transform duration-200",
                            expandedScore === dim.name && "rotate-180",
                          )}
                        />
                      </div>
                      <div
                        className={cn(
                          "overflow-hidden transition-all duration-300",
                          expandedScore === dim.name
                            ? "max-h-48 opacity-100"
                            : "max-h-0 opacity-0",
                        )}
                      >
                        <div className="px-4 pb-4 text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                          <p className="mb-2">{dim.description}</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400 italic">
                            Example: {dim.example}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Opportunity Quality Index (OQI)
                </h4>
                <p className="mb-3">
                  The OQI is a composite score that considers source authority,
                  source diversity, corroboration, recency, and municipal
                  specificity. It provides a single quality indicator at a
                  glance:
                </p>
                <div className="space-y-2 mb-4">
                  {[
                    {
                      range: "70-100",
                      tier: "High",
                      color: "bg-brand-green",
                      width: "85%",
                    },
                    {
                      range: "40-69",
                      tier: "Moderate",
                      color: "bg-extended-orange",
                      width: "55%",
                    },
                    {
                      range: "0-39",
                      tier: "Needs Verification",
                      color: "bg-extended-red",
                      width: "25%",
                    },
                  ].map((s) => (
                    <div
                      key={s.tier}
                      className="flex items-center gap-3 text-sm"
                    >
                      <span className="w-16 text-right font-semibold tabular-nums text-gray-700 dark:text-gray-300">
                        {s.range}
                      </span>
                      <div className="flex-1 h-3 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all duration-200",
                            s.color,
                          )}
                          style={{ width: s.width }}
                        />
                      </div>
                      <span className="text-gray-500 dark:text-gray-400 text-xs w-32">
                        {s.tier}
                      </span>
                    </div>
                  ))}
                </div>

                <ProTip>
                  Use score threshold sliders in the filter panel to surface
                  only opportunities above your minimum bar. Setting Impact
                  above 60 and Relevance above 50 is a good starting point for
                  focused analysis sessions.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* -------------------------------------------------------------- */}
            {/* 8. Review Queue & Run History */}
            {/* -------------------------------------------------------------- */}
            <Accordion.Item value="review" id="review">
              <AccordionTrigger icon={<AlertTriangle className="h-5 w-5" />}>
                Review Queue and Run History
              </AccordionTrigger>
              <AccordionContent>
                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Review Queue
                </h4>
                <p className="mb-3">
                  Not all discovered opportunities are published automatically.
                  Some are placed in the{" "}
                  <Link
                    to="/discover/queue"
                    className="font-medium text-brand-blue dark:text-brand-light-blue hover:underline"
                  >
                    Review Queue
                  </Link>{" "}
                  for human review -- typically opportunities with lower
                  confidence scores, ambiguous classification, or content from
                  unfamiliar sources.
                </p>

                <div className="grid sm:grid-cols-3 gap-3 mb-5">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-4 text-center">
                    <ThumbsUp className="h-6 w-6 text-brand-green mx-auto mb-2" />
                    <p className="font-semibold text-sm text-gray-900 dark:text-white">
                      Approve
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Publish opportunity to the Discover library
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-4 text-center">
                    <ThumbsDown className="h-6 w-6 text-red-500 mx-auto mb-2" />
                    <p className="font-semibold text-sm text-gray-900 dark:text-white">
                      Dismiss
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Remove as irrelevant or low quality
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-4 text-center">
                    <Eye className="h-6 w-6 text-brand-blue mx-auto mb-2" />
                    <p className="font-semibold text-sm text-gray-900 dark:text-white">
                      Review
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Inspect full detail before deciding
                    </p>
                  </div>
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Run History
                </h4>
                <p className="mb-3">
                  The{" "}
                  <Link
                    to="/discover/history"
                    className="font-medium text-brand-blue dark:text-brand-light-blue hover:underline"
                  >
                    Run History
                  </Link>{" "}
                  page shows a log of every discovery pipeline execution. Each
                  entry includes:
                </p>
                <ul className="list-disc list-inside space-y-1 mb-4 text-sm">
                  <li>Timestamp and duration of the discovery run</li>
                  <li>Number of sources scanned per category</li>
                  <li>Number of new opportunities created vs. deduplicated</li>
                  <li>Number of opportunities queued for review</li>
                  <li>Any errors or warnings encountered</li>
                </ul>

                <ProTip>
                  Check Run History when coverage feels sparse for a topic. If
                  recent runs show high deduplication rates, the topic may
                  already be well-covered. If they show errors for certain
                  source categories, it may indicate a temporary data issue.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* -------------------------------------------------------------- */}
            {/* 9. From Discovery to Action */}
            {/* -------------------------------------------------------------- */}
            <Accordion.Item value="workflow" id="workflow">
              <AccordionTrigger icon={<ArrowRight className="h-5 w-5" />}>
                From Discovery to Action
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-5">
                  Discover is the starting point of a workflow that turns raw
                  intelligence into strategic action. Here is how the pieces fit
                  together:
                </p>

                {/* Visual workflow */}
                <div className="flex flex-col sm:flex-row items-stretch gap-0 mb-6">
                  {[
                    {
                      step: "Discover",
                      desc: "Find opportunities",
                      icon: <Compass className="h-5 w-5" />,
                      color:
                        "border-brand-blue/40 bg-brand-light-blue/30 dark:bg-brand-blue/10",
                      textColor: "text-brand-blue dark:text-brand-light-blue",
                      active: true,
                    },
                    {
                      step: "Follow",
                      desc: "Build watchlist",
                      icon: <Star className="h-5 w-5" />,
                      color:
                        "border-amber-300/40 bg-amber-50 dark:bg-amber-900/10",
                      textColor: "text-amber-600 dark:text-amber-400",
                      active: false,
                    },
                    {
                      step: "My Opportunities",
                      desc: "Organize & manage",
                      icon: <BookOpen className="h-5 w-5" />,
                      color:
                        "border-purple-300/40 bg-purple-50 dark:bg-purple-900/10",
                      textColor: "text-purple-600 dark:text-purple-400",
                      active: false,
                    },
                    {
                      step: "Program",
                      desc: "Deep research",
                      icon: <Layers className="h-5 w-5" />,
                      color:
                        "border-brand-green/40 bg-brand-light-green/30 dark:bg-brand-green/10",
                      textColor: "text-brand-green dark:text-brand-green",
                      active: false,
                    },
                    {
                      step: "Brief",
                      desc: "Act on insights",
                      icon: <ExternalLink className="h-5 w-5" />,
                      color: "border-red-300/40 bg-red-50 dark:bg-red-900/10",
                      textColor: "text-red-500 dark:text-red-400",
                      active: false,
                    },
                  ].map((item, idx, arr) => (
                    <React.Fragment key={item.step}>
                      <div
                        className={cn(
                          "flex-1 rounded-lg border p-4 text-center",
                          item.color,
                          item.active && "ring-2 ring-brand-blue/30",
                        )}
                      >
                        <div className={cn("mx-auto mb-1.5", item.textColor)}>
                          {item.icon}
                        </div>
                        <p
                          className={cn(
                            "font-semibold text-sm",
                            item.active
                              ? "text-gray-900 dark:text-white"
                              : "text-gray-700 dark:text-gray-300",
                          )}
                        >
                          {item.step}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {item.desc}
                        </p>
                      </div>
                      {idx < arr.length - 1 && (
                        <div className="flex items-center justify-center py-2 sm:py-0 sm:px-1">
                          <ArrowRight className="h-4 w-4 text-gray-400 rotate-90 sm:rotate-0" />
                        </div>
                      )}
                    </React.Fragment>
                  ))}
                </div>

                <div className="space-y-4">
                  <div>
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
                      1. Discover
                    </h4>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      Browse the grant library, search for topics, and use
                      filters to surface the most relevant opportunities for
                      your area of responsibility. This is where you are now.
                    </p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
                      2. Follow
                    </h4>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      When you find an opportunity worth tracking, follow it.
                      Following is lightweight and reversible -- think of it as
                      adding a bookmark with intelligence updates.
                    </p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
                      3. My Opportunities
                    </h4>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      Your{" "}
                      <Link
                        to="/signals"
                        className="font-medium text-brand-blue dark:text-brand-light-blue hover:underline"
                      >
                        Opportunities page
                      </Link>{" "}
                      collects everything you follow. Review, prioritize, and
                      decide which opportunities warrant deeper investigation.
                    </p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
                      4. Program
                    </h4>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      Route high-priority opportunities into{" "}
                      <Link
                        to="/workstreams"
                        className="font-medium text-brand-blue dark:text-brand-light-blue hover:underline"
                      >
                        Programs
                      </Link>{" "}
                      for structured deep research. Programs provide kanban
                      boards, AI-assisted research, and team collaboration
                      tools.
                    </p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
                      5. Brief
                    </h4>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      Generate executive briefs from your research findings.
                      Briefs synthesize grant intelligence into actionable
                      summaries for decision-makers and leadership.
                    </p>
                  </div>
                </div>

                <ProTip title="Building an Effective Workflow">
                  Start broad in Discover, narrow with filters, follow liberally
                  in the early stages. Then use My Opportunities to periodically
                  prune and prioritize before routing the most actionable
                  opportunities into programs. This funnel approach ensures you
                  do not miss emerging opportunities while keeping your active
                  research focused.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>
          </Accordion.Root>

          {/* ---------------------------------------------------------------- */}
          {/* Footer CTA */}
          {/* ---------------------------------------------------------------- */}
          <section className="mt-14 no-print">
            <div className="rounded-xl border border-brand-blue/20 bg-gradient-to-r from-brand-blue/10 to-brand-green/10 p-6 sm:p-8">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                Continue Learning
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-5">
                Explore the other guide pages to master the complete GrantScope2
                workflow.
              </p>
              <div className="grid sm:grid-cols-3 gap-3">
                <Link
                  to="/guide/signals"
                  className="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-4 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 hover:border-brand-blue/30"
                >
                  <Star className="h-5 w-5 text-amber-500 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm text-gray-900 dark:text-white">
                      How to Use Opportunities
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      Manage your followed opportunities
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-gray-400 ml-auto" />
                </Link>
                <Link
                  to="/guide/workstreams"
                  className="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-4 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 hover:border-brand-blue/30"
                >
                  <Layers className="h-5 w-5 text-brand-green flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm text-gray-900 dark:text-white">
                      How to Use Programs
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      Deep research and collaboration
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-gray-400 ml-auto" />
                </Link>
                <Link
                  to="/"
                  className="flex items-center gap-3 rounded-lg border border-brand-blue/30 bg-brand-blue/5 dark:bg-brand-blue/10 p-4 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5"
                >
                  <BarChart3 className="h-5 w-5 text-brand-blue dark:text-brand-light-blue flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm text-gray-900 dark:text-white">
                      Dashboard
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      View your overview and metrics
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-gray-400 ml-auto" />
                </Link>
              </div>
            </div>
          </section>

          {/* Footer note */}
          <p className="mt-10 text-sm text-gray-400 dark:text-gray-500 text-center no-print">
            Questions about using Discover? Reach out to the GrantScope2 team.
          </p>
        </div>
      </div>
    </>
  );
}
