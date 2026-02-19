# Backend Bug Tracker (Living)

Last updated: 2026-02-19
Scope: backend modules + data operations

## Fixed This Pass

| Priority | Status | Bug | File(s) |
|---|---|---|---|
| P0 | Fixed | IDOR / missing authorization checks across application-scoped routes (`applications`, `budget`, `checklist`, `attachments`, `collaboration`, `exports`). | `/Users/aiml/Projects/grantscope-2/backend/app/services/access_control.py:47`, `/Users/aiml/Projects/grantscope-2/backend/app/routers/applications.py:173`, `/Users/aiml/Projects/grantscope-2/backend/app/routers/budget.py:138`, `/Users/aiml/Projects/grantscope-2/backend/app/routers/checklist.py:61`, `/Users/aiml/Projects/grantscope-2/backend/app/routers/attachments.py:91`, `/Users/aiml/Projects/grantscope-2/backend/app/routers/collaboration.py:106`, `/Users/aiml/Projects/grantscope-2/backend/app/routers/exports.py:179` |
| P0 | Fixed | Workflow bypass: `PATCH /applications/{id}` could mutate status directly and skip transition/history logic. | `/Users/aiml/Projects/grantscope-2/backend/app/routers/applications.py:240` |
| P0 | Fixed | Wizard session ownership not enforced in application creation; plus invalid `workstream_id` source in `create_from_wizard`. | `/Users/aiml/Projects/grantscope-2/backend/app/services/application_service.py:73`, `/Users/aiml/Projects/grantscope-2/backend/app/services/application_service.py:78` |
| P1 | Fixed | Checklist update allowed cross-application attachment linking. | `/Users/aiml/Projects/grantscope-2/backend/app/routers/checklist.py:260` |
| P1 | Fixed | Attachment upload allowed linking `checklist_item_id` from another application. | `/Users/aiml/Projects/grantscope-2/backend/app/routers/attachments.py:176` |
| P1 | Fixed | Blob orphan risk on upload/replace DB failure (blob created before DB flush). Added cleanup-on-error. | `/Users/aiml/Projects/grantscope-2/backend/app/services/attachment_service.py:192`, `/Users/aiml/Projects/grantscope-2/backend/app/services/attachment_service.py:333` |
| P1 | Fixed | Collaboration role integrity: collaborator API could assign `owner` role and did not block removing true app owner. | `/Users/aiml/Projects/grantscope-2/backend/app/services/collaboration_service.py:49`, `/Users/aiml/Projects/grantscope-2/backend/app/services/collaboration_service.py:103` |
| P1 | Fixed | Comments integrity/permissions: no role gate, weak proposal/parent validation. | `/Users/aiml/Projects/grantscope-2/backend/app/routers/collaboration.py:547`, `/Users/aiml/Projects/grantscope-2/backend/app/routers/collaboration.py:662` |
| P2 | Fixed | Checklist update could not clear nullable fields/attachment due `is not None` checks; now supports explicit nulling for nullable fields and validates non-nullables. | `/Users/aiml/Projects/grantscope-2/backend/app/routers/checklist.py:228`, `/Users/aiml/Projects/grantscope-2/backend/app/routers/checklist.py:255` |

Commits:
- `c5f2374` backend: enforce app-scoped access and workflow integrity
- (next commit will include this tracker + checklist nullability fix)

## Deferred To Auth/Login Sprint

| Priority | Status | Bug | File(s) |
|---|---|---|---|
| P1 | Deferred (intentional) | Hardcoded auth dependency still used broadly (`get_current_user_hardcoded`). Keep for current dev/test phase; replace in auth sprint with Entra ID flow. | `/Users/aiml/Projects/grantscope-2/backend/app/deps.py:70` and multiple routers |

## Open Issues Remaining

| Priority | Status | Bug | File(s) |
|---|---|---|---|
| P0 | Open | Migration runner masks SQL errors (`ON_ERROR_STOP=0`) and continues on warnings, which can hide partial/failed migrations. | `/Users/aiml/Projects/grantscope-2/infra/migrate.sh:60`, `/Users/aiml/Projects/grantscope-2/infra/migrate.sh:65`, `/Users/aiml/Projects/grantscope-2/infra/migrate.sh:71` |
| P1 | Open | `run_migration.py` is operationally misleading: says it applies migration but only prints SQL. | `/Users/aiml/Projects/grantscope-2/backend/run_migration.py:4`, `/Users/aiml/Projects/grantscope-2/backend/run_migration.py:119` |
| P1 | Open | Dual migration systems are present (Supabase SQL + Alembic) without a single source-of-truth process documented for runtime use. | `/Users/aiml/Projects/grantscope-2/README.md:86`, `/Users/aiml/Projects/grantscope-2/backend/alembic/env.py:1` |
| P2 | Open | Delete-path consistency still has transactional edge case potential (blob delete and DB commit are not atomic). | `/Users/aiml/Projects/grantscope-2/backend/app/services/attachment_service.py:265`, `/Users/aiml/Projects/grantscope-2/backend/app/services/attachment_service.py:269` |

## Migration Cleanup Guidance (Archive, Do Not Delete)

1. Keep all applied migration SQL immutable.
2. Create `/Users/aiml/Projects/grantscope-2/supabase/migrations/archive/`.
3. Move old/superseded SQL files into `archive/` only after they are applied in every active environment.
4. Keep `infra/migrate.sh` targeting only top-level `supabase/migrations/*.sql` so archived files are ignored.
5. Add a migration ledger table (`schema_migrations`) and switch runner to apply only unapplied files with `ON_ERROR_STOP=1`.
6. Remove or rename `/Users/aiml/Projects/grantscope-2/backend/run_migration.py` to avoid accidental usage.
7. Decide one source of truth: either fully SQL-file-driven migrations, or Alembic-driven; do not run both independently.

## Verification Run

- `python -m compileall backend/app` passed.
- `pytest -q backend/tests` passed (`91 passed`), with existing deprecation warnings unrelated to this fix set.
