---
doc_id: MITRE-T1078
title: "T1078 Valid Accounts"
source_type: mitre_attack_official
url: https://attack.mitre.org/techniques/T1078
attack_release: "20.1"
technique_version: "3.0"
tactics: [initial-access, persistence, privilege-escalation, stealth]
platforms: [Containers, ESXi, IaaS, Identity Provider, Linux, macOS, Network Devices, Office Suite, SaaS, Windows]
license_note: "MITRE ATT&CK(R) content, (c) The MITRE Corporation. Reproduced under the ATT&CK Terms of Use."
---

# T1078 Valid Accounts

## Description

Adversaries may obtain and abuse credentials of existing accounts as a means of gaining Initial Access, Persistence, Privilege Escalation, or Defense Evasion. Compromised credentials may be used to bypass access controls placed on various resources on systems within the network and may even be used for persistent access to remote systems and externally available services, such as VPNs, Outlook Web Access, network devices, and remote desktop. Compromised credentials may also grant an adversary increased privilege to specific systems or access to restricted areas of the network. Adversaries may choose not to use malware or tools in conjunction with the legitimate access those credentials provide to make it harder to detect their presence.

In some cases, adversaries may abuse inactive accounts: for example, those belonging to individuals who are no longer part of an organization. Using these accounts may allow the adversary to evade detection, as the original account user will not be present to identify any anomalous activity taking place on their account.

The overlap of permissions for local, domain, and cloud accounts across a network of systems is of concern because the adversary may be able to pivot across accounts and systems to reach a high level of access (i.e., domain or enterprise administrator) to bypass access controls set within the enterprise.

## Mitigations

- **M1013 Application Developer Guidance:** Ensure that applications do not store sensitive data or credentials insecurely. (e.g. plaintext credentials in code, published credentials in repositories, or credentials in public cloud storage).
- **M1015 Active Directory Configuration:** Disable legacy authentication, which does not support MFA, and require the use of modern authentication protocols instead.
- **M1017 User Training:** Applications may send push notifications to verify a login as a form of multi-factor authentication (MFA). Train users to only accept valid push notifications and to report suspicious push notifications.
- **M1018 User Account Management:** Regularly audit user accounts for activity and deactivate or remove any that are no longer needed.
- **M1026 Privileged Account Management:** Audit domain and local accounts as well as their permission levels routinely to look for situations that could allow an adversary to gain wide access by obtaining credentials of a privileged account. These audits should also include if default accounts have been enabled, or if new local accounts are created that have not been authorized. Follow best practices for design and administration of an enterprise network to limit privileged account use across administrative tiers.
- **M1027 Password Policies:** Applications and appliances that utilize default username and password should be changed immediately after the installation, and before deployment to a production environment. When possible, applications that use SSH keys should be updated periodically and properly secured.

Policies should minimize (if not eliminate) reuse of passwords between different user accounts, especially employees using the same credentials for personal accounts that may not be defended by enterprise security resources.
- **M1032 Multi-factor Authentication:** Implement multi-factor authentication (MFA) across all account types, including default, local, domain, and cloud accounts, to prevent unauthorized access, even if credentials are compromised. MFA provides a critical layer of security by requiring multiple forms of verification beyond just a password. This measure significantly reduces the risk of adversaries abusing valid accounts to gain initial access, escalate privileges, maintain persistence, or evade defenses within your network.
- **M1036 Account Use Policies:** Use conditional access policies to block logins from non-compliant devices or from outside defined organization IP ranges.
