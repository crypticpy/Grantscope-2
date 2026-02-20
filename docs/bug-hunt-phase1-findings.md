# Bug Hunt Findings (Phase 1)

Date: 2026-02-20
Scope: Core frontend pages/interactions and backend contracts they depend on.

## 1. Frontend production build is broken (Critical)
- Symptom: `pnpm build:prod` fails with `TS2769` in `vite.config.ts`.
- Root cause: `test` config is defined while using `defineConfig` from `vite`, which does not include Vitest `test` keys.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/vite.config.ts:4`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/vite.config.ts:26`

## 2. CardDetail crash on research task parsing (High)
- Symptom: runtime `TypeError: tasks.filter is not a function` in CardDetail.
- Root cause: assumes `/api/v1/me/research-tasks` always returns an array.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/CardDetail/CardDetail.tsx:214`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/CardDetail/CardDetail.tsx:216`

## 3. CardDetail emits unhandled promise rejections (High)
- Symptom: async load path rejects from `useEffect`, causing noisy unhandled rejections and unstable UI.
- Root cause: `loadCardDetail()` has `try/finally` with no `catch`.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/CardDetail/CardDetail.tsx:172`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/CardDetail/CardDetail.tsx:473`

## 4. Discover filters are no-op for many controls (High)
- Symptom: several Discover filters appear to work in UI but are ignored server-side.
- Root cause: frontend sends query params unsupported by `/api/v1/cards`.
- Location:
  - Frontend query construction:
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:617`
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:655`
  - Backend `/cards` contract:
    - `/Users/aiml/Projects/grantscope-2/backend/app/routers/cards.py:97`

## 5. Discover sort options partially broken (High)
- Symptom: “Recently Updated” and “Signal Quality” sorts do not sort correctly.
- Root cause: frontend sends sort keys not handled by backend sorter.
- Location:
  - Frontend mapping:
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/utils.ts:29`
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/utils.ts:34`
  - Backend supported sorts:
    - `/Users/aiml/Projects/grantscope-2/backend/app/routers/cards.py:150`

## 6. Discover “following” deep-link race can show empty results (Medium)
- Symptom: navigating to `?filter=following` may render empty and stay empty.
- Root cause: initial load runs before followed IDs are available, and effect intentionally excludes `followedCardIds`.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:383`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:390`

## 7. Discover pagination query diverges from first-page query (Medium)
- Symptom: page 2+ can include mismatched cards relative to active filters.
- Root cause: `loadMoreCards()` omits parts of the base query.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:715`

## 8. Follow/unfollow UI can desync from backend (Medium)
- Symptom: UI toggles follow state even when server call fails.
- Root cause: no `response.ok` validation before local state mutation.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:771`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamFeed.tsx:457`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/CardDetail/CardDetail.tsx:341`

## 9. Unfollowing in “following” view does not remove card from list (Medium)
- Symptom: in Discover following mode, card remains visible after unfollow until reload.
- Root cause: state updates followed ID set but does not evict the card from displayed list.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:756`

## 10. Personalized queue endpoint missing (Low)
- Symptom: PersonalizedQueue integration references endpoint not implemented by backend.
- Root cause: frontend calls `/api/v1/me/discovery/queue` without server route.
- Location:
  - Frontend call site:
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/lib/discovery-api.ts:908`
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/PersonalizedQueue.tsx:318`

