---
doc_id: POL-004
title: "Incident Escalation and Notification Procedure"
source_type: internal_policy_sample
version: "1.1"
fictional: true
---

# POL-004 Incident Escalation and Notification Procedure

> SAMPLE — fictional procedure created for the SentinelAI hackathon demo.

## 1. Severity Levels

- **Low:** unusual but low-impact event with limited evidence.
- **Medium:** suspicious access to a non-critical asset, or repeated suspicious activity.
- **High:** suspicious privileged-account activity involving multiple or high/critical assets.
- **Critical:** only when evidence confirms severe impact, such as unauthorized privileged changes or confirmed sensitive data transfer.

## 2. Who Is Notified

Notify the active **owner** of each affected asset. If an asset has no active individual owner, notify the asset's owner team channel. Backup and operator contacts are not notified by default. Do not notify employees unrelated to the affected assets.

## 3. Approval

High and critical notifications require approval by the Security Incident Lead (Security Operations) before delivery.

## 4. Message Content

Each message must state why the recipient was selected, what happened, why it matters, suggested next steps, the incident ID, and evidence IDs. Messages must not include raw logs, credentials, or other employees' records, and must not attribute fault to any individual.

## 5. Escalation

If unauthorized activity is confirmed, the asset owner escalates to the Security Incident Lead.
