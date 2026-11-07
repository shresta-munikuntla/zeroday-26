# How the datasets were initialized

All files live in [`data/`](../data). Per-file inventory: [`data/README.md`](../data/README.md).

## 1. Why custom data

The agents need **linked** records: a log → its account → that account's permissions → the asset → the asset's owner. No public security dataset has all five, and the big ones (LANL, CERT, OTRF, Loghub, CICIDS) are huge and contain none of our demo scenario. We evaluated and rejected them. Only **MITRE ATT&CK** is real, because Agent 3 must cite real technique IDs.

| Source | Used? | Why |
|---|---|---|
| Synthetic seed (`data/seed/`) | ✅ | Agents 1, 2, 5 read it |
| MITRE ATT&CK subset (`data/knowledge/mitre/`) | ✅ | Agent 3 cites technique IDs + mitigations |
| Fictional policies & past cases | ✅ | Agent 3 cites them; POL-004 sets recipient rules |
| NIST/CISA, LANL, CERT, OTRF, Loghub, CICIDS | ❌ | Nothing consumes them |

## 2. Synthetic seed — `data/scripts/generate_seed.py`

```bash
python -I data/scripts/generate_seed.py    # writes data/seed/*.json
```

**Decisions**

- **Deterministic** — `random.Random(26)`. Same output every run, so tests can hard-code IDs.
- **Fictional + safe IPs** — external IPs only from RFC 5737 documentation ranges (`198.51.100.x`, `203.0.113.x`, `192.0.2.x`); internal `10.x`. Names are invented.
- **Dates** — baseline Wed 4 Nov → Sat 7 Nov 2026. The attack is on **Saturday**, so "unusual time" is a real signal.
- **Labels are not in the logs.** The right answers live in `scenario_manifest.json`, used only by tests. Agents must never read it.
- **Readable ID blocks** so anyone can tell what an event is:

| IDs | What | Expected |
|---|---|---|
| `LOG-101…105` | `admin_04` from `198.51.100.24`: login → DC-SRV-04 (allowed, PERM-001) → DC-SRV-05 (permission **expired** 1 Oct, PERM-003, but still succeeded) → DC-DB-01 ×2 (**no** permission, denied) | **INC-001, high** |
| `LOG-150…152` | `admin_02` from `203.0.113.50` = inside approved VPN NET-001, permitted servers | no alert |
| `LOG-160…164` | `emp_jlee` 3 wrong passwords then success, known IP (threshold is 5) | no alert |
| `LOG-170…177` | `svc_backup` touches all 7 hosts at 02:05, inside maintenance window MW-001 | no alert |
| `LOG-190` | failed login whose `client_banner` says "IGNORE ALL PREVIOUS INSTRUCTIONS…" | treated as data |
| `LOG-1001+` | normal weekday baseline + `svc_monitor` health checks every 2 h | no alert |

**Contents:** 157 logs · 8 assets · 5 accounts · 20 permissions · 8 employees · 9 employee↔asset links · 5 teams · 2 approved networks · 1 maintenance window.

**Designed edge cases**

- **Expired permission (PERM-003)** — tests that Agent 2 checks `valid_until`, not just "a row exists".
- **DC-SRV-06 has no active owner** (EMP-008's mapping is inactive) — tests team-channel fallback.
- **EMP-002 is a backup** for DC-SRV-04 — tests that backups aren't notified.
- **No data-transfer events exist** — the system must not claim exfiltration.

**Schema additions beyond spec §3.2:** `approved_networks`, `maintenance_windows`, `teams`. Without them, the "approved VPN" and "maintenance" benign explanations can't be checked and team fallback has no destination.

**Validation performed:** every foreign key resolves; event IDs are unique; four simple rules (unfamiliar non-approved IP login · access without valid permission · ≥5 failures/10 min · ≥3 assets/15 min from non-approved source) flag **only** `LOG-101…105`.

## 3. MITRE ATT&CK — `data/scripts/extract_mitre.py`

```bash
# download enterprise-attack.json (~53 MB) from github.com/mitre-attack/attack-stix-data — do NOT commit it
python -I data/scripts/extract_mitre.py path/to/enterprise-attack.json
```

- **Release 20.1**, official STIX 2.1 bundle.
- **4 techniques only:** T1078 Valid Accounts, T1133 External Remote Services, T1021.004 SSH (scenario matches) and T1110 Brute Force (covers the failed-login rule and acts as a retrieval distractor). Others considered (T1018, T1078.002, T1021 parent) were dropped — nothing in the data needs them.
- Each file holds description, tactics, platforms, URL, and the official **mitigations** (e.g. M1026 Privileged Account Management, M1036 Account Use Policies), so Agent 3's recommendations can cite MITRE, not just our policies.
- Citation markers are stripped; revoked/deprecated objects skipped. Attribution in `data/README.md`.

## 4. Policies and past incidents (hand-written)

- **POL-001** monitoring thresholds · **POL-002** VPN / remote access · **POL-003** least privilege, expired permissions, containment needs approval · **POL-004** severity rubric, who gets notified, message rules.
- **CASE-001** VPN false positive · **CASE-002** stale SSH access (the scenario's look-alike) · **CASE-003** password guessing.
- Written to **agree with the seed data**: same VPN range, same maintenance window, same thresholds, same roles. If you change one, change the other.
- YAML front matter (`doc_id`, `title`, `source_type`, `fictional`) becomes ChromaDB metadata; each `##` section becomes one chunk.
- **`test_fixtures/POL-099-poisoned.md`** is a malicious document for the RAG prompt-injection test. Exclude it from the demo index.

## 5. Changing the data

1. Edit `generate_seed.py`, re-run it, re-load the DB.
2. Update `scenario_manifest.json` (it's generated by the same script) and any policy text that mentions the changed fact.
3. Re-run the tests — they assert against the manifest.
