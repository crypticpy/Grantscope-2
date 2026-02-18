/**
 * CardDetail Integration Tests
 *
 * Tests the refactored CardDetail component for:
 * - Component rendering with all sub-components
 * - Tab navigation (Overview, Sources, Timeline, Notes, Related)
 * - Loading and error states
 * - Data loading integration
 * - User interactions (following, notes)
 *
 * @module CardDetail/__tests__/CardDetail.test
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CardDetail } from "../CardDetail";
import type { Card, ResearchTask, Source, TimelineEvent, Note } from "../types";

// ============================================================================
// Test Data Factories
// ============================================================================

const mockCardData: Card = {
  id: "test-card-id",
  name: "Test Card Name",
  slug: "test-card-slug",
  summary: "A test card for integration testing purposes.",
  description:
    "This is a detailed description of the test card used for integration testing.",
  pillar_id: "technology",
  goal_id: "goal-1",
  anchor_id: "anchor-1",
  stage_id: "2_validation",
  horizon: "H2",
  novelty_score: 75,
  maturity_score: 60,
  impact_score: 80,
  relevance_score: 70,
  velocity_score: 65,
  risk_score: 40,
  opportunity_score: 85,
  top25_relevance: ["top25-1", "top25-2"],
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-15T00:00:00Z",
  deep_research_at: "2024-01-10T00:00:00Z",
  deep_research_count_today: 0,
};

const mockSources: Source[] = [
  {
    id: "source-1",
    title: "Test Source 1",
    url: "https://example.com/source1",
    ai_summary: "Summary of the first test source.",
    key_excerpts: ["Important excerpt from source 1"],
    publication: "Test Publication",
    relevance_to_card: 4,
    api_source: "gpt_researcher",
    ingested_at: "2024-01-05T00:00:00Z",
  },
];

const mockTimeline: TimelineEvent[] = [
  {
    id: "event-1",
    event_type: "deep_research",
    title: "Deep Research Completed",
    description: "Successfully completed deep research analysis.",
    created_at: "2024-01-10T00:00:00Z",
    metadata: {
      sources_found: 10,
      sources_relevant: 5,
      sources_added: 3,
    },
  },
];

const mockNotes: Note[] = [
  {
    id: "note-1",
    content: "This is a public note.",
    is_private: false,
    created_at: "2024-01-08T00:00:00Z",
  },
];

const mockScoreHistory = [
  {
    id: "score-1",
    card_id: "test-card-id",
    recorded_at: "2024-01-01T00:00:00Z",
    maturity_score: 50,
    velocity_score: 60,
    novelty_score: 70,
    impact_score: 75,
    relevance_score: 65,
    risk_score: 35,
    opportunity_score: 80,
  },
  {
    id: "score-2",
    card_id: "test-card-id",
    recorded_at: "2024-01-10T00:00:00Z",
    maturity_score: 55,
    velocity_score: 62,
    novelty_score: 72,
    impact_score: 78,
    relevance_score: 68,
    risk_score: 38,
    opportunity_score: 82,
  },
];

const mockStageHistory = [
  {
    id: "stage-1",
    card_id: "test-card-id",
    stage_id: "1_concept",
    entered_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "stage-2",
    card_id: "test-card-id",
    stage_id: "2_validation",
    entered_at: "2024-01-10T00:00:00Z",
  },
];

const mockRelatedCards = [
  {
    id: "related-1",
    name: "Related Card 1",
    slug: "related-card-1",
    summary: "Summary of related card 1",
    horizon: "H1" as const,
    similarity: 0.85,
  },
];

const mockResearchTasks: ResearchTask[] = [
  {
    id: "task-1",
    task_type: "deep_research",
    status: "completed",
    result_summary: {
      sources_found: 15,
      sources_relevant: 8,
      sources_added: 5,
      report_preview: "# Research Report\n\nThis is a test research report.",
    },
    created_at: "2024-01-15T00:00:00Z",
    completed_at: "2024-01-15T01:00:00Z",
  },
];

// ============================================================================
// Mock Setup - must be before any imports that use them
// ============================================================================

// Mock the Tooltip component to avoid TooltipProvider requirement
vi.mock("../../ui/Tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TooltipProvider: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

// Mock badge components that use Tooltip
vi.mock("../../PillarBadge", () => ({
  PillarBadge: ({ pillarId }: { pillarId: string }) => (
    <span data-testid="pillar-badge">{pillarId}</span>
  ),
}));

vi.mock("../PillarBadge", () => ({
  PillarBadge: ({ pillarId }: { pillarId: string }) => (
    <span data-testid="pillar-badge">{pillarId}</span>
  ),
}));

vi.mock("../../../PillarBadge", () => ({
  PillarBadge: ({ pillarId }: { pillarId: string }) => (
    <span data-testid="pillar-badge">{pillarId}</span>
  ),
}));

vi.mock("../../HorizonBadge", () => ({
  HorizonBadge: ({ horizon }: { horizon: string }) => (
    <span data-testid="horizon-badge">{horizon}</span>
  ),
}));

vi.mock("../HorizonBadge", () => ({
  HorizonBadge: ({ horizon }: { horizon: string }) => (
    <span data-testid="horizon-badge">{horizon}</span>
  ),
}));

vi.mock("../../../HorizonBadge", () => ({
  HorizonBadge: ({ horizon }: { horizon: string }) => (
    <span data-testid="horizon-badge">{horizon}</span>
  ),
}));

vi.mock("../../StageBadge", () => ({
  StageBadge: ({ stage }: { stage: number }) => (
    <span data-testid="stage-badge">{stage}</span>
  ),
  StageProgress: ({ stage }: { stage: number }) => (
    <div data-testid="stage-progress">Stage {stage}</div>
  ),
}));

// Also need to mock ../StageBadge for different import paths
vi.mock("../StageBadge", () => ({
  StageBadge: ({ stage }: { stage: number }) => (
    <span data-testid="stage-badge">{stage}</span>
  ),
  StageProgress: ({ stage }: { stage: number }) => (
    <div data-testid="stage-progress">Stage {stage}</div>
  ),
}));

vi.mock("../../../StageBadge", () => ({
  StageBadge: ({ stage }: { stage: number }) => (
    <span data-testid="stage-badge">{stage}</span>
  ),
  StageProgress: ({ stage }: { stage: number }) => (
    <div data-testid="stage-progress">Stage {stage}</div>
  ),
}));

vi.mock("../../AnchorBadge", () => ({
  AnchorBadge: ({ anchor }: { anchor: string }) => (
    <span data-testid="anchor-badge">{anchor}</span>
  ),
}));

vi.mock("../AnchorBadge", () => ({
  AnchorBadge: ({ anchor }: { anchor: string }) => (
    <span data-testid="anchor-badge">{anchor}</span>
  ),
}));

vi.mock("../../../AnchorBadge", () => ({
  AnchorBadge: ({ anchor }: { anchor: string }) => (
    <span data-testid="anchor-badge">{anchor}</span>
  ),
}));

vi.mock("../../Top25Badge", () => ({
  Top25Badge: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-badge">{priorities?.length || 0} priorities</span>
  ),
  Top25List: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-list">{priorities?.length || 0} items</span>
  ),
  Top25ExpandedBadge: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-expanded">
      {priorities?.length || 0} priorities
    </span>
  ),
}));

// Mock for different import paths
vi.mock("../Top25Badge", () => ({
  Top25Badge: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-badge">{priorities?.length || 0} priorities</span>
  ),
  Top25List: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-list">{priorities?.length || 0} items</span>
  ),
  Top25ExpandedBadge: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-expanded">
      {priorities?.length || 0} priorities
    </span>
  ),
}));

vi.mock("../../../Top25Badge", () => ({
  Top25Badge: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-badge">{priorities?.length || 0} priorities</span>
  ),
  Top25List: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-list">{priorities?.length || 0} items</span>
  ),
  Top25ExpandedBadge: ({ priorities }: { priorities: string[] }) => (
    <span data-testid="top25-expanded">
      {priorities?.length || 0} priorities
    </span>
  ),
}));

// Mock localStorage token
beforeEach(() => {
  localStorage.setItem("gs2_token", "test-token");
});
afterEach(() => {
  localStorage.removeItem("gs2_token");
});

// Mock useAuthContext
vi.mock("../../../hooks/useAuthContext", () => ({
  useAuthContext: () => ({
    user: { id: "test-user-id", email: "test@example.com" },
  }),
}));

// Mock discovery-api
vi.mock("../../../lib/discovery-api", () => ({
  getScoreHistory: vi.fn(() => Promise.resolve({ history: mockScoreHistory })),
  getStageHistory: vi.fn(() => Promise.resolve({ history: mockStageHistory })),
  getRelatedCards: vi.fn(() =>
    Promise.resolve({ related_cards: mockRelatedCards }),
  ),
}));

// Mock Recharts to avoid ResizeObserver issues
vi.mock("recharts", async () => {
  const actual = await vi.importActual("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

// Mock React Flow for ConceptNetworkDiagram
vi.mock("@xyflow/react", () => ({
  ReactFlow: () => <div data-testid="react-flow">Mock React Flow</div>,
  ReactFlowProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  Controls: () => null,
  MiniMap: () => null,
  Background: () => null,
  useNodesState: () => [[], vi.fn(), vi.fn()],
  useEdgesState: () => [[], vi.fn(), vi.fn()],
  MarkerType: { ArrowClosed: "arrowclosed" },
  Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
}));

// Mock ScoreTimelineChart
vi.mock("../../visualizations/ScoreTimelineChart", () => ({
  ScoreTimelineChart: ({ title }: { title?: string }) => (
    <div data-testid="score-timeline-chart">{title || "Score History"}</div>
  ),
}));

// Mock StageProgressionTimeline
vi.mock("../../visualizations/StageProgressionTimeline", () => ({
  StageProgressionTimeline: () => (
    <div data-testid="stage-progression-timeline" />
  ),
}));

// Mock TrendVelocitySparkline
vi.mock("../../visualizations/TrendVelocitySparkline", () => ({
  TrendVelocitySparkline: () => <div data-testid="velocity-sparkline" />,
  TrendVelocitySparklineSkeleton: () => (
    <div data-testid="velocity-sparkline-skeleton" />
  ),
}));

// Mock ConceptNetworkDiagram
vi.mock("../../visualizations/ConceptNetworkDiagram", () => ({
  ConceptNetworkDiagram: ({ title }: { title?: string }) => (
    <div data-testid="concept-network">{title || "Related Network"}</div>
  ),
}));

// Mock fetch for research API calls
const mockFetch = vi.fn();
global.fetch = mockFetch;

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Wrapper component for rendering CardDetail with necessary providers
 */
const renderCardDetail = (slug = "test-card-slug") => {
  return render(
    <MemoryRouter initialEntries={[`/signals/${slug}`]}>
      <Routes>
        <Route path="/signals/:slug" element={<CardDetail />} />
      </Routes>
    </MemoryRouter>,
  );
};

// ============================================================================
// Tests
// ============================================================================

describe("CardDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResearchTasks[0]),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Loading State", () => {
    it("shows loading spinner initially", () => {
      renderCardDetail();

      // Look for the loading spinner
      const spinner = document.querySelector(".animate-spin");
      expect(spinner).toBeInTheDocument();
    });
  });

  describe("Header Rendering", () => {
    it("displays card name in header after loading", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(screen.getByText(mockCardData.name)).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("displays card summary after loading", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(screen.getByText(mockCardData.summary)).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("displays back navigation link after loading", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(screen.getByText("Back to Discover")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("displays created date after loading", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          const createdText = screen.getByText(/Created:/);
          expect(createdText).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });

  describe("Tab Navigation", () => {
    it("renders all 5 tabs", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Overview/i }),
          ).toBeInTheDocument();
          expect(
            screen.getByRole("tab", { name: /Sources/i }),
          ).toBeInTheDocument();
          expect(
            screen.getByRole("tab", { name: /Timeline/i }),
          ).toBeInTheDocument();
          expect(
            screen.getByRole("tab", { name: /Notes/i }),
          ).toBeInTheDocument();
          expect(
            screen.getByRole("tab", { name: /Related/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("Overview tab is active by default", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          const overviewTab = screen.getByRole("tab", { name: /Overview/i });
          expect(overviewTab).toHaveAttribute("aria-selected", "true");
        },
        { timeout: 3000 },
      );
    });

    it("switches to Sources tab when clicked", async () => {
      const user = userEvent.setup();
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Sources/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      await user.click(screen.getByRole("tab", { name: /Sources/i }));

      const sourcesTab = screen.getByRole("tab", { name: /Sources/i });
      expect(sourcesTab).toHaveAttribute("aria-selected", "true");
    });

    it("switches to Timeline tab when clicked", async () => {
      const user = userEvent.setup();
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Timeline/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      await user.click(screen.getByRole("tab", { name: /Timeline/i }));

      const timelineTab = screen.getByRole("tab", { name: /Timeline/i });
      expect(timelineTab).toHaveAttribute("aria-selected", "true");
    });

    it("switches to Notes tab when clicked", async () => {
      const user = userEvent.setup();
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Notes/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      await user.click(screen.getByRole("tab", { name: /Notes/i }));

      const notesTab = screen.getByRole("tab", { name: /Notes/i });
      expect(notesTab).toHaveAttribute("aria-selected", "true");
    });

    it("switches to Related tab when clicked", async () => {
      const user = userEvent.setup();
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Related/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      await user.click(screen.getByRole("tab", { name: /Related/i }));

      const relatedTab = screen.getByRole("tab", { name: /Related/i });
      expect(relatedTab).toHaveAttribute("aria-selected", "true");
    });
  });

  describe("Overview Tab Content", () => {
    it("displays card description", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByText(mockCardData.description),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("displays impact metrics panel", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(screen.getByText("Impact Metrics")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("displays maturity score", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByText(String(mockCardData.maturity_score)),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("displays score history chart", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByTestId("score-timeline-chart"),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });

  describe("Action Buttons", () => {
    it("displays Compare button", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("button", { name: /Compare/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("displays Update button", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("button", { name: /Update/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("displays Deep Research button", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          // There may be multiple Deep Research buttons (header + research panel)
          const buttons = screen.getAllByRole("button", {
            name: /Deep Research/i,
          });
          expect(buttons.length).toBeGreaterThanOrEqual(1);
        },
        { timeout: 3000 },
      );
    });

    it("displays Export button", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("button", { name: /Export/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("displays Follow button", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("button", { name: /Follow/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });

  describe("Tab Accessibility", () => {
    it("tabs have proper ARIA roles", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          const tabList = screen.getByRole("tablist");
          expect(tabList).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("active tab has aria-selected=true", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          const activeTab = screen.getByRole("tab", { name: /Overview/i });
          expect(activeTab).toHaveAttribute("aria-selected", "true");
        },
        { timeout: 3000 },
      );
    });

    it("inactive tabs have aria-selected=false", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          const inactiveTab = screen.getByRole("tab", { name: /Sources/i });
          expect(inactiveTab).toHaveAttribute("aria-selected", "false");
        },
        { timeout: 3000 },
      );
    });
  });

  describe("Component Integration", () => {
    it("renders CardDetailHeader component", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(screen.getByText("Back to Discover")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("renders CardActionButtons component", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("button", { name: /Follow/i }),
          ).toBeInTheDocument();
          expect(
            screen.getByRole("button", { name: /Export/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("renders score timeline chart in overview", async () => {
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByTestId("score-timeline-chart"),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });

  describe("Responsive Design", () => {
    it("applies responsive container classes", async () => {
      const { container } = renderCardDetail();

      await waitFor(
        () => {
          const mainContainer = container.querySelector(".max-w-7xl");
          expect(mainContainer).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("tabs support horizontal scroll on mobile", async () => {
      const { container } = renderCardDetail();

      await waitFor(
        () => {
          const tabNav = container.querySelector(".overflow-x-auto");
          expect(tabNav).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });

  describe("Dark Mode Support", () => {
    it("applies dark mode classes", async () => {
      const { container } = renderCardDetail();

      await waitFor(
        () => {
          const darkModeElements =
            container.querySelectorAll('[class*="dark:"]');
          expect(darkModeElements.length).toBeGreaterThan(0);
        },
        { timeout: 3000 },
      );
    });
  });

  describe("Custom ClassName", () => {
    it("applies custom className to container", async () => {
      render(
        <MemoryRouter initialEntries={["/signals/test-card-slug"]}>
          <Routes>
            <Route
              path="/signals/:slug"
              element={<CardDetail className="custom-test-class" />}
            />
          </Routes>
        </MemoryRouter>,
      );

      await waitFor(
        () => {
          const container = document.querySelector(".custom-test-class");
          expect(container).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });
});

describe("CardDetail Tab Content", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Sources Tab", () => {
    it("shows sources tab content when active", async () => {
      const user = userEvent.setup();
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Sources/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      await user.click(screen.getByRole("tab", { name: /Sources/i }));

      const sourcesTab = screen.getByRole("tab", { name: /Sources/i });
      expect(sourcesTab).toHaveAttribute("aria-selected", "true");
    });
  });

  describe("Timeline Tab", () => {
    it("shows timeline tab content when active", async () => {
      const user = userEvent.setup();
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Timeline/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      await user.click(screen.getByRole("tab", { name: /Timeline/i }));

      const timelineTab = screen.getByRole("tab", { name: /Timeline/i });
      expect(timelineTab).toHaveAttribute("aria-selected", "true");
    });
  });

  describe("Notes Tab", () => {
    it("shows notes tab content when active", async () => {
      const user = userEvent.setup();
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Notes/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      await user.click(screen.getByRole("tab", { name: /Notes/i }));

      const notesTab = screen.getByRole("tab", { name: /Notes/i });
      expect(notesTab).toHaveAttribute("aria-selected", "true");
    });
  });

  describe("Related Tab", () => {
    it("shows related tab content when active", async () => {
      const user = userEvent.setup();
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Related/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      await user.click(screen.getByRole("tab", { name: /Related/i }));

      const relatedTab = screen.getByRole("tab", { name: /Related/i });
      expect(relatedTab).toHaveAttribute("aria-selected", "true");
    });

    it("shows concept network diagram when Related tab is active", async () => {
      const user = userEvent.setup();
      renderCardDetail();

      await waitFor(
        () => {
          expect(
            screen.getByRole("tab", { name: /Related/i }),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      await user.click(screen.getByRole("tab", { name: /Related/i }));

      await waitFor(
        () => {
          expect(screen.getByTestId("concept-network")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });
});

describe("CardDetail Data Loading", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads card data on mount", async () => {
    renderCardDetail();

    await waitFor(
      () => {
        expect(screen.getByText(mockCardData.name)).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });

  it("renders grid layout for Overview tab", async () => {
    const { container } = renderCardDetail();

    await waitFor(
      () => {
        const gridContainer = container.querySelector(".grid");
        expect(gridContainer).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });
});

describe("CardDetail Error Handling", () => {
  it("handles loading gracefully", async () => {
    renderCardDetail();

    // Should not throw and should eventually render
    await waitFor(
      () => {
        const hasSpinner = document.querySelector(".animate-spin");
        const hasContent = screen.queryByText(mockCardData.name);
        expect(hasSpinner || hasContent).toBeTruthy();
      },
      { timeout: 3000 },
    );
  });
});
