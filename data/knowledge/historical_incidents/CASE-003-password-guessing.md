---
doc_id: CASE-003
title: "Password guessing against employee accounts"
source_type: historical_incident_sample
incident_date: "2026-09-21"
outcome: blocked_attempt
fictional: true
---

# CASE-003 Password guessing against employee accounts

> SAMPLE — fictional historical incident for the SentinelAI hackathon demo.

## Summary

Several employee accounts received more than ten failed login attempts each within a few minutes from one external IP. No attempt succeeded.

## Investigation

The failure rate exceeded the POL-001 threshold of five failures in ten minutes. No successful login or server access followed from the source IP.

## Outcome

Blocked attempt; severity medium. Affected users were asked to confirm MFA enrollment.

## Lessons Learned

- A few failed logins from a known IP are usually user error; review volume, source, and whether a success followed.
