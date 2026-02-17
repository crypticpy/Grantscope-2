import React, { useState } from "react";
import * as Accordion from "@radix-ui/react-accordion";
import { cn } from "../lib/utils";
import { Link } from "react-router-dom";
import {
  FolderOpen,
  ChevronDown,
  ArrowLeft,
  Plus,
  Search,
  FileText,
  Download,
  Presentation,
  Clock,
  Zap,
  Brain,
  ArrowRight,
  Lightbulb,
  CheckCircle,
  BookOpen,
  RefreshCw,
  Archive,
  Eye,
  Star,
  GripVertical,
  Settings,
  Telescope,
  FileDown,
  Inbox,
  Filter,
  ClipboardList,
  Layers,
  BarChart3,
  Compass,
  Sparkles,
  GitBranch,
  Shield,
  Target,
  MousePointerClick,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Sub-components: Accordion
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

// ---------------------------------------------------------------------------
// Sub-components: Pro Tip Callout
// ---------------------------------------------------------------------------

function ProTip({
  children,
  title = "Pro Tip",
}: {
  children: React.ReactNode;
  title?: string;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="my-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl p-4">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 text-left text-sm font-semibold text-amber-600 dark:text-amber-400 transition-colors hover:text-amber-700 dark:hover:text-amber-300"
      >
        <Lightbulb className="h-4 w-4 flex-shrink-0 text-amber-600 dark:text-amber-400" />
        <span className="flex-1">{title}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform duration-200",
            expanded && "rotate-180",
          )}
        />
      </button>
      {expanded && (
        <div className="mt-2 text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          {children}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components: Quick Start Step Card
// ---------------------------------------------------------------------------

interface QuickStartStep {
  step: number;
  title: string;
  icon: React.ReactNode;
  description: string;
  details: string;
}

function QuickStartCard({ data }: { data: QuickStartStep }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <button
      type="button"
      onClick={() => setExpanded(!expanded)}
      className={cn(
        "relative flex flex-col items-center text-center p-5 rounded-xl border transition-all duration-200 cursor-pointer print:break-inside-avoid",
        "bg-white dark:bg-dark-surface",
        expanded
          ? "border-brand-blue shadow-lg shadow-brand-blue/10 dark:shadow-brand-blue/20 ring-1 ring-brand-blue/20"
          : "border-gray-200 dark:border-gray-700 hover:border-brand-blue/40 hover:shadow-md",
      )}
    >
      <div
        className={cn(
          "w-12 h-12 rounded-full flex items-center justify-center mb-3 transition-colors",
          expanded
            ? "bg-brand-blue text-white"
            : "bg-brand-blue/10 text-brand-blue dark:bg-brand-blue/20 dark:text-brand-light-blue",
        )}
      >
        {data.icon}
      </div>
      <span className="text-xs font-bold text-brand-blue dark:text-brand-light-blue uppercase tracking-wider mb-1">
        Step {data.step}
      </span>
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
        {data.title}
      </h3>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        {data.description}
      </p>
      {expanded && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600 w-full">
          <p className="text-xs text-gray-600 dark:text-gray-300 leading-relaxed text-left">
            {data.details}
          </p>
        </div>
      )}
      <ChevronDown
        className={cn(
          "absolute top-3 right-3 h-3.5 w-3.5 text-gray-400 transition-transform duration-200",
          expanded && "rotate-180",
        )}
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Sub-components: Interactive Kanban Diagram
// ---------------------------------------------------------------------------

interface KanbanColumnInfo {
  id: string;
  title: string;
  color: string;
  bgColor: string;
  icon: React.ReactNode;
  description: string;
  workflow: string;
  actions: string[];
}

const KANBAN_COLUMN_INFO: KanbanColumnInfo[] = [
  {
    id: "inbox",
    title: "Inbox",
    color: "text-gray-600 dark:text-gray-300",
    bgColor: "bg-gray-100 dark:bg-gray-700",
    icon: <Inbox className="h-4 w-4" />,
    description:
      "The landing zone for all new opportunities. Cards arrive here via auto-populate, manual additions from Discover, or program scans.",
    workflow:
      "Triage quickly: skim the opportunity, decide if it warrants further attention.",
    actions: ["Move to Screening or Archive", "Add notes for context"],
  },
  {
    id: "screening",
    title: "Screening",
    color: "text-yellow-700 dark:text-yellow-400",
    bgColor: "bg-yellow-100 dark:bg-yellow-900/30",
    icon: <Filter className="h-4 w-4" />,
    description:
      "Initial evaluation stage. Run a Quick Update to gather a concise 5-source research snapshot and decide if the opportunity is worth a deeper look.",
    workflow:
      "Read the quick update summary, then promote or dismiss the opportunity.",
    actions: ["Quick Update (5-source scan)", "Move to Research or Archive"],
  },
  {
    id: "research",
    title: "Research",
    color: "text-blue-700 dark:text-blue-400",
    bgColor: "bg-blue-100 dark:bg-blue-900/30",
    icon: <Search className="h-4 w-4" />,
    description:
      "Deep investigation stage. Trigger a Deep Dive for comprehensive AI research using 15+ sources. The system pulls from academic, government, and industry sources.",
    workflow:
      "Wait for research to complete, review findings, add your own notes.",
    actions: [
      "Deep Dive Research (15+ sources)",
      "Add contextual notes",
      "Move to Brief when ready",
    ],
  },
  {
    id: "brief",
    title: "Brief",
    color: "text-purple-700 dark:text-purple-400",
    bgColor: "bg-purple-100 dark:bg-purple-900/30",
    icon: <FileText className="h-4 w-4" />,
    description:
      "Leadership-ready stage. Generate an AI executive brief with structured sections. Preview, iterate with version history, then export as PDF or PowerPoint.",
    workflow:
      "Generate brief, review in the preview modal, export for stakeholders.",
    actions: [
      "Generate Executive Brief",
      "Preview & iterate versions",
      "Export as PDF or PPTX",
      "Bulk export for portfolios",
    ],
  },
  {
    id: "watching",
    title: "Watching",
    color: "text-green-700 dark:text-green-400",
    bgColor: "bg-green-100 dark:bg-green-900/30",
    icon: <Eye className="h-4 w-4" />,
    description:
      "Ongoing monitoring stage. Opportunities here have been briefed or are important enough to track. Use Check for Updates to poll for new developments periodically.",
    workflow:
      "Periodically check for updates; move back to Research if activity spikes.",
    actions: [
      "Check for Updates",
      "Move back to Research if needed",
      "Archive when no longer relevant",
    ],
  },
  {
    id: "archived",
    title: "Archived",
    color: "text-gray-500 dark:text-gray-400",
    bgColor: "bg-gray-100 dark:bg-gray-600",
    icon: <Archive className="h-4 w-4" />,
    description:
      "Completed or deprioritized opportunities. Archived cards remain accessible but do not appear in active workflows. You can always move them back if circumstances change.",
    workflow: "No active work needed. Reference for historical context.",
    actions: ["Restore to any column if needed"],
  },
];

function InteractiveKanban() {
  const [selectedColumn, setSelectedColumn] = useState<string | null>(null);
  const selected = KANBAN_COLUMN_INFO.find((c) => c.id === selectedColumn);

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
        Click on a column below to learn about its purpose, workflow, and
        available actions.
      </p>

      {/* Column strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {KANBAN_COLUMN_INFO.map((col, idx) => (
          <div key={col.id} className="relative">
            <button
              type="button"
              onClick={() =>
                setSelectedColumn(selectedColumn === col.id ? null : col.id)
              }
              className={cn(
                "w-full rounded-lg p-3 text-center transition-all duration-200 border-2",
                col.bgColor,
                selectedColumn === col.id
                  ? "border-brand-blue shadow-md scale-[1.02]"
                  : "border-transparent hover:border-brand-blue/30",
              )}
            >
              <div className={cn("mx-auto mb-1", col.color)}>{col.icon}</div>
              <div className="text-xs font-semibold text-gray-900 dark:text-white">
                {col.title}
              </div>
            </button>
            {idx < KANBAN_COLUMN_INFO.length - 1 && (
              <ArrowRight className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400 z-10" />
            )}
          </div>
        ))}
      </div>

      {/* Details panel */}
      {selected && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-5 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center gap-2 mb-3">
            <div
              className={cn(
                "p-1.5 rounded-lg",
                selected.bgColor,
                selected.color,
              )}
            >
              {selected.icon}
            </div>
            <h4 className="text-base font-semibold text-gray-900 dark:text-white">
              {selected.title}
            </h4>
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300 mb-3">
            {selected.description}
          </p>
          <div className="flex flex-col sm:flex-row gap-4 text-sm">
            <div className="flex-1">
              <h5 className="font-medium text-gray-900 dark:text-white mb-1">
                Workflow
              </h5>
              <p className="text-gray-600 dark:text-gray-400">
                {selected.workflow}
              </p>
            </div>
            <div className="flex-1">
              <h5 className="font-medium text-gray-900 dark:text-white mb-1">
                Available Actions
              </h5>
              <ul className="space-y-1">
                {selected.actions.map((action, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-1.5 text-gray-600 dark:text-gray-400"
                  >
                    <CheckCircle className="h-3.5 w-3.5 mt-0.5 text-brand-green flex-shrink-0" />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components: Research Comparison Table
// ---------------------------------------------------------------------------

function ResearchComparisonTable() {
  const [highlighted, setHighlighted] = useState<string | null>(null);

  const methods = [
    {
      id: "deep-dive",
      name: "Deep Dive",
      icon: <Brain className="h-4 w-4" />,
      sources: "15+ sources",
      duration: "3-8 minutes",
      depth: "Comprehensive",
      bestFor:
        "Full investigation of high-priority opportunities. Produces detailed research across academic, government, and industry sources.",
      column: "Research",
      color: "border-blue-500",
    },
    {
      id: "quick-update",
      name: "Quick Update",
      icon: <Zap className="h-4 w-4" />,
      sources: "5 sources",
      duration: "30-90 seconds",
      depth: "Surface",
      bestFor:
        "Rapid triage during screening. Provides a concise snapshot to decide if an opportunity warrants deeper research.",
      column: "Screening",
      color: "border-yellow-500",
    },
    {
      id: "check-updates",
      name: "Check for Updates",
      icon: <RefreshCw className="h-4 w-4" />,
      sources: "3-5 sources",
      duration: "20-60 seconds",
      depth: "Focused",
      bestFor:
        "Monitoring opportunities you are watching. Looks for new developments since the last research run.",
      column: "Watching",
      color: "border-green-500",
    },
  ];

  return (
    <div className="space-y-4">
      {/* Desktop table */}
      <div className="hidden sm:block overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-300 dark:border-gray-600">
              {["Method", "Sources", "Duration", "Depth", "Best For"].map(
                (header) => (
                  <th
                    key={header}
                    className="text-left py-2.5 pr-4 font-semibold text-gray-900 dark:text-gray-100"
                  >
                    {header}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {methods.map((m) => (
              <tr
                key={m.id}
                onMouseEnter={() => setHighlighted(m.id)}
                onMouseLeave={() => setHighlighted(null)}
                className={cn(
                  "transition-colors cursor-default",
                  highlighted === m.id &&
                    "bg-brand-blue/5 dark:bg-brand-blue/10",
                )}
              >
                <td className="py-2.5 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="text-brand-blue dark:text-brand-light-blue">
                      {m.icon}
                    </span>
                    <span className="font-medium">{m.name}</span>
                  </div>
                </td>
                <td className="py-2.5 pr-4 tabular-nums">{m.sources}</td>
                <td className="py-2.5 pr-4 tabular-nums">{m.duration}</td>
                <td className="py-2.5 pr-4">
                  <span
                    className={cn(
                      "inline-flex px-2 py-0.5 rounded-full text-xs font-medium",
                      m.depth === "Comprehensive" &&
                        "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
                      m.depth === "Surface" &&
                        "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
                      m.depth === "Focused" &&
                        "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
                    )}
                  >
                    {m.depth}
                  </span>
                </td>
                <td className="py-2.5 text-gray-600 dark:text-gray-400 text-xs leading-relaxed max-w-xs">
                  {m.bestFor}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="sm:hidden space-y-3">
        {methods.map((m) => (
          <div
            key={m.id}
            className={cn(
              "rounded-lg border-l-4 bg-white dark:bg-dark-surface p-4 shadow-sm",
              m.color,
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-brand-blue dark:text-brand-light-blue">
                {m.icon}
              </span>
              <span className="font-semibold text-gray-900 dark:text-white">
                {m.name}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs mb-2">
              <div>
                <span className="text-gray-500 dark:text-gray-400 block">
                  Sources
                </span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {m.sources}
                </span>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400 block">
                  Duration
                </span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {m.duration}
                </span>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400 block">
                  Column
                </span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {m.column}
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400">
              {m.bestFor}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components: Mock Brief Structure Preview
// ---------------------------------------------------------------------------

function BriefStructurePreview() {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const sections = [
    {
      id: "exec-summary",
      title: "Executive Summary",
      icon: <Star className="h-3.5 w-3.5" />,
      content:
        "A concise 2-3 paragraph overview highlighting the most important findings, immediate implications for the City of Austin, and recommended next steps. Written for leadership audiences who need the key takeaways quickly.",
    },
    {
      id: "current-state",
      title: "Current State of Technology / Trend",
      icon: <BarChart3 className="h-3.5 w-3.5" />,
      content:
        "Analysis of the current landscape: where the technology or trend stands today, key metrics and adoption rates, maturity level, and how it compares to alternatives. Includes data from authoritative sources.",
    },
    {
      id: "municipal-apps",
      title: "Municipal Applications",
      icon: <Target className="h-3.5 w-3.5" />,
      content:
        "Specific use cases for the City of Austin. Maps the opportunity to city departments, operational areas, and strategic priorities. Includes examples from peer cities and government agencies.",
    },
    {
      id: "implementation",
      title: "Implementation Considerations",
      icon: <Settings className="h-3.5 w-3.5" />,
      content:
        "Practical guidance on what it would take to adopt or respond to this opportunity. Covers timelines, resource requirements, integration with existing systems, and change management considerations.",
    },
    {
      id: "vendors",
      title: "Key Vendors & Partners",
      icon: <Layers className="h-3.5 w-3.5" />,
      content:
        "Landscape of solution providers, technology vendors, academic partners, and consulting firms relevant to this topic. Includes public-sector-friendly options and cooperative purchasing references where applicable.",
    },
    {
      id: "costs",
      title: "Cost & Budget Implications",
      icon: <BarChart3 className="h-3.5 w-3.5" />,
      content:
        "Estimated cost ranges, funding models (grants, bonds, shared services), ROI analysis, and total cost of ownership considerations. Calibrated for municipal budget constraints.",
    },
    {
      id: "risks",
      title: "Risks & Mitigation",
      icon: <Shield className="h-3.5 w-3.5" />,
      content:
        "Key risks including technical, political, legal, equity, and operational dimensions. Each risk is paired with a recommended mitigation strategy.",
    },
    {
      id: "future-outlook",
      title: "Future Outlook",
      icon: <Telescope className="h-3.5 w-3.5" />,
      content:
        "Where this opportunity is likely headed over the next 1, 3, and 5 years. Scenarios for different adoption trajectories and the implications for Austin if it acts early, on time, or late.",
    },
  ];

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface overflow-hidden">
      <div className="bg-gradient-to-r from-brand-blue/10 to-brand-green/10 dark:from-brand-blue/20 dark:to-brand-green/20 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-brand-blue dark:text-brand-light-blue" />
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            Typical Executive Brief Structure
          </span>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Click any section to see what it contains
        </p>
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
        {sections.map((section) => (
          <div key={section.id}>
            <button
              type="button"
              onClick={() =>
                setExpandedSection(
                  expandedSection === section.id ? null : section.id,
                )
              }
              className={cn(
                "w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors",
                expandedSection === section.id
                  ? "bg-brand-blue/5 dark:bg-brand-blue/10"
                  : "hover:bg-gray-50 dark:hover:bg-gray-700/30",
              )}
            >
              <span className="text-brand-blue dark:text-brand-light-blue">
                {section.icon}
              </span>
              <span className="text-sm font-medium text-gray-900 dark:text-white flex-1">
                {section.title}
              </span>
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 text-gray-400 transition-transform duration-200",
                  expandedSection === section.id && "rotate-180",
                )}
              />
            </button>
            {expandedSection === section.id && (
              <div className="px-4 pb-3 pl-11">
                <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                  {section.content}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components: Export Workflow Diagram
// ---------------------------------------------------------------------------

function ExportWorkflowDiagram() {
  const steps = [
    {
      title: "Cards in Brief Column",
      subtitle: "Researched & ready",
      icon: <ClipboardList className="h-5 w-5" />,
      color:
        "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400",
    },
    {
      title: "Generate Brief",
      subtitle: "AI synthesis",
      icon: <Brain className="h-5 w-5" />,
      color: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400",
    },
    {
      title: "Review & Iterate",
      subtitle: "Preview modal",
      icon: <Eye className="h-5 w-5" />,
      color:
        "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400",
    },
    {
      title: "Choose Format",
      subtitle: "PDF or PPTX",
      icon: <FileDown className="h-5 w-5" />,
      color:
        "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400",
    },
    {
      title: "Download",
      subtitle: "City of Austin branded",
      icon: <Download className="h-5 w-5" />,
      color:
        "bg-brand-blue/10 dark:bg-brand-blue/20 text-brand-blue dark:text-brand-light-blue",
    },
  ];

  return (
    <div className="flex flex-col sm:flex-row items-stretch gap-2 sm:gap-0">
      {steps.map((step, idx) => (
        <React.Fragment key={step.title}>
          <div className="flex-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-3 text-center">
            <div
              className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2",
                step.color,
              )}
            >
              {step.icon}
            </div>
            <div className="text-xs font-semibold text-gray-900 dark:text-white">
              {step.title}
            </div>
            <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
              {step.subtitle}
            </div>
          </div>
          {idx < steps.length - 1 && (
            <div className="flex items-center justify-center sm:px-1">
              <ArrowRight className="h-4 w-4 text-gray-400 hidden sm:block" />
              <ChevronDown className="h-4 w-4 text-gray-400 sm:hidden" />
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function GuideWorkstreams() {
  const quickStartSteps: QuickStartStep[] = [
    {
      step: 1,
      title: "Create Program",
      icon: <Plus className="h-5 w-5" />,
      description: "Define your research focus",
      details:
        "Name your program, write a description, select strategic pillars and goals, pick maturity stages and time horizons, and add keywords. These filters determine which opportunities are relevant to your research stream.",
    },
    {
      step: 2,
      title: "Populate",
      icon: <Sparkles className="h-5 w-5" />,
      description: "Add opportunities automatically or manually",
      details:
        "Use Auto-Populate for AI-matched opportunities from the existing database, run a Program Scan to discover fresh content from the web, or manually add opportunities from the Discover page. Opportunities land in your Inbox column.",
    },
    {
      step: 3,
      title: "Research",
      icon: <Search className="h-5 w-5" />,
      description: "Investigate with AI-powered tools",
      details:
        "Move opportunities through Screening (Quick Update) and Research (Deep Dive) columns. The AI pulls from 5 to 15+ sources to build comprehensive research packages. Add your own notes and context at every stage.",
    },
    {
      step: 4,
      title: "Export",
      icon: <Download className="h-5 w-5" />,
      description: "Generate briefs and presentations",
      details:
        "Generate AI executive briefs, preview and iterate with version history, then export as PDF documents or PowerPoint presentations with City of Austin branding. Use Bulk Export to create portfolio documents combining multiple briefs.",
    },
  ];

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
        {/* ================================================================ */}
        {/* Hero Header */}
        {/* ================================================================ */}
        <div className="bg-gradient-to-r from-brand-blue via-brand-blue/90 to-brand-green">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
            <Link
              to="/workstreams"
              className="no-print inline-flex items-center gap-1.5 text-sm text-white/80 hover:text-white transition-colors mb-6"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Programs
            </Link>
            <div className="flex items-start gap-4">
              <div className="hidden sm:flex w-12 h-12 rounded-xl bg-white/15 items-center justify-center flex-shrink-0">
                <FolderOpen className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                  How to Use Programs
                </h1>
                <p className="mt-3 text-lg text-white/80 max-w-2xl leading-relaxed">
                  Programs transform raw opportunities into structured research
                  and leadership-ready deliverables. This guide walks you
                  through every capability -- from creating your first program
                  to exporting polished executive presentations.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
          {/* ================================================================ */}
          {/* Quick Start (always visible) */}
          {/* ================================================================ */}
          <section className="mb-12">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              Quick Start
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              The four-step workflow from opportunity discovery to stakeholder
              presentation. Click any step to learn more.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {quickStartSteps.map((step) => (
                <QuickStartCard key={step.step} data={step} />
              ))}
            </div>
          </section>

          {/* ================================================================ */}
          {/* Accordion Sections */}
          {/* ================================================================ */}
          <Accordion.Root
            type="multiple"
            defaultValue={[]}
            className="divide-y divide-gray-200 dark:divide-gray-700 border-t border-b border-gray-200 dark:border-gray-700"
          >
            {/* ------------------------------------------------------------ */}
            {/* 1. What Are Workstreams? */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item
              value="what-are-workstreams"
              id="what-are-workstreams"
            >
              <AccordionTrigger icon={<FolderOpen className="h-5 w-5" />}>
                What Are Programs?
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  A{" "}
                  <strong className="text-brand-dark-blue dark:text-brand-light-blue">
                    Program
                  </strong>{" "}
                  is a personal research workspace for systematically
                  investigating a topic area that matters to your team. While
                  following opportunities on the Opportunities page gives you a
                  personal feed of updates, a program goes further: it provides
                  a structured research pipeline, AI-assisted deep dives,
                  executive brief generation, and polished export capabilities.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  How Programs Differ from Following Opportunities
                </h4>
                <div className="overflow-x-auto mb-4">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-gray-300 dark:border-gray-600">
                        <th className="text-left py-2 pr-4 font-semibold text-gray-900 dark:text-gray-100">
                          Capability
                        </th>
                        <th className="text-left py-2 pr-4 font-semibold text-gray-900 dark:text-gray-100">
                          Following Opportunities
                        </th>
                        <th className="text-left py-2 font-semibold text-gray-900 dark:text-gray-100">
                          Programs
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      <tr>
                        <td className="py-2 pr-4 font-medium">Track updates</td>
                        <td className="py-2 pr-4">
                          <CheckCircle className="h-4 w-4 text-brand-green inline" />
                        </td>
                        <td className="py-2">
                          <CheckCircle className="h-4 w-4 text-brand-green inline" />
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-medium">
                          Kanban workflow
                        </td>
                        <td className="py-2 pr-4 text-gray-400">--</td>
                        <td className="py-2">
                          <CheckCircle className="h-4 w-4 text-brand-green inline" />
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-medium">
                          AI deep research
                        </td>
                        <td className="py-2 pr-4 text-gray-400">--</td>
                        <td className="py-2">
                          <CheckCircle className="h-4 w-4 text-brand-green inline" />
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-medium">
                          Executive briefs
                        </td>
                        <td className="py-2 pr-4 text-gray-400">--</td>
                        <td className="py-2">
                          <CheckCircle className="h-4 w-4 text-brand-green inline" />
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-medium">
                          PDF / PPTX export
                        </td>
                        <td className="py-2 pr-4 text-gray-400">--</td>
                        <td className="py-2">
                          <CheckCircle className="h-4 w-4 text-brand-green inline" />
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-medium">
                          Scoped discovery scans
                        </td>
                        <td className="py-2 pr-4 text-gray-400">--</td>
                        <td className="py-2">
                          <CheckCircle className="h-4 w-4 text-brand-green inline" />
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  When to Create a Program
                </h4>
                <ul className="list-disc list-inside space-y-1 mb-4">
                  <li>
                    You need to prepare a briefing, memo, or presentation for
                    leadership
                  </li>
                  <li>
                    A topic requires structured investigation across multiple
                    opportunities
                  </li>
                  <li>
                    Your team is tracking an emerging area that aligns with one
                    or more strategic pillars
                  </li>
                  <li>
                    You want automated, ongoing discovery scans scoped to a
                    specific focus area
                  </li>
                  <li>
                    You need to produce a portfolio of briefs on related topics
                  </li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Strategic Alignment
                </h4>
                <p>
                  Every program can be aligned to Austin's strategic pillars
                  (Community Health, Mobility, Housing, Economic, Environmental,
                  Cultural) and the CMO's Top 25 Priorities. This alignment
                  helps the AI surface the most relevant opportunities and
                  ensures briefs frame findings in terms of the city's goals.
                </p>
              </AccordionContent>
            </Accordion.Item>

            {/* ------------------------------------------------------------ */}
            {/* 2. Creating a Workstream */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item value="creating" id="creating">
              <AccordionTrigger icon={<Plus className="h-5 w-5" />}>
                Creating a Program
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  From the Programs page, click the <strong>New Program</strong>{" "}
                  button in the top right. A modal will appear with the
                  following fields:
                </p>

                <div className="space-y-4 mb-6">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                      1. Name & Description
                    </h4>
                    <p className="text-sm mb-2">
                      Choose a clear, specific name that describes the research
                      focus. The description provides context for anyone
                      reviewing your programs.
                    </p>
                    <div className="bg-gray-50 dark:bg-dark-surface-elevated rounded-md p-3 text-sm">
                      <div className="font-medium text-gray-900 dark:text-white mb-1">
                        Good examples:
                      </div>
                      <ul className="list-disc list-inside text-gray-600 dark:text-gray-400 space-y-0.5 text-xs">
                        <li>
                          "Smart Mobility Innovations" -- clear, scoped topic
                        </li>
                        <li>
                          "Climate Resilience Technology" -- specific domain
                          focus
                        </li>
                        <li>
                          "AI in Municipal Services Q1 2026" -- time-bounded
                          research
                        </li>
                      </ul>
                    </div>
                  </div>

                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                      2. Strategic Pillars & Goals
                    </h4>
                    <p className="text-sm">
                      Select one or more strategic pillars (e.g., Mobility,
                      Community Health) and optionally drill down to specific
                      strategic goals within those pillars. This determines the
                      strategic lens through which opportunities are evaluated
                      and filtered.
                    </p>
                  </div>

                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                      3. Maturity Stages & Time Horizon
                    </h4>
                    <p className="text-sm">
                      Filter by maturity stage (1 = Concept through 8 =
                      Declining) and time horizon (H1: now-2 years, H2: 2-5
                      years, H3: 5+ years). For forward-looking research,
                      combine early-stage maturity with H2/H3 horizons to
                      capture emerging opportunities.
                    </p>
                  </div>

                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                      4. Keywords
                    </h4>
                    <p className="text-sm">
                      Add keywords to fine-tune what opportunities match this
                      program. Keywords are used by both the auto-populate
                      function and program scans to find relevant content.
                    </p>
                  </div>
                </div>

                <ProTip>
                  Start focused, then expand. A narrow program with 3-5 specific
                  keywords will surface higher-quality results than a broad one.
                  You can always edit the filters later from the "Edit Filters"
                  button on the Kanban board.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* ------------------------------------------------------------ */}
            {/* 3. The Kanban Board */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item value="kanban" id="kanban">
              <AccordionTrigger icon={<ClipboardList className="h-5 w-5" />}>
                The Kanban Board
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  Each program has a six-column Kanban board that represents the
                  full lifecycle of a research opportunity. Cards move from left
                  to right as they progress through investigation, and each
                  column unlocks specific AI-powered actions.
                </p>

                <InteractiveKanban />

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mt-6 mb-2">
                  Moving Cards
                </h4>
                <ul className="list-disc list-inside space-y-1 mb-4">
                  <li>
                    <strong>Drag and drop</strong> -- Click and hold a card,
                    then drag it to another column. Release to drop it in
                    position.
                  </li>
                  <li>
                    <strong>Context menu</strong> -- Open the card's action menu
                    (three-dot icon) and select "Move to..." to choose the
                    destination column.
                  </li>
                  <li>
                    <strong>Within-column reordering</strong> -- Drag cards up
                    or down within the same column to change their priority
                    order.
                  </li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Card Actions Available Everywhere
                </h4>
                <ul className="list-disc list-inside space-y-1">
                  <li>
                    <strong>Notes</strong> -- Add context-specific notes to any
                    card. Notes are scoped to this program and do not appear on
                    other programs that include the same opportunity.
                  </li>
                  <li>
                    <strong>Remove</strong> -- Remove a card from this program.
                    The underlying opportunity is not deleted and can be
                    re-added later.
                  </li>
                  <li>
                    <strong>View Details</strong> -- Click the card to navigate
                    to the full opportunity detail page.
                  </li>
                </ul>

                <ProTip title="Keyboard Accessibility">
                  The Kanban board supports keyboard navigation. Use Tab to
                  focus cards, Enter to activate drag mode, and arrow keys to
                  move cards between columns. Press Escape to cancel a drag
                  operation.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* ------------------------------------------------------------ */}
            {/* 4. Populating Your Workstream */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item value="populating" id="populating">
              <AccordionTrigger icon={<Sparkles className="h-5 w-5" />}>
                Populating Your Program
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  There are three ways to add opportunities to your program,
                  each suited to different situations:
                </p>

                <div className="space-y-4 mb-6">
                  {/* Auto-Populate */}
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="p-1.5 bg-green-100 dark:bg-green-900/30 rounded-lg">
                        <Sparkles className="h-4 w-4 text-green-600 dark:text-green-400" />
                      </div>
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                        Auto-Populate
                      </h4>
                      <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded-full">
                        Recommended First
                      </span>
                    </div>
                    <p className="text-sm mb-2">
                      The AI scans the existing opportunity database and matches
                      cards to your program's filters (pillars, keywords,
                      stages, horizon). Matched opportunities are added directly
                      to your Inbox.
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      <strong>When to use:</strong> When you first create a
                      program, or when you want to check if any recently
                      discovered opportunities match your focus area. This
                      happens automatically when you open the Kanban board.
                    </p>
                  </div>

                  {/* Workstream Scan */}
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="p-1.5 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                        <Telescope className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      </div>
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                        Program Scan
                      </h4>
                      <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded-full">
                        New Content
                      </span>
                    </div>
                    <p className="text-sm mb-2">
                      Triggers a targeted discovery scan that searches the web
                      for fresh content matching your program's keywords and
                      pillars. Newly discovered opportunities are created and
                      added to your Inbox.
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      <strong>When to use:</strong> When you need the latest
                      information that may not be in the database yet. Limited
                      to 2 scans per day per program. Requires at least keywords
                      or pillars to be configured.
                    </p>
                  </div>

                  {/* Manual Add */}
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="p-1.5 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                        <MousePointerClick className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                      </div>
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                        Manual Add from Discover
                      </h4>
                    </div>
                    <p className="text-sm mb-2">
                      Browse the Discover page, find an opportunity of interest,
                      and add it to your workstream via the card's action menu.
                      This gives you full control over exactly which
                      opportunities enter your research pipeline.
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      <strong>When to use:</strong> When you spot a specific
                      opportunity during browsing that is relevant to your
                      research, even if it does not match your filter criteria
                      exactly.
                    </p>
                  </div>
                </div>

                <ProTip>
                  The best approach is to combine all three methods. Start with
                  Auto-Populate for breadth, run a Workstream Scan for fresh
                  content, and manually add any specific opportunities you find
                  during your regular browsing of the Discover page.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* ------------------------------------------------------------ */}
            {/* 5. Deep Research */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item value="research" id="research">
              <AccordionTrigger icon={<Brain className="h-5 w-5" />}>
                Deep Research
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  GrantScope2 provides three tiers of AI research, each designed
                  for a different stage of the investigation workflow. All
                  research is powered by gpt-researcher, which orchestrates
                  multiple web searches and synthesizes findings from diverse
                  sources.
                </p>

                <ResearchComparisonTable />

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mt-6 mb-2">
                  How AI Research Works
                </h4>
                <ol className="list-decimal list-inside space-y-2 mb-4">
                  <li>
                    You trigger a research action on a card (Deep Dive, Quick
                    Update, or Check for Updates).
                  </li>
                  <li>
                    The system formulates targeted search queries based on the
                    opportunity's title, summary, and your workstream's focus
                    areas.
                  </li>
                  <li>
                    gpt-researcher conducts multiple parallel web searches
                    across academic databases, government publications, news
                    sources, and industry reports.
                  </li>
                  <li>
                    Retrieved content is validated for relevance and quality,
                    then synthesized into a structured research report.
                  </li>
                  <li>
                    The research findings are attached to the card and become
                    available for brief generation.
                  </li>
                </ol>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Research Status Tracking
                </h4>
                <p className="mb-4">
                  While research is in progress, a status indicator appears on
                  the card in the Kanban board. Cards can be in one of four
                  research states:
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                  {[
                    {
                      label: "Queued",
                      desc: "Waiting to start",
                      color: "bg-gray-100 dark:bg-gray-700",
                    },
                    {
                      label: "Processing",
                      desc: "Research in progress",
                      color: "bg-blue-100 dark:bg-blue-900/30",
                    },
                    {
                      label: "Completed",
                      desc: "Results ready",
                      color: "bg-green-100 dark:bg-green-900/30",
                    },
                    {
                      label: "Failed",
                      desc: "Can retry",
                      color: "bg-red-100 dark:bg-red-900/30",
                    },
                  ].map((s) => (
                    <div
                      key={s.label}
                      className={cn(
                        "rounded-lg p-3 text-center text-xs",
                        s.color,
                      )}
                    >
                      <div className="font-semibold text-gray-900 dark:text-white">
                        {s.label}
                      </div>
                      <div className="text-gray-500 dark:text-gray-400 mt-0.5">
                        {s.desc}
                      </div>
                    </div>
                  ))}
                </div>

                <ProTip>
                  You do not need to wait on the research page. The research
                  runs in the background. Navigate away and come back later --
                  the board will show updated status indicators when you return.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* ------------------------------------------------------------ */}
            {/* 6. Executive Briefs */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item value="briefs" id="briefs">
              <AccordionTrigger icon={<FileText className="h-5 w-5" />}>
                Executive Briefs
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  Executive briefs are the primary deliverable of the workstream
                  system. They synthesize research into structured,
                  leadership-ready documents that can be shared with
                  decision-makers.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                  Generating a Brief
                </h4>
                <ol className="list-decimal list-inside space-y-1 mb-4">
                  <li>
                    Move a card to the <strong>Brief</strong> column (ensure it
                    has research data first)
                  </li>
                  <li>
                    Click the <strong>Generate Brief</strong> action in the
                    card's menu
                  </li>
                  <li>
                    The AI analyzes all attached research and synthesizes a
                    structured brief
                  </li>
                  <li>
                    A preview modal opens automatically when generation
                    completes
                  </li>
                </ol>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                  Brief Structure
                </h4>
                <BriefStructurePreview />

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mt-6 mb-2">
                  Version History
                </h4>
                <p className="mb-3">
                  Every time you generate or regenerate a brief, a new version
                  is created. The preview modal includes a collapsible version
                  history panel where you can:
                </p>
                <ul className="list-disc list-inside space-y-1 mb-4">
                  <li>View all previous versions with timestamps</li>
                  <li>Switch between versions to compare content</li>
                  <li>
                    See how many new sources were available since the previous
                    version
                  </li>
                  <li>Regenerate with the latest data at any time</li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  New Sources Indicator
                </h4>
                <p className="mb-4">
                  When new research sources become available after a brief was
                  generated, a badge appears on the Regenerate button showing
                  how many new sources are available. This helps you decide when
                  to create a fresh version with the latest intelligence.
                </p>

                <ProTip>
                  Run Deep Dive research before generating a brief. The brief
                  quality is directly proportional to the research data
                  available. A card that has been through both Quick Update and
                  Deep Dive will produce a significantly richer brief than one
                  with only initial discovery data.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* ------------------------------------------------------------ */}
            {/* 7. Exporting & Presentations */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item value="exporting" id="exporting">
              <AccordionTrigger icon={<Download className="h-5 w-5" />}>
                Exporting & Presentations
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  GrantScope2's export system is designed to bridge the gap
                  between research and action. It supports both individual brief
                  exports and multi-brief portfolio documents, all branded with
                  the City of Austin identity.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                  Export Workflow
                </h4>
                <ExportWorkflowDiagram />

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mt-6 mb-2">
                  Individual Brief Export
                </h4>
                <div className="grid sm:grid-cols-2 gap-4 mb-6">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <FileText className="h-5 w-5 text-red-500" />
                      <h5 className="font-semibold text-gray-900 dark:text-white">
                        PDF
                      </h5>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Formatted document optimized for printing, email
                      attachments, and official records. Includes structured
                      headings, clean typography, and City of Austin branding
                      elements.
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                      Best for: Documentation, file sharing, meeting pre-reads
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Presentation className="h-5 w-5 text-orange-500" />
                      <h5 className="font-semibold text-gray-900 dark:text-white">
                        PowerPoint (PPTX)
                      </h5>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Presentation-ready slides generated from the brief
                      content. Each section becomes a slide with key points and
                      supporting details formatted for visual impact.
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                      Best for: Leadership presentations, council briefings,
                      stakeholder meetings
                    </p>
                  </div>
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Bulk Portfolio Export
                </h4>
                <p className="mb-3">
                  For comprehensive briefing packages, the Bulk Export feature
                  lets you combine multiple briefs from the Brief column into a
                  single cohesive document:
                </p>
                <ol className="list-decimal list-inside space-y-1 mb-4">
                  <li>
                    Click the <strong>Bulk Export</strong> button in the Brief
                    column header
                  </li>
                  <li>
                    Select which cards to include (only cards with generated
                    briefs are eligible)
                  </li>
                  <li>
                    <strong>Drag to reorder</strong> the cards using the grip
                    handle (
                    <GripVertical className="h-3.5 w-3.5 inline text-gray-400" />
                    ) to set the presentation sequence
                  </li>
                  <li>Choose your export format (PDF or PPTX)</li>
                  <li>
                    The AI synthesizes all selected briefs into a unified
                    portfolio with a cohesive introduction and transitions
                  </li>
                </ol>

                <div className="bg-gradient-to-r from-brand-blue/10 to-brand-green/10 dark:from-brand-blue/15 dark:to-brand-green/15 rounded-lg p-4 border border-brand-blue/20 mb-4">
                  <h5 className="font-semibold text-gray-900 dark:text-white text-sm mb-1">
                    City of Austin Branding
                  </h5>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    All exported documents automatically include City of Austin
                    branding elements including logos, color schemes, and
                    standardized header/footer layouts suitable for official
                    distribution.
                  </p>
                </div>

                <ProTip>
                  Use bulk export when preparing for quarterly strategic reviews
                  or presenting to the City Manager's office. Order the briefs
                  from highest priority to lowest, and the AI will create smooth
                  transitions between topics in the synthesized document.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* ------------------------------------------------------------ */}
            {/* 8. Scanning & Auto-Scan */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item value="scanning" id="scanning">
              <AccordionTrigger icon={<Telescope className="h-5 w-5" />}>
                Scanning & Auto-Scan
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  Workstream scans actively search the web for new content
                  matching your workstream's focus. This goes beyond the
                  existing database -- it discovers fresh opportunities that
                  have not yet been captured by the system.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Manual Scan
                </h4>
                <p className="mb-3">
                  Click <strong>Scan for Updates</strong> on the Kanban board
                  toolbar. The system will:
                </p>
                <ol className="list-decimal list-inside space-y-1 mb-4">
                  <li>
                    Build search queries from your workstream's keywords and
                    pillar context
                  </li>
                  <li>
                    Search multiple source types (RSS, news, web search,
                    academic)
                  </li>
                  <li>Filter results for relevance and freshness</li>
                  <li>
                    De-duplicate against existing opportunities in the database
                  </li>
                  <li>
                    Create new opportunity cards and add them to your Inbox
                  </li>
                </ol>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Auto-Scan
                </h4>
                <p className="mb-3">
                  Enable the auto-scan toggle on your workstream to have scans
                  run automatically on a periodic schedule. When auto-scan is
                  active, new opportunities are added to your Inbox without
                  manual intervention, keeping your workstream continuously fed
                  with fresh intelligence.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Rate Limits & Best Practices
                </h4>
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-4">
                  <div className="grid sm:grid-cols-2 gap-4 text-sm">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Clock className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                        <span className="font-medium text-gray-900 dark:text-white">
                          Scan Limit
                        </span>
                      </div>
                      <p className="text-gray-600 dark:text-gray-400">
                        2 manual scans per workstream per day. This prevents
                        excessive API usage while keeping content fresh.
                      </p>
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Settings className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                        <span className="font-medium text-gray-900 dark:text-white">
                          Requirements
                        </span>
                      </div>
                      <p className="text-gray-600 dark:text-gray-400">
                        Scans require at least keywords or strategic pillars to
                        be configured. A workstream with no filters cannot scan.
                      </p>
                    </div>
                  </div>
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Scan History
                </h4>
                <p>
                  Each scan's results are tracked, including how many new
                  opportunities were created and how many were added to your
                  workstream. The status bar on the Kanban board reflects the
                  total opportunity count across all columns after a scan
                  completes.
                </p>

                <ProTip>
                  Time your manual scans strategically. Run one in the morning
                  to catch overnight developments, and save the second for later
                  in the day if a breaking topic emerges. Rely on auto-scan for
                  routine monitoring.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>

            {/* ------------------------------------------------------------ */}
            {/* 9. Workflow Integration */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item value="workflow" id="workflow">
              <AccordionTrigger icon={<GitBranch className="h-5 w-5" />}>
                Workflow Integration
              </AccordionTrigger>
              <AccordionContent>
                <p className="mb-4">
                  Workstreams are one part of the complete GrantScope2 pipeline.
                  Understanding how they connect to other features helps you get
                  the most value from the system.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                  The Full Pipeline
                </h4>
                <div className="flex flex-col sm:flex-row items-stretch gap-2 sm:gap-0 mb-6">
                  {[
                    {
                      label: "Dashboard",
                      desc: "Overview & metrics",
                      icon: <BarChart3 className="h-4 w-4" />,
                    },
                    {
                      label: "Discover",
                      desc: "Browse all opportunities",
                      icon: <Search className="h-4 w-4" />,
                    },
                    {
                      label: "Opportunities",
                      desc: "Follow & track",
                      icon: <BookOpen className="h-4 w-4" />,
                    },
                    {
                      label: "Workstream",
                      desc: "Research & brief",
                      icon: <FolderOpen className="h-4 w-4" />,
                    },
                    {
                      label: "Export",
                      desc: "Present & act",
                      icon: <Download className="h-4 w-4" />,
                    },
                  ].map((s, idx) => (
                    <React.Fragment key={s.label}>
                      <div
                        className={cn(
                          "flex-1 rounded-lg border p-3 text-center",
                          s.label === "Workstream"
                            ? "border-brand-blue bg-brand-blue/5 dark:bg-brand-blue/10"
                            : "border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface",
                        )}
                      >
                        <div
                          className={cn(
                            "mx-auto mb-1.5",
                            s.label === "Workstream"
                              ? "text-brand-blue dark:text-brand-light-blue"
                              : "text-gray-500 dark:text-gray-400",
                          )}
                        >
                          {s.icon}
                        </div>
                        <div
                          className={cn(
                            "text-xs font-semibold",
                            s.label === "Workstream"
                              ? "text-brand-blue dark:text-brand-light-blue"
                              : "text-gray-900 dark:text-white",
                          )}
                        >
                          {s.label}
                        </div>
                        <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
                          {s.desc}
                        </div>
                      </div>
                      {idx < 4 && (
                        <div className="flex items-center justify-center sm:px-1">
                          <ArrowRight className="h-4 w-4 text-gray-400 hidden sm:block" />
                          <ChevronDown className="h-4 w-4 text-gray-400 sm:hidden" />
                        </div>
                      )}
                    </React.Fragment>
                  ))}
                </div>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  How Features Connect
                </h4>
                <ul className="list-disc list-inside space-y-2 mb-4">
                  <li>
                    <strong>Dashboard to Workstream:</strong> Spot a trend on
                    the dashboard, then create a dedicated workstream to
                    investigate it.
                  </li>
                  <li>
                    <strong>Discover to Workstream:</strong> Find a compelling
                    opportunity on the Discover page and add it directly to a
                    workstream for structured research.
                  </li>
                  <li>
                    <strong>Opportunities to Workstream:</strong> Opportunities
                    you follow can be added to workstreams when they warrant
                    deeper investigation beyond passive monitoring.
                  </li>
                  <li>
                    <strong>Workstream to Action:</strong> Export briefs and
                    portfolios to inform policy decisions, budget requests, and
                    strategic planning.
                  </li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Team Collaboration
                </h4>
                <p>
                  While workstreams are currently personal to each user,
                  exported PDFs and presentations can be shared across teams. A
                  common pattern is for one analyst to build a workstream,
                  conduct research, and export a brief portfolio that becomes
                  the basis for a team discussion or council presentation.
                </p>
              </AccordionContent>
            </Accordion.Item>

            {/* ------------------------------------------------------------ */}
            {/* 10. Tips & Advanced Usage */}
            {/* ------------------------------------------------------------ */}
            <Accordion.Item value="tips" id="tips">
              <AccordionTrigger icon={<Star className="h-5 w-5" />}>
                Tips & Advanced Usage
              </AccordionTrigger>
              <AccordionContent>
                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Workstream Naming Conventions
                </h4>
                <ul className="list-disc list-inside space-y-1 mb-5">
                  <li>
                    Use descriptive names: "Smart Traffic Signals" is better
                    than "Traffic Research"
                  </li>
                  <li>
                    Add time qualifiers for bounded research: "Q1 2026 Climate
                    Tech Review"
                  </li>
                  <li>
                    Prefix with the pillar code for team-wide consistency: "[MC]
                    Autonomous Transit"
                  </li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Focus Area Strategy
                </h4>
                <ul className="list-disc list-inside space-y-1 mb-5">
                  <li>
                    <strong>Narrow and deep:</strong> 3-5 specific keywords with
                    a single pillar for thorough investigation of a niche topic
                  </li>
                  <li>
                    <strong>Broad and exploratory:</strong> Multiple pillars
                    with general keywords to survey an emerging area
                  </li>
                  <li>
                    <strong>Cross-cutting:</strong> Use keywords that span
                    multiple pillars to capture interdisciplinary opportunities
                    (e.g., "digital equity" touches technology, housing, and
                    community health)
                  </li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Brief Scheduling
                </h4>
                <p className="mb-4">
                  Align your brief generation with your organization's cadence.
                  If leadership reviews happen monthly, plan to have cards
                  through the Research column by mid-month and generate briefs
                  the week before the review. Use the version history to show
                  how intelligence evolved between briefing cycles.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Portfolio Building for Leadership
                </h4>
                <p className="mb-4">
                  Build portfolio exports around specific themes or decisions.
                  For a council presentation on infrastructure technology,
                  create a workstream, research 5-8 key opportunities, generate
                  individual briefs, then use Bulk Export to create a unified
                  PPTX deck ordered by strategic priority.
                </p>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Archival Strategy
                </h4>
                <ul className="list-disc list-inside space-y-1 mb-5">
                  <li>
                    <strong>Archive, do not delete:</strong> Move completed
                    opportunities to Archived rather than removing them. They
                    serve as a record of what was investigated.
                  </li>
                  <li>
                    <strong>Periodic review:</strong> Check the Watching column
                    monthly. Opportunities that have been dormant for 3+ months
                    can usually be archived.
                  </li>
                  <li>
                    <strong>Seasonal cleanup:</strong> At the end of each
                    quarter, review all workstreams. Archive those that are
                    complete, and update filters on active ones to reflect
                    evolving priorities.
                  </li>
                </ul>

                <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Maximizing Research Quality
                </h4>
                <div className="rounded-lg bg-gray-50 dark:bg-dark-surface-elevated p-4 mb-4">
                  <ol className="list-decimal list-inside space-y-2 text-sm">
                    <li>
                      <strong>Screen first:</strong> Run a Quick Update before
                      committing to a Deep Dive to avoid wasting research
                      capacity on low-value opportunities.
                    </li>
                    <li>
                      <strong>Add notes before research:</strong> Write what
                      specific questions you want answered. This context helps
                      you evaluate research results more effectively.
                    </li>
                    <li>
                      <strong>Layer research:</strong> After a Deep Dive, move
                      the card to Brief and generate a brief. If the brief
                      reveals gaps, move it back to Research for another round.
                    </li>
                    <li>
                      <strong>
                        Use Check for Updates on watching opportunities:
                      </strong>{" "}
                      Periodically refresh high-priority opportunities in the
                      Watching column to catch breaking developments.
                    </li>
                  </ol>
                </div>

                <ProTip title="Advanced Pattern: Research Sprints">
                  For time-sensitive topics, create a dedicated workstream and
                  batch-process opportunities in a single session. Move 5-10
                  opportunities from Inbox to Screening, run Quick Updates on
                  all of them, then promote the top 3-4 to Research for Deep
                  Dives. This focused approach is more efficient than trickling
                  opportunities through the pipeline over days.
                </ProTip>
              </AccordionContent>
            </Accordion.Item>
          </Accordion.Root>

          {/* ================================================================ */}
          {/* Footer CTA */}
          {/* ================================================================ */}
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
                  to="/guide/discover"
                  className="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-dark-surface p-4 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 hover:border-brand-blue/30"
                >
                  <Compass className="h-5 w-5 text-brand-blue dark:text-brand-light-blue flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm text-gray-900 dark:text-white">
                      How to Use Discover
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      Browse and triage AI-curated opportunities
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
            Questions about workstreams? Reach out to the GrantScope2 team.
          </p>
        </div>
      </div>
    </>
  );
}
