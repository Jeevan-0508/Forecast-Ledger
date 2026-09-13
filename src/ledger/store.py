"""
Append-only ledger.

Physically: one JSON object per line (JSONL) in data/ledger/ledger.jsonl.
Logically: three event kinds --

    SEALED   a forecast contract, frozen, with its hash
    REFUSED  an eligibility refusal
    GRADED   an outcome attached to a previously sealed forecast_id

Nothing in this module ever opens the file in a mode that can touch an
existing line. Every write is an append. "Correcting" a past event means
appending a new event that says so, never rewriting the old one.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

from src.ledger.contract import canonicalize, seal_hash


class LedgerError(Exception):
    pass


class LedgerStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def read_all(self) -> list:
        events = []
        with self.path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise LedgerError(f"ledger line {line_no} is not valid JSON: {e}") from e
        return events

    def _append_raw(self, event: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, ensure_ascii=True))
            f.write("\n")

    # -- SEALED -----------------------------------------------------------

    def find_sealed(self, forecast_id: str):
        for e in self.read_all():
            if e.get("event") == "SEALED" and e["contract"]["forecast_id"] == forecast_id:
                return e
        return None

    def seal(self, contract_dict: dict, config_version: str) -> dict:
        """Appends a SEALED event. Idempotent for an identical contract
        (same forecast_id, same content -> same hash -> no-op, returns the
        existing event). Raises if a forecast_id already exists with a
        DIFFERENT hash: that would mean silently rewriting a sealed value,
        which this store refuses to do."""
        h = seal_hash(contract_dict)
        existing = self.find_sealed(contract_dict["forecast_id"])
        if existing is not None:
            if existing["hash"] == h:
                return existing  # identical re-run, nothing to do
            raise LedgerError(
                f"forecast_id {contract_dict['forecast_id']!r} is already sealed with a "
                f"different hash ({existing['hash']} != {h}). A sealed forecast contract "
                f"must never change; this looks like an attempt to mutate history."
            )
        event = {
            "event": "SEALED",
            "sealed_at": datetime.now(timezone.utc).isoformat(),
            "contract": contract_dict,
            "hash": h,
            "config_version": config_version,
            "status": "AWAITING_OUTCOME",
        }
        self._append_raw(event)
        return event

    # -- REFUSED ------------------------------------------------------------

    def find_refusal(self, dataset: str, series_id: str, observations: int, config_version: str):
        for e in self.read_all():
            if (e.get("event") == "REFUSED"
                    and e["dataset"] == dataset
                    and e["series_id"] == series_id
                    and e["observations"] == observations
                    and e["config_version"] == config_version):
                return e
        return None

    def record_refusal(self, eligibility_dict: dict, dataset: str, series_id: str) -> dict:
        """Idempotent: re-running the same refusal (same dataset, series,
        observation count and config version) does not duplicate."""
        existing = self.find_refusal(dataset, series_id, eligibility_dict["observations"],
                                      eligibility_dict["config_version"])
        if existing is not None:
            return existing
        event = {
            "event": "REFUSED",
            "dataset": dataset,
            "series_id": series_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "observations": eligibility_dict["observations"],
            "eligibility": eligibility_dict,
            "reason_code": eligibility_dict["reason_code"],
            "reason": eligibility_dict["message"],
            "config_version": eligibility_dict["config_version"],
        }
        self._append_raw(event)
        return event

    # -- GRADED -------------------------------------------------------------

    def find_grade(self, forecast_id: str):
        for e in self.read_all():
            if e.get("event") == "GRADED" and e["forecast_id"] == forecast_id:
                return e
        return None

    def grade(self, forecast_id: str, target_period: str, outcome: dict, config_version: str) -> dict:
        """Appends a GRADED event. Raises if this forecast_id has already
        been graded -- grading is a one-time event per forecast, by design
        (src.grading enforces the idempotent "skip if already graded" check
        before ever calling this; this raise is the hard backstop)."""
        if self.find_grade(forecast_id) is not None:
            raise LedgerError(f"forecast_id {forecast_id!r} has already been graded; "
                               f"refusing to grade it a second time.")
        sealed = self.find_sealed(forecast_id)
        if sealed is None:
            raise LedgerError(f"cannot grade {forecast_id!r}: no SEALED event found for it.")
        if sealed["contract"]["target_period"] != target_period:
            raise LedgerError(
                f"outcome target_period {target_period!r} does not match sealed "
                f"contract target_period {sealed['contract']['target_period']!r} for {forecast_id!r}."
            )
        event = {
            "event": "GRADED",
            "forecast_id": forecast_id,
            "target_period": target_period,
            "graded_at": datetime.now(timezone.utc).isoformat(),
            "config_version": config_version,
            **outcome,
        }
        self._append_raw(event)
        return event

    def outstanding_forecasts(self) -> list:
        """SEALED forecast_ids with no corresponding GRADED event yet."""
        events = self.read_all()
        sealed_ids = [e["contract"]["forecast_id"] for e in events if e.get("event") == "SEALED"]
        graded_ids = {e["forecast_id"] for e in events if e.get("event") == "GRADED"}
        return [fid for fid in sealed_ids if fid not in graded_ids]
