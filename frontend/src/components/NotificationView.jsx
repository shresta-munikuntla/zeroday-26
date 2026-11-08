import React, { useEffect, useRef, useState } from "react";
import { safeJson, humanize } from "../model.js";
import { Badge, Button, Panel, Empty, ErrorNotice, Icon } from "./ui.jsx";

export default function NotificationView({
  incident,
  reviewer,
  busy,
  onApprove,
  onReject,
  onSend,
  error,
}) {
  const [confirm, setConfirm] = useState(null);
  const dialog = useRef(null);
  useEffect(() => {
    if (!confirm) return;
    const previous = document.activeElement;
    const buttons = [...dialog.current.querySelectorAll("button")];
    buttons[0]?.focus();
    function key(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        setConfirm(null);
      }
      if (event.key === "Tab") {
        if (event.shiftKey && document.activeElement === buttons[0]) {
          event.preventDefault();
          buttons.at(-1)?.focus();
        } else if (
          !event.shiftKey &&
          document.activeElement === buttons.at(-1)
        ) {
          event.preventDefault();
          buttons[0]?.focus();
        }
      }
    }
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, [confirm]);
  const recipients = incident.recipients || [];
  const pending =
    incident.approval_status === "pending" &&
    incident.status === "awaiting_approval";
  const approved = incident.approval_status === "approved";
  const eligible = recipients
    .filter((r) => ["approved", "failed"].includes(r.status) && !r.sent_at)
    .map((r) => r.recipient_id);
  async function proceed() {
    const action = confirm;
    setConfirm(null);
    if (action === "approve") await onApprove();
    else if (action === "reject") await onReject();
    else await onSend(eligible);
  }
  return (
    <>
      <div className="decision-bar">
        <div>
          <span className="eyebrow">HUMAN-IN-THE-LOOP</span>
          <h3>
            {approved
              ? "Approved for delivery"
              : incident.approval_status === "rejected"
                ? "Notifications rejected"
                : "A reviewer decides what happens next"}
          </h3>
          <p>
            {incident.approval_status === "rejected"
              ? "The saved decision is preserved. Rerunning the demo will not reset it."
              : "Drafting does not send anything. Delivery requires approval and a separate send action."}
          </p>
        </div>
        <Badge
          tone={
            approved
              ? "success"
              : incident.approval_status === "rejected"
                ? "danger"
                : "warning"
          }
        >
          {humanize(incident.approval_status)}
        </Badge>
      </div>
      <ErrorNotice message={error} />
      {!reviewer && (
        <div className="notice info">
          <Icon name="shield" />
          <span>
            Read-only viewer. Reviewer access is required to approve, reject, or
            send.
          </span>
        </div>
      )}
      <div className="view-grid">
        {recipients.length ? (
          recipients.map((person) => {
            const assets =
              person.asset_ids || safeJson(person.asset_ids_json, []);
            const delivery = safeJson(person.delivery_result);
            return (
              <Panel
                key={person.recipient_id}
                title={person.display_name || person.recipient_id}
                subtitle={`${person.role || "Owner team"} · ${person.recipient_id}`}
                aside={
                  <Badge
                    tone={
                      person.status === "mocked"
                        ? "success"
                        : person.status === "failed"
                          ? "danger"
                          : "neutral"
                    }
                  >
                    {person.status === "mocked"
                      ? "Mock sent · simulated"
                      : humanize(person.status)}
                  </Badge>
                }
              >
                <div className="recipient-assets">
                  {assets.map((id) => (
                    <code key={id}>{id}</code>
                  ))}
                </div>
                <p className="body-copy">
                  {person.why_selected || "Selection reason was not supplied."}
                </p>
                <details className="message-disclosure">
                  <summary>
                    Preview notification <Icon name="arrow" size={14} />
                  </summary>
                  <div className="message-body">
                    <strong>{person.subject || "Subject unavailable"}</strong>
                    <p>{person.body || "Draft body unavailable"}</p>
                  </div>
                </details>
                {person.status === "mocked" && (
                  <div className="notice success">
                    Simulated delivery only. No real message was sent by the
                    mock adapter.
                  </div>
                )}
                {delivery?.detail && (
                  <p
                    className={
                      person.status === "failed" ? "danger-text" : "muted"
                    }
                  >
                    {delivery.detail}
                  </p>
                )}
              </Panel>
            );
          })
        ) : (
          <Panel title="No owner drafts available" className="span-two">
            <Empty>
              Agent 5 has not supplied drafts for this saved report. No
              recipients have been inferred.
            </Empty>
          </Panel>
        )}
      </div>
      <Panel
        title="Reviewer actions"
        subtitle="Enforced again by backend authorization and approval checks"
      >
        {reviewer && (
          <div className="button-row">
            {pending && (
              <>
                <Button
                  icon="check"
                  variant="primary"
                  disabled={busy}
                  onClick={() => setConfirm("approve")}
                >
                  Approve incident
                </Button>
                <Button
                  icon="close"
                  variant="danger"
                  disabled={busy}
                  onClick={() => setConfirm("reject")}
                >
                  Reject incident
                </Button>
              </>
            )}
            {approved && (
              <Button
                icon="arrow"
                variant="primary"
                disabled={busy || !eligible.length}
                onClick={() => setConfirm("send")}
              >
                {eligible.length
                  ? `Send notifications (${eligible.length})`
                  : "No eligible deliveries remaining"}
              </Button>
            )}
          </div>
        )}
        {busy && <p role="status">Waiting for the backend decision…</p>}
        <p className="muted">
          {approved
            ? "Delivery uses the server-configured adapter. Mock delivery is explicitly labelled simulated in each result."
            : "Sending is unavailable until the incident is approved."}
        </p>
        {incident.approval_status === "rejected" && (
          <details className="disclosure">
            <summary>
              Need a new pending demo? <span>+</span>
            </summary>
            <p>
              Use the separate demo database commands in docs/how-to-run.md.
              This preserves the existing reviewer decision and avoids duplicate
              incidents.
            </p>
          </details>
        )}
      </Panel>
      {confirm && (
        <div className="modal-backdrop">
          <section
            ref={dialog}
            className="confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
          >
            <span className="eyebrow">CONFIRM REVIEWER ACTION</span>
            <h2 id="confirm-title">
              {confirm === "send"
                ? "Send approved notifications?"
                : confirm === "approve"
                  ? "Approve this incident?"
                  : "Reject this incident?"}
            </h2>
            <p>
              {confirm === "send"
                ? "The configured adapter will handle delivery to eligible recipients. Only mock-mode results represent simulated sending."
                : `Your ${confirm === "approve" ? "approval" : "rejection"} will be saved with your reviewer identity. Approval itself does not send notifications.`}
            </p>
            <div className="button-row">
              <Button autoFocus onClick={() => setConfirm(null)}>
                Cancel
              </Button>
              <Button
                variant={confirm === "reject" ? "danger" : "primary"}
                onClick={proceed}
              >
                Confirm {confirm}
              </Button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
