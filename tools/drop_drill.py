"""Destroy the drill: delete the clone and its Pages deployment.

The drill exists only during the minutes it is in use. This removes
../drill-scratch/ and deletes the allhumans-drill Pages project (which
takes its deployments and URL with it). The drill KV namespace is
deliberately KEPT - it holds nothing real and re-creating bindings is
churn. Idempotent: a missing clone or project is reported, not an
error.

Windows honesty: a folder cannot be deleted while any process stands
inside it (a shell, an editor, a file pane). Deletion is retried, and
if the folder still will not go, this script says exactly that instead
of a traceback. Both halves (folder, Pages project) are always
attempted, so a stuck folder never leaves the drill URL alive.

This script refuses to run inside a drill clone (it cannot delete the
tree a process stands in, and the drill must never manage itself).
Run it from the REAL repository.

Standard library only.
"""
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

# The ONLY project this script may ever delete. Never the production
# project - asserted twice, belt and braces.
DRILL_PROJECT = "allhumans-drill"
INFO_DRILL_PROJECT = "allhumans-info-drill"
PROD_PROJECT = "allhumans"
PROD_INFO_PROJECT = "allhumans-info"
SCRATCH = ahlib.ROOT.parent / "drill-scratch"


def _force_rm(func, path, _exc):
    # git object files are read-only on Windows; make them deletable.
    Path(path).chmod(stat.S_IWRITE)
    func(path)


def _remove_clone():
    """Returns True when the clone is gone."""
    if not SCRATCH.exists():
        print(f"[drop_drill] no clone at {SCRATCH} - nothing to delete")
        return True
    has_marker = (SCRATCH / "DRILL_CLONE").exists()
    has_files = any(p.is_file() for p in SCRATCH.rglob("*"))
    if has_files and not has_marker:
        raise SystemExit(
            f"drop_drill REFUSED: {SCRATCH} holds files but carries no "
            "DRILL_CLONE marker - it may not be a drill. Look at it "
            "yourself before deleting anything.")
    for attempt in range(4):
        try:
            shutil.rmtree(SCRATCH, onerror=_force_rm)
            print(f"[drop_drill] deleted {SCRATCH}")
            return True
        except PermissionError:
            time.sleep(1.5)
    print(f"[drop_drill] COULD NOT DELETE {SCRATCH}: some process is "
          "standing inside it (a shell, an editor, a file pane). Leave "
          "the folder and run drop_drill again.")
    return False


def main():
    assert DRILL_PROJECT != PROD_PROJECT
    if DRILL_PROJECT == PROD_PROJECT or DRILL_PROJECT != "allhumans-drill":
        raise SystemExit("drop_drill REFUSED: project constant tampered.")
    if ahlib.DRILL_MARKER.exists():
        raise SystemExit(
            "drop_drill REFUSED: run this from the REAL repository, not "
            "from inside the drill clone it is about to delete.")

    clone_gone = _remove_clone()

    npx = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"
    for project in (DRILL_PROJECT, INFO_DRILL_PROJECT):
        if project in (PROD_PROJECT, PROD_INFO_PROJECT):
            raise SystemExit("drop_drill REFUSED: would delete production.")
        r = subprocess.run([npx, "wrangler", "pages", "project", "delete",
                            project, "--yes"],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0:
            print(f"[drop_drill] Pages project {project!r} deleted - "
                  "its URL stops serving")
        elif "not found" in out.lower() or "does not exist" in out.lower():
            print(f"[drop_drill] Pages project {project!r} already "
                  "absent - nothing to delete")
        else:
            raise SystemExit("drop_drill: project deletion failed:\n" + out)

    if not clone_gone:
        raise SystemExit(
            "drop_drill: the Pages project is gone but the folder "
            "remains (see above). Step every shell out of it and re-run.")
    print("[drop_drill] the drill is gone. The drill KV namespace is "
          "kept, as designed.")


if __name__ == "__main__":
    main()
