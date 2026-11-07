"""Extract a small MITRE ATT&CK subset (techniques + mitigations) into RAG-ready markdown.

Usage:  python -I data/scripts/extract_mitre.py <path/to/enterprise-attack.json> [out_dir]
Source: https://github.com/mitre-attack/attack-stix-data (enterprise-attack/enterprise-attack.json)
The full bundle (~50 MB) is NOT committed; only the extracted subset is.
"""
import json
import re
import sys
from pathlib import Path

TECHNIQUES = ["T1078", "T1133", "T1021.004", "T1110"]
src = Path(sys.argv[1])
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "knowledge" / "mitre"

objs = json.loads(src.read_text(encoding="utf-8"))["objects"]
by_id = {o["id"]: o for o in objs}
release = next((o.get("x_mitre_version") for o in objs if o.get("type") == "x-mitre-collection"), "unknown")


def ext(o):
    return next((r for r in o.get("external_references", []) if r.get("source_name") == "mitre-attack"), {})


def clean(text):
    return re.sub(r"\s*\(Citation:[^)]*\)", "", text or "").strip()


out.mkdir(parents=True, exist_ok=True)
for o in objs:
    if o.get("type") != "attack-pattern" or o.get("revoked") or o.get("x_mitre_deprecated"):
        continue
    ref = ext(o)
    tid = ref.get("external_id")
    if tid not in TECHNIQUES:
        continue
    mitigations = []
    for r in objs:
        if r.get("type") == "relationship" and r.get("relationship_type") == "mitigates" \
                and r.get("target_ref") == o["id"] and not r.get("revoked") and not r.get("x_mitre_deprecated"):
            m = by_id.get(r["source_ref"], {})
            if m.get("x_mitre_deprecated") or m.get("revoked"):
                continue
            mitigations.append((ext(m).get("external_id", "?"), m.get("name", "?"), clean(r.get("description"))))
    mitigations.sort()
    tactics = sorted({p["phase_name"] for p in o.get("kill_chain_phases", [])})
    lines = [
        "---",
        f"doc_id: MITRE-{tid}",
        f"title: \"{tid} {o['name']}\"",
        "source_type: mitre_attack_official",
        f"url: {ref.get('url', '')}",
        f"attack_release: \"{release}\"",
        f"technique_version: \"{o.get('x_mitre_version', '')}\"",
        f"tactics: [{', '.join(tactics)}]",
        f"platforms: [{', '.join(o.get('x_mitre_platforms', []))}]",
        "license_note: \"MITRE ATT&CK(R) content, (c) The MITRE Corporation. Reproduced under the ATT&CK Terms of Use.\"",
        "---",
        "",
        f"# {tid} {o['name']}",
        "",
        "## Description",
        "",
        clean(o.get("description")),
        "",
    ]
    if o.get("x_mitre_detection"):
        lines += ["## Detection", "", clean(o["x_mitre_detection"]), ""]
    if mitigations:
        lines += ["## Mitigations", ""]
        lines += [f"- **{mid} {name}:** {desc}" if desc else f"- **{mid} {name}**" for mid, name, desc in mitigations]
        lines.append("")
    (out / f"MITRE-{tid}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"MITRE-{tid}: {o['name']} | {len(mitigations)} mitigations | release {release}")
