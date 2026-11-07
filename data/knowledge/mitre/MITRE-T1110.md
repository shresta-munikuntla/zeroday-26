---
doc_id: MITRE-T1110
title: "T1110 Brute Force"
source_type: mitre_attack_official
url: https://attack.mitre.org/techniques/T1110
attack_release: "20.1"
technique_version: "2.8"
tactics: [credential-access]
platforms: [Containers, ESXi, IaaS, Identity Provider, Linux, macOS, Network Devices, Office Suite, SaaS, Windows]
license_note: "MITRE ATT&CK(R) content, (c) The MITRE Corporation. Reproduced under the ATT&CK Terms of Use."
---

# T1110 Brute Force

## Description

Adversaries may use brute force techniques to gain access to accounts when passwords are unknown or when password hashes are obtained. Without knowledge of the password for an account or set of accounts, an adversary may systematically guess the password using a repetitive or iterative mechanism. Brute forcing passwords can take place via interaction with a service that will check the validity of those credentials or offline against previously acquired credential data, such as password hashes.

Brute forcing credentials may take place at various points during a breach. For example, adversaries may attempt to brute force access to [Valid Accounts](https://attack.mitre.org/techniques/T1078) within a victim environment leveraging knowledge gathered from other post-compromise behaviors such as [OS Credential Dumping](https://attack.mitre.org/techniques/T1003), [Account Discovery](https://attack.mitre.org/techniques/T1087), or [Password Policy Discovery](https://attack.mitre.org/techniques/T1201). Adversaries may also combine brute forcing activity with behaviors such as [External Remote Services](https://attack.mitre.org/techniques/T1133) as part of Initial Access. 

If an adversary guesses the correct password but fails to log in to a compromised account due to location-based conditional access policies, they may change their infrastructure until they match the victim’s location and therefore bypass those policies.

## Mitigations

- **M1018 User Account Management:** Proactively reset accounts that are known to be part of breached credentials either immediately, or after detecting bruteforce attempts.
- **M1027 Password Policies:** Refer to NIST guidelines when creating password policies.
- **M1032 Multi-factor Authentication:** Use multi-factor authentication. Where possible, also enable multi-factor authentication on externally facing services.
- **M1036 Account Use Policies:** Set account lockout policies after a certain number of failed login attempts to prevent passwords from being guessed. Too strict a policy may create a denial of service condition and render environments un-usable, with all accounts used in the brute force being locked-out. Use conditional access policies to block logins from non-compliant devices or from outside defined organization IP ranges. Consider blocking risky authentication requests, such as those originating from anonymizing services/proxies.
