"""AllHumans shared helpers. Python standard library only, forever.

Canonical form and hashing are specified in schema/CANONICAL.md.
This file is the reference implementation.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "log" / "registry.log.jsonl"
REGISTRY = ROOT / "registry"
GENESIS_PREV = "0" * 64

# --- rehearsal mode -----------------------------------------------------
# The archive has exactly two modes. PRODUCTION is the default and the
# real thing. DRILL is a disposable rehearsal clone made by
# tools/make_drill.py, which stamps the clone with a DRILL_CLONE marker
# file at its root. Mode is resolved from the AH_MODE environment
# variable AND the marker together, and any disagreement stops the
# machine: a misspelled mode, a drill env in the real repo, or a real
# env in a drill clone must all FAIL LOUDLY, never guess.
DRILL_MARKER = ROOT / "DRILL_CLONE"


def resolve_mode() -> str:
    raw = os.environ.get("AH_MODE", "").strip().lower()
    if raw not in ("", "production", "drill"):
        raise SystemExit(
            f"AH_MODE={raw!r} is not a mode. Use 'drill' or 'production' "
            "(unset means production). A misspelled mode stops the "
            "machine; it never silently falls back.")
    mode = raw or "production"
    marked = DRILL_MARKER.exists()
    if mode == "drill" and not marked:
        raise SystemExit(
            "REFUSED: AH_MODE=drill, but this tree is not a drill clone "
            f"(no DRILL_CLONE marker at {ROOT}).\n"
            "Running drill ceremonies here would write to the REAL "
            "archive. Make a rehearsal ground with tools/make_drill.py "
            "and run inside it.")
    if mode == "production" and marked:
        raise SystemExit(
            f"REFUSED: this tree IS a drill clone ({ROOT}), but AH_MODE "
            "is not 'drill'.\n"
            "Set AH_MODE=drill to rehearse here. Production ceremonies "
            "belong in the real repository only.")
    return mode


def announce_ceremony(tool: str) -> str:
    """Every ceremony prints where and in which mode it operates,
    before it does anything. Returns the resolved mode."""
    mode = resolve_mode()
    print(f"[{tool}] archive: {ROOT}")
    if mode == "drill":
        print(f"[{tool}] mode:    DRILL - a disposable rehearsal clone; "
              "nothing here is kept")
    else:
        print(f"[{tool}] mode:    PRODUCTION - THE REAL ARCHIVE; a number "
              "spent here is spent forever")
    return mode


EVENT_TYPES = [
    "GENESIS", "ENROLLED", "VERSION_ENTERED", "VERSION_WITHDRAWN",
    "MEMORIALIZED", "VERIFICATION_CHANGED", "STATUS_ANNOTATED",
]


def canonical(value) -> bytes:
    """Canonical JSON bytes (schema/CANONICAL.md)."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_value(value) -> str:
    return sha256_hex(canonical(value))


def event_hash(event: dict) -> str:
    """Hash of an event with its 'hash' field absent."""
    unsigned = {k: v for k, v in event.items() if k != "hash"}
    return hash_value(unsigned)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_log() -> list:
    if not LOG.exists():
        return []
    events = []
    with LOG.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def append_event(ev_type: str, data: dict, registry_id: str | None = None) -> dict:
    """Build, chain, and append one event. Returns the written event."""
    if ev_type not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {ev_type}")
    events = read_log()
    if ev_type == "GENESIS" and events:
        raise ValueError("log already has a genesis event")
    if ev_type != "GENESIS" and not events:
        raise ValueError("log has no genesis event yet")
    event = {
        "schema": "event.v1",
        "seq": len(events),
        "ts": now_utc(),
        "type": ev_type,
        "data": data,
        "prev_hash": events[-1]["hash"] if events else GENESIS_PREV,
    }
    if registry_id is not None:
        event["registry_id"] = registry_id
    event["hash"] = event_hash(event)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n")
    return event


def file_sha256(path: Path) -> str:
    return sha256_hex(path.read_bytes())


# --- Continuity keys -------------------------------------------------
# A continuity key is the human's proof of return: shown once at
# enrollment, never stored — only its SHA-256 lives in entry.json.
# Like a wallet seed, keeping it safe is the owner's responsibility.
# Format: "ah1-" + 32 hex chars in groups of 4 (128 bits of entropy).
# The canonical form (the exact string that is hashed, as ASCII) is
# lowercase with dashes, e.g. "ah1-9f2c-08a1-...".

def new_continuity_key() -> str:
    import secrets
    hexstr = secrets.token_hex(16)
    groups = [hexstr[i:i + 4] for i in range(0, 32, 4)]
    return "ah1-" + "-".join(groups)


def normalize_key(key: str) -> str:
    return key.strip().lower()


def continuity_key_hash(key: str) -> str:
    return sha256_hex(normalize_key(key).encode("ascii"))
