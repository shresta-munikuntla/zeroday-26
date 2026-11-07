---
doc_id: CASE-001
title: "Unfamiliar-IP admin login traced to new VPN egress"
source_type: historical_incident_sample
incident_date: "2026-08-12"
outcome: false_positive
fictional: true
---

# CASE-001 Unfamiliar-IP admin login traced to new VPN egress

> SAMPLE — fictional historical incident for the SentinelAI hackathon demo.

## Summary

An administrator account logged in from an unfamiliar external IP and accessed two web servers. The alert was raised as high severity.

## Investigation

The reviewer checked the approved network list and found that the VPN provider had added a new egress address that had not yet been registered in the approved network list. The accessed servers matched the account's current permissions.

## Outcome

False positive. The new egress range was added to the approved network list.

## Lessons Learned

- Check approved networks and current permissions before escalating.
- Unfamiliar IP alone is weak evidence; combine it with authorization checks.
