from pathlib import Path
import json
from math_logic_agent.indexing import IndexStore

index_path = Path("data/master_brain_index.pkl")
if not index_path.exists():
    raise SystemExit(f"Missing index: {index_path}")

store = IndexStore.load(str(index_path), cloud_rerank=False)
manifest = getattr(store, "file_manifest", {}) or {}
entries = sorted(str(k) for k in manifest.keys())

out_dir = Path("data/reports")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "indexed_files.txt").write_text("\n".join(entries), encoding="utf-8")

q_path = Path("data/master_brain_quarantine.json")
if q_path.exists():
    q = json.loads(q_path.read_text(encoding="utf-8"))
    recs = q.get("records", {}) if isinstance(q, dict) else {}
    quarantined = sorted(
        v.get("file_key", "")
        for v in recs.values()
        if isinstance(v, dict) and v.get("file_key")
    )
else:
    quarantined = []

(out_dir / "quarantined_files.txt").write_text("\n".join(quarantined), encoding="utf-8")
print(f"INDEXED_COUNT={len(entries)}")
print(f"QUARANTINED_COUNT={len(quarantined)}")
