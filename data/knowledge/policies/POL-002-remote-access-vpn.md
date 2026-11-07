---
doc_id: POL-002
title: "Remote Administrative Access and VPN Policy"
source_type: internal_policy_sample
version: "2.0"
fictional: true
---

# POL-002 Remote Administrative Access and VPN Policy

> SAMPLE — fictional policy created for the SentinelAI hackathon demo.

## 1. Approved Remote Access Paths

Remote administrative access to data-center assets is permitted only through the corporate remote-access VPN (approved network NET-001, egress range 203.0.113.0/25) or from the internal network (NET-002). Administrative logins should then pass through the bastion host DC-SRV-04.

## 2. Non-Approved Sources

A privileged login from an external address outside NET-001 is a policy exception that must be verified with the account holder and the asset owner before it is considered authorized.

## 3. Benign Explanations to Verify

Before escalating unfamiliar-IP activity, reviewers must check:

1. Whether the source IP falls inside an approved network (NET-001 or NET-002).
2. Whether a recorded maintenance window covers the account and assets (for example, MW-001 nightly backup, 02:00–03:00 UTC).
3. Whether the account holder reports travel or a new, not-yet-registered VPN egress address.

## 4. Responsibilities

Network Security owns the bastion host and the management network segment. Identity Security owns account and directory controls.
