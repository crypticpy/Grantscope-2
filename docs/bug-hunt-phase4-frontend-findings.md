# Frontend Bug Hunt - Phase 4 Findings and Fixes

Date: 2026-02-20

## Fixed Bugs

1. Workstream dropdown can remain permanently empty in Quick Create when auth context loads late (High)
- Symptom: In slow auth/bootstrap paths, the Quick Create tab can render with no workstream options and never recover until remount.
- Root cause: Workstream fetch effect ran only once on mount; if `user` was unavailable then, the early return prevented any later retry.
- Fix:
  - Re-trigger workstream loading when `user?.id` becomes available.
  - Reset loading state per fetch attempt.
  - Added cancellation guard to avoid post-unmount state writes.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/CreateSignal/QuickCreateTab.tsx:86`

2. Create Signal modal has the same auth timing race for workstream options (High)
- Symptom: Opening Create Signal during delayed user hydration can leave workstream selector empty for the entire open session.
- Root cause: Modal workstream effect depended only on `isOpen`, not auth readiness.
- Fix:
  - Added `user?.id` as effect trigger while modal is open.
  - Reset loading and list state predictably.
  - Added cancellation guard.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/components/CreateSignal/CreateSignalModal.tsx:315`

3. Discover quick filter `new` can be silently overridden by explicit date filter (Medium)
- Symptom: Combining `?filter=new` with date range controls could send duplicate `created_after` params, causing backend parsing to apply only one bound unpredictably.
- Root cause: Query builder appended `created_after` once for quick filter and again for `dateFrom`.
- Fix:
  - Added `getEffectiveCreatedAfter()` to merge both lower bounds into one deterministic value.
  - Applied the same merge in both initial load and pagination (`loadMoreCards`).
- Files:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:145`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:659`
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Discover/index.tsx:762`

4. Debounce hook can show stale pending state and can crash on non-serializable values (Medium)
- Symptom:
  - Pending indicator may remain true when input returns to the debounced value before timeout settles.
  - `JSON.stringify` comparison can throw for circular/non-serializable values.
- Root cause: Effect did not account for unchanged value transitions and used unsafe stringify comparison without fallback.
- Fix:
  - Added early return to clear pending when value is effectively unchanged.
  - Added safe fallback to `Object.is` when stringify fails.
  - Included `debouncedValue` in effect dependencies to keep change checks current.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/hooks/useDebounce.ts:44`

5. Settings notification email mode can desync from account email after auth hydration (Medium)
- Symptom: “Use account email” toggle can be initialized incorrectly if preferences load before `user.email` is available.
- Root cause: Notification preference loader captured stale `user?.email` and did not rerun when account identity finished loading.
- Fix:
  - Memoized loaders.
  - Re-ran initial loading effect when notification loader dependencies change.
  - Bound account-email comparison to current `user?.email`.
- File:
  - `/Users/aiml/Projects/grantscope-2/frontend/foresight-frontend/src/pages/Settings.tsx:116`

## Validation

- `pnpm -s lint` passed (warnings only; no errors).
- `pnpm -s test:run` passed.
- `pnpm -s build:prod` passed.
