# SentinelAI demo script

The demo uses fictional seed data and the mock notification adapter. A mocked delivery is recorded for the demo and is never actually sent to a person.

## Before the demo

1. Start the backend and frontend using the commands in the README.
2. Open `http://localhost:5173` and sign in as `reviewer` with `DEMO_REVIEWER_PASSWORD` from the local `.env`.
3. Keep the API running at `http://localhost:8000` and confirm `/api/health` returns `{"status":"ok"}`.

## Walkthrough

1. Click **Run demo scenario**. The API runs Agent 1 detection and Agent 2 investigation on the seeded SQLite database, then sends those outputs to Agent 5. The current synthetic scenario produces `INC-001`.
2. Read the incident summary: the activity occurred Saturday from an unfamiliar source; access to `DC-SRV-05` succeeded after its permission expired; two attempts against critical `DC-DB-01` were denied. No data transfer is claimed.
3. Review the timeline IDs, affected asset criticalities, Agent 2's permission checks and confirmed facts, and its benign explanations to check. ATT&CK and policy sections are waiting for Agent 3's RAG integration.
4. Expand each **Preview message**. Show that `Avery Chen` receives only the bastion host's evidence, `Sam Delgado` only the identity server's evidence, and `Casey Brooks` only the database evidence. Each includes login event `LOG-101` and explains why the owner was selected.
5. Click **Approve notifications**. The reviewer identity and timestamp are saved. Open the audit trail to show the `approved` event.
6. Click **Send notifications**. The mock adapter records each result as **Mocked — not actually sent**. The notification records and audit history show the outcome.
7. Optional: sign out and log in as `viewer`. The incident remains readable, while reviewer actions are unavailable and rejected by the API if called directly.

## Expected routing

- `EMP-001` → `DC-SRV-04`
- `EMP-003` → `DC-SRV-05`
- `EMP-006` → `DC-DB-01`
- `EMP-002` is a backup and receives nothing; `EMP-008` has an inactive mapping and receives nothing.
- Querying `DC-SRV-06` alone routes to `mock:team-server-admin` because there is no active individual owner.

The demo uses the real Agent 1 and Agent 2 functions against the synthetic database. Agent 3 intelligence and Agent 4 orchestration can be connected when those components are available.
