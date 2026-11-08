# Agent correctness audit — before frontend redesign

Audit date: November 8, 2026. This report was created before frontend changes.
Sources: `docs/architecture.md`, `docs/datasets.md`, actual P1/P2/P3 code, seed JSON,
existing tests, an isolated fresh real-agent workflow, and the authenticated running
API. The architecture references a separate spec that is not present; none was invented.

Initial working tree: modified `docs/how-to-run.md` and untracked
`docs/agent-flow-and-frontend.md`; both preserved.

## Baseline results

**141 tests passed, 1 live-API test skipped** in 9.88 s with real local RAG enabled.
No agent algorithm or database schema was changed for this redesign.

| Agent | Expected output | Actual output | Correct? | Frontend issue | Required fix |
|---|---|---|---|---|---|
| 1 Detection | One incident for LOG-101–105; unfamiliar source, invalid access, asset burst; valid accounts/assets/rules | One INC-001, admin_04, 198.51.100.24, 09:10–09:18 UTC; R1/R2/R4, high initial severity; seeded decoys excluded | PASS for audited scenario; boundary checks recorded below | Rules, initial severity, and event IDs scattered/hidden; no dedicated detection view | Show actual detection contract, expandable rule reasons, inputs/outputs, and evidence |
| 2 Investigation | Five ordered events; correct timestamped permission states; facts separate from hypotheses | DC-SRV-04 authorized, DC-SRV-05 expired, DC-DB-01 none; high severity, 0.9 confidence, five events in fresh output | PASS fresh output; PARTIAL legacy persisted report | Current saved API record has no timeline, confidence, affected_assets or potential_impact; hypotheses also absent | Show fresh fields when supplied; label missing legacy data, never reconstruct facts from expectations |
| 3 Intelligence | Filtered MITRE/policy/case retrieval, valid JSON/citations, real inference or labelled fallback | Real local Chroma/MiniLM exercised by tests; isolated no-key run produced grounded fallback; prior saved report has no provenance | PARTIAL: structure/provenance tested, semantic correctness is not guaranteed; current live check pending at initial report creation | Connection status, saved report, preview and fallback mixed; references duplicated | Separate all provenance states; label summaries as summaries; show limitations and exact citation IDs |
| 4 Orchestrator | 1→2→3→5 handoffs, validation, deduplication, audit, incomplete states, saved approval | Fresh isolated run: awaiting_approval, zero errors, 14 audit events; repeat reused exact incident; schema/fake-ID/failure tests pass | PASS tested paths; PARTIAL persistence architecture | Static “Evidence verified” overstates legacy records; tabs look like processing progress; errors lack context | Derive checks from audit only; show not-recorded states, actual lifecycle, failures and persisted events |
| 5 Owners/drafts | Active owners only; personalized asset evidence; approval before mock send | Seed mappings independently yield EMP-001/003/006; excludes backup EMP-002 and inactive mapping; fresh drafts generated; delivery/authorization tests pass | PASS tested paths; PARTIAL old persisted drafts can be incomplete | Owners and decisions always crowd other agents; rejected state prevents repeating approval demo | Dedicated notification view; preserve reviewer decision; clearly explain fresh-demo DBs and simulated delivery |

## Independent source-record checks

Captured in ignored `.cache/validation/agent-outputs-before.json` using
`.cache/validation/audit_agents.py`; no scenario manifest was consumed by agents.

- Exactly LOG-101, 102, 103, 104, 105 were returned by detection.
- Each source event belongs to admin_04 / 198.51.100.24.
- Actual permission rows were compared at each asset's event timestamp; a grant
  is valid only if valid_from <= timestamp < valid_until (open end allowed).
- PERM-001 supports DC-SRV-04. PERM-003 for DC-SRV-05 expired before the event.
  No valid admin_04 grant exists for DC-DB-01.
- Actual employee_assets rows were filtered by active mapping, active employee,
  and responsibility_type=owner. Result: EMP-001/003/006, not backups/inactive links.
- Timeline order/count and confidence 0.9 were asserted against the fresh output.
- Fresh workflow completed with the same owners, no errors, and duplicate reuse.

## Actual running API inspected

An authenticated GET `/api/incidents/INC-001` returned status `rejected`, all
three expected recipient IDs, 32 audit events, no ai_generation, and zero projected
timeline entries. Its saved investigation contained only normalized status, facts,
reasons, incident/evidence/permission/asset IDs, and severity. The current fresh
workflow includes the native fields, but deduplication intentionally preserves
this old rejected record. Changing the UI must not silently replace or repair it.

## Backend findings kept separate from the UI

1. **Legacy data is incomplete.** Existing persisted reports/drafts are not
   automatically migrated or regenerated. Use isolated fresh demo databases for
   a new pending workflow; do not reset reviewer decisions behind the UI.
2. **Two SQLite stores remain.** P1 and P3 writes are not an atomic transaction.
   This redesign does not change schemas or consolidate them.
3. **Provenance is not entailment.** Citation checks establish retrieved IDs and
   metadata consistency. They cannot guarantee each model sentence, especially
   claims about historical-case coverage. T1110 can be a retrieval distractor;
   it must be labelled candidate guidance, not a confirmed attack.
4. **Some failure details are not exposed in successful report API shapes.** The
   UI will show errors that exist in response/audit, and explicitly state when
   an error list or validation event was not supplied.
5. **The list API omits asset and delivery counts.** The frontend must request
   incident details or mark counts unavailable. Global notification metrics
   cannot be inferred from one selected incident.
6. **No live progress stream exists.** Saved stage availability and persisted
   validation events are not real-time agent execution.
7. **Model preview does not save report/drafts.** A fresh preview must remain
   visibly separate from saved intelligence and approved messages.

## Planned frontend response

Replace overlapping detail panels with one selected-agent workspace; preserve
existing API contracts and backend authorization. Expose confidence, permission
states, timelines, hypotheses, citations, and audit checks only when supplied.
Missing fields use informative empty states. All live-model actions stay explicit.

## Follow-up evidence

Later live results, boundary checks, redesigned frontend tests and browser runs
will be recorded in `docs/frontend-test-results.md` and appended here. PASS above
is scoped to the inspected dataset and executed tests, not every possible input.

## Final audit update after redesign

- Controlled R3/R4 threshold/window, maintenance-exclusion, and account/source/gap
  grouping checks were added under `backend/tests/test_agent_rule_boundaries.py`:
  **4 passed**. These are test-only synthetic boundary inputs, separate from the
  independent checks over the original seed records above.
- Final local backend suite: **145 passed, 1 skipped** in 9.09 seconds with real
  Chroma/MiniLM integrations enabled. The skipped test is explicitly live Nemotron.
- Fresh real-agent outputs are captured in the test-only frontend fixture
  `frontend/tests/fixtures/incident.json`; runtime frontend code never imports it.
- Current live Nemotron status: **NOT TESTED / externally blocked**. The supplied
  `brev port-forward` command reported no SSH address for the existing instance.
  A read-only `brev exec ... curl .../v1/models` retry initially could not resolve
  the SSH destination and exited with status 7. No server, GPU, or deployment
  was modified. Earlier successful live checks in runtime-check-results.md are
  historical evidence, not proof of current reachability.
- Agent 3 remains **PARTIAL** overall: local retrieval, fallback, schema validation,
  provenance labels, injection tests, and citation checks pass; live generation
  and sentence-level semantic correctness are not certified by this run.
- The redesigned UI has no assumed “evidence verified” badge. Stage checks come
  from actual validation audit events; missing legacy fields remain explicit.
- Agent 2 confidence, authorization states and five-event timeline are shown for
  fresh output; an old report with absent fields shows empty states instead.
- Agent 5's actual active owners and draft contents are visible in their own
  workspace. Browser approval/delivery scenarios use temporary mock-mode stores.
- Frontend and browser evidence, including explicit response stubs for error/empty
  states, is recorded in [frontend-test-results.md](frontend-test-results.md).

Remaining production gaps were not hidden or silently repaired: separate database
transactions, legacy persisted omissions, generated prose not guaranteed entailed
by its citations, and no live stage-progress stream. Current Agent 2 also passes
`impact_confirmed=False` to the severity rubric; severe-impact escalation outside
the provided scenario needs separate validation before production use.

Final frontend evidence: **8 rendering/selector tests and 31 real-Chrome checks passed**; lint, formatting and production build passed. Live model connectivity remains externally blocked in this run.
