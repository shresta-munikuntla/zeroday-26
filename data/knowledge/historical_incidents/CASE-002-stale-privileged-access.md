---
doc_id: CASE-002
title: "Privileged account used stale SSH access from external IP"
source_type: historical_incident_sample
incident_date: "2026-06-03"
outcome: confirmed_unauthorized_access
fictional: true
---

# CASE-002 Privileged account used stale SSH access from external IP

> SAMPLE — fictional historical incident for the SentinelAI hackathon demo.

## Summary

A privileged account logged in from an external IP outside the approved VPN, then accessed several servers within minutes. One server accepted the connection even though the account's permission had expired, because the SSH key had not been removed. Attempts against a database were denied.

## Investigation

- Timeline built from authentication and server-access events.
- Permission records showed one expired and one missing authorization.
- The account holder confirmed they had not logged in.
- No evidence of data transfer was found.

## Response

After approval by the Security Incident Lead, the asset owners removed the stale key and Identity Security reset the account's credentials. An access review was performed for all accounts with expired permissions.

## Lessons Learned

- Expired permissions must be enforced on target hosts (see POL-003 Section 2).
- Notify each affected asset owner separately with only their asset's details.
