# Bug Hunt Findings (Phase 2 - Frontend Deep Pass)

Date: 2026-02-20  
Scope: Second-level frontend interaction bugs across queue/feed workflows, with contract mismatches affecting user-visible behavior.

## 1) Personalized Queue follow state can desync from backend (High)
- Symptom: Tapping follow/unfollow in the personalized queue can leave UI state inconsistent when the backend call fails (401/500/network), because success is assumed.
- Root cause: Follow/unfollow requests do not validate `response.ok` before considering the optimistic update successful.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/PersonalizedQueue.tsx:409`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/PersonalizedQueue.tsx:414`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/PersonalizedQueue.tsx:419`

## 2) Personalized Queue pagination can skip cards after dismiss (High)
- Symptom: After dismissing one or more cards, subsequent “Load more” can skip valid cards from the backend ordering.
- Root cause: `offset` advances only on fetch, but optimistic removals reduce visible list length without adjusting `offset`; next page request still uses stale pre-dismiss offset.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/PersonalizedQueue.tsx:317`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/PersonalizedQueue.tsx:331`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/PersonalizedQueue.tsx:375`

## 3) Discovery Queue undo is UI-only and does not reverse backend state (High)
- Symptom: Undo appears to restore a card in the queue, but refresh/reload removes it again because backend review/dismiss state was never reverted.
- Root cause: Review/dismiss actions call backend endpoints, while undo only mutates local React state (no compensating API call).
- Location:
  - Backend-mutating actions:
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/DiscoveryQueue.tsx:975`
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/DiscoveryQueue.tsx:1031`
  - UI-only undo path:
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/DiscoveryQueue.tsx:861`
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/DiscoveryQueue.tsx:943`

## 4) Workstream feed silently drops multi-filter values (Medium)
- Symptom: Workstreams with multiple pillars or pipeline statuses return results filtered by only one value (typically the last value in the query string).
- Root cause: Frontend appends repeated `pillar_id`/`pipeline_status`, but `/api/v1/cards` currently accepts each as a single scalar param.
- Location:
  - Frontend query construction:
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamFeed.tsx:353`
    - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/WorkstreamFeed.tsx:362`
  - Backend scalar params:
    - `/Users/aiml/Projects/grantscope-2/backend/app/routers/cards.py:140`
    - `/Users/aiml/Projects/grantscope-2/backend/app/routers/cards.py:143`

## 5) Personalized Queue does not reload when `pageSize` prop changes (Low)
- Symptom: Parent-level page-size changes do not trigger a fresh initial fetch, leaving stale pagination behavior.
- Root cause: Initial load effect depends only on `user?.id`, while fetch logic depends on `pageSize` via callback closure.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/PersonalizedQueue.tsx:343`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/PersonalizedQueue.tsx:347`

## 6) Discovery Queue progress can display stale counts after empty reload (Low)
- Symptom: Progress percentage can be misleading after reloads where pending cards become empty.
- Root cause: `initialCardCount` only updates when `pendingCards.length > 0`, so previous non-zero baseline can persist.
- Location:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/DiscoveryQueue.tsx:792`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/DiscoveryQueue.tsx:1200`
