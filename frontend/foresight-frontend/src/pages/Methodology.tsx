import React, { useEffect } from "react";
import { useLocation } from "react-router-dom";
import * as Accordion from "@radix-ui/react-accordion";
import {
  ChevronDown,
  Rss,
  ShieldCheck,
  Building2,
  Brain,
  PenSquare,
  MessageSquareHeart,
} from "lucide-react";
import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SqiBarProps {
  score: number;
  label: string;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Visual inline bar for SQI score examples. */
const SqiBar: React.FC<SqiBarProps> = ({ score, label }) => {
  const color =
    score >= 70
      ? "bg-brand-green"
      : score >= 40
        ? "bg-extended-orange"
        : "bg-extended-red";

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="w-20 text-right font-semibold tabular-nums text-gray-700 dark:text-gray-300">
        {score}/100
      </span>
      <div className="flex-1 h-3 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-gray-500 dark:text-gray-400 text-xs w-28">
        {label}
      </span>
    </div>
  );
};

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
      "overflow-hidden transition-all",
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

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const Methodology: React.FC = () => {
  const location = useLocation();

  // Scroll to hash anchor on mount or hash change
  useEffect(() => {
    if (location.hash) {
      const id = location.hash.replace("#", "");
      const timer = setTimeout(() => {
        const el = document.getElementById(id);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 150);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [location.hash]);

  // Map hash anchors to accordion section values for auto-opening.
  // Sub-section anchors (e.g. #sqi, #source-authority) map to their
  // parent accordion item so the correct section expands on navigation.
  const HASH_TO_SECTION: Record<string, string> = {
    sqi: "scoring",
    "source-authority": "scoring",
    "source-diversity": "scoring",
    corroboration: "scoring",
    recency: "scoring",
    "municipal-specificity": "scoring",
  };

  // Determine which section to open by default based on hash
  const hashId = location.hash ? location.hash.replace("#", "") : undefined;
  const defaultOpen = hashId ? (HASH_TO_SECTION[hashId] ?? hashId) : undefined;

  return (
    <>
      {/* Print styles: expand all accordion sections when printing */}
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
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
          {/* Page header */}
          <header className="mb-10">
            <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white tracking-tight">
              Methodology
            </h1>
            <p className="mt-3 text-lg text-gray-600 dark:text-gray-400 max-w-2xl leading-relaxed">
              How Foresight discovers, scores, and delivers strategic
              intelligence for the City of Austin.
            </p>
          </header>

          {/* Accordion sections */}
          <Accordion.Root
            type="multiple"
            defaultValue={defaultOpen ? [defaultOpen] : []}
            className="divide-y divide-gray-200 dark:divide-gray-700 border-t border-b border-gray-200 dark:border-gray-700"
          >
            {/* ---------------------------------------------------------- */}
            {/* 1. Pipeline */}
            {/* ---------------------------------------------------------- */}
            <Accordion.Item value="pipeline" id="pipeline">
              <AccordionTrigger icon={<Rss className="h-5 w-5" />}>
                How We Discover Information
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  Foresight continuously monitors hundreds of sources across
                  news, academic research, government publications, and
                  technology media. Our AI-powered pipeline fetches, validates,
                  and classifies content relevant to Austin's strategic
                  priorities.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Source Types
                </h4>
                <ul className="list-disc list-inside space-y-1 mb-4">
                  <li>
                    RSS feeds from curated publications and government outlets
                  </li>
                  <li>NewsAPI for real-time global news coverage</li>
                  <li>
                    Tavily web search for emerging topics not yet in traditional
                    feeds
                  </li>
                  <li>Academic databases for peer-reviewed research</li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Processing Safeguards
                </h4>
                <ul className="list-disc list-inside space-y-1">
                  <li>
                    <span className="font-medium">Update frequency</span>{" "}
                    &mdash; configurable per workstream to balance freshness and
                    volume
                  </li>
                  <li>
                    <span className="font-medium">Content validation</span>{" "}
                    &mdash; minimum content length and freshness filtering by
                    category
                  </li>
                  <li>
                    <span className="font-medium">Deduplication</span> &mdash;
                    semantic similarity matching (via vector embeddings)
                    prevents duplicate coverage across sources
                  </li>
                </ul>
              </AccordionContent>
            </Accordion.Item>

            {/* ---------------------------------------------------------- */}
            {/* 2. Scoring */}
            {/* ---------------------------------------------------------- */}
            <Accordion.Item value="scoring" id="scoring">
              <AccordionTrigger icon={<ShieldCheck className="h-5 w-5" />}>
                How We Score Quality (Source Quality Index)
              </AccordionTrigger>
              <AccordionContent>
                {/* Scroll target for /methodology#sqi deep links */}
                <div id="sqi" className="scroll-mt-4" />

                <p className="mb-4">
                  Every card receives a Source Quality Index (SQI) from
                  0&ndash;100, computed from five dimensions of source quality.
                  Higher scores indicate more credible, well-sourced
                  information.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                  SQI Components
                </h4>
                <div className="overflow-x-auto mb-6">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-gray-300 dark:border-gray-600">
                        <th className="text-left py-2 pr-4 font-semibold text-gray-900 dark:text-gray-100">
                          Component
                        </th>
                        <th className="text-left py-2 pr-4 font-semibold text-gray-900 dark:text-gray-100">
                          Weight
                        </th>
                        <th className="text-left py-2 font-semibold text-gray-900 dark:text-gray-100">
                          What It Measures
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      <tr id="source-authority" className="scroll-mt-4">
                        <td className="py-2 pr-4 font-medium">
                          Source Authority
                        </td>
                        <td className="py-2 pr-4 tabular-nums">30%</td>
                        <td className="py-2">Domain reputation tier scoring</td>
                      </tr>
                      <tr id="source-diversity" className="scroll-mt-4">
                        <td className="py-2 pr-4 font-medium">
                          Source Diversity
                        </td>
                        <td className="py-2 pr-4 tabular-nums">20%</td>
                        <td className="py-2">
                          Variety of source types referenced
                        </td>
                      </tr>
                      <tr id="corroboration" className="scroll-mt-4">
                        <td className="py-2 pr-4 font-medium">Corroboration</td>
                        <td className="py-2 pr-4 tabular-nums">20%</td>
                        <td className="py-2">
                          Number of independent story clusters
                        </td>
                      </tr>
                      <tr id="recency" className="scroll-mt-4">
                        <td className="py-2 pr-4 font-medium">Recency</td>
                        <td className="py-2 pr-4 tabular-nums">15%</td>
                        <td className="py-2">Source freshness and currency</td>
                      </tr>
                      <tr id="municipal-specificity" className="scroll-mt-4">
                        <td className="py-2 pr-4 font-medium">
                          Municipal Specificity
                        </td>
                        <td className="py-2 pr-4 tabular-nums">15%</td>
                        <td className="py-2">Government and local relevance</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                  Score Examples
                </h4>
                <div className="space-y-3">
                  <SqiBar score={85} label="High quality" />
                  <SqiBar score={55} label="Moderate" />
                  <SqiBar score={25} label="Low / needs review" />
                </div>
              </AccordionContent>
            </Accordion.Item>

            {/* ---------------------------------------------------------- */}
            {/* 3. Source Authority Tiers */}
            {/* ---------------------------------------------------------- */}
            <Accordion.Item value="tiers" id="tiers">
              <AccordionTrigger icon={<Building2 className="h-5 w-5" />}>
                Source Authority Tiers
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  We maintain a curated list of over 100 organizations
                  categorized into three credibility tiers. Tier ratings are
                  combined with user feedback and pipeline performance for a
                  composite reputation score.
                </p>

                <div className="space-y-5">
                  {/* Tier 1 */}
                  <div className="rounded-lg border border-brand-green/30 bg-brand-light-green/40 dark:bg-brand-green/10 dark:border-brand-green/20 p-4">
                    <h4 className="font-semibold text-brand-compliant-green dark:text-brand-green mb-1">
                      Tier 1 &mdash; Authoritative
                    </h4>
                    <p className="text-sm">
                      Gartner, McKinsey, RAND Corporation, federal agencies
                      (GAO, CBO, NIST), leading research universities (MIT,
                      Stanford, UT Austin)
                    </p>
                  </div>

                  {/* Tier 2 */}
                  <div className="rounded-lg border border-brand-blue/20 bg-brand-light-blue/40 dark:bg-brand-blue/10 dark:border-brand-blue/20 p-4">
                    <h4 className="font-semibold text-brand-blue dark:text-brand-light-blue mb-1">
                      Tier 2 &mdash; Credible
                    </h4>
                    <p className="text-sm">
                      Municipal associations (ICMA, NLC), innovation networks
                      (Bloomberg Cities, Ash Center), professional associations
                      (APA, ASCE)
                    </p>
                  </div>

                  {/* Tier 3 */}
                  <div className="rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 p-4">
                    <h4 className="font-semibold text-gray-700 dark:text-gray-300 mb-1">
                      Tier 3 &mdash; General
                    </h4>
                    <p className="text-sm">
                      Technology media (TechCrunch, Wired, Ars Technica), think
                      tanks, international organizations (OECD, World Bank)
                    </p>
                  </div>
                </div>

                <p className="mt-4 text-sm text-gray-500 dark:text-gray-400 italic">
                  Users can rate individual sources to adjust domain reputation
                  scores over time, ensuring the system evolves with the team's
                  expertise.
                </p>
              </AccordionContent>
            </Accordion.Item>

            {/* ---------------------------------------------------------- */}
            {/* 4. AI Analysis */}
            {/* ---------------------------------------------------------- */}
            <Accordion.Item value="analysis" id="analysis">
              <AccordionTrigger icon={<Brain className="h-5 w-5" />}>
                How AI Analyzes Content
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  We use GPT-4 to classify content across multiple dimensions
                  including strategic pillar alignment, maturity stage, time
                  horizon, and multi-factor scoring for impact, relevance,
                  velocity, novelty, opportunity, and risk.
                </p>

                <div className="grid sm:grid-cols-2 gap-6">
                  {/* Classification */}
                  <div>
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                      Strategic Pillars
                    </h4>
                    <div className="flex flex-wrap gap-2 text-xs">
                      {[
                        { code: "CH", label: "Community Health" },
                        { code: "EW", label: "Economic Workforce" },
                        { code: "HG", label: "Housing" },
                        { code: "HH", label: "Homelessness" },
                        { code: "MC", label: "Mobility" },
                        { code: "PS", label: "Public Safety" },
                      ].map(({ code, label }) => (
                        <span
                          key={code}
                          className="inline-flex items-center px-2 py-1 rounded bg-brand-blue/10 text-brand-blue dark:bg-brand-blue/20 dark:text-brand-light-blue font-medium"
                        >
                          {code}
                          <span className="ml-1 font-normal text-gray-500 dark:text-gray-400 hidden sm:inline">
                            {label}
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Maturity */}
                  <div>
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                      Maturity Stages
                    </h4>
                    <ol className="list-decimal list-inside text-sm space-y-0.5">
                      <li>Concept</li>
                      <li>Exploring</li>
                      <li>Pilot</li>
                      <li>Implementing</li>
                      <li>Scaling</li>
                      <li>Mature</li>
                    </ol>
                  </div>
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mt-5 mb-2">
                  Score Dimensions (0&ndash;100 each)
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                  {[
                    {
                      name: "Impact",
                      desc: "Potential effect on city operations",
                    },
                    {
                      name: "Relevance",
                      desc: "Alignment to Austin priorities",
                    },
                    { name: "Velocity", desc: "Speed of change or adoption" },
                    {
                      name: "Novelty",
                      desc: "How new or emerging the topic is",
                    },
                    {
                      name: "Opportunity",
                      desc: "Potential for positive action",
                    },
                    { name: "Risk", desc: "Threats if the topic is ignored" },
                  ].map(({ name, desc }) => (
                    <div
                      key={name}
                      className="rounded-md border border-gray-200 dark:border-gray-700 p-3"
                    >
                      <span className="font-medium text-gray-900 dark:text-gray-100">
                        {name}
                      </span>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {desc}
                      </p>
                    </div>
                  ))}
                </div>

                <p className="mt-4 text-sm text-gray-500 dark:text-gray-400 italic">
                  When AI parsing cannot determine a score with confidence, the
                  value is flagged as a default so analysts can review and
                  adjust manually.
                </p>
              </AccordionContent>
            </Accordion.Item>

            {/* ---------------------------------------------------------- */}
            {/* 5. User-Generated Content */}
            {/* ---------------------------------------------------------- */}
            <Accordion.Item value="user-content" id="user-content">
              <AccordionTrigger icon={<PenSquare className="h-5 w-5" />}>
                User-Generated Content
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  Users can create cards for topics not covered by automated
                  discovery. User-created cards are clearly labeled with their
                  origin and undergo the same quality assessment as discovered
                  cards.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Creation Modes
                </h4>
                <ul className="list-disc list-inside space-y-1 mb-4">
                  <li>
                    <span className="font-medium">Quick create</span> &mdash;
                    enter a topic phrase and the system generates the full card
                    via AI analysis
                  </li>
                  <li>
                    <span className="font-medium">Manual form</span> &mdash;
                    fill out structured fields for pillar, stage, summary, and
                    scores
                  </li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Additional Capabilities
                </h4>
                <ul className="list-disc list-inside space-y-1">
                  <li>
                    Exploratory cards for topics outside predefined pillars
                  </li>
                  <li>
                    Source seeding &mdash; users can provide URLs for AI
                    analysis and context gathering
                  </li>
                  <li>
                    All user-created cards are quality-scored once sources are
                    attached
                  </li>
                </ul>
              </AccordionContent>
            </Accordion.Item>

            {/* ---------------------------------------------------------- */}
            {/* 6. Feedback */}
            {/* ---------------------------------------------------------- */}
            <Accordion.Item value="feedback" id="feedback">
              <AccordionTrigger
                icon={<MessageSquareHeart className="h-5 w-5" />}
              >
                How Your Feedback Improves the System
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  When you rate sources, your ratings are aggregated into domain
                  reputation scores that directly influence how the discovery
                  pipeline prioritizes and filters content.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Feedback Mechanisms
                </h4>
                <ul className="list-disc list-inside space-y-1 mb-4">
                  <li>
                    <span className="font-medium">Quality rating</span> &mdash;
                    per-source rating on a 1&ndash;5 star scale
                  </li>
                  <li>
                    <span className="font-medium">Municipal relevance</span>{" "}
                    &mdash; High / Medium / Low / Not Relevant assessment
                  </li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  How Feedback Flows Back
                </h4>
                <ol className="list-decimal list-inside space-y-1">
                  <li>User rates a source on a card</li>
                  <li>
                    Ratings are aggregated nightly into domain composite scores
                  </li>
                  <li>
                    Higher-rated domains receive a boost during future triage,
                    surfacing their content more prominently
                  </li>
                  <li>
                    Lower-rated domains are de-prioritized, reducing noise over
                    time
                  </li>
                </ol>
              </AccordionContent>
            </Accordion.Item>
          </Accordion.Root>

          {/* Footer note */}
          <p className="mt-10 text-sm text-gray-400 dark:text-gray-500 text-center no-print">
            Questions about our methodology?{" "}
            <span className="text-brand-blue dark:text-brand-light-blue">
              Reach out to the Foresight team.
            </span>
          </p>
        </div>
      </div>
    </>
  );
};

export default Methodology;
