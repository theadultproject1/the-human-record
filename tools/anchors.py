"""The uniqueness ledger — one human, one record (schema/ANCHORS.md).

Anchors are durable contact identifiers (the enrollment email today,
verified phone when that tier exists) kept ONLY as keyed one-way
fingerprints in a private ledger under operator custody. They never
enter the repository, the archive, or the web host. tools/enroll.py
refuses to spend a number while any anchor on a submission matches.

Custody layout (AH_CUSTODY_DIR; the in-repo custody/ fallback is
gitignored and for drills only — keep real custody OUTSIDE the repo):

    pepper-v1.txt              the HMAC pepper (or AH_ANCHOR_PEPPER_FILE)
    anchors/staged.jsonl       anchor lines awaiting a seal (kept sorted)
    anchors/ledger.jsonl       hash-chained sealed batches
    edges/vouch-edges.jsonl    voucher # -> vouchee #, nothing else
    agreements/                retained acceptance records (fetch_inbox)
    ops-log.jsonl              recorded --anchor-override reasons

Usage:
    python tools/anchors.py init                 create the pepper (once)
    python tools/anchors.py fingerprint          print pepper SHA-256
    python tools/anchors.py normalize EMAIL      show canonical form
    python tools/anchors.py check EMAIL [...]    exit 0 = free, 3 = match
    python tools/anchors.py stage EMAIL [...]    stage anchors by hand
    python tools/anchors.py seal [--allow-small] seal staged into a batch
    python tools/anchors.py backfill EMAIL|FILE [...]
                                                 anchor ALREADY-ENROLLED
                                                 humans (never mere drafts)
    python tools/anchors.py verify               re-verify the batch chain
    python tools/anchors.py edge VOUCHER VOUCHEE record a vouch edge
    python tools/anchors.py edge --count RID     voucher's edges, last year

Standard library only, forever.
"""
import hashlib
import hmac as hmac_mod
import json
import os
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

GENESIS_PREV = "0" * 64
_warned_fallback = False


# --- custody ----------------------------------------------------------

def custody_dir(create=False) -> Path:
    global _warned_fallback
    env = os.environ.get("AH_CUSTODY_DIR", "").strip()
    d = Path(env) if env else (ahlib.ROOT / "custody")
    # Warn only when the fallback would actually be USED — it exists or
    # is being created. A bare probe on a public clone stays silent.
    if not env and not _warned_fallback and (create or d.exists()):
        _warned_fallback = True
        print("note : AH_CUSTODY_DIR is not set — using the in-repo gitignored")
        print("       fallback custody/. Real custody belongs OUTSIDE the repo;")
        print("       a drill ledger here would silently stand in for the real one.")
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def pepper_path() -> Path:
    env = os.environ.get("AH_ANCHOR_PEPPER_FILE", "").strip()
    return Path(env) if env else custody_dir() / "pepper-v1.txt"


def load_pepper() -> bytes:
    p = pepper_path()
    if not p.exists():
        raise SystemExit(
            f"anchors: no pepper at {p}\n"
            "Run `python tools/anchors.py init` once (see schema/ANCHORS.md),\n"
            "or point AH_ANCHOR_PEPPER_FILE / AH_CUSTODY_DIR at your custody.")
    hexstr = p.read_text(encoding="utf-8").strip()
    try:
        key = bytes.fromhex(hexstr)
    except ValueError:
        raise SystemExit(f"anchors: pepper file {p} is not hex")
    if len(key) < 32:
        raise SystemExit(f"anchors: pepper in {p} is shorter than 256 bits")
    require_pepper_matches_ledger()
    return key


def pepper_fingerprint() -> str:
    """SHA-256 of the pepper's canonical hex string (stripped, ASCII) —
    NOT of raw file bytes, so a pepper re-typed from the paper vault
    copy fingerprints identically regardless of line endings."""
    p = pepper_path()
    if not p.exists():
        raise SystemExit(f"anchors: no pepper at {p}")
    return hashlib.sha256(
        p.read_text(encoding="utf-8").strip().encode("ascii")).hexdigest()


def require_pepper_matches_ledger():
    """A ledger built under one pepper is meaningless under another:
    checking with the wrong pepper would answer 'free' for everything.
    Every sealed batch records the pepper fingerprint; refuse loudly
    on mismatch instead of failing open."""
    batches = read_batches()
    if not batches:
        return
    recorded = batches[0].get("pepper")
    if recorded and recorded != pepper_fingerprint():
        raise SystemExit(
            "anchors: THE PEPPER DOES NOT MATCH THE LEDGER.\n"
            f"  ledger was sealed under pepper {recorded[:16]}…\n"
            f"  the pepper in service is      {pepper_fingerprint()[:16]}…\n"
            "Every membership answer would be falsely 'free'. Restore the\n"
            "true pepper (schema/ANCHORS.md, published fingerprints) before\n"
            "any enrollment proceeds.")


def staged_path() -> Path:
    return custody_dir() / "anchors" / "staged.jsonl"


def ledger_path() -> Path:
    return custody_dir() / "anchors" / "ledger.jsonl"


def edges_path() -> Path:
    return custody_dir() / "edges" / "vouch-edges.jsonl"


def ops_log_path() -> Path:
    return custody_dir() / "ops-log.jsonl"


def configured() -> bool:
    """True when a pepper exists — the ledger machinery is in service."""
    return pepper_path().exists()


# --- canonical forms and fingerprints (schema/ANCHORS.md) -------------

def normalize_email(email: str) -> str:
    e = unicodedata.normalize("NFC", str(email)).strip().lower()
    local, sep, domain = e.rpartition("@")
    if not sep or not local or not domain or any(c.isspace() for c in e):
        raise ValueError("not a plausible email address")
    if "+" in local:
        local = local[:local.index("+")]
    if domain == "googlemail.com":
        domain = "gmail.com"   # same mailbox namespace — one anchor
    if domain == "gmail.com":
        local = local.replace(".", "")
    if not local:
        raise ValueError("not a plausible email address")
    return f"em1|{local}@{domain}"


def anchor_line(canonical: str, pepper: bytes) -> str:
    typ = canonical.split("|", 1)[0]
    mac = hmac_mod.new(pepper, canonical.encode("utf-8"), hashlib.sha256)
    return f"{typ}:{mac.hexdigest()}"


def email_anchor(email: str, pepper: bytes) -> str:
    return anchor_line(normalize_email(email), pepper)


def valid_rid(rid: str) -> str:
    r = str(rid).strip()
    if not r.isdigit() or len(r) > 9:
        raise SystemExit(f"anchors: {rid!r} is not a registry number")
    return r.zfill(9)


# --- ledger reads ------------------------------------------------------

def _read_jsonl(path: Path) -> list:
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            raise SystemExit(
                f"anchors: {path} line {i + 1} is not valid JSON — the file\n"
                "may hold a partially written line from an interrupted run.\n"
                "Inspect it by hand before any enrollment proceeds.")
    return out


def read_batches() -> list:
    p = ledger_path()
    return _read_jsonl(p) if p.exists() else []


def read_staged() -> list:
    p = staged_path()
    if not p.exists():
        return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def all_anchor_lines() -> set:
    """Membership universe: sealed batches ∪ staged lines."""
    lines = set(read_staged())
    for b in read_batches():
        lines.update(b.get("anchors", []))
    return lines


def membership(anchor_lines) -> list:
    """Return the subset of the given anchor lines already in the ledger."""
    known = all_anchor_lines()
    return [a for a in anchor_lines if a in known]


def check_emails(emails) -> list:
    """Convenience for enroll/review: which of these emails are taken.
    Raises ValueError for an implausible address — callers decide the
    humane wording; never let the raw address reach a rendered page."""
    pepper = load_pepper()
    known = all_anchor_lines()
    return [e for e in emails if e and email_anchor(e, pepper) in known]


def ledger_tip() -> dict | None:
    batches = read_batches()
    if not batches:
        return None
    return {"batches": len(batches), "tip_hash": batches[-1]["hash"]}


# --- ledger writes -----------------------------------------------------

def _write_staged(lines):
    """Rewrite staged.jsonl sorted and unique: insertion order IS
    linkage, so it is destroyed at write time, not just at sealing.
    fsynced before the swap — a staged anchor must survive power loss,
    because the number it guards may already be spent and durable."""
    p = staged_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write("".join(a + "\n" for a in sorted(set(lines))))
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(p)


def stage_anchors(anchor_lines) -> int:
    """Stage anchor lines (skipping ones already known)."""
    load_pepper()  # also validates pepper-ledger binding
    fresh = [a for a in anchor_lines if a not in all_anchor_lines()]
    if fresh:
        _write_staged(read_staged() + fresh)
    return len(fresh)


def seal(allow_small=False) -> dict:
    load_pepper()   # refuses loudly if the pepper does not match the ledger
    batches = read_batches()
    sealed = set()
    for b in batches:
        sealed.update(b.get("anchors", []))
    staged = sorted(set(read_staged()) - sealed)  # idempotent after a crash
    if not staged:
        raise SystemExit("anchors: nothing staged — no batch to seal")
    if len(staged) < 2 and not allow_small:
        raise SystemExit(
            "anchors: refusing to seal a single-anchor batch — it would tie\n"
            "that anchor to one enrollment window. Wait for more, or pass\n"
            "--allow-small for a founding backfill (see schema/ANCHORS.md).")
    batch = {
        "schema": "anchorbatch.v1",
        "seq": len(batches),
        "sealed_at": ahlib.now_utc(),
        "count": len(staged),
        "anchors": staged,
        "pepper": pepper_fingerprint(),
        "prev_hash": batches[-1]["hash"] if batches else GENESIS_PREV,
    }
    batch["hash"] = ahlib.event_hash(batch)
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(batch, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n")
        f.flush()
        os.fsync(f.fileno())
    _write_staged([])   # after the fsync: a crash between the two only
    return batch        # re-reads staged lines seal() now filters out


def record_override(reason: str, context: str):
    p = ops_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"ts": ahlib.now_utc(), "kind": "anchor-override",
                            "reason": reason, "context": context},
                           ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n")


# --- vouch edges --------------------------------------------------------

def record_edge(voucher: str, vouchee: str):
    voucher, vouchee = valid_rid(voucher), valid_rid(vouchee)
    # A vouch edge is permanent: the voucher must actually exist. (The
    # vouchee may be mid-enrollment; its directory was written first.)
    if not (ahlib.REGISTRY / voucher / "entry.json").exists():
        raise SystemExit(
            f"anchors: no enrolled record #{voucher} — a vouch edge from a "
            "nonexistent voucher would stand forever. Check the number.")
    p = edges_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"schema": "vouchedge.v1", "voucher": voucher,
                            "vouchee": vouchee, "ts": ahlib.now_utc()},
                           ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n")


def edge_count(voucher: str, days=365) -> int:
    voucher = valid_rid(voucher)
    p = edges_path()
    if not p.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    n = 0
    for e in _read_jsonl(p):
        if e.get("voucher") != voucher:
            continue
        try:
            ts = datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if ts >= cutoff:
            n += 1
    return n


# --- chain verification --------------------------------------------------

def verify_chain() -> list:
    """Return a list of problems (empty = the batch chain holds)."""
    problems = []
    batches = read_batches()
    fp = pepper_fingerprint() if configured() else None
    peppers = {b.get("pepper") for b in batches if b.get("pepper")}
    if len(peppers) > 1:
        problems.append("ledger batches were sealed under DIFFERENT peppers "
                        f"({len(peppers)} distinct) — the ledger is split and "
                        "membership answers are unreliable")
    for i, b in enumerate(batches):
        where = f"anchor batch seq {b.get('seq', '?')}"
        if b.get("seq") != i:
            problems.append(f"{where}: seq is not contiguous (expected {i})")
        expected_prev = GENESIS_PREV if i == 0 else batches[i - 1]["hash"]
        if b.get("prev_hash") != expected_prev:
            problems.append(f"{where}: prev_hash does not match previous batch")
        if ahlib.event_hash(b) != b.get("hash"):
            problems.append(f"{where}: hash does not recompute — batch altered")
        if b.get("anchors") != sorted(set(b.get("anchors", []))):
            problems.append(f"{where}: anchors are not sorted and unique")
        if b.get("count") != len(b.get("anchors", [])):
            problems.append(f"{where}: count does not match anchors")
        if fp and b.get("pepper") and b["pepper"] != fp:
            problems.append(f"{where}: sealed under a different pepper "
                            f"({b['pepper'][:16]}… vs {fp[:16]}… in service)")
    return problems


def verify_against_checkpoints() -> list:
    """Cross-check checkpoint-recorded anchor tips against this ledger."""
    problems = []
    ledger = ahlib.ROOT / "checkpoints" / "checkpoints.jsonl"
    if not ledger.exists():
        return problems
    batches = read_batches()
    for i, line in enumerate(ledger.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            cp = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"checkpoint {i}: unreadable JSON — cannot "
                            "cross-check its anchor tip")
            continue
        al = cp.get("anchor_ledger")
        if not al:
            continue
        n, tip = al.get("batches"), al.get("tip_hash")
        if not (isinstance(n, int) and n >= 1 and isinstance(tip, str)):
            problems.append(f"checkpoint {i}: malformed anchor_ledger")
            continue
        if n > len(batches):
            problems.append(f"checkpoint {i}: anchor ledger truncated since "
                            f"anchored ({n} batches frozen, {len(batches)} held)")
        elif batches[n - 1].get("hash") != tip:
            problems.append(f"checkpoint {i}: anchor batch {n - 1} does not "
                            f"match its anchored tip — ledger rewritten")
    return problems


# --- CLI -----------------------------------------------------------------

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]

    if cmd == "init":
        import secrets
        p = pepper_path()
        if p.exists():
            print(f"anchors: pepper already exists at {p} — refusing to overwrite")
            return 1
        custody_dir(create=True)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(secrets.token_hex(32) + "\n", encoding="utf-8", newline="\n")
        print(f"pepper v1 created: {p}")
        print(f"pepper fingerprint (SHA-256 of the hex string): {pepper_fingerprint()}")
        print()
        print("Ceremony (schema/ANCHORS.md): print the pepper to paper for the")
        print("vault and the succession papers; record the fingerprint in the")
        print("'Published pepper fingerprints' table of schema/ANCHORS.md and")
        print("commit — the push and the next checkpoint are its witnesses.")
        return 0

    if cmd == "fingerprint":
        print(pepper_fingerprint())
        return 0

    if cmd == "normalize":
        for e in rest:
            try:
                print(normalize_email(e))
            except ValueError:
                print(f"  {e}: not a plausible email address")
                return 2
        return 0

    if cmd == "check":
        if not rest:
            print("anchors check: give one or more email addresses")
            return 2
        try:
            taken = check_emails(rest)
        except ValueError:
            print("anchors check: one of those is not a plausible email "
                  "address — nothing to check")
            return 2
        for e in rest:
            mark = "MATCH — already enrolled" if e in taken else "free"
            print(f"  {e}: {mark}")
        return 3 if taken else 0

    if cmd == "stage":
        pepper = load_pepper()
        try:
            n = stage_anchors([email_anchor(e, pepper) for e in rest])
        except ValueError:
            print("anchors stage: one of those is not a plausible email "
                  "address — nothing was staged")
            return 2
        print(f"staged {n} new anchor(s) "
              f"({len(rest) - n} already known); seal with `anchors.py seal`")
        return 0

    if cmd == "seal":
        b = seal(allow_small="--allow-small" in rest)
        print(f"sealed batch {b['seq']}: {b['count']} anchor(s), "
              f"tip {b['hash'][:16]}…")
        print("next: python tools/checkpoint.py  (the checkpoint witnesses it)")
        return 0

    if cmd == "backfill":
        # Backfill anchors ONLY for humans who are actually ENROLLED.
        # An acceptance record alone is a draft, not a record: anchoring
        # every acceptance would permanently refuse people who once
        # submitted but never enrolled. The founder names the enrolled
        # humans' emails (or their acceptance files) explicitly.
        pepper = load_pepper()
        emails = []
        for a in rest:
            p = Path(a)
            if p.suffix == ".json" and p.exists():
                rec = json.loads(p.read_text(encoding="utf-8"))
                e = rec.get("email") or (rec.get("acceptance") or {}).get("email")
                if not e:
                    print(f"backfill: {a} carries no email — skipped")
                    continue
                emails.append(e)
            else:
                emails.append(a)
        if not emails:
            print("backfill: name the ENROLLED humans' emails (or their")
            print("acceptance .json files) explicitly:")
            print("  python tools/anchors.py backfill a@x.org inbox/acceptances/acc-….json")
            print("Never backfill an acceptance whose human was not enrolled —")
            print("it would refuse their real enrollment later.")
            return 2
        lines = []
        for e in emails:
            try:
                lines.append(email_anchor(e, pepper))
            except ValueError:
                print(f"backfill: not a plausible email address — fix and "
                      "re-run (nothing was staged)")
                return 2
        n = stage_anchors(lines)
        print(f"backfill: staged {n} anchor(s) from {len(emails)} enrolled human(s)")
        # Only the FOUNDING backfill (batch 0) may seal small: later runs
        # follow the normal k-anonymity sealing rules. Sealing looks at
        # what is STAGED, not what this run added, so an interrupted
        # founding backfill can be completed by re-running.
        if not read_batches() and read_staged():
            b = seal(allow_small=True)
            print(f"sealed as founding batch {b['seq']} ({b['count']} anchor(s))")
        elif n:
            print("staged only — seal with the next regular batch "
                  "(single-anchor batches would link anchor to window)")
        return 0

    if cmd == "verify":
        problems = verify_chain() + verify_against_checkpoints()
        for p in problems:
            print(f"ERROR: {p}")
        if problems:
            return 1
        tip = ledger_tip()
        if tip:
            print(f"anchor ledger OK — {tip['batches']} batch(es), "
                  f"tip {tip['tip_hash'][:16]}…, {len(all_anchor_lines())} anchor(s) "
                  f"({len(read_staged())} staged, unsealed)")
        else:
            print(f"anchor ledger OK — no sealed batches yet "
                  f"({len(read_staged())} staged)")
        return 0

    if cmd == "edge":
        if rest and rest[0] == "--count":
            if len(rest) != 2:
                print("anchors edge --count: give one registry number")
                return 2
            print(edge_count(rest[1]))
            return 0
        if len(rest) != 2:
            print("anchors edge: give VOUCHER and VOUCHEE registry numbers")
            return 2
        voucher, vouchee = valid_rid(rest[0]), valid_rid(rest[1])
        record_edge(voucher, vouchee)
        print(f"recorded: #{voucher} vouched for #{vouchee} "
              f"(#{voucher}: {edge_count(voucher)} edge(s) this year)")
        return 0

    print(f"anchors: unknown command {cmd!r}")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
