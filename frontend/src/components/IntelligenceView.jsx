import React, { useState } from "react";
import { generation, intelligenceState } from "../model.js";
import {
  Badge,
  Button,
  Panel,
  Empty,
  Facts,
  ErrorNotice,
  Icon,
} from "./ui.jsx";

export default function IntelligenceView({
  incident,
  preview,
  onPreview,
  generating,
  aiError,
  connection,
  onCheck,
  checking,
  reviewer,
  onClearPreview,
}) {
  const [sourceType, setSourceType] = useState("policy_references");
  const [focused, setFocused] = useState("");
  const [showAllActions, setShowAllActions] = useState(false);
  const ai = preview?.intelligence || incident.intelligence;
  const [label, tone] = intelligenceState(
    ai,
    preview ? { mode: preview.mode } : incident.ai_generation,
  );
  const [savedLabel, savedTone] = intelligenceState(
    incident.intelligence,
    incident.ai_generation,
  );
  const groups = [
    ["matched_techniques", "MITRE techniques"],
    ["policy_references", "Internal policies"],
    ["historical_cases", "Past incidents"],
  ];
  function focusSource(id) {
    setSourceType(
      id.startsWith("MITRE-")
        ? "matched_techniques"
        : id.startsWith("CASE-")
          ? "historical_cases"
          : "policy_references",
    );
    setFocused(id);
  }
  const refs = ai?.[sourceType] || [];
  return (
    <>
      <div className="rag-explainer">
        <Icon name="search" />
        <span>
          <strong>Retrieve knowledge</strong>MITRE · policies · historical cases
        </span>
        <Icon name="arrow" />
        <Icon name="spark" />
        <span>
          <strong>Generate with Nemotron</strong>Evidence-grounded
          recommendations
        </span>
        <Icon name="arrow" />
        <Icon name="shield" />
        <span>
          <strong>Validate & review</strong>Source IDs checked · human decision
        </span>
      </div>
      <div className="view-grid">
        <Panel
          title="Live model connection"
          subtitle="A separate connection check—not report provenance"
          aside={
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
                ? "Live inference verified"
                : connection
                  ? "Not verified"
                  : "Not checked"}
            </Badge>
          }
        >
          <p className="body-copy">
            {checking
              ? "Sending a fresh JSON inference request…"
              : connection?.message ||
                "Check the real model through the backend and private Brev tunnel."}
          </p>
          {connection && (
            <div className="model-meta">
              <code>{connection.model || "Model not configured"}</code>
              <span>
                {connection.latency_ms} ms ·{" "}
                {new Date(connection.checked_at).toLocaleTimeString()}
              </span>
            </div>
          )}
          <Button
            icon="activity"
            busy={checking}
            disabled={checking || generating || !reviewer}
            onClick={onCheck}
          >
            {checking ? "Checking connection…" : "Test Nemotron"}
          </Button>
          {!reviewer && (
            <p className="muted">
              Reviewer access is required for model requests.
            </p>
          )}
        </Panel>
        <Panel
          title="Saved report vs fresh preview"
          subtitle="Your saved report and notification drafts remain unchanged"
        >
          <div className="provenance-row">
            <span>Saved report</span>
            <Badge tone={savedTone}>{savedLabel}</Badge>
          </div>
          {preview && (
            <div className="provenance-row">
              <span>Fresh preview</span>
              <Badge tone={tone}>{label}</Badge>
            </div>
          )}
          <div className="button-row">
            <Button
              variant="primary"
              icon="spark"
              busy={generating}
              disabled={
                generating || checking || !reviewer || !incident.investigation
              }
              onClick={onPreview}
            >
              {generating ? "Retrieving & generating…" : "Generate AI Preview"}
            </Button>
            {preview && (
              <Button onClick={onClearPreview}>Show saved report</Button>
            )}
          </div>
          <p className="muted">
            Makes a real inference request when configured and relevant sources
            exist. Preview is not saved over the report or drafts.
          </p>
        </Panel>
      </div>
      <ErrorNotice message={aiError} />
      {generating && (
        <div className="loading-card" role="status">
          <span className="spinner" />
          <div>
            <strong>
              Retrieving relevant knowledge and requesting structured guidance
            </strong>
            <p>
              Waiting for the backend. Output will be labelled from its actual
              generation result.
            </p>
          </div>
        </div>
      )}
      <div className="section-heading">
        <div>
          <span className="eyebrow">
            {preview ? "FRESH AI PREVIEW" : "SAVED INTELLIGENCE"}
          </span>
          <h3>Guidance, with sources you can inspect</h3>
        </div>
        <Badge tone={tone}>{label}</Badge>
      </div>
      {!ai ? (
        <Empty title="Intelligence not included in this report">
          Generate a preview if the saved investigation is available.
        </Empty>
      ) : (
        <>
          <div className="notice info">
            <Icon name="info" />
            <span>
              Recommendations are suggestions—not executed remediation.
              Candidate techniques and historical cases are context, not proof
              of an attack. Source IDs validate provenance, not every sentence.
            </span>
          </div>
          <div className="view-grid">
            <Panel
              title="Recommended actions"
              subtitle="Each action must cite retrieved document IDs"
            >
              {ai.recommended_actions?.length ? (
                <ol className="recommendations">
                  {ai.recommended_actions
                    .slice(0, showAllActions ? undefined : 3)
                    .map((action, i) => (
                      <li key={i}>
                        <span className="action-number">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <div>
                          <p>
                            {typeof action === "string"
                              ? action
                              : action.action}
                          </p>
                          <div className="citation-buttons">
                            {action.source_document_ids?.map((id) => (
                              <button
                                key={id}
                                onClick={() => focusSource(id)}
                                title="Inspect this cited reference"
                              >
                                {id}
                                <Icon name="arrow" size={12} />
                              </button>
                            ))}
                          </div>
                        </div>
                      </li>
                    ))}
                </ol>
              ) : (
                <Empty title="No sourced recommendation available">
                  {ai.limitations?.includes("No relevant source was retrieved.")
                    ? "No relevant sources passed retrieval. No policy was invented."
                    : "The backend did not return any recommendations."}
                </Empty>
              )}
              {(ai.recommended_actions?.length || 0) > 3 && (
                <div className="more-actions">
                  <p className="muted">
                    Showing {showAllActions ? ai.recommended_actions.length : 3}{" "}
                    of {ai.recommended_actions.length} returned actions.
                  </p>
                  <Button onClick={() => setShowAllActions((value) => !value)}>
                    {showAllActions
                      ? "Show fewer actions"
                      : `Show all ${ai.recommended_actions.length} actions`}
                  </Button>
                </div>
              )}
            </Panel>
            <Panel
              title="Reference explorer"
              subtitle="Output summaries; original text is not exposed. Counts are returned entries and can repeat across sections."
            >
              <div
                className="source-tabs"
                role="group"
                aria-label="Reference categories"
              >
                {groups.map(([key, name]) => (
                  <button
                    key={key}
                    aria-pressed={sourceType === key}
                    onClick={() => {
                      setSourceType(key);
                      setFocused("");
                    }}
                  >
                    {name}
                    <span>{ai[key]?.length || 0}</span>
                  </button>
                ))}
              </div>
              {refs.length ? (
                refs.map((source, i) => {
                  const id =
                    source.policy_id ||
                    source.case_id ||
                    `MITRE-${source.technique_id}`;
                  return (
                    <details
                      className="source-detail"
                      key={`${id}-${i}`}
                      open={focused === id || undefined}
                    >
                      <summary>
                        <span>
                          <code>{id}</code>
                          <strong>
                            {source.name || source.section || "Historical case"}
                          </strong>
                        </span>
                        <span>+</span>
                      </summary>
                      <p>
                        {source.summary ||
                          source.relevance ||
                          "No summary supplied."}
                      </p>
                      {source.relevance && source.summary && (
                        <p className="muted">{source.relevance}</p>
                      )}
                      <div className="citation-buttons">
                        {source.source_document_ids?.map((s) => (
                          <code key={s}>{s}</code>
                        ))}
                      </div>
                    </details>
                  );
                })
              ) : (
                <Empty title="No references in this category" />
              )}
            </Panel>
            <Panel
              title="Limitations & uncertainties"
              subtitle="Returned by the backend—never hidden"
              className="span-two"
            >
              <Facts
                items={ai.limitations}
                empty="No limitations were included. This is not proof that the output is complete or correct."
              />
            </Panel>
            {ai.recommended_resources?.length > 0 && (
              <Panel title="Recommended resources" className="span-two">
                <ul className="resource-list">
                  {ai.recommended_resources.map((r, i) => (
                    <li key={i}>
                      {/^https?:\/\//.test(r.url || "") ? (
                        <a href={r.url} target="_blank" rel="noreferrer">
                          {r.title}
                          <Icon name="arrow" size={14} />
                        </a>
                      ) : (
                        <span>{r.title} · URL unavailable</span>
                      )}
                      <small>{r.source_document_ids?.join(", ")}</small>
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </div>
        </>
      )}
      {preview?.model && (
        <p className="footnote">
          Preview model: <code>{preview.model}</code> ·{" "}
          {generation(preview.mode)[0]}
        </p>
      )}
    </>
  );
}
