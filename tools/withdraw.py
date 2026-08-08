"""Withdraw one testimony version. The words go; the tombstone stays.

Usage:
    python tools/withdraw.py <registry_id> <version 1|2|3> --key ah1-....
    python tools/withdraw.py <registry_id> <version 1|2|3> --founder-override "reason"

Withdrawal belongs to the human: it requires their continuity key.
--founder-override exists for the human who has lost their key but
proven their identity out of band; the reason is recorded in the
log event, permanently.

Replaces the version's answers with nothing, sets status: withdrawn,
keeps entered_at and the original content_hash (proof of what was
once said, without saying it), and appends VERSION_WITHDRAWN to the
log. The slot stays spent. After running: verify, rebuild the site,
commit, and propagate to every external deposit (their agreements
carry these tombstone semantics).

Built and tested from day one, because retrofitting erasure into a
permanence system is the one rewrite this architecture must never
need.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib


def main():
    ahlib.announce_ceremony("withdraw")
    args = sys.argv[1:]
    key = override = None
    if "--key" in args:
        i = args.index("--key")
        key = args[i + 1]
        del args[i:i + 2]
    if "--founder-override" in args:
        i = args.index("--founder-override")
        override = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2 or args[1] not in ("1", "2", "3"):
        print(__doc__)
        sys.exit(2)
    rid, n = args[0].zfill(9), args[1]
    vpath = ahlib.REGISTRY / rid / "versions" / f"{n}.json"
    if not vpath.exists():
        print(f"no such version: registry/{rid}/versions/{n}.json")
        sys.exit(1)

    entry = json.loads((ahlib.REGISTRY / rid / "entry.json").read_text(encoding="utf-8"))
    cont = entry.get("continuity")
    if cont:
        if key is not None:
            if ahlib.continuity_key_hash(key) != cont["key_hash"]:
                print("REFUSED: continuity key does not match this record")
                sys.exit(1)
        elif not override:
            print("REFUSED: withdrawal belongs to the human — provide --key, or "
                  "--founder-override \"reason\" after out-of-band identity proof")
            sys.exit(1)

    v = json.loads(vpath.read_text(encoding="utf-8"))
    if v["status"] == "withdrawn":
        print("already withdrawn; nothing to do")
        sys.exit(0)

    v.pop("answers", None)
    v["status"] = "withdrawn"
    v["withdrawn_at"] = ahlib.now_utc()
    vpath.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8", newline="\n")
    data = {"version": int(n), "content_hash": v["content_hash"]}
    if cont and key is not None:
        data["continuity_proven"] = True
    if override:
        data["founder_override"] = override
    ahlib.append_event("VERSION_WITHDRAWN", data, registry_id=rid)
    print(f"withdrawn: registry #{rid} version {n}. The slot stays spent.")
    print("next: verify, rebuild site, commit, propagate to deposits.")


if __name__ == "__main__":
    main()
