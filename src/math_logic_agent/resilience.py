from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class QuarantineRecord:
    file_key: str
    path: str
    module_id: str | None
    reason: str
    fail_count: int
    last_failed_at: str
    quarantined: bool = True


class QuarantineStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.records: dict[str, QuarantineRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.records = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.records = {
                k: QuarantineRecord(**v)
                for k, v in data.get("records", {}).items()
                if isinstance(v, dict)
            }
        except Exception:
            self.records = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _utc_now(),
            "records": {k: asdict(v) for k, v in self.records.items()},
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def is_quarantined(self, file_key: str) -> bool:
        r = self.records.get(file_key)
        return bool(r and r.quarantined)

    def record_failure(self, file_key: str, path: str, module_id: str | None, reason: str) -> None:
        old = self.records.get(file_key)
        fail_count = old.fail_count + 1 if old else 1
        self.records[file_key] = QuarantineRecord(
            file_key=file_key,
            path=path,
            module_id=module_id,
            reason=reason[:500],
            fail_count=fail_count,
            last_failed_at=_utc_now(),
            quarantined=True,
        )

    def clear(self, module_id: str | None = None) -> int:
        if module_id is None:
            n = len(self.records)
            self.records = {}
            return n
        keys = [k for k, v in self.records.items() if v.module_id == module_id]
        for k in keys:
            del self.records[k]
        return len(keys)


def write_checkpoint(path: str | Path, payload: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out = dict(payload)
    out["updated_at"] = _utc_now()
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
