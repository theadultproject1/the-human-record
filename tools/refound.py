"""The re-founding ceremony. Runs at most once, and only while empty.

On 2026-07-05 this institution was founded as "the AllHumans Registry."
Before any human enrolled, a trademark conflict forced the public name
to change, and the founder chose to re-found the still-empty archive
under its final name, THE HUMAN RECORD, so that the immutable set
carries the true name and no rented domain. This tool performs that
re-founding, completely and atomically:

  1. CONSTITUTION.md: the institution's name becomes The Human Record
     (five occurrences), and the founding wound "Registry IDs" heals to
     "Registry numbers" (Article: numbers, never IDs).
  2. questions/v1.md: the questionnaire title carries the new name.
  3. The three v1 schema $ids become domain-free URNs
     (urn:humanrecord:schema:{entry,version,event}:v1): those files are
     hash-anchored, so whatever they contain is permanent, and a rented
     domain does not belong in the immutable set.
  4. tools/genesis.py: the genesis statement names The Human Record.
  5. SHA256SUMS.txt: the constitution's hash line is recomputed.
  6. NAMING.md is rewritten for the new reality; ARCHITECTURE.md gains
     the URN decision with its reasoning; FOUNDER_INTENT.md records the
     re-founding in the founder's words.
  7. The first genesis and its Bitcoin receipt move to
     checkpoints/pre-refounding/ with a README: archived, never hidden.
     They prove exactly what existed before: one genesis event, nothing
     else.
  8. The log is emptied; genesis.py writes the new genesis; verify.py
     must print OK; a fresh checkpoint is cut; verify.py must print OK
     again.

GUARDS: refuses if any human is enrolled, if the log holds anything but
the first genesis, or without --confirm. Rehearse in a drill clone
first (tools/make_drill.py); the real run is the same code.

After the real run: git add -A, commit, push. The push makes the
anchoring Action stamp the new genesis into Bitcoin the same hour.

Standard library only.
"""
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

OLD_GENESIS = "ef3c6a2d61dee234114c2add6b9a4ad320c42ebf1ea75a4501dcd00c08344895"
PY = sys.executable
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def die(msg):
    raise SystemExit("refound REFUSED: " + msg)


def run_tool(args, why):
    r = subprocess.run([PY] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       cwd=str(ahlib.ROOT))
    if r.returncode != 0:
        die(f"{why} failed:\n" + (r.stdout or "") + (r.stderr or ""))
    return r.stdout or ""


def edit(relpath, pairs):
    p = ahlib.ROOT / relpath
    t = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in t:
            die(f"{relpath}: expected text not found: {old[:60]!r}")
        t = t.replace(old, new)
    p.write_text(t, encoding="utf-8", newline="\n")
    print(f"[refound] edited {relpath}")


NAMING_NEW = """# On the names of this institution

*This is the public annotation that explains the institution's names:
what the founding documents say, what came before them, and which words
are fixed forever versus free to change.*

---

## The name, and the founding before the founding

The founding documents read **The Human Record**. That is the
institution's name, ratified in the genesis event and immutable from
that moment on.

It was not the first name. The institution was first founded on
2026-07-05 as *"the AllHumans Registry."* Before any human enrolled -
while the registry held zero records and no testimony existed - a
trademark conflict forced the public name to change, and rather than
carry a dead name in its immutable founding documents forever, the
founder re-founded the still-empty archive under its final name on
__REFOUND_DATE__. Nothing was lost, because nothing yet existed to
lose; nothing was hidden, because the first founding is archived in
`checkpoints/pre-refounding/` - its genesis event and its Bitcoin
timestamp receipt - where anyone, in any decade, can verify exactly
what the archive was before the re-founding: one genesis line and
nothing else. The re-founding is also recorded in
`founder/FOUNDER_INTENT.md`.

This door closed permanently the moment the first human enrolled. The
founding documents will never change again, for the same reason the
change was honest: immutability protects testimony, and now testimony
exists.

## The public name - free to change anyway

What the living website calls the institution, and the address it
answers at, remain *presentation*, not *record*. They may change - a
rebrand, a new domain - without touching a single fingerprint. Those
changeable strings live in exactly one place: `tools/brand.py`
(`BRAND`, `DOMAIN`). The founding record now happens to match the
public name; if the public name ever moves again, this annotation is
where the bridge gets written.

## The words we use

- **"The Archive."** In living text the institution is called *the
  Archive* (or its full name). The founding word *"Registry"* remains
  in the Constitution as the functional word for the register of
  records, and in wire format.
- **"A number," never "an ID."** A human holds a *number* - Human #2 -
  never an "ID." The internal data field is still `registry_id` and
  the folder is still `registry/`; that is wire format and directory
  structure, frozen in schema v1, and no human ever reads it. Names
  humans read, and names machines read, are allowed to differ.
- **The schema $ids are URNs** (`urn:humanrecord:schema:entry:v1` and
  siblings): identifiers, not addresses, so the immutable set names no
  rented domain. See ARCHITECTURE.md for the reasoning.

## Domains

The institution answers at `thehumanrecord.earth`. The first public
address, `allhumans.world`, is kept and redirects, forever: a century
archive never breaks a link.
"""

ATTIC_README = """# The first founding, archived

This institution was founded on 2026-07-05 under the name "the
AllHumans Registry," and re-founded as "The Human Record" on
__REFOUND_DATE__, while the registry was still empty: zero humans
enrolled, no testimony in existence, nothing lost, and no promise
broken - the promises protect testimony, and none yet existed. The
name changed because of a trademark conflict with a pending mark.

These files are the first founding's proof, kept forever:

- `2026-07-08-ef3c6a2d61de.tip` - the first checkpoint: the first
  genesis event's hash (ef3c6a2d61de...), frozen three days after the
  founding.
- `2026-07-08-ef3c6a2d61de.tip.ots` - its OpenTimestamps receipt,
  attested in the Bitcoin blockchain. It proves the first founding
  EXISTED and WHEN - and therefore also proves what it was: one
  genesis event and nothing else.
- `checkpoints.jsonl` - the first checkpoint ledger.

The current chain begins at the new genesis in
`log/registry.log.jsonl`; `python tools/verify.py` proves it from
scratch. This folder is history, deliberately kept where anyone can
find it.
"""

FOUNDER_NOTE = """
## The re-founding

*Recorded __REFOUND_DATE__ by the Founder.*

Founded as AllHumans on 2026-07-05; re-founded as The Human Record on
__REFOUND_DATE__ after a trademark conflict with a pending mark. The
registry was empty; no testimony existed; nothing was lost. The old
genesis (ef3c6a2d61dee234114c2add6b9a4ad320c42ebf1ea75a4501dcd00c08344895)
and its Bitcoin receipt are archived in `checkpoints/pre-refounding/`
and prove the empty founding.
"""

ARCH_NOTE = """**Domain-free schema identifiers (decided __REFOUND_DATE__).** The
immutable v1 schemas identify themselves by URN
(`urn:humanrecord:schema:entry:v1` and siblings), never by URL.
Deliberate: those files are hash-anchored in the genesis event, so
whatever they contain is permanent - and a rented domain does not
belong in the immutable set. A URN is a valid absolute URI that never
needs to resolve, so the institution's front door (whatever address it
answers at, in any decade) is decoupled from its founding documents
forever.

"""


def main():
    mode = ahlib.announce_ceremony("refound")

    if any(p.is_dir() for p in (ahlib.ROOT / "registry").glob("[0-9]*")):
        die("humans are enrolled. The re-founding was only ever possible "
            "while the registry was empty; that door is closed forever.")
    log_lines = [ln for ln in ahlib.LOG.read_text(encoding="utf-8")
                 .splitlines() if ln.strip()]
    if len(log_lines) != 1:
        die(f"the log holds {len(log_lines)} events; the re-founding "
            "requires exactly the first genesis and nothing else.")
    import json as _json
    if _json.loads(log_lines[0]).get("hash") != OLD_GENESIS:
        die("the log's genesis is not the first founding's genesis - "
            "already re-founded, or something is very wrong. Stopping.")

    if "--confirm" not in sys.argv:
        print(__doc__)
        print("This is the plan. Nothing was touched. Run with --confirm "
              "to perform the re-founding.")
        return

    # 1. The Constitution: the name, and the ID wound healed
    edit("CONSTITUTION.md", [
        ("# AllHumans — Constitution", "# The Human Record — Constitution"),
        ("of AllHumans. Its SHA-256 hash", "of The Human Record. Its SHA-256 hash"),
        ("AllHumans exists to preserve", "The Human Record exists to preserve"),
        ("AllHumans is not a social network", "The Human Record is not a social network"),
        ("The mission of AllHumans is", "The mission of The Human Record is"),
        ("Registry IDs are permanent.", "Registry numbers are permanent."),
        ("Registry IDs shall never be reused, sold, or transferred.",
         "Registry numbers shall never be reused, sold, or transferred."),
        ("Registry IDs begin at #2. Registry ID #1 is reserved forever.",
         "Registry numbers begin at #2. Number #1 is reserved forever."),
    ])

    # 2. The questionnaire title
    edit("questions/v1.md", [
        ("# AllHumans — The Questionnaire (Version 1)",
         "# The Human Record — The Questionnaire (Version 1)"),
    ])

    # 3. The three $ids become URNs
    for name in ("entry", "version", "event"):
        edit(f"schema/{name}.v1.json", [
            (f'"$id": "https://allhumans.world/schema/{name}.v1.json"',
             f'"$id": "urn:humanrecord:schema:{name}:v1"'),
        ])

    # 4. The genesis statement
    edit("tools/genesis.py", [
        ('"AllHumans Registry genesis. One number, at most three "',
         '"The Human Record genesis. One number, at most three "'),
    ])

    # 5. SHA256SUMS.txt: recompute the constitution's hash
    new_hash = hashlib.sha256(
        (ahlib.ROOT / "CONSTITUTION.md").read_bytes()).hexdigest()
    sums = ahlib.ROOT / "SHA256SUMS.txt"
    lines = sums.read_text(encoding="utf-8").splitlines()
    lines[0] = f"{new_hash}  CONSTITUTION.md"
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("[refound] SHA256SUMS.txt recomputed")

    # 6. The annotations: NAMING rewritten, ARCHITECTURE gains the URN
    #    decision, FOUNDER_INTENT records the founder's words
    (ahlib.ROOT / "NAMING.md").write_text(
        NAMING_NEW.replace("__REFOUND_DATE__", TODAY),
        encoding="utf-8", newline="\n")
    print("[refound] NAMING.md rewritten for the new reality")
    arch = ahlib.ROOT / "ARCHITECTURE.md"
    t = arch.read_text(encoding="utf-8")
    if "## Preservation" not in t:
        die("ARCHITECTURE.md anchor for the URN note not found")
    t = t.replace("## Preservation",
                  ARCH_NOTE.replace("__REFOUND_DATE__", TODAY)
                  + "## Preservation", 1)
    arch.write_text(t, encoding="utf-8", newline="\n")
    print("[refound] ARCHITECTURE.md: URN decision recorded")
    fi = ahlib.ROOT / "founder" / "FOUNDER_INTENT.md"
    fi.write_text(fi.read_text(encoding="utf-8").rstrip() + "\n" +
                  FOUNDER_NOTE.replace("__REFOUND_DATE__", TODAY),
                  encoding="utf-8", newline="\n")
    print("[refound] FOUNDER_INTENT.md: the re-founding recorded")

    # 7. The first founding moves to the attic - archived, never hidden
    attic = ahlib.ROOT / "checkpoints" / "pre-refounding"
    attic.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in list((ahlib.ROOT / "checkpoints").iterdir()):
        if f.is_file() and (f.suffix in (".tip", ".ots")
                            or f.name == "checkpoints.jsonl"):
            f.rename(attic / f.name)
            moved += 1
    (attic / "README.md").write_text(
        ATTIC_README.replace("__REFOUND_DATE__", TODAY),
        encoding="utf-8", newline="\n")
    print(f"[refound] first founding archived: {moved} file(s) -> "
          "checkpoints/pre-refounding/")

    # 8. The re-founding itself
    ahlib.LOG.write_text("", encoding="utf-8")
    out = run_tool(["tools/genesis.py"], "genesis")
    print("[refound] " + out.strip())
    out = run_tool(["tools/verify.py"], "verify (after genesis)")
    if not out.startswith("OK"):
        die("verify did not print OK after the new genesis:\n" + out)
    print("[refound] verify: OK")
    run_tool(["tools/checkpoint.py"], "checkpoint")
    print("[refound] new checkpoint cut")
    out = run_tool(["tools/verify.py"], "verify (after checkpoint)")
    if not out.startswith("OK"):
        die("verify did not print OK after the checkpoint:\n" + out)
    print("[refound] verify: OK")

    new_genesis = _json.loads(
        ahlib.LOG.read_text(encoding="utf-8").splitlines()[0])["hash"]
    print()
    print("THE RE-FOUNDING IS COMPLETE.")
    print(f"  first genesis (archived): {OLD_GENESIS}")
    print(f"  new genesis:              {new_genesis}")
    print(f"  date: {TODAY}")
    if mode == "production":
        print()
        print("Now: git add -A, commit, push. The push makes the anchoring")
        print("Action stamp the new genesis into Bitcoin within the hour.")


if __name__ == "__main__":
    main()
