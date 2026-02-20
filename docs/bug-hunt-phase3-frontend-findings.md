# Frontend Bug Hunt - Phase 3 Findings and Fixes

Date: 2026-02-20

## Fixed Bugs

1. `localStorage`/`sessionStorage` API instability in Vitest runtime (Node 22)
- Symptom: auth-dependent tests crashed with `localStorage.setItem is not a function`.
- Root cause: runtime exposed a partial global storage object with missing Storage methods.
- Fix:
  - Added deterministic in-memory Storage shim for both `localStorage` and `sessionStorage`.
  - Cleared both storages before each test to prevent cross-test state leaks.
- Files:
  - `frontend/foresight-frontend/src/test/setup.ts:38`
  - `frontend/foresight-frontend/src/test/setup.ts:88`

2. Tooltip hard crash outside top-level provider
- Symptom: component-level renders crashed with ``Tooltip` must be used within `TooltipProvider``.
- Root cause: desktop tooltip branch required external provider context.
- Fix:
  - Wrapped desktop tooltip rendering path in a local `TooltipPrimitive.Provider` fallback.
- File:
  - `frontend/foresight-frontend/src/components/ui/Tooltip.tsx:90`

3. Lint-blocking unsafe `any` type in chat admin setting API
- Symptom: lint failed on `@typescript-eslint/no-explicit-any`.
- Root cause: `fetchAdminSetting` returned `value: any`.
- Fix:
  - Introduced recursive `JsonValue` type and updated return signature.
- File:
  - `frontend/foresight-frontend/src/lib/chat-api.ts:68`
  - `frontend/foresight-frontend/src/lib/chat-api.ts:649`

4. Broken card-detail integration test contract (fetch mocks inconsistent with actual data flow)
- Symptom: card detail suites intermittently failed due wrong response shapes and loading-state assumptions.
- Root cause: mocks returned research task payloads for card detail endpoints and expected spinner instead of skeleton UI.
- Fix:
  - Added route-aware fetch mock responses for card detail endpoints.
  - Updated loading assertion to skeleton pulse placeholder.
  - Updated maturity assertion to current label-based rendering.
- File:
  - `frontend/foresight-frontend/src/components/CardDetail/__tests__/CardDetail.test.tsx:267`
  - `frontend/foresight-frontend/src/components/CardDetail/__tests__/CardDetail.test.tsx:431`

5. CardDetailHeader test drift from component behavior
- Symptom: header tests failed due outdated expectations (Horizon/Stage badges and old style tokens).
- Root cause: component now uses deadline + pipeline badges and updated summary/style classes.
- Fix:
  - Updated mocks and assertions to current badge model and classes.
- File:
  - `frontend/foresight-frontend/src/components/CardDetail/__tests__/CardDetailHeader.test.tsx:33`
  - `frontend/foresight-frontend/src/components/CardDetail/__tests__/CardDetailHeader.test.tsx:213`
  - `frontend/foresight-frontend/src/components/CardDetail/__tests__/CardDetailHeader.test.tsx:369`

6. Trend comparison label assertions too strict for duplicated label render points
- Symptom: test failed with "Found multiple elements" on card labels.
- Root cause: same label appears in multiple sections of the comparison view.
- Fix:
  - Switched to `getAllByText(...).length > 0` assertions.
- File:
  - `frontend/foresight-frontend/src/components/visualizations/__tests__/TrendComparisonView.test.tsx:353`

7. Login page test contract drift
- Symptom: duplicate title text and outdated subtitle copy caused assertion failures.
- Root cause: redesigned login layout renders desktop+mobile headings and updated subtitle text.
- Fix:
  - Updated tests to use `getAllByText` and current subtitle string.
- File:
  - `frontend/foresight-frontend/src/pages/__tests__/Login.test.tsx:123`

## Validation

- `pnpm -s lint` passed (warnings only; no errors).
- `pnpm -s test:run` passed (`18 passed`, `519 passed`, `9 skipped`).
- `pnpm -s build:prod` passed.
