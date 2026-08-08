"""Freeze the archive's state into external, dated proof.

Usage:
    python tools/checkpoint.py            # record a checkpoint (git-anchored)
    python tools/checkpoint.py --ots      # also request a Bitcoin timestamp
                                          # (needs the OpenTimestamps client:
                                          #  pip install opentimestamps-client)

Why this exists. The hash chain makes the archive tamper-EVIDENT: any
altered byte breaks verification. But a chain alone cannot prove WHICH
of two internally-consistent copies came first — that takes a witness
outside the operator's hands. The log tip (the newest event's hash)
commits to the entire history, so anchoring that one hash somewhere
dated and independent freezes everything before it in provable time.

Each run appends one line to checkpoints/checkpoints.jsonl and writes
the tip to a small checkpoints/<date>-<tip12>.tip file (a stable target
for external anchors). Checkpoints carry fingerprints only, never words
— the directory is safe to publish and belongs in the repository; the
commit and push that follow are themselves the first anchor (the host
timestamps it, every clone witnesses it).

Anchors, in ascending strength:
  git               commit + push; GitHub's timestamp and every clone
  opentimestamps    a free Bitcoin-attested "existed by this date"
                    proof no one, operator included, can backdate
  anywhere public   the printed tip hash can be posted to any dated,
                    independent place (archives, lists, partners)

Losing an anchor service can never hurt the archive — anchors only add
witnesses. Verification of checkpoints lives in tools/verify.py and is
standard library only, per the founding constraints.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

CHECKPOINTS = ahlib.ROOT / "checkpoints"
LEDGER = CHECKPOINTS / "checkpoints.jsonl"


def read_checkpoints() -> list:
    if not LEDGER.exists():
        return []
    entries = []
    with LEDGER.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def main():
    events = ahlib.read_log()
    if not events:
        print("nothing to checkpoint: the log is empty")
        sys.exit(1)
    tip = events[-1]["hash"]
    ts = ahlib.now_utc()

    # The private uniqueness ledger (schema/ANCHORS.md) is witnessed by
    # the same checkpoint: only a batch count and tip hash, never an
    # anchor. A checkpoint is "nothing new" only when NEITHER tip moved.
    import anchors as anchor_ledger
    al_tip = None
    if not anchor_ledger.configured():
        print("note : anchor ledger not witnessed — custody is not configured")
        print("       in this shell (expected on public clones; on the desk,")
        print("       set AH_CUSTODY_DIR and re-run)")
    else:
        al_tip = anchor_ledger.ledger_tip()
        if al_tip is None:
            print("note : anchor ledger has no sealed batches yet — "
                  "nothing to witness")

    previous = read_checkpoints()
    if previous and previous[-1]["log_tip_hash"] == tip:
        # With custody unconfigured (al_tip None) this shell cannot see
        # the anchor ledger at all — appending would only write a
        # strictly weaker duplicate line, so an unchanged log tip is
        # "nothing new" regardless.
        if al_tip is None or previous[-1].get("anchor_ledger") == al_tip:
            print(f"already checkpointed at this tip ({tip[:16]}…) — "
                  f"nothing new to freeze")
            sys.exit(0)

    CHECKPOINTS.mkdir(exist_ok=True)
    tipfile = CHECKPOINTS / f"{ts[:10]}-{tip[:12]}.tip"
    tipfile.write_text(tip + "\n", encoding="utf-8", newline="\n")

    anchors = [{"kind": "git"}]
    if "--ots" in sys.argv:
        try:
            subprocess.run(["ots", "stamp", str(tipfile)], check=True)
            anchors.append({"kind": "opentimestamps",
                            "proof": tipfile.name + ".ots"})
            print(f"opentimestamps: proof requested -> {tipfile.name}.ots")
            print("(the Bitcoin attestation completes within hours; "
                  "`ots upgrade` then `ots verify` the file later)")
        except FileNotFoundError:
            print("opentimestamps: `ots` not found — skipped "
                  "(pip install opentimestamps-client)")
        except subprocess.CalledProcessError as e:
            print(f"opentimestamps: stamp failed ({e}) — skipped")

    entry = {
        "schema": "checkpoint.v1",
        "checkpoint_at": ts,
        "log_events": len(events),
        "log_tip_hash": tip,
        "anchors": anchors,
    }
    if al_tip:
        entry["anchor_ledger"] = al_tip
    with LEDGER.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n")

    print(f"checkpoint: {len(events)} event(s), tip {tip[:16]}… at {ts}")
    print()
    print("This hash now stands for the entire archive. Publish it anywhere")
    print("dated and outside your control — every witness strengthens it:")
    print()
    print(f"    {tip}")
    print()
    print("next: python tools/verify.py && git add -A && git commit && git push")
    print("      (the push is the first anchor: the host timestamps it and")
    print("       every clone becomes a witness)")


if __name__ == "__main__":
    main()
