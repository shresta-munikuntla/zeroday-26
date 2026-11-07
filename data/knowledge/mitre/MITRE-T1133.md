---
doc_id: MITRE-T1133
title: "T1133 External Remote Services"
source_type: mitre_attack_official
url: https://attack.mitre.org/techniques/T1133
attack_release: "20.1"
technique_version: "2.5"
tactics: [initial-access, persistence]
platforms: [Containers, Linux, macOS, Windows]
license_note: "MITRE ATT&CK(R) content, (c) The MITRE Corporation. Reproduced under the ATT&CK Terms of Use."
---

# T1133 External Remote Services

## Description

Adversaries may leverage external-facing remote services to initially access and/or persist within a network. Remote services such as VPNs, Citrix, and other access mechanisms allow users to connect to internal enterprise network resources from external locations. There are often remote service gateways that manage connections and credential authentication for these services. Services such as [Windows Remote Management](https://attack.mitre.org/techniques/T1021/006) and [VNC](https://attack.mitre.org/techniques/T1021/005) can also be used externally.

Access to [Valid Accounts](https://attack.mitre.org/techniques/T1078) to use the service is often a requirement, which could be obtained through credential pharming or by obtaining the credentials from users after compromising the enterprise network. Access to remote services may be used as a redundant or persistent access mechanism during an operation.

Access may also be gained through an exposed service that doesn’t require authentication. In containerized environments, this may include an exposed Docker API, Kubernetes API server, kubelet, or web application such as the Kubernetes dashboard.

Adversaries may also establish persistence on network by configuring a Tor hidden service on a compromised system. Adversaries may utilize the tool `ShadowLink` to facilitate the installation and configuration of the Tor hidden service. Tor hidden service is then accessible via the Tor network because `ShadowLink` sets up a .onion address on the compromised system. `ShadowLink` may be used to forward any inbound connections to RDP, allowing the adversaries to have remote access. Adversaries may get `ShadowLink` to persist on a system by masquerading it as an MS Defender application.

## Mitigations

- **M1021 Restrict Web-Based Content:** Restrict all traffic to and from public Tor nodes.
- **M1030 Network Segmentation:** Deny direct remote access to internal systems through the use of network proxies, gateways, and firewalls.
- **M1032 Multi-factor Authentication:** Use strong two-factor or multi-factor authentication for remote service accounts to mitigate an adversary's ability to leverage stolen credentials, but be aware of [Multi-Factor Authentication Interception](https://attack.mitre.org/techniques/T1111) techniques for some two-factor authentication implementations.
- **M1035 Limit Access to Resource Over Network:** Limit access to remote services through centrally managed concentrators such as VPNs and other managed remote access systems.
- **M1042 Disable or Remove Feature or Program:** Disable or block remotely available services that may be unnecessary.
