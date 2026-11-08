# SentinelAI: a 2–3 minute judge demonstration

## Prepare before the judges arrive

1. Start the private model tunnel, backend on 8001, and Vite on 5173 using
   [how-to-run.md](how-to-run.md). Open http://localhost:5173.
2. Sign in as **reviewer** with your local `.env` password.
3. A saved rejected incident intentionally stays rejected. To demonstrate a new
   approval workflow, stop only your backend and start it with two **unused** demo
   database filenames:

   ```sh
   DATABASE_URL=sqlite:///./.cache/judge-session-01-agent.db \
   DATABASE_PATH=./.cache/judge-session-01-app.sqlite3 \
   NOTIFICATION_MODE=mock \
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
   ```

   Change `01` to another unused suffix for a later independent demo. Do not
   delete records or expect Run Demo to reset an existing reviewer decision.
4. Finish ingestion before serving if the knowledge index is missing:
   `python -m backend.rag.ingest`. Do not rebuild during active retrieval.
5. Choose **Intelligence → Test Nemotron** before presenting. If unavailable,
   explain the fallback honestly; never call a fallback report live AI generation.
   The supplied Brev instance was unreachable during this redesign's final checks.

## The story

> “An unfamiliar administrator login reaches three machines. One access is
> permitted, another succeeds after permission expired, and a critical database
> denies access without permission. We connect those events to evidence,
> relevant guidance, and the people responsible for the machines.”

The logs, people, policies and cases are synthetic. MITRE references come from an
official subset. The application does not monitor a production data center yet.

## 0:00–0:25 — Overview and detection

**Do:** Click Run Demo. Select INC-001. Open Detect and expand R2.

**Say:** “Deterministic rules detect suspicious activity. Here we preserve the
account, source IP, event window and exact log IDs. The model does not decide
whether an incident exists or what severity it has.”

**Point out:** R1 unfamiliar login, R2 invalid permission, R4 multi-asset burst.
R3 is not triggered in this incident. Run Demo reuses matching evidence.

## 0:25–0:55 — Investigation

**Do:** Open Investigate. Select identity-sync-01 / DC-SRV-05.

**Say:** “We check access permission at the actual event time. This machine had
an expired grant, even though access succeeded. The database attempts were
denied, while the jump host access was permitted.”

**Point out:** Five chronological events; Authorized / Expired / No permission;
PERM-003; high severity. Confidence is a rule-based estimate, not a probability.
Confirmed facts are separate from hypotheses and benign alternatives.

If a legacy report has missing fields, show its “not recorded” state rather than
claiming that the frontend verified a permission outcome it did not receive.

## 0:55–1:35 — RAG and Nemotron

**Do:** Open Intelligence. Click Test Nemotron; then Generate AI Preview.

**Say:** “RAG finds relevant MITRE, policy and historical knowledge. Nemotron
uses that context to produce structured recommendations. We validate the output
and citations before displaying an accepted result.”

**Point out:** Connection status, saved provenance and fresh-preview provenance
are three different things. Each action has source-ID buttons; click one to
inspect its output summary. References are candidate guidance, not proof of an
attack. Expand the full action list only if needed.

**If the tunnel/model is unavailable:** “The system continues with clearly labelled
source-only fallback. We can still inspect the retrieved guidance, but this
response is not being presented as Nemotron-generated.”

**Do not say:** “The model fixed the server.” Recommendations do not execute actions.
A preview does not rewrite the saved report or notification drafts.

## 1:35–1:55 — Validation

**Do:** Open Validate and expand one validation/retrieval audit event.

**Say:** “Agent 4 orchestrates every stage. It checks contracts, evidence IDs,
incident identity and retrieved citations, prevents duplicates, and records
failures. These are persisted events, not simulated progress animation.”

Do not claim source-ID checks establish that every generated sentence is true.
Human review remains part of the design.

## 1:55–2:35 — Responsible owners and human approval

**Do:** Open Notify, expand a draft, approve the pending incident and confirm.
Then click Send notifications and confirm, with `NOTIFICATION_MODE=mock` set.

**Say:** “Only active responsible owners receive focused drafts. Backups and
inactive mappings are excluded. Approval is a real server-side gate. This demo
simulates delivery and labels each result accordingly.”

**Point out:** EMP-001, EMP-003 and EMP-006; responsible assets and local evidence;
escalation contact; “Mock sent · simulated.” Approval alone does not send.
A viewer cannot approve or send. Previously delivered recipients cannot be resent.

If rejected, explain that the reviewer decision is preserved and sending is blocked.
Do not reset it mid-demo.

## Closing

> “SentinelAI joins detection, evidence, grounded guidance and owner communication
> in one reviewable workflow. Rules control severity and recipients. AI recommends.
> Humans decide what happens next.”

## Quick answers

| Judge asks | Answer |
|---|---|
| Where is Nemotron used? | Agent 3 generation, plus the explicit connection probe. Agents 1/2/5 are deterministic here. |
| How do you stop hallucinations? | Retrieved context, strict schemas, ID/metadata validation, rejected output/fallback, and reviewer inspection. These reduce risk; they do not guarantee every sentence. |
| What if the GPU is down? | The app labels source-only fallback or no sources; it does not fabricate success. |
| Why is Agent 4 drawn as step 4? | That tab exposes its validation/audit view. The orchestrator actually manages the whole sequence. |
| Is an email really sent? | Not in mock mode. Successful mock results explicitly say simulated. |
| Is this a live production feed? | No. The demo uses linked synthetic records and an official MITRE reference subset. |
| Why does an older report omit fields? | The backend preserved a legacy result. We expose missing fields honestly rather than infer them. |

Executed results and limitations: [agent-validation-report.md](agent-validation-report.md)
and [frontend-test-results.md](frontend-test-results.md).
