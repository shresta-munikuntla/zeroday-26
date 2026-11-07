---
doc_id: MITRE-T1021.004
title: "T1021.004 SSH"
source_type: mitre_attack_official
url: https://attack.mitre.org/techniques/T1021/004
attack_release: "20.1"
technique_version: "1.4"
tactics: [lateral-movement]
platforms: [ESXi, Linux, macOS, Windows]
license_note: "MITRE ATT&CK(R) content, (c) The MITRE Corporation. Reproduced under the ATT&CK Terms of Use."
---

# T1021.004 SSH

## Description

Adversaries may use [Valid Accounts](https://attack.mitre.org/techniques/T1078) to log into remote machines using Secure Shell (SSH). The adversary may then perform actions as the logged-on user.

SSH is a protocol that allows authorized users to open remote shells on other computers. Many Linux and macOS versions come with SSH installed by default, although typically disabled until the user enables it. On ESXi, SSH can be enabled either directly on the host (e.g., via `vim-cmd hostsvc/enable_ssh`) or via vCenter. Modern versions of Windows include a built-in SSH server and client. The SSH server can be configured to use standard password authentication or public-private keypairs in lieu of or in addition to a password. In this authentication scenario, the user’s public key must be in a special file on the computer running the server that lists which keypairs are allowed to log in as that user (i.e., [SSH Authorized Keys](https://attack.mitre.org/techniques/T1098/004)).

## Mitigations

- **M1018 User Account Management:** Limit which user accounts are allowed to login via SSH.
- **M1032 Multi-factor Authentication:** Require multi-factor authentication for SSH connections wherever possible, such as password protected SSH keys.
- **M1042 Disable or Remove Feature or Program:** Disable the SSH daemon on systems that do not require it, especially ESXi servers. For macOS, ensure Remote Login is disabled under Sharing Preferences.
