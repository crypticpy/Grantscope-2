# Frontend Bug Hunt - Phase 6 Findings and Fixes

Date: 2026-02-20

## Fixed Bugs

1. Workstream Kanban research-status polling could fail to start after cards load (High)
- Symptom: Research badges/progress could remain stale after initial board load until a manual action triggered polling.
- Root cause: Polling start effect depended on `hasCardsRef.current`, but ref updates from card loads did not retrigger the effect.
- Fix:
  - Replaced ref-driven gate with memoized `hasAnyCards` derived from cards state.
  - Made polling effect depend on `hasAnyCards` so it starts deterministically once cards appear.
- Files:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamKanban.tsx:799`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamKanban.tsx:807`

2. Workstream Kanban card loads could apply stale/out-of-order responses (High)
- Symptom: Fast repeated loads (initial load + auto-populate refresh + manual refresh) could race and apply an older card snapshot.
- Root cause: `loadCards` wrote state unconditionally with no request-order guard.
- Fix:
  - Added monotonic request guard (`cardsRequestRef`) and ignored stale responses.
  - Scoped loading state updates to the active request only.
  - Propagated success/failure from `loadCards` so refresh toast only reports success on actual refresh.
- Files:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamKanban.tsx:494`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamKanban.tsx:644`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamKanban.tsx:1456`

3. Workstream Kanban mount-time auto-populate flow could update state after unmount (Medium)
- Symptom: Navigating away during initial auto-populate sequence could still run stale state updates and follow-up loads.
- Root cause: mount flow lacked cancellation guard around async auto-populate and reload steps.
- Fix:
  - Added cancellation guards in initial load and load+auto-populate effects.
  - Prevented post-unmount state writes/reloads.
- Files:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamKanban.tsx:678`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamKanban.tsx:697`

4. Discover result list could be overwritten by stale responses during rapid filter/search changes (High)
- Symptom: Quickly changing filters/search mode could briefly show older result sets after newer queries had already started.
- Root cause: concurrent `loadCards` calls had no query-version protection.
- Fix:
  - Added query versioning (`cardsQueryVersionRef`) and applied response/error/loading updates only for the latest query.
  - Hardened `following` mode empty-state handling to explicitly clear cards/count/pagination.
- Files:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:293`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:509`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:520`

5. Discover “Load More” could append stale page data after a query change (Medium)
- Symptom: Pagination responses from an older query could append into the new query’s result list.
- Root cause: `loadMoreCards` appended results without checking current query generation.
- Fix:
  - Captured query version at pagination start and ignored append when query generation changed.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:782`

## Stability Hardening

1. Workstream wizard callbacks now track full form state container (Low)
- Reduced stale-closure risk in step validation/toggle handlers by depending on the full `form` object where callbacks access nested state/actions.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/workstream/WorkstreamWizard.tsx:61`

2. Wizard interview hook removes unnecessary callback wrapping (Low)
- Removed wrapper indirection for `sendMessage` pass-through to avoid dependency ambiguity and reduce hook noise.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/hooks/useWizardInterview.ts:219`

## Validation

- `pnpm -s lint` passed (`0` errors, warnings reduced from `23` to `17`).
- `pnpm -s test:run` passed (`18` files, `519` passed, `9` skipped).
- `pnpm -s build:prod` passed.
