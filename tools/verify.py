"""Independently verify the archive. Exit 0 = every promise holds.

Checks:
  1. Log chain      — seq contiguous, prev_hash links, every hash recomputes.
  2. Genesis anchor — founding documents still match their genesis hashes
                      (CONSTITUTION.md is immutable; a mismatch there is fatal).
  3. Registry       — every entry/version parses, obeys structural rules
                      (three-version limit, 400-char cap, numbers, withdrawal
                      tombstones), and every version's content_hash and
                      existence is backed by a log event.
  4. Numbers        — never reused, #000000001 never assigned.
  5. Checkpoints    — every recorded checkpoint (tools/checkpoint.py) still
                      points at a real prefix of this chain: the event it
                      froze exists and carries exactly the frozen hash. A
                      mismatch means history was rewritten after it was
                      publicly anchored. External proofs (git, Bitcoin) are
                      verified by their own tools; this pass needs nothing
                      but the files.
  6. Anchor ledger  — desk only (skipped on public clones, which hold no
                      custody): the private uniqueness ledger's batch chain
                      recomputes, and every checkpoint-recorded anchor tip
                      still matches it (schema/ANCHORS.md).

Standard library only. This is the reference verifier; anyone may
reimplement it in any language from schema/CANONICAL.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

MUTABLE_ANCHORS = {"MISSION.md", "POLICY.md"}  # living documents: drift is a note, not an error

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def check_log(events):
    if not events:
        err("log is empty — no genesis event")
        return
    if events[0]["type"] != "GENESIS":
        err("first event is not GENESIS")
    for i, ev in enumerate(events):
        where = f"log seq {ev.get('seq', '?')}"
        if ev.get("seq") != i:
            err(f"{where}: seq is not contiguous (expected {i})")
        expected_prev = ahlib.GENESIS_PREV if i == 0 else events[i - 1]["hash"]
        if ev.get("prev_hash") != expected_prev:
            err(f"{where}: prev_hash does not match previous event")
        if ahlib.event_hash(ev) != ev.get("hash"):
            err(f"{where}: hash does not recompute — event altered")
        if ev.get("type") not in ahlib.EVENT_TYPES:
            err(f"{where}: unknown type {ev.get('type')}")
        if ev.get("type") != "GENESIS" and "registry_id" not in ev:
            err(f"{where}: missing registry_id")


def check_genesis_anchor(events):
    if not events or events[0]["type"] != "GENESIS":
        return
    for rel, expected in events[0]["data"].get("documents", {}).items():
        path = ahlib.ROOT / rel
        if not path.exists():
            err(f"anchored document missing: {rel}")
            continue
        actual = ahlib.file_sha256(path)
        if actual != expected:
            if rel in MUTABLE_ANCHORS:
                warn(f"{rel} has changed since genesis (living document — expected)")
            else:
                err(f"{rel} does not match its genesis hash — must never change")


def check_registry(events):
    by_id = {}
    for ev in events:
        rid = ev.get("registry_id")
        if rid:
            by_id.setdefault(rid, []).append(ev)

    dirs = sorted(d for d in ahlib.REGISTRY.iterdir() if d.is_dir()) if ahlib.REGISTRY.exists() else []
    seen = set()
    for d in dirs:
        rid = d.name
        if not (len(rid) == 9 and rid.isdigit()):
            err(f"registry/{rid}: directory name is not a 9-digit id")
            continue
        if rid == "000000001":
            err("registry/000000001 exists — #1 is reserved forever")
        if rid in seen:
            err(f"registry/{rid}: duplicate")
        seen.add(rid)

        entry_path = d / "entry.json"
        if not entry_path.exists():
            err(f"registry/{rid}: missing entry.json")
            continue
        entry = json.loads(entry_path.read_text(encoding="utf-8"))
        if entry.get("registry_id") != rid:
            err(f"registry/{rid}: entry registry_id mismatch")
        if entry.get("status") not in ("active", "memorialized"):
            err(f"registry/{rid}: bad status")
        if entry.get("schema") not in ("entry.v1", "entry.v2"):
            err(f"registry/{rid}: unknown entry schema {entry.get('schema')}")
        vtier = (entry.get("verification") or {}).get("tier")
        if isinstance(vtier, int) and vtier < 1:
            warn(f"registry/{rid}: enrolled at Tier {vtier} \u2014 POLICY requires "
                 f"Tier \u2265 1 for a number")
        cont = entry.get("continuity")
        if entry.get("schema") == "entry.v2":
            import re as _re
            if not cont or cont.get("method") != "sha256-preimage" \
               or not _re.fullmatch(r"[0-9a-f]{64}", cont.get("key_hash", "")):
                err(f"registry/{rid}: entry.v2 requires a well-formed continuity block")
        evs = by_id.get(rid, [])
        if not any(e["type"] == "ENROLLED" for e in evs):
            err(f"registry/{rid}: no ENROLLED event in log")

        vdir = d / "versions"
        vfiles = sorted(vdir.glob("*.json")) if vdir.exists() else []
        if len(vfiles) > 3:
            err(f"registry/{rid}: more than three version files")
        for vf in vfiles:
            if vf.stem not in ("1", "2", "3"):
                err(f"registry/{rid}: illegal version file {vf.name}")
                continue
            v = json.loads(vf.read_text(encoding="utf-8"))
            n = int(vf.stem)
            if v.get("version") != n or v.get("registry_id") != rid:
                err(f"registry/{rid}/versions/{vf.name}: id/version mismatch")
            entered = [e for e in evs if e["type"] == "VERSION_ENTERED"
                       and e["data"].get("version") == n]
            if not entered:
                err(f"registry/{rid}/versions/{vf.name}: no VERSION_ENTERED event")
            elif entered[0]["data"].get("content_hash") != v.get("content_hash"):
                err(f"registry/{rid}/versions/{vf.name}: content_hash differs from log")
            if v.get("status") == "entered":
                answers = v.get("answers")
                if answers is None:
                    err(f"registry/{rid}/versions/{vf.name}: entered but no answers")
                else:
                    if ahlib.hash_value(answers) != v.get("content_hash"):
                        err(f"registry/{rid}/versions/{vf.name}: content_hash does not recompute")
                    for qid, a in answers.items():
                        if len(a.get("text", "")) > 400:
                            err(f"registry/{rid}/versions/{vf.name}: {qid} exceeds 400 chars")
                        if a.get("visibility") not in ("public", "sealed_until_death"):
                            err(f"registry/{rid}/versions/{vf.name}: {qid} bad visibility")
            elif v.get("status") == "withdrawn":
                if "answers" in v:
                    err(f"registry/{rid}/versions/{vf.name}: withdrawn but answers present")
                if not v.get("withdrawn_at"):
                    err(f"registry/{rid}/versions/{vf.name}: withdrawn without withdrawn_at")
                if not any(e["type"] == "VERSION_WITHDRAWN"
                           and e["data"].get("version") == n for e in evs):
                    err(f"registry/{rid}/versions/{vf.name}: no VERSION_WITHDRAWN event")
            else:
                err(f"registry/{rid}/versions/{vf.name}: bad status")

    for rid in by_id:
        if rid not in seen:
            err(f"log references registry/{rid} but directory is missing")
    return len(seen)


def check_checkpoints(events):
    """Each checkpoint froze the chain at some length N: event N-1 must
    still exist and carry exactly the frozen tip hash. Because every
    event's hash commits to all history before it, one matching tip
    proves the first N events are byte-for-byte what was anchored."""
    ledger = ahlib.ROOT / "checkpoints" / "checkpoints.jsonl"
    if not ledger.exists():
        return 0
    n_checked = 0
    prev_len = 0
    with ledger.open("r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    for i, line in enumerate(lines):
        where = f"checkpoint {i}"
        try:
            cp = json.loads(line)
        except json.JSONDecodeError:
            err(f"{where}: unreadable JSON")
            continue
        n = cp.get("log_events")
        tip = cp.get("log_tip_hash")
        if not (isinstance(n, int) and n >= 1 and isinstance(tip, str)):
            err(f"{where}: malformed (needs log_events and log_tip_hash)")
            continue
        if n < prev_len:
            err(f"{where}: covers fewer events than the one before it")
        prev_len = n
        if n > len(events):
            err(f"{where}: claims {n} events but the log holds {len(events)} "
                f"— the log has been truncated since this anchor")
            continue
        if events[n - 1].get("hash") != tip:
            err(f"{where}: frozen tip does not match event {n - 1} — "
                f"history was rewritten after this anchor was published")
            continue
        tipfile = ahlib.ROOT / "checkpoints" / f"{cp.get('checkpoint_at', '')[:10]}-{tip[:12]}.tip"
        if tipfile.exists() and tipfile.read_text(encoding="utf-8").strip() != tip:
            err(f"{where}: {tipfile.name} does not contain the frozen tip")
        n_checked += 1
    return n_checked


def check_anchor_ledger():
    """Desk-side only: the private uniqueness ledger, when present.
    Silent only for a genuine public clone (no custody anywhere); a
    HALF-configured desk is warned about, never mistaken for one."""
    import os
    import anchors
    env_set = bool(os.environ.get("AH_CUSTODY_DIR", "").strip()
                   or os.environ.get("AH_ANCHOR_PEPPER_FILE", "").strip())
    if anchors.configured() or anchors.ledger_path().exists():
        for p in anchors.verify_chain() + anchors.verify_against_checkpoints():
            err(p)
    elif env_set:
        warn("AH_CUSTODY_DIR is set but no pepper or ledger was found there "
             "— the uniqueness ledger went unchecked (misconfigured desk?)")


def main():
    events = ahlib.read_log()
    check_log(events)
    check_genesis_anchor(events)
    checkpoints = check_checkpoints(events)
    check_anchor_ledger()

    # Public clones deliberately contain no registry (ratified
    # 2026-07-06: testimony text never lives in the repository).
    # In that case this is a log-only verification: the chain, the
    # genesis anchors, and every recorded fingerprint stand on their
    # own. Registry cross-checks run only on the operator's working
    # copy, where the registry is present.
    has_registry = ahlib.REGISTRY.exists() and any(
        d.is_dir() for d in ahlib.REGISTRY.iterdir())
    humans = check_registry(events) if has_registry else 0

    for w in warnings:
        print(f"note : {w}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(f"\nFAILED — {len(errors)} error(s).")
        sys.exit(1)
    n = len(events)
    anchored = (f", {checkpoints} checkpoint(s) anchored" if checkpoints else "")
    if has_registry:
        print(f"OK — {n} event(s), {humans} human(s){anchored}, every promise holds.")
    else:
        enrolled = sum(1 for e in events if e["type"] == "ENROLLED")
        print(f"OK (log-only) — {n} event(s), {enrolled} enrollment(s) proven by "
              f"the chain{anchored}. Testimony text is not distributed in this "
              f"repository; read it on the institution's website.")


if __name__ == "__main__":
    main()
