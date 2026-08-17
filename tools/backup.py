"""Make a dated backup bundle for the shelf, the drive and the vault.

OPERATIONS has asked for "a dated backup bundle in ../backups/<date>/"
after every enrollment batch since the beginning, and nothing ever made
one: they were assembled by hand, so the newest bundle was ten days
older than the first human in the archive. A ceremony that depends on
remembering a sequence of shell commands is a ceremony that stops.

    python tools/backup.py                 # make today's backup
    python tools/backup.py --with-custody  # include the pepper and keys
    python tools/backup.py --check         # is the newest backup current?

WHAT GOES IN, AND WHY IT IS TWO FILES

  <name>-<sha>.bundle          the whole git history, one file
  <name>-worktree-<sha>.tar.gz the working tree INCLUDING registry/

The bundle alone is not enough and this is the trap: registry/ is
gitignored, so the testimonies are NOT in git and NOT in the bundle. A
backup of the repository is a backup of the machinery, not of the
words. The tar carries the words. Keep both or keep neither.

CUSTODY IS SEPARATE ON PURPOSE

The custody directory holds the pepper, the enrollment agreements and
LOCATIONS.md. --with-custody folds it in, and then the backup is as
secret as the pepper: it must go only onto encrypted or offline media,
never a plain USB stick left in a drawer. Without the flag a backup is
still a complete archive of every testimony; it simply cannot recompute
uniqueness anchors until a pepper is restored beside it.

Nothing here is destructive. It never deletes an older generation; the
withdrawal rotation in OPERATIONS is a deliberate human act.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ahlib

ROOT = ahlib.ROOT
BACKUPS = ROOT.parent / "backups"
# Generated views and caches: rebuildable from the tools in seconds, and
# together they are most of the bytes. Excluding them keeps a backup small
# enough that making one is never a reason to put it off.
SKIP = {".git", "site", "info-site", "__pycache__", ".pytest_cache", "node_modules"}


def run(args, **kw):
    return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, **kw)


def head_sha():
    r = run(["git", "rev-parse", "--short", "HEAD"])
    return r.stdout.strip() or "nogit"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_humans():
    try:
        return sum(1 for d in (ROOT / "registry").iterdir()
                   if d.is_dir() and d.name.isdigit())
    except FileNotFoundError:
        return 0


def newest_backup():
    if not BACKUPS.is_dir():
        return None
    dated = sorted((d for d in BACKUPS.iterdir() if d.is_dir()), key=lambda d: d.name)
    return dated[-1] if dated else None


def do_check():
    """Does the newest backup contain every human currently enrolled?
    A backup older than the newest record is the failure this tool
    exists to make visible."""
    humans = count_humans()
    newest = newest_backup()
    if newest is None:
        print(f"NO BACKUP EXISTS, and the archive holds {humans} human(s).")
        return 1
    tars = sorted(newest.glob("*-worktree-*.tar.gz"))
    if not tars:
        print(f"newest backup {newest.name} has no worktree archive — "
              f"it holds the machinery but not the testimonies.")
        return 1
    latest = tars[-1]
    inside = set()
    with tarfile.open(latest, "r:gz") as t:
        for m in t.getnames():
            parts = m.split("/")
            for i, seg in enumerate(parts):
                if seg == "registry" and i + 1 < len(parts) and parts[i + 1].isdigit():
                    inside.add(parts[i + 1])
    missing = sorted({d.name for d in (ROOT / "registry").iterdir()
                      if d.is_dir() and d.name.isdigit()} - inside)
    print(f"newest backup : {newest.name} ({latest.name})")
    print(f"humans in it  : {len(inside)}")
    print(f"humans now    : {humans}")
    if missing:
        print(f"MISSING       : {', '.join('#' + m for m in missing)}")
        print("Run: python tools/backup.py")
        return 1
    print("CURRENT — every enrolled human is in the newest backup.")
    return 0


def main():
    args = sys.argv[1:]
    if "--check" in args:
        return do_check()
    with_custody = "--with-custody" in args

    if ahlib.resolve_mode() == "drill":
        print("REFUSED: this is a drill clone. Backing it up would put "
              "rehearsal records on the shelf beside the real ones.")
        return 2

    if not shutil.which("git"):
        print("REFUSED: git is not on PATH; the history bundle cannot be made.")
        return 2

    sha = head_sha()
    dirty = bool(run(["git", "status", "--porcelain"]).stdout.strip())
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = BACKUPS / day
    out.mkdir(parents=True, exist_ok=True)
    name = ROOT.name
    written = []

    # 1. the whole history, one file, verifiable on its own
    bundle = out / f"{name}-{sha}.bundle"
    r = run(["git", "bundle", "create", str(bundle), "--all"])
    if r.returncode != 0:
        print("git bundle failed:\n" + (r.stderr or ""))
        return 1
    v = run(["git", "bundle", "verify", str(bundle)])
    print(f"bundle   {bundle.name}  ({bundle.stat().st_size:,} bytes)  "
          f"{'verified' if v.returncode == 0 else 'FAILED VERIFY'}")
    if v.returncode != 0:
        print(v.stderr or "")
        return 1
    written.append(bundle)

    # 2. the working tree, which is where the testimonies actually live
    tar_path = out / f"{name}-worktree-{sha}.tar.gz"
    def keep(ti):
        parts = Path(ti.name).parts
        return None if any(p in SKIP for p in parts) else ti
    with tarfile.open(tar_path, "w:gz") as t:
        t.add(str(ROOT), arcname=name, filter=keep)
        if with_custody:
            cust = os.environ.get("AH_CUSTODY_DIR", "").strip()
            if not cust or not Path(cust).is_dir():
                print("REFUSED: --with-custody but AH_CUSTODY_DIR is not set "
                      "or does not exist. Nothing partial goes on the shelf.")
                tar_path.unlink(missing_ok=True)
                bundle.unlink(missing_ok=True)
                return 2
            t.add(cust, arcname="custody", filter=keep)
    print(f"worktree {tar_path.name}  ({tar_path.stat().st_size:,} bytes)"
          + ("  + CUSTODY" if with_custody else ""))
    written.append(tar_path)

    # 3. the checksums, so a drive that rots quietly can be caught
    sums = out / "SHA256SUMS-backup.txt"
    lines = [f"{sha256_file(p)}  {p.name}" for p in sorted(out.glob("*"))
             if p.name != sums.name]
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    humans = count_humans()
    events = len(ahlib.read_log())
    (out / "README.md").write_text(
        f"# Backup {day}\n\n"
        f"Commit `{sha}`{' (WORKING TREE WAS DIRTY)' if dirty else ''}, "
        f"{humans} human(s), {events} log event(s).\n"
        f"Custody {'INCLUDED — treat this backup as secret as the pepper'
                   if with_custody else 'NOT included (pepper and keys are elsewhere)'}.\n\n"
        "## To restore\n\n"
        "1. `git clone <name>.bundle allhumans` — recovers the history and tools.\n"
        "2. Unpack the worktree archive and copy its `registry/` into the clone.\n"
        "   The bundle does NOT contain the testimonies: `registry/` is\n"
        "   gitignored, so the words live only in the worktree archive.\n"
        "3. Restore the custody directory beside it and set `AH_CUSTODY_DIR`.\n"
        "4. `python tools/verify.py` must print OK and count the enrollments.\n"
        "5. Rebuild and deploy (OPERATIONS section 1).\n\n"
        "## To check this backup has not rotted\n\n"
        "`sha256sum -c SHA256SUMS-backup.txt` in this folder.\n",
        encoding="utf-8", newline="\n")

    print(f"\n{out}")
    print(f"{humans} human(s), {events} log event(s), checksums written.")
    if dirty:
        print("NOTE: the working tree had uncommitted changes; the tar holds "
              "them, the bundle does not.")
    print("\nCopy this whole folder to: the offline drive, the encrypted cloud "
          "copy, and any other custody named in LOCATIONS.md.")
    if not with_custody:
        print("The pepper and keys are NOT in it. That is the default, and it "
              "means this folder is safe on ordinary media.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
