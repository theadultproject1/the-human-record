"""Pull submissions from the website into the review desk.

Usage:
    python tools/fetch_inbox.py            # fetch, keep remote copies
    python tools/fetch_inbox.py --purge    # fetch, then delete fetched keys
    python tools/fetch_inbox.py --archive-acceptances
                                           # move inbox/acceptances/ into
                                           # custody (the retained agreements)

Run --purge with every fetch: plaintext email should live in KV only
briefly. After submissions are resolved, --archive-acceptances moves
the acceptance records into AH_CUSTODY_DIR/agreements/ — the one
linkage the institution keeps (POLICY.md, Uniqueness), on encrypted
media, in the same custody class as the archive.

Reads the Cloudflare KV namespace the site's worker writes to and
lands each record locally, then leaves review to the humans:

    inbox/sub-<timestamp>.json          testimony submissions -> tools/review.py
    inbox/acceptances/acc-<ts>.json     acceptance records (the agreements)

Requires two environment variables (create an API token with
"Workers KV Storage: Edit" at dash.cloudflare.com -> My Profile ->
API Tokens):

    CF_ACCOUNT_ID        Cloudflare account id
    CF_API_TOKEN         the API token

**Which mailbox this reads is decided by the tree you are standing in,
not by your shell.** The namespace comes from this repository's own
`wrangler.toml` — the same file the site deploys with — so the real
repository reads the real mailbox and a drill clone reads the drill's,
automatically. `make_drill.py` rewrites that binding when it builds a
clone, so the two can never be crossed.

This matters more than it looks. Before 2026-08-01 the namespace came
from CF_KV_NAMESPACE_ID, which meant a drill session inherited whatever
the shell happened to hold: a rehearsal politely read the PRODUCTION
mailbox and would have pulled real testimony down into a disposable
folder that gets deleted without ceremony. A drill must never be able
to touch real words. CF_KV_NAMESPACE_ID is still honoured as a fallback
when wrangler.toml cannot be read, but never in a drill clone.

Standard library only. Nothing here touches the archive: inbox/ is
operational scratch space (gitignored), and numbers are spent only
by tools/enroll.py.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
ACCEPT = INBOX / "acceptances"
WITHDRAW = INBOX / "withdrawals"
LEGACY = INBOX / "legacy"

API = "https://api.cloudflare.com/client/v4"


def submissions_namespace():
    """The KV namespace THIS tree's worker writes to.

    Read from this repository's own wrangler.toml, so the mailbox is
    decided by the tree you are standing in rather than by whatever the
    shell inherited. A drill clone carries the drill's binding (written
    by make_drill.py) and therefore cannot reach production's words.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ahlib
    mode = ahlib.resolve_mode()          # fails closed on any mismatch
    toml = ROOT / "wrangler.toml"
    ns = None
    if toml.exists():
        # The binding block, in file order: id belongs to SUBMISSIONS.
        block = re.search(r'binding\s*=\s*"SUBMISSIONS".*?id\s*=\s*"([0-9a-f]{32})"'
                          r'|id\s*=\s*"([0-9a-f]{32})".*?binding\s*=\s*"SUBMISSIONS"',
                          toml.read_text(encoding="utf-8"), re.S)
        if block:
            ns = block.group(1) or block.group(2)
    if ns:
        loose = os.environ.get("CF_KV_NAMESPACE_ID", "").strip()
        if loose and loose != ns:
            print(f"note : CF_KV_NAMESPACE_ID is set to a different namespace and is")
            print(f"       being ignored. wrangler.toml decides, so the {mode} tree")
            print(f"       reads the {mode} mailbox and nothing crosses over.")
        return ns
    # No binding readable. In production the environment may still stand
    # in; in a drill it may not, because the shell's value is the very
    # thing that could point at real testimony.
    if mode == "drill":
        print("REFUSED: this is a drill clone and its wrangler.toml carries no")
        print("SUBMISSIONS binding, so the mailbox cannot be proven to be the")
        print("drill's. A rehearsal must never read real testimony. Rebuild the")
        print("drill with tools/make_drill.py.")
        sys.exit(2)
    return env("CF_KV_NAMESPACE_ID")


def env(name):
    v = os.environ.get(name, "").strip()
    if not v:
        print(f"missing environment variable: {name}  (see this file's docstring)")
        sys.exit(2)
    return v


def call(token, url, method="GET"):
    req = urllib.request.Request(url, method=method,
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8")


def archive_acceptances():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import anchors
    dest = anchors.custody_dir(create=True) / "agreements"
    dest.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in sorted(ACCEPT.glob("*.json")) if ACCEPT.exists() else []:
        target = dest / f.name
        if target.exists():
            print(f"  skip {f.name}: already archived")
            continue
        target.write_bytes(f.read_bytes())
        f.unlink()
        moved += 1
    print(f"archived {moved} acceptance record(s) -> {dest}")
    print("(the retained agreements: keep this store on encrypted media,")
    print(" custody class of the archive itself — POLICY.md, Uniqueness)")


def main():
    if "--archive-acceptances" in sys.argv:
        archive_acceptances()
        return
    purge = "--purge" in sys.argv
    acct, ns, token = env("CF_ACCOUNT_ID"), submissions_namespace(), env("CF_API_TOKEN")
    base = f"{API}/accounts/{acct}/storage/kv/namespaces/{ns}"

    keys, cursor = [], ""
    while True:
        url = f"{base}/keys?limit=1000"
        if cursor:
            url += "&cursor=" + urllib.parse.quote(cursor)
        page = json.loads(call(token, url))
        keys += [k["name"] for k in page.get("result", [])]
        cursor = (page.get("result_info") or {}).get("cursor") or ""
        if not cursor:
            break

    INBOX.mkdir(exist_ok=True)
    ACCEPT.mkdir(exist_ok=True)
    fetched = 0
    returns = []
    withdrawals = []
    legacies = []
    vouched = []
    for key in sorted(keys):
        kind = ("sub" if key.startswith("sub:") else
                "acc" if key.startswith("accept:") else
                "ret" if key.startswith("ret:") else
                "withdraw" if key.startswith("withdraw:") else
                "legacy" if key.startswith("legacy:") else None)
        if not kind:
            continue
        safe = re.sub(r"[^A-Za-z0-9_.-]", "-", key)
        if kind == "acc":
            dest = ACCEPT / f"{safe}.json"
        elif kind == "withdraw":
            WITHDRAW.mkdir(exist_ok=True)
            dest = WITHDRAW / f"{safe}.json"
        elif kind == "legacy":
            LEGACY.mkdir(exist_ok=True)
            dest = LEGACY / f"{safe}.json"
        else:
            dest = INBOX / f"{safe}.json"
        if dest.exists():
            continue
        raw = call(token, f"{base}/values/{urllib.parse.quote(key, safe='')}")
        record = json.loads(raw)  # refuse to land anything that isn't JSON
        if kind in ("sub", "ret"):
            # review.py expects a bare sitting; keep the envelope beside it.
            # For returns the envelope holds the continuity key: verify with
            # testify.py, then DELETE the envelope — the key is never kept.
            sitting = record.get("sitting", record)
            dest.write_text(json.dumps(sitting, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
            (INBOX / f"{safe}.envelope.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8", newline="\n")
            if kind == "ret":
                returns.append((record.get("registry_id", "?"), safe))
            elif record.get("vouched_by"):
                vouched.append((str(record.get("vouched_by")), safe))
        elif kind == "withdraw":
            # An authenticated withdrawal request. The record carries the
            # continuity key (already verified at the edge) so the steward
            # can complete it with tools/withdraw.py, then DELETE the file —
            # the key is never kept.
            dest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
            withdrawals.append((record.get("registry_id", "?"),
                                record.get("version", "?"), safe))
        elif kind == "legacy":
            # A death report carrying a Legacy Key. The worker checked only
            # the FORMAT — the words are verified at the desk (unseal.py),
            # after the mourning ceremony. Delete the file when the
            # ceremony is done — the words are never kept.
            dest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
            legacies.append((record.get("registry_id", "?"), safe))
        else:
            dest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
        fetched += 1
        if purge:
            call(token, f"{base}/values/{urllib.parse.quote(key, safe='')}", method="DELETE")

    for rid, safe in returns:
        print(f"RETURN for registry #{rid}: after review, enter it with")
        print(f"  python tools/testify.py {rid} inbox/{safe}.json --key <key from inbox/{safe}.envelope.json>")
        print(f"  then delete inbox/{safe}.envelope.json — the key is never kept.")

    for rid, ver, safe in withdrawals:
        print(f"WITHDRAWAL for registry #{rid}, version {ver}: the key was verified "
              f"at submission. After confirming, complete it with")
        print(f"  python tools/withdraw.py {rid} {ver} --key <key from inbox/withdrawals/{safe}.json>")
        print(f"  then delete inbox/withdrawals/{safe}.json — the key is never kept.")

    for rid, safe in legacies:
        print(f"LEGACY KEY brought for registry #{rid} — a death report.")
        print("  The mourning ceremony comes FIRST (POLICY.md, The seal):")
        print("  write to the record's enrollment email, and wait thirty days —")
        print("  a living author may simply answer. Then, and only then:")
        print(f"  python tools/unseal.py {rid} --words \"<six words from inbox/legacy/{safe}.json>\"")
        print(f"  then delete inbox/legacy/{safe}.json — the words are never kept.")

    for by, safe in vouched:
        shown = by if by.isdigit() else "(malformed - inspect the envelope)"
        print(f"VOUCHED submission (inbox/{safe}.json): the worker verified a")
        print(f"  single-use invitation minted by #{shown}. review.py shows the")
        print(f"  voucher's quota; confirm, then enroll with --vouched-by {shown}")
        print("  to record the edge.")

    kept = "purged from KV" if purge else "left in KV (run with --purge to delete)"
    print(f"fetched {fetched} new record(s) -> inbox/ ; remote copies {kept}")
    print("next: python tools/review.py")


if __name__ == "__main__":
    main()
