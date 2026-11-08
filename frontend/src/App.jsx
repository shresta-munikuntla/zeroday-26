import React, { useCallback, useEffect, useRef, useState } from "react";
import Login from "./Login.jsx";
import Workflow from "./components/Workflow.jsx";
import {
  DetectionView,
  InvestigationView,
  ValidationView,
} from "./components/AgentViews.jsx";
import IntelligenceView from "./components/IntelligenceView.jsx";
import NotificationView from "./components/NotificationView.jsx";
import {
  Badge,
  Button,
  Empty,
  ErrorNotice,
  Icon,
  Severity,
  StageIntro,
} from "./components/ui.jsx";
import { stages, assetCount, humanize, validationFor } from "./model.js";
import {
  approve,
  checkNemotron,
  getHealth,
  getIncident,
  getIncidents,
  previewIntelligence,
  reject,
  runDemo,
  send,
} from "./api.js";

function readUser() {
  try {
    return JSON.parse(sessionStorage.getItem("sentinel_user") || "null");
  } catch {
    return null;
  }
}
function apiMessage(error, fallback) {
  const detail = error.response?.data?.detail;
  return typeof detail === "string"
    ? detail
    : error.response?.status === 403
      ? "Reviewer access is required for this action."
      : error.response?.status === 401
        ? "Your session has expired. Sign in again."
        : fallback;
}

export default function App() {
  const [user, setUser] = useState(readUser);
  const [incidents, setIncidents] = useState([]);
  const [incident, setIncident] = useState(null);
  const [selected, setSelected] = useState("");
  const [stageId, setStageId] = useState("detect");
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [backend, setBackend] = useState("checking");
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [operation, setOperation] = useState("");
  const [connection, setConnection] = useState(null);
  const [checking, setChecking] = useState(false);
  const [preview, setPreview] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [aiError, setAiError] = useState("");
  const [search, setSearch] = useState("");
  const selectedRef = useRef("");
  const requestRef = useRef(0);
  const previewId = useRef("");
  const detailCache = useRef({});
  const refresh = useCallback(async (id = selectedRef.current) => {
    const request = ++requestRef.current;
    setLoading(true);
    setError("");
    const health = await getHealth()
      .then((data) => data.status === "ok")
      .catch(() => false);
    if (request !== requestRef.current) return;
    setBackend(health ? "online" : "offline");
    try {
      const list = await getIncidents();
      const details = await Promise.allSettled(
        list.map((row) => getIncident(row.incident_id)),
      );
      if (request !== requestRef.current) return;
      const cache = {};
      const joined = list.map((row, i) => {
        if (details[i].status === "fulfilled") {
          cache[row.incident_id] = details[i].value;
          return { ...row, ...details[i].value };
        }
        return row;
      });
      detailCache.current = cache;
      setIncidents(joined);
      setLoaded(true);
      const target = list.some((row) => row.incident_id === id)
        ? id
        : list[0]?.incident_id || "";
      selectedRef.current = target;
      setSelected(target);
      setIncident(cache[target] || null);
      if (target && !cache[target])
        setError(
          "This incident detail could not be loaded. Retry to inspect its agent outputs.",
        );
      else if (details.some((d) => d.status === "rejected"))
        setError(
          "Some incident details could not be loaded. Their asset counts are unavailable.",
        );
    } catch (e) {
      if (request !== requestRef.current) return;
      setError(
        apiMessage(
          e,
          "Could not load incidents. Check that the backend is running on port 8001.",
        ),
      );
      if (e.response?.status === 401) {
        sessionStorage.removeItem("sentinel_user");
        sessionStorage.removeItem("sentinel_token");
        setUser(null);
      }
    } finally {
      if (request === requestRef.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (user) refresh();
  }, [user, refresh]);
  function select(id) {
    selectedRef.current = id;
    setSelected(id);
    setIncident(detailCache.current[id] || null);
    setPreview(null);
    setAiError("");
    setActionError("");
    setNotice("");
    setStageId("detect");
    if (!detailCache.current[id]) refresh(id);
  }
  async function doRun() {
    setOperation("demo");
    setError("");
    setNotice("");
    try {
      const result = await runDemo();
      await refresh(result.incident_id);
      setStageId("detect");
      setNotice(
        result.errors?.length
          ? "Workflow returned errors. Open Validate to inspect them."
          : "Workflow returned its persisted result. Matching evidence reuses the existing incident and decision.",
      );
    } catch (e) {
      setError(
        apiMessage(
          e,
          "The demo could not finish. No successful workflow has been assumed.",
        ),
      );
    } finally {
      setOperation("");
    }
  }
  async function action(fn, name) {
    setOperation(name);
    setActionError("");
    try {
      await fn(selected);
      await refresh(selected);
      setNotice(
        name === "send"
          ? "Delivery results refreshed. Inspect each recipient status."
          : `Reviewer ${name === "approve" ? "approval" : "rejection"} recorded.`,
      );
    } catch (e) {
      setActionError(
        apiMessage(
          e,
          "The action failed. Check the current approval and delivery state.",
        ),
      );
    } finally {
      setOperation("");
    }
  }
  async function check() {
    setChecking(true);
    setAiError("");
    try {
      setConnection(await checkNemotron());
      await refresh();
    } catch (e) {
      setConnection(null);
      setAiError(
        apiMessage(
          e,
          "The model check could not complete. Check backend access.",
        ),
      );
    } finally {
      setChecking(false);
    }
  }
  async function generate() {
    const id = selected;
    previewId.current = id;
    setGenerating(true);
    setAiError("");
    try {
      const result = await previewIntelligence(id);
      if (selectedRef.current === id) {
        setPreview(result);
        await refresh(id);
      }
    } catch (e) {
      if (selectedRef.current === id)
        setAiError(
          apiMessage(
            e,
            "Preview generation failed. Saved report and drafts remain unchanged.",
          ),
        );
    } finally {
      if (previewId.current === id) setGenerating(false);
    }
  }
  function logout() {
    requestRef.current++;
    sessionStorage.removeItem("sentinel_user");
    sessionStorage.removeItem("sentinel_token");
    setUser(null);
    setIncident(null);
    setConnection(null);
    setPreview(null);
  }
  if (!user) return <Login onLogin={setUser} />;
  const stage = stages.find((s) => s.id === stageId);
  const reviewer = user.role === "reviewer";
  const busy = Boolean(operation);
  const delivered =
    incident?.recipients?.filter((r) => ["sent", "mocked"].includes(r.status))
      .length || 0;
  const owners = incident?.recipients;
  const filtered = incidents.filter((row) =>
    `${row.incident_id} ${row.summary}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <div className="soc-app">
      <a className="skip-link" href="#main-content">
        Skip to agent workspace
      </a>
      <header className="top-nav">
        <a className="brand" href="#main-content">
          <span className="brand-symbol">
            <Icon name="shield" size={24} />
          </span>
          <span>
            Sentinel<span className="brand-ai">AI</span>
            <small>SECURITY OPERATIONS</small>
          </span>
        </a>
        <div className="system-signals">
          <Badge
            tone={
              backend === "online"
                ? "success"
                : backend === "offline"
                  ? "danger"
                  : "neutral"
            }
            dot
          >
            {backend === "online"
              ? "Backend connected"
              : backend === "offline"
                ? "Backend unavailable"
                : "Checking backend"}
          </Badge>
          <Badge
            tone={
              connection?.verified
                ? "success"
                : connection
                  ? "warning"
                  : "neutral"
            }
            dot
          >
            {connection?.verified
              ? "Nemotron verified"
              : connection
                ? "Nemotron not verified"
                : "Nemotron not checked"}
          </Badge>
          <span className="environment-tag">SYNTHETIC DEMO</span>
        </div>
        <div className="nav-actions">
          <Button
            icon="refresh"
            onClick={() => refresh()}
            disabled={loading || busy}
            title="Refresh persisted backend data"
            aria-label="Refresh dashboard"
          />
          <Button
            variant="primary"
            icon="play"
            busy={operation === "demo"}
            disabled={busy || loading || generating || checking}
            onClick={doRun}
          >
            Run Demo
          </Button>
          <div className="role-chip">
            <span>{user.username?.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{user.username}</strong>
              <small>{reviewer ? "Reviewer" : "Read-only viewer"}</small>
            </div>
          </div>
          <Button icon="logout" aria-label="Sign out" onClick={logout} />
        </div>
      </header>
      <div className="dashboard-shell">
        <aside className="incident-sidebar">
          <div className="sidebar-heading">
            <span className="eyebrow">INCIDENT QUEUE</span>
            <Badge>{incidents.length}</Badge>
          </div>
          <h2>Investigations</h2>
          <p className="sidebar-description">
            One incident. A clear chain of evidence.
          </p>
          <label className="search-box">
            <Icon name="search" size={16} />
            <input
              aria-label="Search incidents"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search ID or summary"
            />
          </label>
          <div className="incident-queue">
            {filtered.map((row) => (
              <button
                className={`incident-item ${selected === row.incident_id ? "active" : ""}`}
                key={row.incident_id}
                onClick={() => select(row.incident_id)}
                aria-pressed={selected === row.incident_id}
              >
                <span className="incident-item-top">
                  <strong>{row.incident_id}</strong>
                  <Severity value={row.severity} />
                </span>
                <span className="incident-summary">
                  {row.summary || "Summary not supplied"}
                </span>
                <span className="incident-item-bottom">
                  <span>
                    {assetCount(row) === null
                      ? "Asset count unavailable"
                      : `${assetCount(row)} assets`}
                  </span>
                  <span>{humanize(row.status)}</span>
                </span>
              </button>
            ))}
            {!filtered.length && (
              <p className="muted">
                {search
                  ? "No matching incidents."
                  : "No incidents returned. Run the demo to inspect the backend result."}
              </p>
            )}
          </div>
          <div className="sidebar-footer">
            <Icon name="shield" />
            <div>
              <strong>Human-controlled response</strong>
              <p>AI recommends. Reviewers decide.</p>
            </div>
          </div>
        </aside>
        <main id="main-content" className="dashboard-main">
          <div className="page-heading">
            <div>
              <span className="eyebrow">INCIDENT RESPONSE WORKSPACE</span>
              <h1>Every finding. One clear workflow.</h1>
              <p>
                Follow the evidence from detection to responsible-owner
                notification.
              </p>
            </div>
            <span className="read-only-label">
              {reviewer ? "Reviewer workspace" : "Read-only workspace"}
            </span>
          </div>
          <section className="overview-metrics" aria-label="Incident overview">
            <div>
              <span>Total incidents</span>
              <strong>{loaded ? incidents.length : "—"}</strong>
              <small>Returned by the backend</small>
            </div>
            <div>
              <span>High severity</span>
              <strong>
                {loaded
                  ? incidents.filter((i) => i.severity === "high").length
                  : "—"}
              </strong>
              <small>Rule-based severity: high</small>
            </div>
            <div>
              <span>Awaiting approval</span>
              <strong>
                {loaded
                  ? incidents.filter(
                      (i) =>
                        i.status === "awaiting_approval" &&
                        i.approval_status === "pending",
                    ).length
                  : "—"}
              </strong>
              <small>Pending human review</small>
            </div>
            <div>
              <span>Selected incident delivery</span>
              <strong>
                {owners ? `${delivered} / ${owners.length}` : "—"}
              </strong>
              <small>Sent or simulated · see recipient status</small>
            </div>
          </section>
          <ErrorNotice message={error} />
          {notice && (
            <div className="notice info" role="status">
              <Icon name="info" />
              <span>{notice}</span>
            </div>
          )}
          {loading && !incident ? (
            <div
              className="workspace-skeleton"
              role="status"
              aria-label="Loading incident"
            >
              <div />
              <div />
              <div />
            </div>
          ) : incident ? (
            <>
              <section className="case-heading">
                <div>
                  <div className="breadcrumb">
                    Investigations <span>/</span> {incident.incident_id}
                  </div>
                  <div className="case-title">
                    <h2>{incident.incident_id}</h2>
                    <Severity value={incident.severity} />
                    <Badge
                      tone={
                        incident.status === "incomplete"
                          ? "danger"
                          : incident.approval_status === "pending"
                            ? "warning"
                            : "neutral"
                      }
                    >
                      {humanize(incident.status)}
                    </Badge>
                  </div>
                  <p>
                    {incident.summary ||
                      incident.detection?.summary ||
                      "Summary not supplied."}
                  </p>
                </div>
                <Button icon="download" onClick={() => window.print()}>
                  Export report
                </Button>
              </section>
              <Workflow
                incident={incident}
                selected={stageId}
                onSelect={setStageId}
              />
              <section
                key={selected}
                id="agent-panel"
                role="tabpanel"
                aria-labelledby={`agent-tab-${stageId}`}
                className="agent-workspace"
              >
                <StageIntro
                  stage={stage}
                  validation={validationFor(incident, stage.step)}
                />
                {stageId === "detect" && <DetectionView incident={incident} />}
                {stageId === "investigate" && (
                  <InvestigationView
                    key={incident.incident_id}
                    incident={incident}
                  />
                )}
                {stageId === "intelligence" && (
                  <IntelligenceView
                    incident={incident}
                    preview={preview}
                    onPreview={generate}
                    generating={generating}
                    aiError={aiError}
                    connection={connection}
                    onCheck={check}
                    checking={checking}
                    reviewer={reviewer}
                    onClearPreview={() => setPreview(null)}
                  />
                )}
                {stageId === "validate" && (
                  <ValidationView incident={incident} />
                )}
                {stageId === "notify" && (
                  <NotificationView
                    incident={incident}
                    reviewer={reviewer}
                    busy={busy}
                    onApprove={() => action(approve, "approve")}
                    onReject={() => action(reject, "reject")}
                    onSend={(ids) => action((id) => send(id, ids), "send")}
                    error={actionError}
                  />
                )}
              </section>
            </>
          ) : (
            !error && (
              <Empty title="No incident selected">
                Run Demo to request a workflow, or select an incident in the
                queue.
              </Empty>
            )
          )}
          <footer className="workspace-footer">
            <span>SentinelAI · Evidence-led incident review</span>
            <span>
              Deterministic rules · Cited intelligence · Human approval
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
