---
doc_id: POL-003
title: "Privileged Access Management Policy"
source_type: internal_policy_sample
version: "1.4"
fictional: true
---

# POL-003 Privileged Access Management Policy

> SAMPLE — fictional policy created for the SentinelAI hackathon demo.

## 1. Least Privilege

Accounts may access only the assets listed in their current, unexpired permission records. Access to an asset without a current permission record is unauthorized, even if the target system allowed the connection.

## 2. Expired Permissions

When a permission reaches its end date, the asset owner must remove the corresponding credentials (including SSH keys) from the target system. Successful access after a permission's end date indicates that revocation was not enforced and must be reported to the asset owner and to Identity Security.

## 3. Critical Assets

Access attempts against **critical** assets (for example, production databases) by accounts without permission must be reported to the asset owner, whether or not the attempt succeeded.

## 4. Containment Requires Approval

Disabling accounts, revoking credentials, blocking IP addresses, or changing firewall rules requires approval from the Security Incident Lead. Automated tools may recommend these actions but must not perform them.
