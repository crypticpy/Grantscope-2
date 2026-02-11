import React, { useState } from "react";
import * as Accordion from "@radix-ui/react-accordion";
import { Link } from "react-router-dom";
import {
  Radio,
  ChevronDown,
  ArrowLeft,
  Plus,
  Star,
  Filter,
  Search,
  Eye,
  Newspaper,
  GraduationCap,
  Landmark,
  Cpu,
  Rss,
  Zap,
  PenTool,
  Settings,
  ArrowRight,
  Lightbulb,
  CheckCircle,
  BookOpen,
  Layers,
  BarChart3,
  Target,
  Clock,
  Compass,
  Grid,
  List,
  Tag,
  Globe,
  FileText,
  Sparkles,
} from "lucide-react";
import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Accordion sub-components (matching Methodology page pattern)
// ---------------------------------------------------------------------------

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
// Pro Tip callout
// ---------------------------------------------------------------------------

interface ProTipProps {
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function ProTip({ children, defaultOpen = false }: ProTipProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="my-4 rounded-lg border border-amber-200 dark:border-amber-700/40 bg-amber-50/60 dark:bg-amber-900/10">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm font-medium text-amber-800 dark:text-amber-300 hover:text-amber-900 dark:hover:text-amber-200 transition-colors"
      >
        <Lightbulb className="h-4 w-4 shrink-0" aria-hidden />
        <span className="flex-1">Pro Tip</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-amber-500 transition-transform duration-200",
            isOpen && "rotate-180",
          )}
          aria-hidden
        />
      </button>
      {isOpen && (
        <div className="px-4 pb-3 text-sm text-amber-900 dark:text-amber-200/80 leading-relaxed">
          {children}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Quick Start step data
// ---------------------------------------------------------------------------

interface QuickStartStep {
  number: number;
  title: string;
  subtitle: string;
  icon: React.ElementType;
  detail: string;
  linkText: string;
  linkTo: string;
}

const QUICK_START_STEPS: QuickStartStep[] = [
  {
    number: 1,
    title: "Discover",
    subtitle: "Find emerging trends",
    icon: Compass,
    detail:
      "Browse the Discover page to explore AI-curated signals across all strategic pillars. The system continuously scans hundreds of sources to surface relevant trends, technologies, and issues for Austin.",
    linkText: "Go to Discover",
    linkTo: "/discover",
  },
  {
    number: 2,
    title: "Follow",
    subtitle: "Track what matters",
    icon: Eye,
    detail:
      "When you find a signal that matters to your work, follow it. Following adds the signal to your personal hub so you receive updates when new sources or analysis become available.",
    linkText: "Browse signals",
    linkTo: "/discover",
  },
  {
    number: 3,
    title: "Manage",
    subtitle: "Organize your signals",
    icon: Settings,
    detail:
      "Use filters, sorting, grouping, and pin/star to organize your signal collection. Group by pillar, horizon, or workstream to see patterns. Pin your highest-priority signals so they always appear first.",
    linkText: "View My Signals",
    linkTo: "/signals",
  },
  {
    number: 4,
    title: "Research",
    subtitle: "Go deeper",
    icon: BookOpen,
    detail:
      "Add signals to workstreams for structured research. The system runs deep research using AI to gather comprehensive analysis, then you can generate executive briefs for stakeholder communication.",
    linkText: "View Workstreams",
    linkTo: "/workstreams",
  },
];

// ---------------------------------------------------------------------------
// Source category explorer data
// ---------------------------------------------------------------------------

interface SourceCategory {
  id: string;
  label: string;
  icon: React.ElementType;
  color: string;
  bgColor: string;
  borderColor: string;
  description: string;
  examples: string[];
  bestFor: string;
}

const SOURCE_CATEGORIES: SourceCategory[] = [
  {
    id: "news",
    label: "News",
    icon: Newspaper,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-50 dark:bg-blue-900/20",
    borderColor: "border-blue-200 dark:border-blue-700/50",
    description:
      "Real-time coverage from major wire services and specialized government/technology publications. Provides the broadest and most timely view of emerging topics.",
    examples: ["Reuters", "AP News", "GCN", "GovTech", "StateScoop"],
    bestFor:
      "Tracking breaking developments, policy announcements, and industry-wide trends as they unfold.",
  },
  {
    id: "academic",
    label: "Academic",
    icon: GraduationCap,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-50 dark:bg-purple-900/20",
    borderColor: "border-purple-200 dark:border-purple-700/50",
    description:
      "Peer-reviewed research papers and preprints from academic databases. Delivers deep, evidence-based analysis with high source authority scores.",
    examples: ["arXiv (AI, ML, Computers & Society)", "Research databases"],
    bestFor:
      "Grounding signals in rigorous evidence, especially for technology feasibility and long-range horizon scanning.",
  },
  {
    id: "government",
    label: "Government",
    icon: Landmark,
    color: "text-emerald-600 dark:text-emerald-400",
    bgColor: "bg-emerald-50 dark:bg-emerald-900/20",
    borderColor: "border-emerald-200 dark:border-emerald-700/50",
    description:
      "Federal agency publications, standards, and reports from .gov domains. These sources carry the highest municipal-specificity scores in the quality index.",
    examples: ["GSA", "NIST", "Census Bureau", "HUD", "DOT", "EPA", "FCC"],
    bestFor:
      "Regulatory changes, federal funding opportunities, compliance requirements, and government technology standards.",
  },
  {
    id: "tech_blog",
    label: "Tech Blogs",
    icon: Cpu,
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-50 dark:bg-orange-900/20",
    borderColor: "border-orange-200 dark:border-orange-700/50",
    description:
      "Technology media and industry analysis from leading publications. Offers accessible explanations of complex technologies and adoption trends.",
    examples: ["TechCrunch", "Ars Technica", "Wired", "The Verge"],
    bestFor:
      "Early-stage technology scouting, understanding vendor landscapes, and tracking innovation velocity.",
  },
  {
    id: "rss",
    label: "Custom RSS",
    icon: Rss,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-50 dark:bg-amber-900/20",
    borderColor: "border-amber-200 dark:border-amber-700/50",
    description:
      "Your own curated RSS feeds for specialized or niche publications not covered by the default categories. Fully customizable during signal creation.",
    examples: [
      "Municipal blogs",
      "Niche industry feeds",
      "Internal newsletters",
    ],
    bestFor:
      "Monitoring hyper-specific domains, local government blogs, or specialized industry verticals.",
  },
];

// ---------------------------------------------------------------------------
// Workflow flow diagram data
// ---------------------------------------------------------------------------

interface FlowStep {
  label: string;
  sublabel: string;
  icon: React.ElementType;
  color: string;
}

const WORKFLOW_STEPS: FlowStep[] = [
  {
    label: "Dashboard",
    sublabel: "Overview",
    icon: BarChart3,
    color: "bg-indigo-500",
  },
  {
    label: "Discover",
    sublabel: "Browse signals",
    icon: Compass,
    color: "bg-blue-500",
  },
  {
    label: "Follow",
    sublabel: "Track signal",
    icon: Eye,
    color: "bg-cyan-500",
  },
  {
    label: "My Signals",
    sublabel: "Personal hub",
    icon: Radio,
    color: "bg-brand-blue",
  },
  {
    label: "Workstream",
    sublabel: "Organize",
    icon: Layers,
    color: "bg-violet-500",
  },
  {
    label: "Research",
    sublabel: "Deep dive",
    icon: BookOpen,
    color: "bg-emerald-500",
  },
  {
    label: "Brief",
    sublabel: "Share insights",
    icon: FileText,
    color: "bg-brand-green",
  },
];

// ---------------------------------------------------------------------------
// SQI bar (from Methodology pattern)
// ---------------------------------------------------------------------------

interface SqiBarProps {
  score: number;
  label: string;
}

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

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function GuideSignals() {
  const [activeStep, setActiveStep] = useState<number | null>(null);
  const [activeSource, setActiveSource] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-brand-faded-white dark:bg-brand-dark-blue">
      {/* ================================================================ */}
      {/* Hero Header                                                      */}
      {/* ================================================================ */}
      <div className="relative overflow-hidden bg-gradient-to-r from-brand-blue via-brand-blue/90 to-brand-green">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />
        <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
          {/* Back link */}
          <Link
            to="/signals"
            className="inline-flex items-center gap-1.5 text-sm text-white/70 hover:text-white transition-colors mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to My Signals
          </Link>

          <div className="flex items-center gap-3 mb-3">
            <Radio className="w-8 h-8 text-white/90" />
            <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              How to Use Signals
            </h1>
          </div>
          <p className="text-white/80 text-lg max-w-2xl leading-relaxed">
            Your personal intelligence hub for tracking emerging trends,
            technologies, and strategic issues. Learn how to discover, create,
            organize, and act on signals that matter to your work.
          </p>
        </div>
      </div>

      {/* ================================================================ */}
      {/* Main Content                                                      */}
      {/* ================================================================ */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
        {/* ============================================================== */}
        {/* Quick Start (always visible, not in accordion)                  */}
        {/* ============================================================== */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            Quick Start
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Four steps from discovery to action. Click each step to learn more.
          </p>

          {/* Step cards grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            {QUICK_START_STEPS.map((step) => {
              const Icon = step.icon;
              const isActive = activeStep === step.number;

              return (
                <button
                  key={step.number}
                  type="button"
                  onClick={() => setActiveStep(isActive ? null : step.number)}
                  className={cn(
                    "relative text-left rounded-xl border p-5 transition-all duration-200",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue",
                    isActive
                      ? "bg-brand-blue/10 dark:bg-brand-blue/20 border-brand-blue dark:border-brand-blue/60 shadow-md -translate-y-1"
                      : "bg-white dark:bg-[#2d3166] border-gray-200 dark:border-gray-700 hover:border-brand-blue/40 hover:shadow-sm",
                  )}
                >
                  {/* Step number badge */}
                  <div
                    className={cn(
                      "absolute -top-2.5 -left-2.5 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold",
                      isActive
                        ? "bg-brand-blue text-white"
                        : "bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300",
                    )}
                  >
                    {step.number}
                  </div>

                  <div
                    className={cn(
                      "inline-flex items-center justify-center w-10 h-10 rounded-lg mb-3",
                      isActive
                        ? "bg-brand-blue/20 text-brand-blue dark:text-brand-light-blue"
                        : "bg-gray-100 dark:bg-[#3d4176] text-gray-500 dark:text-gray-400",
                    )}
                  >
                    <Icon className="h-5 w-5" />
                  </div>

                  <h3
                    className={cn(
                      "font-semibold mb-0.5",
                      isActive
                        ? "text-brand-blue dark:text-brand-light-blue"
                        : "text-gray-900 dark:text-white",
                    )}
                  >
                    {step.title}
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {step.subtitle}
                  </p>
                </button>
              );
            })}
          </div>

          {/* Expanded detail for active step */}
          {activeStep !== null && (
            <div className="bg-white dark:bg-[#2d3166] rounded-xl border border-brand-blue/20 dark:border-brand-blue/30 p-5 animate-in fade-in-0 slide-in-from-top-2 duration-200">
              {(() => {
                const step = QUICK_START_STEPS.find(
                  (s) => s.number === activeStep,
                );
                if (!step) return null;
                const Icon = step.icon;
                return (
                  <div className="flex items-start gap-4">
                    <div className="flex items-center justify-center w-11 h-11 rounded-lg bg-brand-blue/10 dark:bg-brand-blue/20 shrink-0">
                      <Icon className="h-6 w-6 text-brand-blue dark:text-brand-light-blue" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-gray-900 dark:text-white mb-1">
                        Step {step.number}: {step.title}
                      </h4>
                      <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed mb-3">
                        {step.detail}
                      </p>
                      <Link
                        to={step.linkTo}
                        className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-blue dark:text-brand-light-blue hover:underline"
                      >
                        {step.linkText}
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </section>

        {/* ============================================================== */}
        {/* Accordion Sections                                              */}
        {/* ============================================================== */}
        <Accordion.Root
          type="multiple"
          defaultValue={[]}
          className="divide-y divide-gray-200 dark:divide-gray-700 border-t border-b border-gray-200 dark:border-gray-700"
        >
          {/* -------------------------------------------------------------- */}
          {/* 1. What Are Signals?                                            */}
          {/* -------------------------------------------------------------- */}
          <Accordion.Item value="what-are-signals" id="what-are-signals">
            <AccordionTrigger icon={<Radio className="h-5 w-5" />}>
              What Are Signals?
            </AccordionTrigger>
            <AccordionContent>
              <p className="mb-4">
                Signals are the atomic units of strategic intelligence in
                Foresight. Each signal tracks a single emerging trend,
                technology, policy shift, or issue that could impact City of
                Austin operations. Signals are continuously enriched with new
                sources, AI analysis, and quality scoring to keep your
                intelligence current.
              </p>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Strategic Pillars
              </h4>
              <p className="text-sm mb-3">
                Every signal is classified under one of six strategic pillars
                that align with Austin&rsquo;s priorities:
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-5">
                {[
                  { code: "CH", label: "Community Health" },
                  { code: "MC", label: "Mobility" },
                  { code: "HS", label: "Housing" },
                  { code: "EC", label: "Economic" },
                  { code: "ES", label: "Environmental" },
                  { code: "CE", label: "Cultural" },
                ].map(({ code, label }) => (
                  <div
                    key={code}
                    className="flex items-center gap-2 px-3 py-2 rounded-md bg-brand-blue/10 dark:bg-brand-blue/20 border border-brand-blue/15 dark:border-brand-blue/30"
                  >
                    <span className="text-xs font-mono font-bold text-brand-blue dark:text-brand-light-blue">
                      {code}
                    </span>
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      {label}
                    </span>
                  </div>
                ))}
              </div>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Time Horizons
              </h4>
              <p className="text-sm mb-3">
                Horizons indicate when a signal is likely to have its primary
                impact:
              </p>
              <div className="space-y-2 mb-5">
                {[
                  {
                    code: "H1",
                    label: "Now (0-2 years)",
                    desc: "Immediate or near-term impacts that require attention now.",
                  },
                  {
                    code: "H2",
                    label: "Near (2-5 years)",
                    desc: "Medium-term trends that should inform planning and strategy.",
                  },
                  {
                    code: "H3",
                    label: "Far (5+ years)",
                    desc: "Long-range developments to monitor for future positioning.",
                  },
                ].map(({ code, label, desc }) => (
                  <div
                    key={code}
                    className="flex items-start gap-3 px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#2d3166]"
                  >
                    <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-brand-blue/10 dark:bg-brand-blue/20 text-xs font-bold text-brand-blue dark:text-brand-light-blue shrink-0">
                      {code}
                    </span>
                    <div>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {label}
                      </span>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {desc}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Signal Quality Index (SQI)
              </h4>
              <p className="text-sm mb-3">
                Every signal receives a quality score from 0 to 100, computed
                from five dimensions: source authority, source diversity,
                corroboration, recency, and municipal specificity. Higher scores
                indicate more credible, well-sourced intelligence.
              </p>
              <div className="space-y-3 mb-3">
                <SqiBar score={85} label="High quality" />
                <SqiBar score={55} label="Moderate" />
                <SqiBar score={25} label="Needs review" />
              </div>

              <ProTip>
                Use the quality score filter on the Signals page to focus on
                high-confidence intelligence. A minimum threshold of 60 is a
                good starting point for strategic decisions.
              </ProTip>
            </AccordionContent>
          </Accordion.Item>

          {/* -------------------------------------------------------------- */}
          {/* 2. Your Personal Hub                                            */}
          {/* -------------------------------------------------------------- */}
          <Accordion.Item value="personal-hub" id="personal-hub">
            <AccordionTrigger icon={<Target className="h-5 w-5" />}>
              Your Personal Hub
            </AccordionTrigger>
            <AccordionContent>
              <p className="mb-4">
                The My Signals page is your personalized intelligence dashboard.
                It brings together signals from three different sources into one
                unified view:
              </p>

              <div className="space-y-3 mb-5">
                {[
                  {
                    icon: Eye,
                    title: "Followed Signals",
                    desc: "Signals you discovered and chose to track from the Discover page. Following a signal adds it to your hub and subscribes you to updates.",
                    badge: "Followed",
                    badgeClass:
                      "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800",
                  },
                  {
                    icon: PenTool,
                    title: "Created Signals",
                    desc: "Signals you created manually or via the quick-create wizard. These track topics you identified that were not yet in the system.",
                    badge: "Created",
                    badgeClass:
                      "bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800",
                  },
                  {
                    icon: Layers,
                    title: "Workstream Signals",
                    desc: "Signals that have been added to one or more of your research workstreams. These are actively being researched as part of a structured investigation.",
                    badge: "Workstream",
                    badgeClass:
                      "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-800",
                  },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={item.title}
                      className="flex items-start gap-4 px-4 py-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#2d3166]"
                    >
                      <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-gray-100 dark:bg-[#3d4176] shrink-0">
                        <Icon className="h-5 w-5 text-gray-500 dark:text-gray-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium text-gray-900 dark:text-gray-100 text-sm">
                            {item.title}
                          </h4>
                          <span
                            className={cn(
                              "inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded border",
                              item.badgeClass,
                            )}
                          >
                            {item.badge}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {item.desc}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Stats Row
              </h4>
              <p className="text-sm mb-3">
                At the top of the page, four stat cards give you an at-a-glance
                summary:
              </p>
              <div className="grid grid-cols-2 gap-3 mb-5">
                {[
                  {
                    label: "Total Signals",
                    desc: "Count of all signals in your hub",
                  },
                  {
                    label: "Followed / Created",
                    desc: "Breakdown by source type",
                  },
                  {
                    label: "Updated This Week",
                    desc: "Signals with fresh activity",
                  },
                  {
                    label: "Needs Research",
                    desc: "Low-source signals to investigate",
                  },
                ].map((stat) => (
                  <div
                    key={stat.label}
                    className="px-3 py-2.5 rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-[#2d3166]"
                  >
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {stat.label}
                    </span>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      {stat.desc}
                    </p>
                  </div>
                ))}
              </div>

              <ProTip>
                The &ldquo;Needs Research&rdquo; stat highlights signals with
                few sources. These are good candidates for adding to a
                workstream and running a deep research task.
              </ProTip>
            </AccordionContent>
          </Accordion.Item>

          {/* -------------------------------------------------------------- */}
          {/* 3. Creating Signals                                             */}
          {/* -------------------------------------------------------------- */}
          <Accordion.Item value="creating-signals" id="creating-signals">
            <AccordionTrigger icon={<Plus className="h-5 w-5" />}>
              Creating Signals
            </AccordionTrigger>
            <AccordionContent>
              <p className="mb-4">
                In addition to following signals from the Discover page, you can
                create new signals for topics not yet covered by the automated
                discovery pipeline. Click the{" "}
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  New Signal
                </span>{" "}
                button on the Signals page to open the creation wizard.
              </p>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                The 3-Step Wizard
              </h4>

              {/* Wizard steps visual */}
              <div className="flex items-center gap-2 mb-5">
                {[
                  { num: 1, label: "Define Signal" },
                  { num: 2, label: "Source Preferences" },
                  { num: 3, label: "Review & Create" },
                ].map((s, i) => (
                  <React.Fragment key={s.num}>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center justify-center w-7 h-7 rounded-full bg-brand-blue text-white text-xs font-semibold">
                        {s.num}
                      </div>
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300 hidden sm:inline">
                        {s.label}
                      </span>
                    </div>
                    {i < 2 && (
                      <div className="flex-1 h-0.5 bg-brand-blue/30 dark:bg-brand-blue/50 rounded-full" />
                    )}
                  </React.Fragment>
                ))}
              </div>

              {/* Step 1 detail */}
              <div className="mb-5">
                <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-brand-blue/10 text-brand-blue dark:text-brand-light-blue text-xs font-bold">
                    1
                  </span>
                  Define Signal
                </h4>
                <p className="text-sm mb-3">
                  Choose between two creation modes:
                </p>
                <div className="grid sm:grid-cols-2 gap-3 mb-3">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-white dark:bg-[#2d3166]">
                    <div className="flex items-center gap-2 mb-2">
                      <Zap className="h-4 w-4 text-brand-blue" />
                      <span className="font-medium text-sm text-gray-900 dark:text-gray-100">
                        Quick Create
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 dark:text-gray-400">
                      Enter a topic phrase (e.g., &ldquo;AI-powered traffic
                      signal optimization&rdquo;) and the system generates the
                      full signal using AI analysis. Optionally assign to a
                      workstream and get AI-suggested keywords.
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-white dark:bg-[#2d3166]">
                    <div className="flex items-center gap-2 mb-2">
                      <PenTool className="h-4 w-4 text-brand-blue" />
                      <span className="font-medium text-sm text-gray-900 dark:text-gray-100">
                        Manual Create
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 dark:text-gray-400">
                      Full control over signal name, description, strategic
                      pillar(s), horizon, maturity stage, and seed URLs. Use
                      this when you have specific classifications in mind.
                    </p>
                  </div>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  In Quick Create mode, click{" "}
                  <span className="font-medium text-gray-800 dark:text-gray-200">
                    Suggest Keywords
                  </span>{" "}
                  to have AI generate relevant monitoring terms based on your
                  topic phrase. You can add or remove keywords before
                  proceeding.
                </p>
              </div>

              {/* Step 2 detail */}
              <div className="mb-5">
                <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-brand-blue/10 text-brand-blue dark:text-brand-light-blue text-xs font-bold">
                    2
                  </span>
                  Source Preferences
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Configure which source categories to search, set a preferred
                  content type, add priority domains, custom RSS feeds, and
                  keywords for ongoing monitoring. See the{" "}
                  <span className="font-medium text-gray-800 dark:text-gray-200">
                    Source Preferences
                  </span>{" "}
                  section below for a detailed breakdown of each option.
                </p>
              </div>

              {/* Step 3 detail */}
              <div className="mb-4">
                <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-brand-blue/10 text-brand-blue dark:text-brand-light-blue text-xs font-bold">
                    3
                  </span>
                  Review & Create
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  Review your configuration and choose a research depth:
                </p>
                <div className="grid sm:grid-cols-2 gap-3">
                  <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#2d3166]">
                    <Search className="h-5 w-5 text-gray-400 shrink-0" />
                    <div>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Quick Scan
                      </span>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        ~5 sources, faster results
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#2d3166]">
                    <BookOpen className="h-5 w-5 text-gray-400 shrink-0" />
                    <div>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Deep Dive
                      </span>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        ~15 sources, comprehensive analysis
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <ProTip>
                Quick Create with a deep dive is the fastest way to generate a
                comprehensive signal. Start with a clear, specific topic phrase
                for best results &mdash; for example, &ldquo;autonomous shuttle
                pilots in mid-size cities&rdquo; rather than just
                &ldquo;autonomous vehicles.&rdquo;
              </ProTip>
            </AccordionContent>
          </Accordion.Item>

          {/* -------------------------------------------------------------- */}
          {/* 4. Source Preferences                                           */}
          {/* -------------------------------------------------------------- */}
          <Accordion.Item value="source-preferences" id="source-preferences">
            <AccordionTrigger icon={<Sparkles className="h-5 w-5" />}>
              Source Preferences
            </AccordionTrigger>
            <AccordionContent>
              <p className="mb-4">
                Source preferences determine where Foresight looks for
                information about your signal. Configuring these thoughtfully
                improves both the relevance and quality of the intelligence
                gathered. Click each category below to explore its details.
              </p>

              {/* Source Category Explorer */}
              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Source Categories
              </h4>
              <div className="space-y-2 mb-5">
                {SOURCE_CATEGORIES.map((cat) => {
                  const Icon = cat.icon;
                  const isActive = activeSource === cat.id;

                  return (
                    <div key={cat.id}>
                      <button
                        type="button"
                        onClick={() =>
                          setActiveSource(isActive ? null : cat.id)
                        }
                        className={cn(
                          "w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-all duration-150",
                          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue",
                          isActive
                            ? cn(cat.bgColor, cat.borderColor, "shadow-sm")
                            : "bg-white dark:bg-[#2d3166] border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600",
                        )}
                      >
                        <div
                          className={cn(
                            "flex items-center justify-center w-9 h-9 rounded-lg shrink-0",
                            isActive
                              ? cn(cat.bgColor)
                              : "bg-gray-100 dark:bg-[#3d4176]",
                          )}
                        >
                          <Icon
                            className={cn(
                              "h-5 w-5",
                              isActive
                                ? cat.color
                                : "text-gray-500 dark:text-gray-400",
                            )}
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <span
                            className={cn(
                              "text-sm font-medium",
                              isActive
                                ? cat.color
                                : "text-gray-900 dark:text-gray-100",
                            )}
                          >
                            {cat.label}
                          </span>
                        </div>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 shrink-0 text-gray-400 transition-transform duration-200",
                            isActive && "rotate-180",
                          )}
                          aria-hidden
                        />
                      </button>

                      {/* Expanded detail */}
                      {isActive && (
                        <div
                          className={cn(
                            "mt-1 ml-12 mr-2 px-4 py-3 rounded-lg border text-sm animate-in fade-in-0 slide-in-from-top-1 duration-150",
                            cat.bgColor,
                            cat.borderColor,
                          )}
                        >
                          <p className="text-gray-700 dark:text-gray-300 mb-3">
                            {cat.description}
                          </p>
                          <div className="mb-3">
                            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                              Example Sources
                            </span>
                            <div className="flex flex-wrap gap-1.5 mt-1">
                              {cat.examples.map((ex) => (
                                <span
                                  key={ex}
                                  className="inline-flex px-2 py-0.5 rounded-full bg-white/70 dark:bg-white/10 border border-gray-200/50 dark:border-gray-600/50 text-xs text-gray-700 dark:text-gray-300"
                                >
                                  {ex}
                                </span>
                              ))}
                            </div>
                          </div>
                          <div>
                            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                              Best For
                            </span>
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                              {cat.bestFor}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Additional Configuration
              </h4>
              <div className="space-y-3 mb-4">
                {[
                  {
                    icon: Globe,
                    title: "Priority Domains",
                    desc: "Specify domains (e.g., gartner.com, mckinsey.com) to weight higher in results. Content from these domains is boosted during triage.",
                  },
                  {
                    icon: Rss,
                    title: "Custom RSS Feeds",
                    desc: "Add RSS feed URLs for specialized or niche publications. These are fetched alongside the built-in source categories.",
                  },
                  {
                    icon: Tag,
                    title: "Keywords",
                    desc: "Define monitoring keywords that the system uses to filter and rank incoming content for relevance to your signal.",
                  },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={item.title}
                      className="flex items-start gap-3 px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#2d3166]"
                    >
                      <Icon className="h-4 w-4 text-gray-400 shrink-0 mt-0.5" />
                      <div>
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {item.title}
                        </span>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {item.desc}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>

              <ProTip>
                Enable at least two source categories for better corroboration
                scores. Signals with diverse sources score significantly higher
                on the Signal Quality Index than those relying on a single
                category.
              </ProTip>
            </AccordionContent>
          </Accordion.Item>

          {/* -------------------------------------------------------------- */}
          {/* 5. Filtering & Organizing                                       */}
          {/* -------------------------------------------------------------- */}
          <Accordion.Item value="filtering" id="filtering">
            <AccordionTrigger icon={<Filter className="h-5 w-5" />}>
              Filtering and Organizing
            </AccordionTrigger>
            <AccordionContent>
              <p className="mb-4">
                As your signal collection grows, the filtering and organization
                tools help you focus on what matters most. All filters work
                together and can be combined freely.
              </p>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Filter Options
              </h4>
              <div className="overflow-x-auto mb-5">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-gray-300 dark:border-gray-600">
                      <th className="text-left py-2 pr-4 font-semibold text-gray-900 dark:text-gray-100">
                        Filter
                      </th>
                      <th className="text-left py-2 font-semibold text-gray-900 dark:text-gray-100">
                        Options
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {[
                      {
                        filter: "Search",
                        options:
                          "Free-text search across signal names and summaries",
                      },
                      {
                        filter: "Pillar",
                        options: "CH, MC, HS, EC, ES, CE, or All Pillars",
                      },
                      {
                        filter: "Horizon",
                        options:
                          "H1 (0-2 years), H2 (2-5 years), H3 (5+ years), or All Horizons",
                      },
                      {
                        filter: "Source",
                        options:
                          "All Sources, Followed, Created by Me, In Workstreams",
                      },
                      {
                        filter: "Quality Score",
                        options:
                          "Slider from 0 to 100 to set a minimum threshold",
                      },
                    ].map((row) => (
                      <tr key={row.filter}>
                        <td className="py-2 pr-4 font-medium text-gray-800 dark:text-gray-200">
                          {row.filter}
                        </td>
                        <td className="py-2 text-gray-600 dark:text-gray-400">
                          {row.options}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Sorting
              </h4>
              <ul className="list-disc list-inside space-y-1 mb-5 text-sm">
                <li>
                  <span className="font-medium">Last Updated</span> &mdash;
                  Signals with the most recent activity appear first
                </li>
                <li>
                  <span className="font-medium">Date Followed</span> &mdash;
                  Most recently followed signals first
                </li>
                <li>
                  <span className="font-medium">Quality Score</span> &mdash;
                  Highest SQI scores first
                </li>
                <li>
                  <span className="font-medium">Name (A-Z)</span> &mdash;
                  Alphabetical ordering
                </li>
              </ul>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Grouping
              </h4>
              <p className="text-sm mb-3">
                Group your signals by one dimension to see clusters and
                patterns:
              </p>
              <div className="grid grid-cols-3 gap-3 mb-5">
                {[
                  {
                    label: "By Pillar",
                    desc: "See signals organized under their strategic pillars",
                  },
                  {
                    label: "By Horizon",
                    desc: "Separate short, medium, and long-range signals",
                  },
                  {
                    label: "By Workstream",
                    desc: "Signals grouped by research workstream",
                  },
                ].map((g) => (
                  <div
                    key={g.label}
                    className="px-3 py-2.5 rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-[#2d3166]"
                  >
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {g.label}
                    </span>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      {g.desc}
                    </p>
                  </div>
                ))}
              </div>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                View Modes and Pinning
              </h4>
              <div className="space-y-3 mb-4">
                <div className="flex items-start gap-3">
                  <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
                    <Grid className="h-4 w-4 text-brand-blue" />
                    <List className="h-4 w-4 text-gray-400" />
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    <span className="font-medium text-gray-800 dark:text-gray-200">
                      Grid and List views
                    </span>{" "}
                    &mdash; Switch between a card grid layout and a compact list
                    layout depending on your preference. Grid view shows full
                    summaries and badges; list view is denser for scanning many
                    signals quickly.
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <Star className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    <span className="font-medium text-gray-800 dark:text-gray-200">
                      Pin/Star signals
                    </span>{" "}
                    &mdash; Click the star icon on any signal card to pin it for
                    priority tracking. Pinned signals always appear at the top
                    of their group, regardless of sort order.
                  </p>
                </div>
              </div>

              <ProTip>
                Combine grouping by pillar with sorting by quality score to
                quickly identify the strongest signals in each strategic area.
                This is especially useful for preparing pillar-specific
                briefings.
              </ProTip>
            </AccordionContent>
          </Accordion.Item>

          {/* -------------------------------------------------------------- */}
          {/* 6. Integrating with Workflows                                   */}
          {/* -------------------------------------------------------------- */}
          <Accordion.Item value="workflows" id="workflows">
            <AccordionTrigger icon={<ArrowRight className="h-5 w-5" />}>
              Integrating with Workflows
            </AccordionTrigger>
            <AccordionContent>
              <p className="mb-5">
                Signals are designed to flow through a structured workflow from
                initial discovery to actionable intelligence. Here is how each
                stage connects:
              </p>

              {/* Visual flow diagram */}
              <div className="mb-6">
                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">
                  Intelligence Workflow
                </h4>

                {/* Desktop: horizontal flow */}
                <div className="hidden lg:flex items-center gap-1 overflow-x-auto pb-2">
                  {WORKFLOW_STEPS.map((step, i) => {
                    const Icon = step.icon;
                    return (
                      <React.Fragment key={step.label}>
                        <div className="flex flex-col items-center min-w-[90px]">
                          <div
                            className={cn(
                              "flex items-center justify-center w-12 h-12 rounded-xl text-white mb-2",
                              step.color,
                            )}
                          >
                            <Icon className="h-6 w-6" />
                          </div>
                          <span className="text-xs font-semibold text-gray-900 dark:text-gray-100 text-center">
                            {step.label}
                          </span>
                          <span className="text-[10px] text-gray-500 dark:text-gray-400 text-center">
                            {step.sublabel}
                          </span>
                        </div>
                        {i < WORKFLOW_STEPS.length - 1 && (
                          <ArrowRight className="h-4 w-4 text-gray-300 dark:text-gray-600 shrink-0 mx-1" />
                        )}
                      </React.Fragment>
                    );
                  })}
                </div>

                {/* Mobile/tablet: vertical flow */}
                <div className="lg:hidden space-y-0">
                  {WORKFLOW_STEPS.map((step, i) => {
                    const Icon = step.icon;
                    return (
                      <div key={step.label}>
                        <div className="flex items-center gap-3 py-2">
                          <div
                            className={cn(
                              "flex items-center justify-center w-10 h-10 rounded-lg text-white shrink-0",
                              step.color,
                            )}
                          >
                            <Icon className="h-5 w-5" />
                          </div>
                          <div>
                            <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                              {step.label}
                            </span>
                            <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                              {step.sublabel}
                            </span>
                          </div>
                        </div>
                        {i < WORKFLOW_STEPS.length - 1 && (
                          <div className="flex justify-center py-1">
                            <div className="w-0.5 h-4 bg-gray-200 dark:bg-gray-700 rounded-full" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Stage Details
              </h4>
              <ol className="list-decimal list-inside space-y-3 text-sm mb-4">
                <li>
                  <span className="font-medium">Dashboard</span> &mdash; Your
                  landing page shows aggregate metrics, recent activity, and top
                  signals across all pillars.
                </li>
                <li>
                  <span className="font-medium">Discover</span> &mdash; Browse
                  the full catalog of AI-curated signals. Filter by pillar,
                  horizon, and quality. Triage with bulk actions.
                </li>
                <li>
                  <span className="font-medium">Follow</span> &mdash; Add
                  promising signals to your personal hub with one click. This
                  creates a persistent subscription to updates.
                </li>
                <li>
                  <span className="font-medium">My Signals</span> &mdash; Your
                  organized collection. Filter, sort, group, and pin to manage
                  your intelligence portfolio.
                </li>
                <li>
                  <span className="font-medium">Workstream</span> &mdash; Move
                  signals into structured research workstreams. Use the kanban
                  board to track progress through investigation stages.
                </li>
                <li>
                  <span className="font-medium">Research</span> &mdash; Run
                  AI-powered deep research tasks that gather 10-15+ sources and
                  produce comprehensive analysis reports.
                </li>
                <li>
                  <span className="font-medium">Brief</span> &mdash; Generate
                  executive briefs from your researched signals for stakeholder
                  communication. Export as PDF, PowerPoint, or CSV.
                </li>
              </ol>

              <ProTip>
                Not every signal needs to complete the full workflow. Some
                signals are valuable simply as &ldquo;watch items&rdquo; on your
                Signals page. Reserve deep research and briefing for signals
                that require active strategic response.
              </ProTip>
            </AccordionContent>
          </Accordion.Item>

          {/* -------------------------------------------------------------- */}
          {/* 7. Tips & Best Practices                                        */}
          {/* -------------------------------------------------------------- */}
          <Accordion.Item value="tips" id="tips">
            <AccordionTrigger icon={<CheckCircle className="h-5 w-5" />}>
              Tips and Best Practices
            </AccordionTrigger>
            <AccordionContent>
              {/* Quality thresholds */}
              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Quality Thresholds
              </h4>
              <div className="space-y-2 mb-5">
                {[
                  {
                    range: "70-100",
                    label: "High confidence",
                    desc: "Well-sourced, corroborated intelligence suitable for strategic decisions and executive briefings.",
                    color:
                      "border-brand-green/30 bg-brand-light-green/20 dark:bg-brand-green/10",
                  },
                  {
                    range: "40-69",
                    label: "Moderate",
                    desc: "Useful for monitoring and planning. Consider running additional research to strengthen the evidence base.",
                    color:
                      "border-amber-200/50 bg-amber-50/50 dark:bg-amber-900/10",
                  },
                  {
                    range: "0-39",
                    label: "Needs attention",
                    desc: "Emerging or under-sourced signals. Good candidates for deep research tasks to gather more evidence.",
                    color: "border-red-200/50 bg-red-50/30 dark:bg-red-900/10",
                  },
                ].map((tier) => (
                  <div
                    key={tier.range}
                    className={cn("rounded-lg border p-4", tier.color)}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-semibold text-gray-900 dark:text-gray-100 tabular-nums">
                        SQI {tier.range}
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {tier.label}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {tier.desc}
                    </p>
                  </div>
                ))}
              </div>

              {/* Horizon strategy */}
              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Horizon Strategy
              </h4>
              <ul className="list-disc list-inside space-y-1.5 text-sm mb-5">
                <li>
                  <span className="font-medium">H1 signals</span> need the most
                  frequent attention. Review weekly and consider immediate
                  workstream assignment for action planning.
                </li>
                <li>
                  <span className="font-medium">H2 signals</span> benefit from
                  periodic deep research. Review monthly to identify signals
                  that are accelerating toward H1.
                </li>
                <li>
                  <span className="font-medium">H3 signals</span> are strategic
                  watches. Monitor quarterly and use the quality score trend to
                  detect early acceleration.
                </li>
              </ul>

              {/* When to create vs follow */}
              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                When to Create vs. Follow
              </h4>
              <div className="grid sm:grid-cols-2 gap-3 mb-5">
                <div className="rounded-lg border border-brand-blue/20 bg-brand-light-blue/20 dark:bg-brand-blue/10 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Eye className="h-4 w-4 text-brand-blue" />
                    <span className="text-sm font-semibold text-brand-blue dark:text-brand-light-blue">
                      Follow a signal when:
                    </span>
                  </div>
                  <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                    <li>&bull; The topic already exists in Discover</li>
                    <li>&bull; Existing sources and analysis are sufficient</li>
                    <li>
                      &bull; You want to track but not customize source
                      preferences
                    </li>
                  </ul>
                </div>
                <div className="rounded-lg border border-brand-green/20 bg-brand-light-green/20 dark:bg-brand-green/10 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Plus className="h-4 w-4 text-brand-green" />
                    <span className="text-sm font-semibold text-brand-compliant-green dark:text-brand-green">
                      Create a signal when:
                    </span>
                  </div>
                  <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                    <li>&bull; The topic does not exist yet in the system</li>
                    <li>
                      &bull; You need specific source preferences or keywords
                    </li>
                    <li>&bull; You have seed URLs to bootstrap the analysis</li>
                  </ul>
                </div>
              </div>

              {/* Naming conventions */}
              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Naming Conventions
              </h4>
              <ul className="list-disc list-inside space-y-1 text-sm mb-5">
                <li>
                  Use specific, descriptive names: &ldquo;AI-Powered Traffic
                  Signal Optimization&rdquo; not &ldquo;AI Traffic&rdquo;
                </li>
                <li>
                  Include geographic scope when relevant: &ldquo;Modular Housing
                  Pilots in Texas&rdquo;
                </li>
                <li>
                  Avoid acronyms unless universally understood within your team
                </li>
                <li>
                  For Quick Create, write topic phrases as you would describe
                  the topic to a colleague
                </li>
              </ul>

              {/* General best practices */}
              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                General Best Practices
              </h4>
              <div className="space-y-3 mb-4">
                {[
                  {
                    icon: Clock,
                    tip: "Review your signals weekly. Unfollow or archive signals that are no longer relevant to keep your hub focused.",
                  },
                  {
                    icon: Layers,
                    tip: "Add high-priority signals to workstreams early. Structured research yields better briefings than ad-hoc monitoring.",
                  },
                  {
                    icon: Star,
                    tip: "Pin no more than 5-7 signals at a time. If everything is a priority, nothing is. Reserve pins for your most active investigations.",
                  },
                  {
                    icon: Filter,
                    tip: "Save mental energy by using quality-score filtering. Set a minimum of 40 to reduce noise from under-sourced signals.",
                  },
                  {
                    icon: Compass,
                    tip: "Check the Discover page weekly for new signals. The AI continuously adds new intelligence that may be relevant to your work.",
                  },
                ].map((item, i) => {
                  const Icon = item.icon;
                  return (
                    <div key={i} className="flex items-start gap-3 text-sm">
                      <Icon className="h-4 w-4 text-brand-blue dark:text-brand-light-blue shrink-0 mt-0.5" />
                      <p className="text-gray-600 dark:text-gray-400">
                        {item.tip}
                      </p>
                    </div>
                  );
                })}
              </div>

              <ProTip defaultOpen>
                Combine horizon strategy with pillar grouping for the most
                effective scanning pattern. Group by pillar, then mentally scan
                each pillar across all three horizons. This ensures
                comprehensive coverage without missing emerging threats or
                opportunities in any strategic area.
              </ProTip>
            </AccordionContent>
          </Accordion.Item>
        </Accordion.Root>

        {/* ============================================================== */}
        {/* Footer CTA                                                      */}
        {/* ============================================================== */}
        <div className="mt-12 mb-4">
          {/* Related guides */}
          <div className="rounded-xl bg-gradient-to-r from-brand-blue/10 to-brand-green/10 dark:from-brand-blue/5 dark:to-brand-green/5 border border-brand-blue/20 dark:border-brand-blue/15 p-6">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
              Continue Learning
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Explore related guides to get the most out of Foresight.
            </p>
            <div className="grid sm:grid-cols-2 gap-3">
              <Link
                to="/guide/discover"
                className="flex items-center gap-3 px-4 py-3 rounded-lg bg-white dark:bg-[#2d3166] border border-gray-200 dark:border-gray-700 hover:border-brand-blue/40 hover:shadow-sm transition-all group"
              >
                <Compass className="h-5 w-5 text-brand-blue shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-900 dark:text-white group-hover:text-brand-blue dark:group-hover:text-brand-light-blue transition-colors">
                    How to Use Discover
                  </span>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Browse and triage AI-curated signals
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-gray-300 group-hover:text-brand-blue transition-colors shrink-0" />
              </Link>
              <Link
                to="/guide/workstreams"
                className="flex items-center gap-3 px-4 py-3 rounded-lg bg-white dark:bg-[#2d3166] border border-gray-200 dark:border-gray-700 hover:border-brand-blue/40 hover:shadow-sm transition-all group"
              >
                <Layers className="h-5 w-5 text-brand-blue shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-900 dark:text-white group-hover:text-brand-blue dark:group-hover:text-brand-light-blue transition-colors">
                    How to Use Workstreams
                  </span>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Organize structured research campaigns
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-gray-300 group-hover:text-brand-blue transition-colors shrink-0" />
              </Link>
            </div>
          </div>

          {/* Back to signals link */}
          <div className="mt-6 text-center">
            <Link
              to="/signals"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-brand-blue hover:bg-brand-dark-blue text-white font-medium rounded-xl transition-colors"
            >
              <Radio className="w-5 h-5" />
              Go to My Signals
            </Link>
          </div>

          <p className="mt-8 text-sm text-gray-400 dark:text-gray-500 text-center">
            Questions about signals or the methodology behind them?{" "}
            <Link
              to="/methodology"
              className="text-brand-blue dark:text-brand-light-blue hover:underline"
            >
              View the full methodology
            </Link>{" "}
            or reach out to the Foresight team.
          </p>
        </div>
      </div>
    </div>
  );
}
