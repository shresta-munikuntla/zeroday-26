---
doc_id: POL-001
title: "Privileged Account Monitoring Standard"
source_type: internal_policy_sample
version: "1.2"
fictional: true
---

# POL-001 Privileged Account Monitoring Standard

> SAMPLE — fictional policy created for the SentinelAI hackathon demo.

## 1. Scope

Applies to all administrator and service accounts with access to data-center servers, databases, and network segments.

## 2. Account Monitoring

Privileged account activity must be reviewed when unexpected access is detected. Unexpected access includes:

- A successful login from an IP address that is neither on the account's registered known-IP list nor inside an approved network listed in POL-002.
- Access to three or more distinct assets within 15 minutes from a non-approved source.
- Privileged activity outside the account's normal working pattern (for example, weekend activity for an account that normally operates on weekdays).

## 3. Failed Authentication

Five or more failed authentication attempts for a single account within 10 minutes must be reviewed as possible password guessing. Fewer failures from a registered known IP are treated as routine user error unless combined with other indicators.

## 4. Review Timelines

- Activity touching **high** or **critical** assets: review within 1 hour.
- Activity touching **medium** or **low** assets: review within 1 business day.

## 5. Evidence Handling

Reviewers must reference specific event IDs. An unfamiliar IP address alone is **not** proof of compromise; reviewers must check the benign explanations in POL-002 Section 3 before escalating.
