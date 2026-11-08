import React, { useState } from "react";
import { auditDetails, eventTime, humanize } from "../model.js";
import {
  Badge,
  Panel,
  Empty,
  Chips,
  Facts,
  KeyValues,
  Severity,
} from "./ui.jsx";
const ruleNames = {
  R1: "Unfamiliar login source",
  R2: "Access without valid permission",
  R3: "Failed-login burst",
  R4: "Multi-asset access burst",
};
export function DetectionView({ incident }) {
  const d = incident.detection;
  if (!d)
    return (
      <Empty title="Detection not included">
        This saved report has no Agent 1 output.
      </Empty>
    );
  return (
    <div className="view-grid">
      <Panel
        title="Detection summary"
        subtitle="Deterministic rules · no model verdict"
      >
        <p className="lead-copy">{d.summary || "No summary supplied."}</p>
        <KeyValues
          items={[
            ["Account", d.account_ids?.join(", ")],
            ["Source IP", d.source_ip_addresses?.join(", ")],
            [
              "Initial severity",
              d.severity_initial ? (
                <Severity value={d.severity_initial} />
              ) : null,
            ],
            [
              "Detected window",
              d.time_window
                ? `${eventTime(d.time_window.start)} → ${eventTime(d.time_window.end)}`
                : null,
            ],
          ]}
        />
        <h4>Affected asset IDs</h4>
        <Chips ids={d.affected_asset_ids} />
      </Panel>
      <Panel
        title="Triggered detection rules"
        subtitle="Expand the backend's recorded explanation"
      >
        {d.rules_triggered?.length ? (
          d.rules_triggered.map((rule) => {
            const prefix = rule.split("_")[0];
            const reasons = (d.reasons || []).filter((text) =>
              (
                ({
                  R1: /Successful login/,
                  R2: /without a currently valid permission/,
                  R3: /failed logins/,
                  R4: /different assets/,
                })[prefix] || /$^/
              ).test(text),
            );
            return (
              <details className="disclosure" key={rule}>
                <summary>
                  <code>{prefix}</code>
                  <strong>{ruleNames[prefix] || humanize(rule)}</strong>
                  <span>+</span>
                </summary>
                <Facts
                  items={reasons}
                  empty="No separate explanation was supplied for this rule."
                />
              </details>
            );
          })
        ) : (
          <Empty title="Rule IDs not recorded" />
        )}
        <details className="disclosure">
          <summary>
            All recorded reasons <span>+</span>
          </summary>
          <Facts items={d.reasons} />
        </details>
      </Panel>
      <Panel
        title="Detection evidence"
        subtitle="Exact event IDs referenced by Agent 1"
      >
        <Chips ids={d.evidence_ids} />
      </Panel>
      <Panel
        title="Detection uncertainties"
        subtitle="A signal requires investigation; it is not proof of compromise"
      >
        <Facts items={d.uncertainties} />
      </Panel>
    </div>
  );
}
export function InvestigationView({ incident }) {
  const inv = incident.investigation || {};
  const assets = inv.affected_assets || [];
  const [assetId, setAssetId] = useState("");
  const asset = assets.find((a) => a.asset_id === assetId) || assets[0];
  const timeline = inv.timeline || incident.timeline || [];
  const statusNames = {
    authorized: ["Authorized", "success"],
    expired: ["Expired", "warning"],
    none: ["No permission", "danger"],
  };
  return (
    <>
      <div className="findings-strip">
        <div>
          <small>FINAL SEVERITY</small>
          <Severity value={inv.severity || incident.severity} />
        </div>
        <div>
          <small>INVESTIGATION STATUS</small>
          <strong>{humanize(inv.investigation_status || inv.status)}</strong>
        </div>
        <div>
          <small>CONFIDENCE</small>
          <strong>
            {typeof inv.confidence === "number"
              ? `${Math.round(inv.confidence * 100)}%`
              : "Not recorded"}
          </strong>
          <span>Rule-based estimate, not a calibrated probability</span>
        </div>
      </div>
      <div className="view-grid">
        <Panel
          title="Chronological timeline"
          subtitle="Recorded events and evidence · UTC"
        >
          {timeline.length ? (
            <ol className="event-timeline">
              {[...timeline]
                .sort((a, b) =>
                  String(a.timestamp).localeCompare(String(b.timestamp)),
                )
                .map((event, i) => (
                  <li key={event.event_id || i}>
                    <time>{eventTime(event.timestamp)}</time>
                    <strong>
                      {event.description || humanize(event.event_type)}
                    </strong>
                    <Chips
                      ids={
                        event.evidence_ids ||
                        (event.event_id ? [event.event_id] : [])
                      }
                    />
                  </li>
                ))}
            </ol>
          ) : (
            <Empty title="Timeline not recorded">
              This older report does not contain timeline entries. The current
              workflow supplies them for new incidents.
            </Empty>
          )}
        </Panel>
        <Panel
          title="Permission checks by asset"
          subtitle="Select a machine to inspect its access evidence"
        >
          {assets.length ? (
            <>
              <div className="asset-selector">
                {assets.map((a) => (
                  <button
                    key={a.asset_id}
                    aria-pressed={asset?.asset_id === a.asset_id}
                    onClick={() => setAssetId(a.asset_id)}
                  >
                    <span>
                      <strong>{a.asset_name || a.asset_id}</strong>
                      <code>{a.asset_id}</code>
                    </span>
                    <Badge tone={statusNames[a.authorization]?.[1]}>
                      {statusNames[a.authorization]?.[0] || "Unknown"}
                    </Badge>
                  </button>
                ))}
              </div>
              {asset && (
                <div className="asset-detail">
                  <KeyValues
                    items={[
                      [
                        "Permission",
                        asset.permission_id ||
                          (asset.authorization === "none"
                            ? "No permission on record"
                            : "Not supplied"),
                      ],
                      ["Asset criticality", humanize(asset.criticality)],
                      ["Owner team", asset.owner_team],
                    ]}
                  />
                  <h4>Successful access evidence</h4>
                  <Chips ids={asset.successful_access_ids} />
                  <h4>Denied access evidence</h4>
                  <Chips ids={asset.denied_access_ids} />
                  <p className="muted">
                    Permission state is evaluated by the backend at the actual
                    access timestamp.
                  </p>
                </div>
              )}
            </>
          ) : (
            <Empty title="Asset authorization details not recorded">
              Asset IDs alone do not prove a permission state. No authorization
              outcome has been inferred.
            </Empty>
          )}
        </Panel>
        <Panel
          title="Confirmed facts"
          subtitle="Findings supported by source records"
        >
          <Facts items={inv.confirmed_facts || incident.facts} />
        </Panel>
        <Panel
          title="Potential impact"
          subtitle="Backend assessment, distinct from confirmed damage"
        >
          {inv.potential_impact ? (
            <p className="body-copy">{inv.potential_impact}</p>
          ) : (
            <Empty />
          )}
        </Panel>
        <Panel
          title="Hypotheses"
          subtitle="Possible explanations—not established facts"
          className="hypothesis"
        >
          <Facts items={inv.hypotheses} />
        </Panel>
        <Panel
          title="Benign explanations to check"
          subtitle="Alternative explanations requiring human follow-up"
        >
          <Facts items={inv.benign_explanations_to_check} />
        </Panel>
        <Panel title="Checks performed" className="span-two">
          <Facts items={inv.checks_performed} />
        </Panel>
      </div>
    </>
  );
}
export function ValidationView({ incident }) {
  const events = incident.audit || [];
  const checks = events.filter((e) =>
    [
      "validation",
      "validation_rejected",
      "intelligence_validation",
      "error",
    ].includes(e.action),
  );
  const failures = events.filter((e) =>
    ["validation_rejected", "error"].includes(e.action),
  );
  return (
    <div className="view-grid">
      <Panel
        title="Recorded validation checks"
        subtitle="Each row comes from a persisted audit event"
      >
        {checks.length ? (
          <div className="validation-list">
            {checks.map((e, i) => {
              const detail = auditDetails(e);
              const passed =
                e.action === "validation" && detail.status === "passed";
              const rejected =
                ["validation_rejected", "error"].includes(e.action) ||
                detail.status === "model_output_rejected";
              return (
                <div key={e.event_id || i}>
                  <span>
                    <strong>{humanize(detail.step || e.action)}</strong>
                    <small>
                      {humanize(detail.status || detail.error_type || e.action)}
                    </small>
                  </span>
                  <Badge
                    tone={passed ? "success" : rejected ? "danger" : "neutral"}
                  >
                    {passed
                      ? "Passed"
                      : rejected
                        ? "Failure recorded"
                        : "Recorded outcome"}
                  </Badge>
                </div>
              );
            })}
          </div>
        ) : (
          <Empty title="No validation events recorded">
            Older reports may predate validation-event logging. No passing
            checklist has been assumed.
          </Empty>
        )}
      </Panel>
      <Panel title="Workflow state & errors">
        <KeyValues
          items={[
            ["Persisted incident status", humanize(incident.status)],
            ["Human decision", humanize(incident.approval_status)],
            [
              "Saved generation mode",
              humanize(incident.ai_generation?.mode || "unknown"),
            ],
            ["Saved model", incident.ai_generation?.model],
          ]}
        />
        {Array.isArray(incident.errors) && incident.errors.length > 0 && (
          <Facts items={incident.errors} />
        )}
        {failures.length > 0 && (
          <div className="notice warning">
            Failure/rejection events exist. Inspect their details and chronology
            below.
          </div>
        )}
        <p className="muted">
          {Array.isArray(incident.errors)
            ? `The response supplied ${incident.errors.length} workflow errors.`
            : "A separate workflow error list was not supplied; persisted audit events are shown."}
        </p>
        <p className="muted">
          Agent 4 manages detection, investigation, intelligence, report
          validation and drafting. The frontend does not execute these checks.
        </p>
      </Panel>
      <Panel
        title="Audit history"
        subtitle={`${events.length} persisted events · chronological order`}
        className="span-two"
      >
        {events.length ? (
          <div className="audit-history">
            {events.map((event, i) => (
              <details key={event.event_id || event.audit_id || i}>
                <summary>
                  <span className="audit-index">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>
                    <strong>{humanize(event.action)}</strong>
                    <small>
                      {event.actor_id} ·{" "}
                      {eventTime(event.timestamp || event.created_at)}
                    </small>
                  </span>
                  <span>+</span>
                </summary>
                <pre>{JSON.stringify(auditDetails(event), null, 2)}</pre>
              </details>
            ))}
          </div>
        ) : (
          <Empty title="Audit history unavailable" />
        )}
      </Panel>
    </div>
  );
}
