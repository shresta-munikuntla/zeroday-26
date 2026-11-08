# Run SentinelAI locally on your Mac

This guide follows the setup used for the successful [live runtime verification](runtime-check-results.md).

**Website:** http://localhost:5173  
**Project:** `/Users/sadwitha_1/Desktop/shit/HackUTD/zeroday-26`

You need three services running:

| Service | Local port | Purpose |
|---|---|---|
| Brev tunnel | 8000 | Connects the Mac to the existing Nemotron server |
| Python backend | 8001 | Runs agents, retrieval, authentication, and APIs |
| React frontend | 5173 | Displays the website |

Do not start another GPU or reinstall the remote model. The existing Brev instance must be running with vLLM available on its port 8000.

## 1. Check whether services are already running

In any terminal:

```sh
lsof -nP -iTCP:8000 -iTCP:8001 -iTCP:5173 -sTCP:LISTEN
```

If the website and backend are already working, reuse them. Do not start duplicate servers on the same ports. The prior verification left all three services running, but they may stop after closing terminals or restarting the Mac.

## 2. One-time local setup

Open a terminal in the project:

```sh
cd "/Users/sadwitha_1/Desktop/shit/HackUTD/zeroday-26"
```

If `.venv` already exists, activate it:

```sh
source .venv/bin/activate
```

Only if it does not exist:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Install frontend packages if needed:

```sh
npm --prefix frontend install
```

These installation commands are setup instructions; the successful runtime verification reused installed dependencies.

## 3. Configure the local .env

Your project already has `.env`. Open it in the editor and preserve existing passwords and secrets.

For a new checkout only, create it without overwriting an existing file:

```sh
cp -n .env.example .env
```

The real-model settings are:

```dotenv
NEMOTRON_BASE_URL=http://127.0.0.1:8000/v1
NEMOTRON_API_KEY=local-vllm
NEMOTRON_MODEL=nvidia/NVIDIA-Nemotron-Nano-9B-v2
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHROMA_PERSIST_DIRECTORY=./data/chroma
NOTIFICATION_MODE=mock
```

`local-vllm` is a non-secret placeholder for the existing unauthenticated vLLM endpoint. An empty API key deliberately selects fallback mode. Keep the endpoint accessible through the private tunnel.

Also fill in these existing authentication settings in `.env`:

```dotenv
JWT_SECRET_KEY=
DEMO_VIEWER_PASSWORD=
DEMO_REVIEWER_PASSWORD=
```

Choose local passwords for viewer and reviewer. Generate a JWT secret of sufficient length with:

```sh
python -c 'import secrets; print(secrets.token_hex(32))'
```

Paste the generated value after `JWT_SECRET_KEY=`. Do not leave these three authentication settings empty when starting the website.

Keep `.env` local and ignored by Git. Leave `.env.example` as the shared empty template. Restart the backend after changing `.env`.

## 4. Terminal 1 — Open the Brev tunnel

Run the exact command used successfully:

```sh
brev port-forward hackutd-nemotron --org sadwi840-84a2d6-3uw7 -p 8000:8000
```

Expected output includes:

```text
localhost:8000 -> hackutd-nemotron:8000
```

The CLI may finish after launching a background SSH forward. Check the listener:

```sh
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

You should see an SSH process listening on loopback port 8000.

Check the remote model through the tunnel:

```sh
curl --fail http://127.0.0.1:8000/v1/models
```

The response should list:

```text
nvidia/NVIDIA-Nemotron-Nano-9B-v2
```

## 5. Terminal 2 — Index documents and start the backend

```sh
cd "/Users/sadwitha_1/Desktop/shit/HackUTD/zeroday-26"
source .venv/bin/activate
```

On first setup, or after knowledge documents change, run ingestion before starting the backend:

```sh
python -m backend.rag.ingest
```

Expected output:

```text
Documents processed: 11; chunks stored: 38; skipped/errors: 0
Excluded test_fixtures/ (use --include-test-fixtures to include).
```

The embedding model may download on first use. Do not rebuild the index while the app is actively retrieving from it.

Verify actual Nemotron JSON inference:

```sh
NEMOTRON_RUN_LIVE=1 python -m pytest backend/tests/test_nemotron_live.py -q
```

Expected result: **1 passed**. This test calls the real model; fallback cannot make it pass.

Start the backend using the command used during verification:

```sh
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

Wait for:

```text
Application startup complete.
```

Leave this terminal running. The backend initializes missing demo databases automatically; there is no need to run the destructive reseeding command.

Open http://localhost:8001/api/health or run:

```sh
curl --fail http://127.0.0.1:8001/api/health
```

Expected response:

```json
{"status":"ok"}
```

Port 8001 serves the API, not the React website. A 404 from its `/` or `/favicon.ico` is expected.

## 6. Terminal 3 — Start the frontend

```sh
cd "/Users/sadwitha_1/Desktop/shit/HackUTD/zeroday-26/frontend"
npm run dev -- --host localhost --port 5173 --strictPort
```

The frontend defaults to `http://localhost:8001/api`. To set it explicitly:

```sh
VITE_API_URL=http://localhost:8001/api npm run dev -- --host localhost --port 5173 --strictPort
```

Use either command, not both. Expected output includes:

```text
Local: http://localhost:5173/
```

Leave this terminal running.

## 7. Open the website and check Nemotron

1. Open **http://localhost:5173**. Use `localhost`, matching the backend's allowed frontend origin.
2. Sign in with username **reviewer** and the value of `DEMO_REVIEWER_PASSWORD` from `.env`.
3. Select **INC-001**.
4. Click **Test Nemotron**. A successful real request displays **Live inference verified**, the model ID, and response time.
5. Click **Generate AI preview**. Wait for **Fresh AI preview → Generated by Nemotron**.
6. Inspect the recommendations and their source IDs. Expand policy, MITRE, or historical-case references.
7. Explore the five tabs: Detect, Investigate, Intelligence, Validate, and Notify.
8. Use Export report to open the print/save-as-PDF dialog.

The first preview may take longer while local embeddings load. Each AI button can make a real GPU inference request when configured.

### Understand the labels

| Label | Meaning |
|---|---|
| Live inference verified | A fresh model request returned the expected verified JSON |
| Generated by Nemotron | This preview/report passed model-output and citation checks |
| Source-only fallback | Retrieval worked, but validated AI generation was unavailable |
| Generation not recorded | An older saved report lacks generation metadata |
| Rejected | The saved reviewer decision rejected notifications; it does not prove the incident harmless |

A successful connection check does not rewrite the saved report. A fresh preview also does not change approval, severity, recipients, or notification drafts. The old saved report may still display fallback guidance below the preview.

## 8. Optional — Start a separate fresh demo

Use this if you want a new pending incident with live-generated intelligence while preserving the existing rejected incident.

Stop the backend in Terminal 2 with Ctrl+C. Then, from the project root with `.venv` active, run:

```sh
DATABASE_URL=sqlite:///./.cache/judges-demo-agent.db \
DATABASE_PATH=./.cache/judges-demo-app.sqlite3 \
NOTIFICATION_MODE=mock \
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

The separate demo databases are created automatically. Refresh the website. The tunnel and frontend remain unchanged.

Reuse this same backend command for subsequent runs of that demo. Its existing incident will be reused. To create another independent demo, choose two new database filenames rather than deleting existing records.

With `NOTIFICATION_MODE=mock`, delivery is simulated after reviewer approval. No real email is sent.

## 9. Reproduce the verification checks

In an additional terminal, from the project root:

```sh
source .venv/bin/activate
python -m pytest -q
SENTINELAI_RUN_RAG_INTEGRATION=1 NEMOTRON_RUN_LIVE=1 python -m pytest -q
python -m compileall -q backend tests
python -m pip check
```

The second test command requires the running tunnel/model and available local embeddings. It includes real inference; the default suite does not.

Frontend checks:

```sh
cd frontend
npm run build
node --test tests/incident-render.test.mjs
```

The recorded verification passed **142 Python tests with no skips**, **2 frontend rendering tests**, and the frontend build. Test counts may change as the project evolves. See [runtime-check-results.md](runtime-check-results.md) for the browser screenshots and isolated full-workflow results.

The earlier run used an already-downloaded embedding cache with this machine-specific command:

```sh
SENTINELAI_RUN_RAG_INTEGRATION=1 NEMOTRON_RUN_LIVE=1 HF_HOME=/private/tmp/sentinelai-p2-huggingface HF_HUB_OFFLINE=1 MPLCONFIGDIR=/private/tmp/sentinelai-p2-matplotlib .venv/bin/python -m pytest -q -o addopts=''
```

Use that variant only if that cache still exists. Normal commands can download MiniLM when needed; do not set offline mode against a missing cache.

## 10. Troubleshooting

| Problem | Action |
|---|---|
| Port already in use | Check with `lsof`; reuse the existing service or stop it in its original terminal with Ctrl+C |
| `brev: command not found` | Use the Mac where the Brev CLI is already installed and signed in, or complete the CLI setup for this Mac |
| Brev requests login | Authenticate with your existing Brev account that can access this instance |
| Connection refused on 8000 | Start/check the Brev forward; confirm `/v1/models` responds |
| Model endpoint responds but AI test fails | Confirm the exact model ID and inspect the test failure; the client already includes the verified Nano v2 JSON-mode fixes |
| JWT/password startup error | Fill the three authentication settings in `.env`, then restart the backend |
| Website cannot reach backend | Verify `/api/health` on 8001 and the frontend API URL; restart Vite after changing its environment |
| Blank page or old layout | Hard-refresh with Cmd+Shift+R; use Cmd+Option+J in Chrome to inspect a red JavaScript error |
| Report is still rejected or shows old fallback | Expected for an existing saved incident; use Generate AI preview or the separate fresh-demo databases |
| Preview shows fallback | Check the tunnel, API key, knowledge index, and backend output; an invalid model response is deliberately rejected |
| Hugging Face warning about no token | It is not a Nemotron authentication failure; the embedding model can download without a token, subject to rate limits |

## 11. Stop the project

- Frontend: Ctrl+C in Terminal 3.
- Backend: Ctrl+C in Terminal 2.
- Tunnel: Ctrl+C if it is still attached to Terminal 1. If the CLI launched SSH in the background, use `lsof -nP -iTCP:8000 -sTCP:LISTEN`, identify that specific forwarding process, and stop only that process.

Stopping the tunnel does not stop or deallocate the remote GPU. Manage GPU uptime separately in Brev.
