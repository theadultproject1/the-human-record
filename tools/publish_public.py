"""Build the public transparency instrument from this repository.

Usage:
    python tools/publish_public.py
        say what would be published and what would be withheld. Writes
        nothing.

    python tools/publish_public.py --write ../public-record
        materialise it into that folder. Still pushes nothing anywhere.

ARCHITECTURE.md ratified what the public repository is: "code,
Constitution, schemas, the event log, and the verification tools —
nothing else." This tool is that sentence, executable.

WHY A SEPARATE REPOSITORY AND NOT JUST FLIPPING THIS ONE PUBLIC
Git history can never be un-published. This repository has carried
OPERATIONS.md and SECURITY.md since it began — the runbook, the
infrastructure map, the audit naming what is still open. Making this
repository public would publish every past version of those files, and
deleting them first would not help, because history remembers. So the
public instrument is a separate repository, built from this one.

WHY GENERATED AND NOT A FORK
Two hand-kept copies drift, and a drifted public copy is worse than
none: a reader would verify a mirror while believing they had verified
the real thing. So this is a generated view, exactly as `site/` is —
never edited by hand, rebuilt from the source of truth.

WHY AN ALLOW-LIST AND NEVER A DENY-LIST
Everything published is named below. Anything not named is withheld,
including files that do not exist yet. A deny-list fails the wrong way:
add a private note tomorrow and it publishes itself. This way a new
file is private until someone deliberately adds it here.

WHY IT NEVER PUSHES
It writes a folder. Committing and pushing stay human acts, because
publishing cannot be undone and should never be something a script did
while nobody was reading.

Standard library only.
"""
import re
import shutil
import sys
import urllib.request
from pathlib import Path

# Where the published copy lives, so drift can be checked against the
# real thing rather than against a local folder that might itself be
# stale.
PUBLIC_RAW = ("https://raw.githubusercontent.com/theadultproject1/"
              "the-human-record/main/log/registry.log.jsonl")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

ROOT = ahlib.ROOT

# ---------------------------------------------------------------- published
# The founding and governed documents. These are the institution's
# promises; a reader must be able to hold them and check their hashes.
DOCS = ["CONSTITUTION.md", "MISSION.md", "POLICY.md", "PRIVACY.md",
        "ARCHITECTURE.md", "LICENSING.md", "NAMING.md", "SHA256SUMS.txt"]

# Git's own rules travel with the repository, and one of them is
# load-bearing: `* -text` in .gitattributes stops git rewriting line
# endings. Without it a clone on Windows checks out different bytes and
# verify.py correctly reports every anchored document as altered. The
# .gitignore is published as evidence too — it is where a reader sees
# that testimony is excluded by design, not by accident.
DOTFILES = [".gitattributes", ".gitignore"]

# The record itself, and the proof it was not written after the fact.
RECORD = ["log/registry.log.jsonl",
          "questions/v1.md", "questions/v1.json",
          "registry/README.md"]

TREES = ["schema", "checkpoints"]      # schemas; checkpoints incl. .ots receipts

# Every tool, including the site generator. The founder's ruling of
# 2026-08-01: LICENSING.md already says the code is Apache-2.0 and that
# "anyone may recreate the interface from the open code", so withholding
# the generator would have broken a promise already made. It costs
# nothing to keep: the gate's difficulty and time floor are already
# returned by /api/ceremony to anyone who asks, and the honeypot field
# is in the HTML every visitor downloads. Nothing here is safe because
# it is unread — it is safe because the ceremony secret, the pepper and
# 128-bit keys are elsewhere, and because a human reads every submission
# before a number is spent.
TREES_CODE = ["tools"]

# Written for a stranger, and kept in public/ so they cannot be confused
# with the steward's own README and SECURITY.md, which stay private. The
# same file cannot serve both readers honestly: this repository's README
# points a steward at the runbook and the founder's papers, and every one
# of those links would be broken — or worse, a signpost to something
# withheld — in a public clone. So there are two documents, and the
# generator renames these on the way out.
RENAMED = {"public/README.md": "README.md",
           "public/SECURITY.md": "SECURITY.md"}

# ---------------------------------------------------------------- withheld
# Each entry: (path, why). The reason is printed on every run, because a
# withholding nobody sees is indistinguishable from a thing forgotten.
WITHHELD = [
    ("OPERATIONS.md",
     "the runbook: account identifiers, the break-glass plan, the traps. "
     "Not needed to verify anything; useful only to someone attacking."),
    ("SECURITY.md",
     "the audit, including what is still open. Publishing your own "
     "to-do list of weaknesses hands it to the wrong reader."),
    ("founder/",
     "steward-private by design (README): the founder's reasons and the "
     "legal playbook."),
    ("wrangler.toml",
     "deployment config for the operator's own Cloudflare account. "
     "Proves nothing; anyone recreating the interface writes their own."),
    (".github/workflows/",
     "the anchoring workflow would RUN in the public repository and "
     "commit receipts back, so the two copies would diverge. The "
     "receipts it produces ARE published, in checkpoints/ — and the "
     "receipt is the proof, not the script that fetched it."),
    ("site-assets/",
     "the film: brand work under different licence terms, twenty-three "
     "megabytes of video in a repository people clone to check text."),
    ("inbox/, site/, info-site/, registry/*",
     "never in git to begin with: pending submissions, generated views, "
     "and the testimonies themselves (the distribution ruling)."),
]

# ------------------------------------------------------------------- checks
# A last look before anything is written. These are the shapes that
# should never appear in a public file. Hashes are everywhere here and
# are meant to be, so this looks for secrets and for this machine, not
# for high entropy.
FORBIDDEN = [
    # A real key carries both a capital and a digit; a Python name like
    # `re_pepper_matches_ledger` carries neither. Demanding both is the
    # difference between a check that is trusted and one that is muted:
    # this fired on that identifier first, and a check people switch off
    # protects nothing.
    (re.compile(r"re_(?=[A-Za-z0-9_]*[A-Z])(?=[A-Za-z0-9_]*[0-9])[A-Za-z0-9_]{20,}"),
     "what looks like a Resend API key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a private key block"),
    (re.compile(r"[A-Za-z]:\\\\Users\\\\[A-Za-z0-9_.-]+"), "a path on someone's machine"),
    (re.compile(r"AH_SMTP_PASS\s*=\s*\S+"), "a mail password"),
]


def _pepper_pattern():
    """If the pepper is readable, make sure it never leaves. It is the one
    secret whose loss cannot be repaired and whose leak cannot be undone."""
    try:
        import anchors
        p = anchors.custody_dir(create=False) / "pepper-v1.txt"
        if p.exists():
            raw = p.read_text(encoding="utf-8").strip()
            if len(raw) >= 16:
                return re.compile(re.escape(raw)), "THE PEPPER ITSELF"
    except Exception:
        pass
    return None, None


def gather():
    """Every file to publish, as (source, name-it-gets-in-public) pairs."""
    out = []
    for name in DOCS + DOTFILES + RECORD:
        if (ROOT / name).exists():
            out.append((name, name))
    for tree in TREES + TREES_CODE:
        base = ROOT / tree
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                rel = p.relative_to(ROOT).as_posix()
                out.append((rel, rel))
    for src, dst in RENAMED.items():
        if (ROOT / src).exists():
            out.append((src, dst))
    return out


def scan(paths):
    """Return a list of (path, what) for anything that must not be published."""
    checks = list(FORBIDDEN)
    pep, why = _pepper_pattern()
    if pep:
        checks.append((pep, why))
    hits = []
    for src, _dst in paths:
        p = ROOT / src
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue                       # binary: nothing textual to leak
        for rx, what in checks:
            if rx.search(text):
                hits.append((src, what))
    return hits


def check_drift():
    """Is the published copy still telling the truth?

    Silence is the danger here. If a publish is forgotten, the website
    keeps saying anyone may verify while the public log falls behind —
    and nothing anywhere complains. So this compares the live public log
    against this one and says plainly which it is.
    """
    local = (ROOT / "log" / "registry.log.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    try:
        with urllib.request.urlopen(PUBLIC_RAW, timeout=30) as r:
            remote = r.read().decode("utf-8").strip().splitlines()
    except Exception as exc:                       # noqa: BLE001
        print(f"could not read the public log ({exc.__class__.__name__}). "
              "No network, or the repository moved.")
        return 1
    if local == remote:
        print(f"public copy is CURRENT — {len(local)} log line(s), identical.")
        return 0
    behind = len(local) - len(remote)
    if behind > 0:
        print(f"public copy is BEHIND by {behind} log line(s). "
              "Publish: python tools/publish_public.py --write ../public-record")
    else:
        print("public log DIFFERS from this one and is not simply behind. "
              "Something rewrote history on one side; investigate before "
              "publishing anything over it.")
    return 1


def main():
    args = sys.argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    if "--check" in args:
        return check_drift()
    if ahlib.resolve_mode() == "drill":
        print("REFUSED: a drill must never publish. Run this from the real "
              "repository.")
        return 2

    dest = None
    for i, a in enumerate(args):
        if a == "--write" and i + 1 < len(args):
            dest = Path(args[i + 1]).expanduser().resolve()

    paths = gather()
    print(f"WOULD PUBLISH {len(paths)} file(s) from {ROOT}:")
    shown = {}
    for _src, dst in paths:
        top = dst.split("/")[0] if "/" in dst else "(root)"
        shown.setdefault(top, []).append(dst)
    for top in sorted(shown):
        print(f"  {top:14} {len(shown[top]):3} file(s)")

    print("\nWITHHELD, and why:")
    for what, why in WITHHELD:
        print(f"  {what}")
        for line in (why[i:i + 62] for i in range(0, len(why), 62)):
            print(f"      {line}")

    print("\nCHECKING what would be published…")
    hits = scan(paths)
    if hits:
        print("  STOPPED. These must not be published:")
        for rel, what in hits:
            print(f"    {rel}: {what}")
        print("  Nothing was written.")
        return 1
    print("  clean: no keys, no private paths, no pepper.")

    if dest is None:
        print("\nDry run. Nothing written. Add --write <folder> to build it.")
        return 0

    # Willing to overwrite an empty folder, the public clone, or its own
    # previous output — and nothing else. Without the stamp this refused
    # to preview twice into the same folder, which teaches people to
    # reach for --force; a guard that is inconvenient gets disabled, and
    # a disabled guard is how a publish lands on top of someone's work.
    STAMP = ".built-by-publish_public"
    if (dest.exists() and any(dest.iterdir())
            and not (dest / ".git").exists()
            and not (dest / STAMP).exists()):
        print(f"\nREFUSED: {dest} is not empty, is not a git repository, and "
              "was not built by this tool. Point it at a fresh folder or at "
              "the public clone.")
        return 2

    written = 0
    for src, dst in paths:
        target = dest / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / src, target)
        written += 1
    (dest / STAMP).write_text(
        "Built by tools/publish_public.py from the operator's repository.\n"
        "Every file here is generated; edit the source, not this copy.\n",
        encoding="utf-8")
    print(f"\nwrote {written} file(s) -> {dest}")
    print("Read it, then commit and push it yourself. This tool never will:")
    print("publishing cannot be undone, so it stays a human act.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
