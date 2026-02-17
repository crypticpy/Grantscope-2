# GrantScope2: Frontend Specification

## Overview

React SPA with TypeScript. Clean, professional UI focused on information density without overwhelming users.

**Key Principles:**

- Cards are the primary UI element
- Minimal clicks to core actions
- Information hierarchy: summary → detail → sources
- Mobile-responsive but desktop-first

---

## Pages & Routes

```
/                     → Dashboard (home)
/discover             → Discovery Feed
/cards/:slug          → Card Detail
/workstreams          → Workstream Management
/workstreams/:id      → Workstream Feed
/analysis/:id         → Implications Analysis View
/research             → Research Tasks
/settings             → User Settings
/login                → Auth (handled by Supabase)
```

---

## Page Specifications

### Dashboard (`/`)

User's personalized home view.

**Sections:**

1. **Greeting & Summary Stats**
   - "Good morning, Jane"
   - Cards you follow: 24
   - New updates today: 7
   - Workstreams: 3

2. **Recent Activity** (your followed cards with updates)
   - List of CardPreview components
   - "3 new sources" badges
   - Quick follow/unfollow toggle

3. **High Velocity Cards** (across all users)
   - Top 5 cards by velocity score
   - Shows why it's trending

4. **Stage Changes This Week**
   - Cards that moved stages
   - "Solid State Batteries: Stage 3 → 4"

**Wireframe:**

```
┌─────────────────────────────────────────────────────────┐
│  [Logo] GrantScope2          [Search]    [👤 Jane Smith] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Good morning, Jane                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                   │
│  │ 24      │ │ 7       │ │ 3       │                   │
│  │ Following│ │ Updates │ │ Streams │                   │
│  └─────────┘ └─────────┘ └─────────┘                   │
│                                                         │
│  ─── Your Updates ───────────────────────────────────  │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🔋 Solid State Batteries         H2 · Stage 4   │   │
│  │ 3 new sources today                    [View →] │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🚗 Autonomous Vehicle Regulation  H2 · Stage 5  │   │
│  │ Stage changed from 4 → 5                [View →]│   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ─── Trending Across City ───────────────────────────  │
│  ...                                                    │
└─────────────────────────────────────────────────────────┘
```

---

### Discovery Feed (`/discover`)

Browse all cards with filtering.

**Features:**

- Filter sidebar (pillars, horizons, stages)
- Sort dropdown (recent, velocity, followers)
- Search bar
- Infinite scroll card list

**Filters:**

```
Pillars (multi-select):
  ☑ CH - Community Health
  ☑ MC - Mobility
  ☐ EW - Economic
  ...

Horizon (multi-select):
  ☑ H3 - Weak signals
  ☑ H2 - Transitional
  ☐ H1 - Mainstream

Stage Range:
  [1] ────●──── [8]

Time:
  ○ All time
  ● Last 7 days
  ○ Last 30 days
```

**Wireframe:**

```
┌─────────────────────────────────────────────────────────┐
│  [Logo] GrantScope2    [🔍 Search cards...]  [👤 Jane]   │
├─────────────────────────────────────────────────────────┤
│ ┌──────────┐  ┌────────────────────────────────────────┐│
│ │ FILTERS  │  │ Sort: [Recent ▾]      Showing 142 cards││
│ │          │  │                                        ││
│ │ Pillars  │  │ ┌────────────────────────────────────┐ ││
│ │ ☑ CH     │  │ │ 🔋 Solid State Batteries           │ ││
│ │ ☑ MC     │  │ │ Revolutionary battery tech...      │ ││
│ │ ☐ EW     │  │ │ H2 · Stage 4 · MC, CH              │ ││
│ │ ☐ HG     │  │ │ 👥 12  📄 47  ⚡ 8.5              │ ││
│ │ ☐ HH     │  │ │                      [+ Follow]    │ ││
│ │ ☐ PS     │  │ └────────────────────────────────────┘ ││
│ │          │  │                                        ││
│ │ Horizon  │  │ ┌────────────────────────────────────┐ ││
│ │ ☑ H3     │  │ │ 🤖 AI-Powered 311 Systems          │ ││
│ │ ☑ H2     │  │ │ Chatbots handling citizen...       │ ││
│ │ ☐ H1     │  │ │ H2 · Stage 5 · HG                  │ ││
│ │          │  │ │ 👥 8   📄 23  ⚡ 6.2               │ ││
│ │ Stage    │  │ │                      [Following ✓] │ ││
│ │ [1]──[8] │  │ └────────────────────────────────────┘ ││
│ │          │  │                                        ││
│ └──────────┘  │ [Load more...]                         ││
│               └────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

---

### Card Detail (`/cards/:slug`)

Full card view with tabs.

**Tabs:**

1. **Overview** - Summary, classification, scoring
2. **Timeline** - Evolution history
3. **Sources** - All linked articles
4. **Analysis** - Implications analyses

**Actions:**

- Follow / Unfollow (with workstream selector)
- Add Note
- Run Implications Analysis
- Share (copy link)

**Wireframe:**

```
┌─────────────────────────────────────────────────────────┐
│  ← Back to Discovery                                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🔋 Solid State Batteries                               │
│  ─────────────────────────────────────────────────────  │
│  Revolutionary battery technology using solid           │
│  electrolytes instead of liquid, promising higher       │
│  energy density, faster charging, and improved safety.  │
│                                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ H2      │ │ Stage 4 │ │ MC, CH  │ │ ⚡ 8.5  │       │
│  │ Horizon │ │ Pilot   │ │ Pillars │ │ Velocity│       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
│                                                         │
│  [+ Follow ▾]  [📝 Add Note]  [🔬 Analyze]  [🔗 Share] │
│                                                         │
│  ┌──────────┬──────────┬──────────┬──────────┐         │
│  │ Overview │ Timeline │ Sources  │ Analysis │         │
│  └──────────┴──────────┴──────────┴──────────┘         │
│  ═══════════════════════════════════════════════════    │
│                                                         │
│  CLASSIFICATION                                         │
│  ├─ Goals: MC.3 (Sustainable transport), CH.3 (Climate)│
│  ├─ Anchors: Innovation, Sustainability                │
│  └─ Top 25: Climate Revolving Fund ✓                   │
│                                                         │
│  SCORING                                                │
│  ├─ Credibility: ████░ 4.2                             │
│  ├─ Novelty: █████ 4.5                                 │
│  ├─ Likelihood: ██████░░░ 6.0                          │
│  ├─ Impact: ████░ 4.0                                  │
│  └─ Time to prepare: ~36 months                        │
│                                                         │
│  NOTES (2)                                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │ "Discuss with Budget in Q2" - You, Dec 15       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Timeline Tab:**

```
│  TIMELINE                                               │
│                                                         │
│  2024-12 ──●── Stage Change: 3 → 4                     │
│            │   Denver announces pilot program           │
│            │   [View source →]                          │
│            │                                            │
│  2024-11 ──●── 8 new sources added                     │
│            │   Coverage spike after CES announcements   │
│            │                                            │
│  2024-08 ──●── Stage Change: 2 → 3                     │
│            │   Working demos at CES validated           │
│            │                                            │
│  2024-03 ──●── Card Created                            │
│                Initial discovery via arXiv paper        │
```

**Sources Tab:**

```
│  SOURCES (47)                          [Sort: Recent ▾] │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Toyota Announces Solid State Battery Production  │   │
│  │ Reuters · Dec 18, 2024                          │   │
│  │ Toyota revealed plans to begin mass production  │   │
│  │ of solid-state batteries by 2027...             │   │
│  │ Relevance: 92%                    [Read full →] │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ QuantumScape Reports Q3 Progress                 │   │
│  │ TechCrunch · Dec 15, 2024                       │   │
│  │ ...                                              │   │
│  └─────────────────────────────────────────────────┘   │
```

---

### Implications Analysis (`/analysis/:id`)

Visual tree of implications with scoring.

**Wireframe:**

```
┌─────────────────────────────────────────────────────────┐
│  Analysis: Solid State Batteries                        │
│  Perspective: Austin Transportation Department          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                    ┌─────────────┐                      │
│                    │ Solid State │                      │
│                    │  Batteries  │                      │
│                    └──────┬──────┘                      │
│           ┌───────────────┼───────────────┐             │
│           ▼               ▼               ▼             │
│    ┌────────────┐  ┌────────────┐  ┌────────────┐      │
│    │ City pilots│  │ Supply     │  │ Private    │      │
│    │ 25 vehicles│  │ delays     │  │ sector     │      │
│    │            │  │ 18 months  │  │ accelerate │      │
│    │ [Expand]   │  │ [Expand]   │  │ [Expand]   │      │
│    └────────────┘  └────────────┘  └────────────┘      │
│           │                                             │
│           ▼ (expanded)                                  │
│    ┌────────────┐  ┌────────────┐  ┌────────────┐      │
│    │ Budget req │  │ Maintenance│  │ Charging   │      │
│    │ Q3 2027    │  │ retraining │  │ assessment │      │
│    │ L:6 D:-2   │  │ L:7 D:+2   │  │ L:5 D:-1   │      │
│    │ [Score]    │  │ [Score]    │  │ [Score]    │      │
│    └────────────┘  └────────────┘  └────────────┘      │
│                          │                              │
│                          ▼                              │
│                   ┌────────────┐                        │
│                   │ Grid       │                        │
│                   │ constraints│                        │
│                   │ L:5 D:-4   │ 🔴 Likely Strong Neg   │
│                   └────────────┘                        │
│                                                         │
│  ─── Key Findings ──────────────────────────────────── │
│  🔴 3 Likely Strong Negatives identified               │
│  🟢 1 Unlikely Strong Positive (opportunity)           │
│                                                         │
│  [Save Analysis]  [Export PDF]                          │
└─────────────────────────────────────────────────────────┘
```

---

### Workstreams (`/workstreams`)

Manage personal workstreams.

**Features:**

- List of workstreams with card counts
- Create new workstream
- Edit workstream filters
- Delete workstream

---

## Components

### CardPreview

Compact card display for lists.

```tsx
interface CardPreviewProps {
  card: {
    id: string;
    name: string;
    summary: string;
    horizon: string;
    stage: number;
    pillars: string[];
    velocity_score: number;
    follower_count: number;
    source_count: number;
    new_sources_24h?: number;
  };
  isFollowing?: boolean;
  onFollow?: () => void;
  onUnfollow?: () => void;
}
```

### CardDetail

Full card view with all metadata.

### TimelineEvent

Single event in card timeline.

### SourceCard

Article/source display.

### ImplicationNode

Single node in implications tree.

### FilterSidebar

Reusable filter controls.

### WorkstreamCard

Workstream summary display.

### StageIndicator

Visual stage display (1-8 with labels).

### HorizonBadge

H1/H2/H3 badge with color coding.

### PillarTags

Colored pillar tag list.

### ScoreBar

Horizontal score visualization.

---

## State Management

Using Zustand for global state.

```tsx
interface AppState {
  // Auth
  user: User | null;
  setUser: (user: User | null) => void;

  // UI
  sidebarOpen: boolean;
  toggleSidebar: () => void;

  // Filters (persisted)
  discoveryFilters: DiscoveryFilters;
  setDiscoveryFilters: (filters: Partial<DiscoveryFilters>) => void;

  // Cache
  followedCardIds: Set<string>;
  addFollowedCard: (id: string) => void;
  removeFollowedCard: (id: string) => void;
}
```

React Query handles server state (cards, workstreams, etc.).

---

## Real-time Updates

Using Supabase Realtime for:

- New cards appearing in feed
- Source count updates on followed cards
- Stage change notifications

```tsx
// Subscribe to card updates
supabase
  .channel("card-updates")
  .on(
    "postgres_changes",
    { event: "UPDATE", schema: "public", table: "cards" },
    (payload) => {
      // Invalidate react-query cache for this card
      queryClient.invalidateQueries(["card", payload.new.id]);
    },
  )
  .subscribe();
```

---

## Responsive Breakpoints

```css
/* Mobile first */
sm: 640px   /* Small tablets */
md: 768px   /* Tablets */
lg: 1024px  /* Desktop */
xl: 1280px  /* Large desktop */
```

**Mobile adaptations:**

- Filter sidebar becomes modal/drawer
- Card grid becomes single column
- Timeline becomes vertical only
- Implications tree scrolls horizontally

---

## Color System (TailwindCSS)

```js
// tailwind.config.js extend
colors: {
  // Horizons
  'h1': { DEFAULT: '#10B981', light: '#D1FAE5' }, // Green
  'h2': { DEFAULT: '#F59E0B', light: '#FEF3C7' }, // Amber
  'h3': { DEFAULT: '#8B5CF6', light: '#EDE9FE' }, // Purple

  // Pillars
  'pillar-ch': '#10B981', // Community Health - Green
  'pillar-ew': '#3B82F6', // Economic - Blue
  'pillar-hg': '#6366F1', // High Performing - Indigo
  'pillar-hh': '#EC4899', // Housing - Pink
  'pillar-mc': '#F59E0B', // Mobility - Amber
  'pillar-ps': '#EF4444', // Public Safety - Red

  // Implications
  'likely-negative': '#EF4444',
  'unlikely-positive': '#10B981',
  'catastrophe': '#7F1D1D',
  'triumph': '#065F46',
}
```

---

## Accessibility

- All interactive elements keyboard accessible
- ARIA labels on icons and non-text elements
- Color not sole indicator (use shapes/text)
- Focus visible states
- Minimum contrast ratios (WCAG AA)

---

_Document Version: 1.0_
_Last Updated: December 2024_
