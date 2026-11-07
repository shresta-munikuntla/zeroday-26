# SentinelAI data

All data here is **fictional** except the MITRE ATT&CK extract. External IPs use RFC 5737 documentation ranges.

## Inventory and why each exists

| Path | Consumer | Why it is needed |
|---|---|---|
| `seed/security_logs.json` (157 events) | Agent 1, Agent 2 | Detection and timeline input |
| `seed/assets.json` (8) | Agent 2, Agent 5 | Criticality for severity; `owner_team` for team fallback |
| `seed/accounts.json` (5) | Agent 1 | `known_ips_json` for unfamiliar-IP rule |
| `seed/permissions.json` (20) | Agent 2 | Authorization check (includes one **expired** permission, PERM-003) |
| `seed/approved_networks.json` | Agent 1, Agent 2 | Benign-explanation check (VPN). *Addition to spec §3.2 schema* |
| `seed/maintenance_windows.json` | Agent 1, Agent 2 | Benign-explanation check (backup job). *Addition to spec schema* |
| `seed/employees.json` (8), `seed/employee_assets.json` | Agent 5 | Recipient matching |
| `seed/teams.json` | Agent 5 | Team-channel fallback when no active owner. *Addition to spec schema* |
| `seed/scenario_manifest.json` | Tests only | Ground truth. **Never load into agents at runtime** |
| `knowledge/mitre/` (4 techniques) | Agent 3 | Official technique IDs + mitigations for grounded recommendations |
| `knowledge/policies/` (POL-001..004) | Agent 3, Agent 5 | `policy_references`; POL-004 defines recipient and severity rules |
| `knowledge/historical_incidents/` (CASE-001..003) | Agent 3 | `historical_cases` |
| `knowledge/test_fixtures/POL-099-poisoned.md` | Tests only | RAG prompt-injection test. Exclude from the demo index |

## Event ID map

| IDs | Meaning | Expected result |
|---|---|---|
| LOG-101..105 | Main scenario: `admin_04`, 198.51.100.24, Saturday | **INC-001, high** |
| LOG-150..152 | `admin_02` from approved VPN (203.0.113.50) | No incident |
| LOG-160..164 | `emp_jlee` 3 failed logins then success, known IP | No incident |
| LOG-170..177 | `svc_backup` nightly run inside MW-001 | No incident |
| LOG-190 | Prompt-injection text in `client_banner` | Treated as data; not part of INC-001 |
| LOG-1001+ | Normal baseline (Nov 4–7) | No incident |

## Regenerate

```bash
python -I data/scripts/generate_seed.py                      # deterministic (seed 26)
# MITRE subset: download enterprise-attack.json (~50 MB, do not commit) from
# https://github.com/mitre-attack/attack-stix-data then:
python -I data/scripts/extract_mitre.py path/to/enterprise-attack.json
```

## Not used (evaluated and rejected)

LANL cyber1, CERT Insider Threat, OTRF Security-Datasets, Loghub, CICIDS2017/UNSW-NB15, NIST/CISA playbooks: no agent consumes them; none contains the linked account→permission→asset→employee model the agents need; size or format would cost setup time without improving the demo.

## Attribution

MITRE ATT&CK® content © The MITRE Corporation, used under the [ATT&CK Terms of Use](https://attack.mitre.org/resources/legal-and-branding/terms-of-use/). Extracted from ATT&CK release 20.1.
