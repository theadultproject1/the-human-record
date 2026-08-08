"""The unsealing ceremony: a Legacy Key opens a record's sealed words.

Usage:
    python tools/unseal.py RID --words "ember harvest quiet door lantern sparrow"
    python tools/unseal.py RID --words "..." --confirm     complete the ceremony

Someone the author trusted has brought their six words and attested the
author's death (the report arrives via fetch_inbox.py into inbox/legacy/).
This tool verifies the words against the record's stretched fingerprint
(salted with the record's continuity key_hash) and — only with --confirm,
only after the mourning ceremony has run — completes the unsealing:

    the record's status becomes "memorialized" (a completed life),
    a MEMORIALIZED event is appended to the log,
    and the next site build shows every sealed answer, open.

THE MOURNING PROTOCOL COMES FIRST (POLICY.md, The seal): write to the
record's enrollment email and wait thirty days. A living author may
simply answer "I am alive" — and nothing happens. This tool asks you to
attest that the protocol ran before it will complete anything.

Without a Legacy Key, seals still open by time alone: one hundred years
after enrollment, the site shows them without any ceremony — that door
needs no operator, no tool, and no machinery to survive.

Some are opened by those we trust. The rest are opened by time itself.
Standard library only, forever.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib


def flag(args, name):
    if name in args:
        i = args.index(name)
        if i + 1 >= len(args):
            print(f"{name} needs a value")
            sys.exit(2)
        value = args[i + 1]
        del args[i:i + 2]
        return value
    return None


def main():
    ahlib.announce_ceremony("unseal")
    args = sys.argv[1:]
    words = flag(args, "--words")
    confirm = "--confirm" in args
    if confirm:
        args.remove("--confirm")
    if len(args) != 1 or not words:
        print(__doc__)
        sys.exit(2)

    rid = str(args[0]).strip().lstrip("#")
    if not rid.isdigit() or len(rid) > 9:
        print(f"REFUSED: {args[0]!r} is not a registry number")
        sys.exit(1)
    rid = rid.zfill(9)

    entry_path = ahlib.REGISTRY / rid / "entry.json"
    if not entry_path.exists():
        print(f"REFUSED: no record #{rid} in the registry")
        sys.exit(1)
    entry = json.loads(entry_path.read_text(encoding="utf-8"))

    if entry.get("status") == "memorialized":
        print(f"Record #{rid} is already memorialized — its seals are open.")
        sys.exit(0)
    lg = entry.get("legacy")
    if not lg:
        print(f"REFUSED: record #{rid} holds no Legacy Key fingerprint.")
        print("Its seals open by time alone, one hundred years after")
        print("enrollment — no key, and no ceremony, can open them sooner.")
        sys.exit(1)

    # canonical form: lowercase, single spaces — exactly as minted
    canon = " ".join(words.strip().lower().split())
    if len(canon.split()) != lg.get("words", 6):
        print(f"REFUSED: a Legacy Key is exactly {lg.get('words', 6)} words.")
        sys.exit(1)
    salt = entry["continuity"]["key_hash"].encode("ascii")
    fp = hashlib.pbkdf2_hmac("sha256", canon.encode("utf-8"), salt,
                             lg["iterations"]).hex()
    if fp != lg["fingerprint"]:
        print("REFUSED: these words do not open this record.")
        print("Check them letter by letter — they must be exactly as given.")
        sys.exit(3)

    print(f"The key opens record #{rid}.")
    if not confirm:
        print()
        print("The mourning ceremony (POLICY.md, The seal) must run first:")
        print("  1. a note was sent to the record's enrollment email;")
        print("  2. thirty days have passed;")
        print("  3. no one answered 'I am alive.'")
        print()
        print("When all three are true, run again with --confirm.")
        sys.exit(0)

    ts = ahlib.now_utc()
    entry["status"] = "memorialized"
    entry["memorialized_at"] = ts
    entry_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")
    ahlib.append_event("MEMORIALIZED",
                       {"via": "legacy-key", "attested": True,
                        "mourning_ceremony": "completed"},
                       registry_id=rid)
    print(f"memorialized: record #{rid} is a completed life.")
    print("Its sealed words open on the next build of the site.")
    print("Delete the report file in inbox/legacy/ — the words are never kept.")
    print()
    print("next: python tools/verify.py && python tools/build_site.py")
    print("      && python tools/checkpoint.py && git add -A && git commit")


if __name__ == "__main__":
    main()
