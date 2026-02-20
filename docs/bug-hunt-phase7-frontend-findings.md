# Frontend Bug Hunt - Phase 7 Findings and Fixes

Date: 2026-02-20

## Fixed Bugs

1. Signal chat thread state could leak between cards (High)
- Symptom: Opening chat on one signal card, then switching to another card, could preserve prior thread/UI state in the panel.
- Root cause: `ChatPanel` instance in the signal detail tab was reused across `cardId` changes without a remount boundary.
- Fix:
  - Added a stable per-card React key to force remount on scope changes.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/CardDetail/ChatTabContent.tsx:48`

2. Workstream chat thread state could leak across workstream navigation (High)
- Symptom: Chat context/messages could persist when navigating between workstreams in the right-side chat panel.
- Root cause: `ChatPanel` instance in workstream chat was reused across `workstreamId` changes.
- Fix:
  - Added a stable per-workstream React key so component lifecycle resets correctly on route/scope transitions.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/WorkstreamChatPanel.tsx:120`

3. Proposal preview could apply stale async responses and miss late proposal-id updates (High)
- Symptom:
  - Overlapping generate/load requests could race and overwrite newer state with stale responses.
  - If `initialProposalId` arrived after mount, the preview could stay on generation path or stale proposal data.
- Root cause:
  - Proposal loading effect ran only on mount and async handlers lacked request-order guards.
- Fix:
  - Added request sequencing (`proposalRequestRef`) to ignore stale responses/errors/loading updates.
  - Updated load/generate flow to pass request IDs through async operations.
  - Added reactive sync for incoming `initialProposalId` and replaced mount-only effect with dependency-based effect.
  - Ensured generation progress interval is always cleaned up.
- Files:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/wizard/ProposalPreview.tsx:109`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/wizard/ProposalPreview.tsx:112`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/wizard/ProposalPreview.tsx:174`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/wizard/ProposalPreview.tsx:198`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/wizard/ProposalPreview.tsx:203`

## Validation

- `pnpm -s lint` passed (warnings only; no errors).
- `pnpm -s test:run` passed (`18` files, `519` passed, `9` skipped).
- `pnpm -s build:prod` passed.
