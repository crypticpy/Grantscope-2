# Frontend Bug Hunt - Phase 5 Findings and Fixes

Date: 2026-02-20

## Fixed Bugs

1. Workstream Feed can render stale data after route changes or overlapping fetches (High)
- Symptom: Rapidly switching workstream routes or triggering refreshes could show mismatched workstream/card data from an older in-flight request.
- Root cause: Async loaders updated state without request ordering guards.
- Fix:
  - Added monotonic request guards for workstream and feed fetches.
  - Ignored stale responses and prevented stale loading/error state writes.
  - Stabilized effect wiring with memoized loaders and explicit dependencies.
- Files:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamFeed.tsx:271`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamFeed.tsx:277`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamFeed.tsx:349`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamFeed.tsx:461`

2. Workstream Feed follow badges can drift after refresh (Medium)
- Symptom: Refreshing the workstream feed could update cards but leave follow-heart state outdated.
- Root cause: Refresh action reloaded feed cards but not followed-card IDs.
- Fix:
  - Refresh now reloads both feed results and followed IDs.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamFeed.tsx:527`

3. Workstreams page can apply stale list responses during overlapping loads (High)
- Symptom: Triggering multiple list reloads (initial load + mutation-driven refreshes) could apply out-of-order responses.
- Root cause: No request sequencing guard on `loadWorkstreams`.
- Fix:
  - Added request-id guard to ignore stale responses.
  - Clears stale workstream/scan state when auth token is missing.
  - Stabilized initial-load effect via memoized loader dependency.
- Files:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Workstreams.tsx:663`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Workstreams.tsx:740`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Workstreams.tsx:791`

4. Discover followed-only state can leak across auth transitions (Medium)
- Symptom: Followed-card filters could persist stale IDs when auth/token state changed.
- Root cause: Initial data effect depended on user ID but used detached loader functions and did not consistently clear followed IDs when auth was unavailable.
- Fix:
  - Inlined initial data load with cancellation guard.
  - Explicitly clears `followedCardIds` when no user or token is present.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:417`

5. AskGrantScope URL scope deep-linking ignored updates after mount (Medium)
- Symptom: Navigating to Ask with `?scope=grant_assistant` after initial mount could fail to reinitialize chat scope.
- Root cause: Scope initialization effect ran only once on mount.
- Fix:
  - Made scope init reactive to URL/search state with guard to avoid redundant resets.
  - Clears stale scope ID when switching to grant scope from URL.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/AskGrantScope.tsx:273`

## Validation

- `pnpm -s lint` passed (warnings only; no errors).
- `pnpm -s test:run` passed (`18` test files, `519 passed`, `9 skipped`).
- `pnpm -s build:prod` passed.
