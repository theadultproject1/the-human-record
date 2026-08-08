"""Create a disposable rehearsal ground (the drill), on demand.

The drill is a CLONE, not a fork: it is built fresh from the current
repository every time, so it can never drift, and it is destroyed with
tools/drop_drill.py when the rehearsal ends. Physical isolation without
permanence:

  - cloned to ../drill-scratch/, OUTSIDE this repository
  - `origin` is removed immediately: a push from a drill is impossible,
    not merely discouraged
  - registry/ is gitignored, so the clone starts with ZERO records and
    can never contain real testimony
  - a DRILL_CLONE marker is stamped at the clone root; every ceremony
    resolves AH_MODE against that marker and refuses any disagreement
  - drill builds stamp every page with a rehearsal banner, robots
    noindex, and a robots.txt disallow
  - deploys go to the DRILL Pages project bound to the DRILL KV
    namespace; this script refuses to proceed if it ever sees the
    production project, the production namespace, or a populated
    registry as its source

Usage:  python tools/make_drill.py          (run from the REAL repo)
Then:   cd ../drill-scratch, set AH_MODE=drill, and rehearse.
Seed a synthetic cast with tools/seed_drill.py. Destroy the drill with
tools/drop_drill.py.

Standard library only.
"""
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

PROD_PROJECT = "allhumans"
DRILL_PROJECT = "allhumans-drill"
INFO_DRILL_PROJECT = "allhumans-info-drill"
PROD_KV = "6125ec9a11ff424db9d0d86464319281"
DRILL_KV = "cdb61c4723ce4a499d4ea10760b74fab"
SCRATCH = ahlib.ROOT.parent / "drill-scratch"

MARKER_TEXT = """This tree is a DRILL CLONE - a disposable rehearsal ground.
Nothing here is kept. It was created by tools/make_drill.py and is
destroyed by tools/drop_drill.py. Ceremonies here require AH_MODE=drill;
the real archive refuses that mode, and this clone refuses production.
"""


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def die(msg):
    raise SystemExit("make_drill REFUSED: " + msg)


def main():
    if ahlib.DRILL_MARKER.exists():
        die(f"{ahlib.ROOT} is itself a drill clone. Run make_drill.py "
            "from the REAL repository only.")
    if SCRATCH.exists():
        die(f"{SCRATCH} already exists. A drill is disposable: destroy "
            "the old one first (python tools/drop_drill.py).")

    npx = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"
    if not Path(npx).exists():
        die("npx (Node.js) not found - needed to deploy the drill.")

    print(f"[make_drill] source:  {ahlib.ROOT}")
    print(f"[make_drill] scratch: {SCRATCH}")

    rc, out = run(["git", "clone", str(ahlib.ROOT), str(SCRATCH)])
    if rc != 0:
        die("git clone failed:\n" + out)
    rc, head = run(["git", "-C", str(SCRATCH), "log", "--oneline", "-1"])
    print(f"[make_drill] cloned COMMITTED state: {head.strip()}")
    rc, dirty = run(["git", "-C", str(ahlib.ROOT), "status", "--porcelain"])
    if dirty.strip():
        print("[make_drill] NOTE: the real repo has uncommitted changes - "
              "they are NOT in this drill. A drill rehearses what is "
              "committed; commit first if you meant to rehearse them.")

    # A push from a drill must be IMPOSSIBLE, not merely discouraged.
    rc, out = run(["git", "-C", str(SCRATCH), "remote", "remove", "origin"])
    if rc != 0:
        die("could not remove origin from the clone:\n" + out)
    rc, remotes = run(["git", "-C", str(SCRATCH), "remote"])
    if remotes.strip():
        die(f"the clone still has remotes ({remotes.strip()!r}) - "
            "a drill that can push is not a drill.")
    print("[make_drill] origin removed - remotes: none; a push from this "
          "drill is impossible")

    (SCRATCH / "DRILL_CLONE").write_text(MARKER_TEXT, encoding="utf-8")
    print("[make_drill] DRILL_CLONE marker stamped")

    entries = [p for p in (SCRATCH / "registry").glob("[0-9]*") if p.is_dir()]
    if entries:
        die("the clone's registry/ is not empty - it must never carry "
            "records into a drill. Investigate before proceeding.")
    print("[make_drill] registry/ is gitignored: the clone starts with "
          "ZERO records and can never contain real testimony")

    toml = SCRATCH / "wrangler.toml"
    text = toml.read_text(encoding="utf-8")
    text = text.replace(f'name = "{PROD_PROJECT}"',
                        f'name = "{DRILL_PROJECT}"', 1)
    text = text.replace(PROD_KV, DRILL_KV)
    toml.write_text(text, encoding="utf-8", newline="\n")

    # Hard locks: refuse production plumbing in a drill, absolutely.
    text = toml.read_text(encoding="utf-8")
    if PROD_KV in text:
        die("the drill wrangler.toml still names the PRODUCTION KV "
            "namespace. Refusing to continue.")
    if f'name = "{DRILL_PROJECT}"' not in text:
        die("the drill wrangler.toml does not name the drill project. "
            "Refusing to continue.")
    if DRILL_KV not in text:
        die("the drill wrangler.toml does not bind the drill KV "
            "namespace. Refusing to continue.")
    print(f"[make_drill] clone bound to project {DRILL_PROJECT!r} + drill "
          "KV; production plumbing verified absent")

    env = dict(os.environ)
    env["AH_MODE"] = "drill"
    env["AH_REGISTRY_OPEN"] = "true"
    rc, out = run([sys.executable, "tools/build_site.py"],
                  cwd=str(SCRATCH), env=env)
    if rc != 0:
        die("drill build failed:\n" + out)
    index = (SCRATCH / "site" / "index.html").read_text(encoding="utf-8")
    if "REHEARSAL SITE" not in index or "noindex" not in index:
        die("the drill landing page is missing the rehearsal stamp.")
    if not (SCRATCH / "site" / "robots.txt").exists():
        die("the drill build wrote no robots.txt.")
    print("[make_drill] drill site built: banner, noindex, robots.txt "
          "all verified present")

    rc, out = run([npx, "wrangler", "pages", "project", "create",
                   DRILL_PROJECT, "--production-branch", "main"])
    if rc != 0 and "already exists" not in out.lower():
        die("could not create the drill Pages project:\n" + out)

    throwaway = secrets.token_hex(32)
    r = subprocess.run([npx, "wrangler", "pages", "secret", "put",
                        "CEREMONY_SECRET", "--project-name", DRILL_PROJECT],
                       input=throwaway, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        die("could not set the drill CEREMONY_SECRET:\n" +
            (r.stdout or "") + (r.stderr or ""))
    print("[make_drill] throwaway CEREMONY_SECRET set on the drill project")

    rc, out = run([npx, "wrangler", "pages", "deploy", "--commit-dirty=true"],
                  cwd=str(SCRATCH))
    if rc != 0:
        die("drill deploy failed:\n" + out)
    url = ""
    for tok in out.split():
        if DRILL_PROJECT + ".pages.dev" in tok:
            url = tok.strip().rstrip(".")
    print(f"[make_drill] deployed: {url or '(see wrangler output above)'}")

    # The drill's reading room: same rehearsal, same stamp, same lifetime.
    rc, out = run([sys.executable, "tools/build_info.py"],
                  cwd=str(SCRATCH), env=env)
    if rc != 0:
        die("drill reading-room build failed:\n" + out)
    info_index = (SCRATCH / "info-site" / "index.html").read_text(encoding="utf-8")
    if "REHEARSAL SITE" not in info_index or "noindex" not in info_index:
        die("the drill reading room is missing the rehearsal stamp.")
    rc, out = run([npx, "wrangler", "pages", "project", "create",
                   INFO_DRILL_PROJECT, "--production-branch", "main"])
    if rc != 0 and "already exists" not in out.lower():
        die("could not create the drill reading-room project:\n" + out)
    rc, out = run([npx, "wrangler", "pages", "deploy", "info-site",
                   "--project-name", INFO_DRILL_PROJECT,
                   "--commit-dirty=true"], cwd=str(SCRATCH))
    if rc != 0:
        die("drill reading-room deploy failed:\n" + out)
    print(f"[make_drill] reading room deployed: "
          f"https://{INFO_DRILL_PROJECT}.pages.dev")

    print()
    print("The drill is up. Next:")
    print(f"  cd {SCRATCH}")
    print("  PowerShell:  $env:AH_MODE='drill'; "
          "python tools\\seed_drill.py")
    print("  bash:        AH_MODE=drill python tools/seed_drill.py")
    print("When the rehearsal ends: python tools/drop_drill.py "
          "(from the real repo)")


if __name__ == "__main__":
    main()
