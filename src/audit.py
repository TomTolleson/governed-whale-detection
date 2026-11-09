"""Append-only, hash-chained audit log.

Each line in the log is one JSON object. Every entry stores the SHA-256 hash
of the previous line (the exact bytes, without the trailing newline), so editing
or deleting an earlier line breaks the chain and `verify_chain` will detect it.
The first entry uses a prev_hash of 64 zeros.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG = Path(__file__).resolve().parent.parent / "audit_log.jsonl"
GENESIS_HASH = "0" * 64


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _last_line(path: Path) -> str | None:
    if not path.exists():
        return None
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return lines[-1] if lines else None


def log_event(actor: str, action: str, details=None, log_path=DEFAULT_LOG) -> dict:
    """Append one event to the log and return the entry that was written."""
    path = Path(log_path)
    last = _last_line(path)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "details": details if details is not None else {},
        "prev_hash": _sha256(last) if last is not None else GENESIS_HASH,
    }
    line = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    # Mode "a" only ever appends; existing lines are never rewritten.
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return entry


def verify_chain(log_path=DEFAULT_LOG) -> bool:
    """Return True if every entry's prev_hash matches the line before it."""
    path = Path(log_path)
    if not path.exists():
        return True
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    expected = GENESIS_HASH
    for line in lines:
        if json.loads(line).get("prev_hash") != expected:
            return False
        expected = _sha256(line)
    return True


if __name__ == "__main__":
    # CLI: python -m src.audit <actor> <action> '<json details>'
    import sys

    actor, action = sys.argv[1], sys.argv[2]
    details = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    print(json.dumps(log_event(actor, action, details)))
