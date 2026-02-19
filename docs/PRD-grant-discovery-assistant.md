# PRD: Intelligent Grant Discovery Assistant

**Status:** Draft
**Date:** 2026-02-18
**Author:** GrantScope Team

---

## 1. Vision

Users come to GrantScope without expertise in grants or the system. They don't know what to search for, what programs exist, or how the pieces fit together. The Grant Discovery Assistant transforms the existing **Ask GrantScope** chat into a proactive, agentic partner that pulls the user's profile context, searches internal and external grant sources, analyzes fit, and guides users toward actionable next steps — including creating opportunity cards, setting up programs, and starting applications.

This is not a new page. It is an evolution of the existing Ask GrantScope experience into a tool-equipped AI agent that meets users where they are.

---

## 2. Goals

1. **Reduce time-to-relevance** — Users find grants that fit their program within one conversation, not hours of manual browsing
2. **Bridge the knowledge gap** — The assistant explains grant concepts, eligibility, and fit in plain language appropriate to the user's experience level
3. **Connect features holistically** — The assistant nudges users toward Programs, Applications, and other features they haven't discovered yet
4. **Surface hidden opportunities** — When the internal database doesn't have a match, the assistant can search Grants.gov, SAM.gov, and the web (when enabled)
5. **Admin control over external access** — Administrators can enable or disable online search capabilities system-wide

---

## 3. Scenarios & User Stories

### Scenario A: "I don't know what I'm looking for"

> A Community Health department staffer opens the Discover page, sees 200+ grants, and has no idea where to start. They click an "Ask GrantScope" prompt and describe their situation in plain language.

**US-A1: Profile-aware conversation start**

> As a user, when I open Ask GrantScope, I want the assistant to already know my department, program, grant interests, and priorities so I don't have to repeat information that's in my profile.

Acceptance Criteria:

- [ ] The assistant's system prompt includes the user's `department`, `program_name`, `program_mission`, `grant_categories`, `strategic_pillars`, `priorities`, `funding_range_min/max`, `grant_experience`, `team_size`, and `budget_range`
- [ ] If the user's profile is incomplete (<50% completion), the assistant's first message acknowledges this and asks targeted questions to fill gaps before searching
- [ ] If the user's profile is complete, the assistant greets them by context: "I see you're focused on community health programs in Housing & Economic Stability. How can I help today?"
- [ ] The current date is always injected into the system prompt so the AI can filter by deadline relevance

**US-A2: Guided discovery through questions**

> As a user, I want the assistant to ask me a few clarifying questions before searching so it can narrow down to grants that actually fit my situation.

Acceptance Criteria:

- [ ] After understanding the user's context, the assistant asks 2-3 targeted questions (e.g., "Are you looking for federal, state, or foundation grants?", "What's your approximate budget need?", "Is there a timeline pressure?")
- [ ] Questions adapt based on `grant_experience` — beginners get more explanatory phrasing; experienced users get more direct questions
- [ ] The assistant does not ask questions that the profile already answers (e.g., don't ask about department if it's set)

**US-A3: Internal database search**

> As a user, I want the assistant to search through all grants in the system and explain which ones match my needs and why.

Acceptance Criteria:

- [ ] The assistant uses a tool to perform hybrid search (vector + FTS) against all grant cards, filtered by user's pillars, categories, and funding range
- [ ] Results are ranked by a combined fit score that considers the user's profile against each grant's characteristics
- [ ] The assistant presents results as a summarized list with: grant name, grantor, funding range, deadline, and a 1-2 sentence fit explanation
- [ ] Each recommended grant links to its opportunity card (clickable in the chat)
- [ ] If results are poor (few matches, low relevance), the assistant proactively says: "I didn't find strong matches in our database. Would you like me to search online sources for more options?" (if online search is enabled)

**US-A4: Online source search (when enabled)**

> As a user, when the internal database doesn't have what I need, I want the assistant to search Grants.gov, SAM.gov, and the web to find additional opportunities.

Acceptance Criteria:

- [ ] The assistant has tools for: `search_grants_gov` (Grants.gov API), `search_sam_gov` (SAM.gov API), and `web_search` (Tavily/SearXNG)
- [ ] Online search is only available when the `online_search_enabled` admin flag is `true`
- [ ] When online search is disabled, the assistant does not offer it and does not have access to external search tools
- [ ] When online search is enabled, the assistant explains what it's doing: "Let me check Grants.gov and SAM.gov for current opportunities..."
- [ ] Progress events stream to the UI: "Searching our database...", "Checking Grants.gov...", "Analyzing 12 potential matches..."
- [ ] External results include source attribution (e.g., "Found on Grants.gov, posted 2026-01-15")

### Scenario B: "I found a grant and want to know if it's a good fit"

> A user found a grant opportunity through a colleague's email or a Google search. They want to know if it's worth pursuing given their department's situation.

**US-B1: Analyze a URL**

> As a user, I want to paste a grant URL into the chat and have the assistant analyze whether it's a good fit for my program.

Acceptance Criteria:

- [ ] The assistant detects URLs in the user's message and offers to analyze them
- [ ] It uses the existing `extract_grant_from_url()` capability (wizard service) to crawl and parse grant details
- [ ] It evaluates the grant against the user's profile: program alignment, eligibility match, funding range fit, deadline feasibility
- [ ] The assistant provides a structured assessment: fit rating (e.g., "Strong Fit", "Moderate Fit", "Likely Not Eligible"), key reasons, potential concerns, and recommended next steps
- [ ] The assessment accounts for the current date relative to the deadline

**US-B2: Analyze uploaded documents**

> As a user, I want to share files (PDFs, documents) about a grant opportunity and have the assistant analyze them.

Acceptance Criteria:

- [ ] The chat supports file attachments (PDF, DOCX, TXT — reuse the existing wizard file upload infrastructure)
- [ ] The assistant extracts text from uploaded files and incorporates it into its analysis context
- [ ] The assistant can answer questions about the uploaded document: eligibility requirements, application components, budget constraints, etc.
- [ ] Uploaded documents are associated with the conversation for future reference

**US-B3: Turn a finding into an opportunity card**

> As a user, after the assistant confirms a grant is a good fit, I want to save it as an opportunity card in the system so I can track it.

Acceptance Criteria:

- [ ] The assistant offers: "Would you like me to create an opportunity card for this grant so you can track it?"
- [ ] On confirmation, it creates a card with all extracted metadata (name, grantor, funding amounts, deadline, CFDA number, eligibility, etc.) using the existing `create_card_from_grant()` wizard service method
- [ ] The new card is linked to the user (added to their followed items)
- [ ] The assistant returns a link to the newly created card
- [ ] If a card already exists for this grant (detected via deduplication), the assistant says "This opportunity is already in our system" and links to the existing card

### Scenario C: "I found my grant, now what?"

> The assistant has helped the user identify one or more grants. Now it should guide them toward the next logical steps in the system.

**US-C1: Nudge toward program creation**

> As a user, when I've identified a grant that fits my work, I want the assistant to check whether I have a relevant program set up and suggest creating one if I don't.

Acceptance Criteria:

- [ ] After a user expresses intent to pursue a grant (e.g., "Yes, I want to track that one", "That looks perfect"), the assistant checks the user's existing programs (workstreams)
- [ ] If the user has no programs, the assistant says: "I notice you don't have any programs set up yet. Programs help you organize and track grants around a focus area — like 'Public Safety Grants' or 'Youth Services Funding'. Want me to help you create one?"
- [ ] If the user has programs but none that match the grant's pillar/category, the assistant suggests creating a new program for this focus area
- [ ] If the user has a matching program, the assistant offers to add the opportunity card to that program's kanban board
- [ ] The assistant can create a program on behalf of the user via a tool call (name, description, pillar filters, category filters pre-populated from the grant context)

**US-C2: Nudge toward the application wizard**

> As a user, when I've committed to pursuing a grant, I want the assistant to suggest starting the application process.

Acceptance Criteria:

- [ ] When the user indicates they want to apply, the assistant says: "Great choice! You can start the application process with our Grant Wizard — it'll walk you through everything step by step. Want me to take you there?"
- [ ] Provides a direct link to `/apply` with context about the selected grant
- [ ] If the user's profile is incomplete, the assistant suggests completing it first: "Before you start the application, it would help to complete your profile — especially your program mission and team size. That information feeds directly into the application."

**US-C3: Proactive feature education**

> As a user who is new to the system, I want the assistant to naturally introduce me to relevant features I haven't used yet, without being pushy.

Acceptance Criteria:

- [ ] The assistant tracks which features the user has engaged with (has programs? has used the wizard? has cards on a kanban board?)
- [ ] Suggestions are contextual and limited to 1 per conversation turn — never a feature dump
- [ ] Suggestions are framed as helpful, not salesy: "By the way, you can set up a program to have GrantScope automatically scan for new grants matching these criteria. Want to know more?"
- [ ] The assistant explains the value proposition of each feature in 1 sentence before offering to help set it up

### Scenario D: Entry points and navigation

> Users should be able to reach the assistant from multiple places, especially when they're stuck.

**US-D1: CTA from Discover empty/poor results state**

> As a user on the Discover page, when I can't find what I'm looking for, I want a clear path to get AI help.

Acceptance Criteria:

- [ ] When the Discover page shows empty results (any empty state), an additional CTA appears: "Not finding what you need? Ask GrantScope to help you search." (links to `/ask`)
- [ ] When search returns <3 results, a subtle banner appears below the results: "Looking for more? GrantScope's AI assistant can search beyond our database." (links to `/ask`)
- [ ] The link carries search context via URL params (e.g., `/ask?context=discover&query=...`) so the assistant can continue where the user left off

**US-D2: Contextual entry from Discover page**

> As a user browsing the Discover page, I want quick access to the assistant without losing my place.

Acceptance Criteria:

- [ ] A persistent "Ask GrantScope" floating action button (FAB) or header prompt exists on the Discover page
- [ ] Alternatively, a brief inline prompt appears at the top of the Discover page: "Need help finding the right grant? Ask GrantScope →"
- [ ] When navigating from Discover to Ask, the assistant receives the user's active filters/search query as context

**US-D3: Scope indicator in Ask**

> As a user in Ask GrantScope, I want to understand what sources the assistant has access to.

Acceptance Criteria:

- [ ] The scope selector shows the current mode clearly: "Internal Only" or "Internal + Online Sources"
- [ ] If online search is admin-disabled, only "Internal" appears (no indication that online mode exists)
- [ ] If online search is admin-enabled, the user can toggle between modes per conversation
- [ ] A small info tooltip explains what each mode includes: "Internal: searches X grants in the GrantScope database. Online: also checks Grants.gov, SAM.gov, and web sources."

### Scenario E: Admin controls

> An administrator needs to control system-wide capabilities like online search access.

**US-E1: Admin feature flag for online search**

> As an admin, I want to enable or disable the AI assistant's ability to search online sources so I can control costs and data exposure.

Acceptance Criteria:

- [ ] A new admin settings section exists (either in the Settings page for admin users, or a dedicated `/admin` page)
- [ ] The setting `online_search_enabled` is a toggle (default: `false`)
- [ ] When disabled, the chat service does not register online search tools for any user
- [ ] When enabled, all users can access online search through the assistant
- [ ] The setting persists in the database (new `system_settings` table or JSONB column on an admin config)
- [ ] Changes take effect immediately (no restart required)

**US-E2: Admin visibility into assistant usage**

> As an admin, I want to see how the assistant is being used to understand adoption and costs.

Acceptance Criteria:

- [ ] A lightweight usage summary is available: total conversations, tool calls by type (internal search, grants.gov, sam.gov, web search), cards created via assistant
- [ ] This can be a simple API endpoint initially; a UI dashboard is a future enhancement

---

## 4. Tool Definitions

The assistant operates through a set of tools it can invoke autonomously. The AI decides when and how to use them based on the conversation.

| Tool                      | Purpose                                                                               | Source               | Always Available                |
| ------------------------- | ------------------------------------------------------------------------------------- | -------------------- | ------------------------------- |
| `search_internal_grants`  | Hybrid vector+FTS search against all grant cards, filtered by user profile            | RAGEngine + db_utils | Yes                             |
| `get_grant_details`       | Retrieve full details of a specific grant card by ID or slug                          | Cards table          | Yes                             |
| `search_grants_gov`       | Real-time query to Grants.gov API                                                     | grants_gov_fetcher   | Only if `online_search_enabled` |
| `search_sam_gov`          | Real-time query to SAM.gov API                                                        | sam_gov_fetcher      | Only if `online_search_enabled` |
| `web_search`              | General web search via Tavily/SearXNG                                                 | search_provider      | Only if `online_search_enabled` |
| `analyze_url`             | Crawl and extract grant details from a URL                                            | wizard_service       | Yes                             |
| `assess_fit`              | Compare a grant's requirements against user profile, return structured fit assessment | New (AI prompt)      | Yes                             |
| `create_opportunity_card` | Create a new card from grant data, link to user                                       | wizard_service       | Yes                             |
| `add_card_to_program`     | Add a card to one of the user's workstreams                                           | workstream API       | Yes                             |
| `create_program`          | Create a new workstream/program for the user                                          | workstream API       | Yes                             |
| `check_user_programs`     | List user's existing programs and their focus areas                                   | workstream API       | Yes                             |
| `check_user_profile`      | Retrieve current profile completion status and missing fields                         | user API             | Yes                             |

---

## 5. System Prompt Design

The assistant's system prompt includes:

```
You are GrantScope's AI grant discovery assistant. Today's date is {current_date}.

## Your User
- Name: {display_name}
- Department: {department}
- Role: {title}
- Program: {program_name}
- Program Mission: {program_mission}
- Team Size: {team_size}
- Budget Range: {budget_range}
- Grant Experience: {grant_experience} (adapt your language accordingly)
- Grant Categories of Interest: {grant_categories}
- Strategic Pillars: {strategic_pillars}
- Priorities: {priorities}
- Desired Funding: ${funding_range_min} - ${funding_range_max}
- Profile Completion: {completion_pct}%

## Your Capabilities
You help users discover, evaluate, and pursue grant opportunities. You can:
1. Search the internal GrantScope database ({card_count} opportunities)
2. {if online_enabled} Search Grants.gov, SAM.gov, and the web for current opportunities
3. Analyze grant URLs and documents the user shares
4. Assess how well a grant fits the user's program
5. Create opportunity cards for grants worth tracking
6. Set up programs to organize grant tracking
7. Guide users to the application wizard when ready

## Your Approach
- Start by understanding what the user needs — don't immediately search
- Ask 1-2 clarifying questions if the user's request is broad
- Always check internal sources first before going online
- When presenting grants, explain WHY each one fits (or doesn't)
- Proactively suggest next steps (create card, create program, start application)
- Flag expired deadlines and time-sensitive opportunities
- Be honest when something isn't a good fit — don't oversell
- If the user seems new, briefly explain features before suggesting them

## Important Rules
- Never fabricate grant details — only present information from tools or the user
- Always cite sources (internal card link, Grants.gov URL, etc.)
- When creating cards or programs, confirm with the user first
- Limit online searches to 3 per conversation turn to manage costs
- If profile is <50% complete, gently encourage completing it before deep searching
```

---

## 6. UX & Navigation Changes

### 6.1 Ask GrantScope Page Enhancements

**Scope selector redesign:**

- Current: "All Opportunities" | [Workstream 1] | [Workstream 2]
- New: "All Opportunities" | "All Opportunities + Online" (if admin-enabled) | [Workstream 1] | ...
- The "Online" mode is presented as an enhancement, not a separate scope

**Suggested questions update:**

- Replace generic questions with profile-aware starters:
  - "Find grants that match my program" (profile-aware search)
  - "What deadlines should I prioritize this month?" (date-aware)
  - "Analyze a grant I found" (URL/file analysis)
  - "Help me set up a grant tracking program" (program creation)
  - "What's new on Grants.gov for {user_department}?" (if online enabled)

**Progress indicators:**

- When the agent is using tools, show step-by-step progress:
  - "Reading your profile..."
  - "Searching {N} grants in the database..."
  - "Checking Grants.gov..." (if online)
  - "Analyzing {N} potential matches..."
  - "Preparing recommendations..."

**Structured result cards:**

- When the assistant presents grant recommendations, render them as mini-cards within the chat (not just text):
  - Grant name (linked to card page if internal)
  - Grantor + type badge (Federal/State/Foundation)
  - Funding range
  - Deadline (with urgency color coding: green >30 days, yellow 7-30 days, red <7 days)
  - Fit indicator (Strong / Moderate / Low)
  - Quick actions: "Track this" (creates card), "Learn more" (asks assistant for details)

### 6.2 Discover Page Additions

**Empty state enhancement:**
Add to all empty state variants:

```
Need help finding the right opportunity?
[Ask GrantScope →]  (icon: Sparkles)
GrantScope's AI can search our database and help match grants to your program.
```

**Low results banner:**
When search returns <5 results, show a subtle banner after the results grid:

```
Looking for more options? [Ask GrantScope] can search beyond the database.
```

**Header inline prompt (optional):**
Small text link near the search bar: "Or describe what you need → Ask GrantScope"

### 6.3 Programs Page Addition

**Empty state enhancement:**
Update the existing "No programs yet" empty state to include:

```
Not sure where to start?
[Ask GrantScope] can help you identify grants and set up a program in minutes.
```

---

## 7. Data Model Changes

### 7.1 System Settings Table

```sql
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Seed default settings
INSERT INTO system_settings (key, value) VALUES
    ('online_search_enabled', 'false'),
    ('max_online_searches_per_turn', '3'),
    ('assistant_model', '"gpt-4.1"');
```

### 7.2 Conversation Metadata Extension

Add to existing `conversations` table or a new column:

```sql
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS
    tool_usage JSONB DEFAULT '{}';
-- Tracks: {"internal_searches": 3, "grants_gov_searches": 1, "cards_created": 2, ...}
```

---

## 8. Technical Architecture

### 8.1 Backend Changes

**New/Modified Files:**

| File                                    | Change                                                                                                                                                                                       |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/chat_service.py`                   | Add `grant_assistant` tool definitions; extend tool-calling loop to support multiple tools per turn; inject user profile into system prompt; add progress event streaming for each tool call |
| `app/models/db/system_settings.py`      | New: `SystemSetting` ORM model                                                                                                                                                               |
| `app/routers/admin.py`                  | New endpoints: `GET/PUT /admin/settings/{key}` with admin role enforcement                                                                                                                   |
| `app/routers/chat.py`                   | Pass `online_search_enabled` flag to chat service                                                                                                                                            |
| `app/services/grant_assistant_tools.py` | New: Tool handler functions that wrap existing services (RAGEngine, grants_gov_fetcher, sam_gov_fetcher, wizard_service, workstream creation)                                                |
| `app/wizard_service.py`                 | Minor: expose `create_card_from_grant()` and `match_grants()` for tool use                                                                                                                   |

**Architecture pattern:** The chat service remains the orchestrator. A new `GrantAssistantToolkit` class defines tool schemas and handlers. The chat service's existing tool-calling loop is generalized to support N tools (currently hardcoded for 1 web_search tool). Tool availability is determined at conversation start based on admin settings.

### 8.2 Frontend Changes

| File                                 | Change                                                                                         |
| ------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `src/pages/AskGrantScope.tsx`        | Updated scope selector with online mode; new suggested questions; pass context from URL params |
| `src/pages/Discover/index.tsx`       | Add "Ask GrantScope" CTAs to empty states and low-result states                                |
| `src/pages/Workstreams.tsx`          | Add "Ask GrantScope" CTA to empty state                                                        |
| `src/components/ChatPanel.tsx`       | Render structured grant cards in chat; show progress steps; support file upload in chat        |
| `src/components/GrantResultCard.tsx` | New: mini grant card component for rendering recommendations inline in chat                    |
| `src/pages/Settings.tsx`             | Add admin section (visible to admin role users only) with online search toggle                 |
| `src/lib/chat-api.ts`                | Update to pass scope mode (internal/online)                                                    |

---

## 9. Implementation Phases

### Phase 1: Foundation (Core agent + internal search)

- Generalize chat service tool-calling loop to support multiple tools
- Build `GrantAssistantToolkit` with internal tools: `search_internal_grants`, `get_grant_details`, `assess_fit`, `check_user_programs`, `check_user_profile`
- Inject user profile context into system prompt
- Inject current date into system prompt
- Update suggested questions on Ask page
- Add progress event streaming for tool calls

### Phase 2: Actions (Create cards + programs)

- Add tools: `create_opportunity_card`, `add_card_to_program`, `create_program`
- Add confirmation flow in chat before creating resources
- Render created card/program links in chat
- Nudge logic: check user's programs after grant identification

### Phase 3: External search (Online sources)

- `system_settings` table + admin endpoints
- Add tools: `search_grants_gov`, `search_sam_gov`, `web_search`
- Conditional tool registration based on admin setting
- Admin UI in Settings page
- Scope selector update (Internal vs Internal + Online)

### Phase 4: URL & document analysis

- Add tool: `analyze_url` (wraps wizard's `extract_grant_from_url`)
- File upload support in chat (reuse wizard upload infrastructure)
- Structured fit assessment display

### Phase 5: Navigation & UX polish

- Discover page CTAs (empty states, low results, inline prompt)
- Programs page CTA
- Structured grant result cards in chat
- Profile-aware suggested questions
- Context passing from Discover to Ask via URL params

---

## 10. Success Metrics

| Metric                                        | Target                             | Measurement                                                         |
| --------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------- |
| Users who find a relevant grant via assistant | >60% of assistant conversations    | Tool call analysis: did `assess_fit` return "Strong" or "Moderate"? |
| Cards created via assistant                   | >20% of new cards                  | `added_from` field on card creation                                 |
| Programs created via assistant                | >15% of new programs               | Tool call tracking                                                  |
| Discover → Ask navigation rate                | >10% of users who see empty state  | Analytics event                                                     |
| Repeat assistant usage                        | >40% of users return within 7 days | Conversation creation dates                                         |
| Assistant conversations with online search    | Track adoption rate                | Tool call type tracking                                             |

---

## 11. Out of Scope (Future)

- **Proactive notifications** — "New grant matching your profile posted on Grants.gov today" (requires scheduled matching)
- **Multi-user collaboration** — "Share this grant recommendation with your team"
- **Application progress tracking** — The assistant tracking where the user is in the application process
- **Budget analysis** — "Based on your budget range, here's how you'd allocate this grant"
- **Competitive intelligence** — "5 other Texas cities applied for this grant last year"
- **Automated program creation** — System auto-creates a program based on user's first grant interest (vs. assistant-suggested)

---

## 12. Risks & Mitigations

| Risk                                      | Impact                          | Mitigation                                                                                          |
| ----------------------------------------- | ------------------------------- | --------------------------------------------------------------------------------------------------- |
| AI hallucinating grant details            | Users pursue nonexistent grants | Tool-only data policy: assistant never invents grant info, only cites tool results                  |
| Expensive API costs from online search    | Budget overrun                  | Max 3 online searches per turn; admin can disable; usage tracking                                   |
| Slow agent response (multiple tool calls) | Poor UX, user abandonment       | Parallel tool execution where possible; progress streaming; "This may take 30-60 seconds" messaging |
| Stale grant data in DB                    | Users pursue expired grants     | Always check `deadline > current_date`; flag stale cards; assistant warns about old data            |
| Users skip profile setup                  | Poor recommendations            | Assistant detects incomplete profile and guides completion first                                    |
| Admin setting lacks UI                    | Setting never gets configured   | Default to `false` (safe); add to Settings page in Phase 3                                          |
