# Frontend redesign: executed tests and integration results

Date: November 8, 2026. See [agent-validation-report.md](agent-validation-report.md)
for the agent/source-record audit completed before UI changes.

## Implementation

The dashboard now has a top status/navigation bar, backend-derived metrics, an
incident queue with search, and one agent workspace selected through a horizontal
five-stage rail. Every workspace states its inputs, outputs, purpose, and recorded
validation status. Agent 4's coordinating role is stated explicitly.

| Workspace | Data displayed |
|---|---|
| Detect | Native summary, triggered rules and expandable reasons, account/IP, time window, initial severity, assets, evidence and uncertainty |
| Investigate | Ordered timeline, timestamped permission outcomes, clickable asset evidence, final severity, confidence, facts, potential impact, hypotheses, benign explanations and checks |
| Intelligence | Explicit model test and fresh preview, independent saved/preview provenance, cited actions, source-summary categories, resource URLs and limitations |
| Validate | Actual audit-backed handoff/check outcomes, recorded failures, lifecycle/approval/provenance, expandable chronological audit |
| Notify | Active matched recipients and assets, selection reasons, individual drafts, decision confirmation, approval-gated delivery and simulated status labels |

The frontend fetches detail records to obtain asset counts omitted by the list
API. Metrics stay unavailable before the first successful load; delivery counts
are labelled for the selected incident. No agent output or successful status is
hardcoded. The long fallback recommendation list initially shows three items,
with its actual total and an expand/collapse control. Source-entry counts may
repeat across sections and are labelled accordingly.

## Executed automated checks

| Check | Result |
|---|---|
| `npm run lint` | PASS, zero errors/warnings |
| `npm run format:check` | PASS |
| `npm test` | PASS, 8 rendering/selector tests |
| `npm run build` | PASS, Vite production build |
| Backend + actual local RAG suite | PASS, 145 passed / 1 live-model test skipped |
| Rule boundary audit | PASS, 4 included tests |
| Python compileall | PASS |
| Real Chrome browser scenarios | PASS, 31 checks |
| Real Nemotron from current Brev instance | NOT TESTED: instance connection unavailable |

## Browser test method

`frontend/tests/browser-e2e.mjs` uses Playwright with real Google Chrome on this
Mac. It launches `backend.tests.run_browser_backend` on isolated ports 8003 and
8004. The helpers seed temporary P1/P3 databases, run the actual agents, force an
empty model key, and use mock notification delivery. Requests from the real Vite
frontend are forwarded to these real test backends. No user database is reset.
The existing backend on 8001 is also read to verify the actual legacy rejected
report, without changing it.

UI response stubs are used only for deliberately controlled loading, no-source,
403, 503, empty-list, and network-abort scenarios. Those are frontend contract
checks, not claims that agents produced a live-model response. Core agent output,
preview isolation, approval, send blocking, mock delivery and deduplication use
real backend responses.

### Verified scenarios

- Reviewer login, authenticated data loading and backend health.
- Incident overview and actual asset count from detail API.
- Incident search, selected report unchanged by filtering.
- Detection IDs/rules and expanded backend explanations.
- Five-event timeline, 90% rule confidence, all three permission states, and
  selecting DC-SRV-05 to inspect PERM-003 evidence.
- No-key connection test reports fallback, never live success.
- Fresh actual RAG preview preserves saved intelligence, recipients and approval.
- Return from preview to saved intelligence.
- Long recommendation sets expand while retaining the actual count.
- Recommendation citation opens the referenced summary.
- Actual recorded validation checklist and audit entries.
- Three recipient-specific message previews.
- Before approval: no send action and backend send returns 409.
- Confirmation cancel/Escape works; confirmed approval enables sending.
- Rerun creates no duplicate and preserves approval.
- Actual mock sending produces three “Mock sent · simulated” results; repeat send
  is rejected with 409.
- Confirmed rejection on another real temporary backend removes send actions.
- Viewer cannot approve via UI or API (403); live-model actions are disabled.
- Sign out clears browser authentication.
- Keyboard ArrowLeft/ArrowRight workflow navigation.
- All five workspaces fit a 390px viewport without page horizontal overflow;
  the stage rail scrolls internally.
- Pending/loading, no-source, authorization error, offline health, API failure,
  and empty collection states.
- Export invokes browser print (print function instrumented; physical printing
  and OS print-dialog interaction were not tested).
- Actual legacy missing fields are labelled, and its rejected decision survives.
- No uncaught browser JavaScript exceptions. Intentional 403/409/503 and aborted
  requests in the scenarios above are expected test conditions.

Final result: **31 browser checks passed**. Individual PASS entries are saved in the JSON artifact.

## Review artifacts

Artifacts are local, ignored by Git:

- [Intelligence desktop](../.cache/validation/redesign-intelligence-desktop.png)
- [Notifications desktop](../.cache/validation/redesign-notifications-desktop.png)
- [Mobile](../.cache/validation/redesign-mobile.png)
- [Browser results](../.cache/validation/redesign-browser-results.json)
- [Pre-redesign actual agent outputs](../.cache/validation/agent-outputs-before.json)
- [Pre-redesign existing API response](../.cache/validation/existing-api-before.json)

## Files changed or added

Production frontend: `src/App.jsx`, `src/styles.css`, `src/api.js`, `src/model.js`,
`src/components/{ui,Workflow,AgentViews,IntelligenceView,NotificationView}.jsx`.
The prior unused `IncidentDetail.jsx` lost an unused prop to satisfy lint; old
components remain for compatibility but are not mounted by the new App.

Tooling/tests: package.json/lock, eslint.config.js,
`tests/{agent-workspace.test,incident-render.test,browser-e2e}.mjs`,
`tests/fixtures/incident.json`. Development-only lint/format/browser dependencies
were added; no new runtime framework or backend dependency was introduced.

Backend changes are limited to **test-only additions**:
`backend/tests/test_agent_rule_boundaries.py` and
`backend/tests/run_browser_backend.py`. Production backend/agent logic, contracts,
and schemas are unchanged.

Documentation: this report, agent-validation-report.md, demo-walkthrough.md,
and a link/navigation update in how-to-run.md. Pre-existing user documentation
changes were preserved. No commit or push was performed.

## Reproduce locally

From the project root:

```sh
source .venv/bin/activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

In another terminal:

```sh
cd frontend
npm install
npm run dev -- --host localhost --port 5173 --strictPort
```

In a third terminal, from `frontend/`:

```sh
npm run lint
npm run format:check
npm test
npm run build
npm run test:e2e
```

Browser tests expect a populated knowledge index, local `.env` with reviewer/viewer
passwords and JWT secret, `.venv` at the root, and ports 8003/8004 free. They expect
frontend API default `http://localhost:8001/api` and read the real existing INC-001
legacy incident on 8001. The Mac uses installed Google Chrome. On other systems,
install Playwright's Chromium (`npx playwright install chromium`) or set
`PLAYWRIGHT_CHROMIUM_EXECUTABLE` to the browser executable.

Local-RAG/backend checks, from project root:

```sh
SENTINELAI_RUN_RAG_INTEGRATION=1 python -m pytest -q
python -m compileall -q backend tests
```

The executed run used the existing cached MiniLM model:

```sh
SENTINELAI_RUN_RAG_INTEGRATION=1 HF_HOME=/private/tmp/sentinelai-p2-huggingface HF_HUB_OFFLINE=1 MPLCONFIGDIR=/private/tmp/sentinelai-p2-matplotlib .venv/bin/python -m pytest -q -o addopts=''
```

The browser test used the same cache environment. Those paths are machine-specific;
normal first-time use can download embeddings. Do not use offline mode with an
empty cache.

For real inference, restore access to the supplied existing Brev instance, open
its tunnel, then run the opt-in test. It was not claimed to pass in this run:

```sh
brev port-forward hackutd-nemotron --org sadwi840-84a2d6-3uw7 -p 8000:8000
NEMOTRON_RUN_LIVE=1 python -m pytest backend/tests/test_nemotron_live.py -q
```

## Remaining issues

- Current remote instance is unreachable through the supplied Brev connection.
  Real inference in this redesigned UI is NOT TESTED for this run. Model-generated
  provenance rendering is covered by contract tests; live success is not fabricated.
- Old saved reports can lack timeline/permissions/confidence/provenance. Empty
  states remain until a separate fresh workflow is used; UI does not migrate data.
- Citation provenance is not semantic entailment; generated advice can still need
  correction. Candidate techniques are labelled context rather than confirmed attacks.
- Existing P1/P3 persistence is non-atomic. Some native state fields may lag API
  approval/delivery updates; the UI uses current API incident and recipient rows.
- No agent streaming/progress endpoint exists; tabs show recorded results only.
- The existing rejected incident cannot demonstrate approve/send again. Use new
  isolated demo database filenames as described in demo-walkthrough.md.
