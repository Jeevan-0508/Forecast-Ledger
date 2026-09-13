"""
Ledger integrity verification.

Checks, independently of whatever wrote the ledger:
  - every SEALED contract's stored hash matches a fresh recomputation
  - no forecast_id is sealed twice with different hashes
  - no forecast_id is graded twice
  - every GRADED event corresponds to a SEALED event, and targets the same period
  - event ordering: a GRADED event's timestamp is not before its SEALED event's
  - every event carries a config_version

Returns VERIFIED / WARNING / INVALID with the specific issues found, never a
bare boolean.
"""
from __future__ import annotations

from src.ledger.contract import seal_hash


def verify(events: list) -> dict:
    issues = []       # (severity, message) -- severity in {"INVALID", "WARNING"}

    sealed_by_id = {}
    for e in events:
        if e.get("event") != "SEALED":
            continue
        fid = e["contract"]["forecast_id"]
        recomputed = seal_hash(e["contract"])
        if recomputed != e["hash"]:
            issues.append(("INVALID", f"{fid}: stored hash {e['hash']} does not match "
                                       f"recomputed hash {recomputed}; contract has been altered."))
        if fid in sealed_by_id:
            if sealed_by_id[fid]["hash"] != e["hash"]:
                issues.append(("INVALID", f"{fid}: sealed more than once with different hashes."))
            else:
                issues.append(("WARNING", f"{fid}: sealed more than once with the identical hash "
                                           f"(harmless duplicate, but should not recur)."))
        else:
            sealed_by_id[fid] = e
        if "config_version" not in e:
            issues.append(("INVALID", f"{fid}: SEALED event missing config_version."))

    graded_seen = set()
    for e in events:
        if e.get("event") != "GRADED":
            continue
        fid = e["forecast_id"]
        if fid in graded_seen:
            issues.append(("INVALID", f"{fid}: graded more than once."))
        graded_seen.add(fid)

        if fid not in sealed_by_id:
            issues.append(("INVALID", f"{fid}: GRADED event with no matching SEALED event."))
            continue

        contract = sealed_by_id[fid]["contract"]
        if contract["target_period"] != e.get("target_period"):
            issues.append(("INVALID", f"{fid}: GRADED target_period {e.get('target_period')!r} "
                                       f"does not match sealed target_period {contract['target_period']!r}."))
        if e.get("graded_at", "") < sealed_by_id[fid].get("sealed_at", ""):
            issues.append(("INVALID", f"{fid}: graded_at precedes sealed_at -- impossible ordering."))
        if "config_version" not in e:
            issues.append(("INVALID", f"{fid}: GRADED event missing config_version."))

    for e in events:
        if e.get("event") == "REFUSED" and "config_version" not in e:
            issues.append(("INVALID", f"REFUSED event for {e.get('series_id')} missing config_version."))

    if any(sev == "INVALID" for sev, _ in issues):
        status = "INVALID"
    elif issues:
        status = "WARNING"
    else:
        status = "VERIFIED"

    return {
        "status": status,
        "issues": [{"severity": sev, "message": msg} for sev, msg in issues],
        "sealed_count": len(sealed_by_id),
        "graded_count": len(graded_seen),
    }
