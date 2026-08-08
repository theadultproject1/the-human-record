"""Seed a drill clone with the rehearsal cast - every path the code has.

A fresh drill starts empty (registry/ is gitignored). This fills it,
deliberately, with a DESIGNED set of synthetic humans:

    #2   a 1920 elder whose seals opened by TIME (the century door) -
         also the return/withdraw rehearsal record, since its one-year
         spacing is long past
    #3   a plain, ordinary record
    #4   sealed answers showing BOTH doors: a Legacy Key (words printed
         below) or the year the century opens them
    #5   silences - questions left unanswered
    #6   every cap: a 30-character name, 400-character answers
    #7   withdrawn, so the tombstone renders
    #8   memorialized through the real unseal ceremony, so sealed
         answers reveal with "(opened at memorialization)"
    #9   hostile text: script tags, quotes, unicode, RTL, emoji -
         proving the escaping in a real browser, not just a unit test
    #10+ thirty plain lights, so the galaxy layout is visible

THE REGRESSION RULE (permanent): when a bug is found in any rendering
or ceremony path, add the scenario that exposed it to this cast, so the
machine can never regress into it unnoticed. This file is the living
memory of every shape the archive must survive.

DETERMINISM: identities, keys, Legacy words and text are drawn from a
fixed seed and reproduce exactly, forever. Timestamps (and therefore
log hashes) follow the clock; the CAST is what is reproducible, not the
bytes of the log.

Hard locks: runs ONLY inside a drill clone (AH_MODE=drill and the
DRILL_CLONE marker must both hold, like every ceremony), refuses a tree
that still has a git remote, and refuses a registry that already has
records - it can never seed the real archive, and it never reseeds on
top of a previous cast.

Standard library only.  Usage (inside the clone):  AH_MODE=drill
python tools/seed_drill.py
"""
import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

RNG = random.Random("allhumans-drill-seed-v1")
PY = sys.executable
TMP = ahlib.ROOT / ".seed-sitting.json"


def die(msg):
    raise SystemExit("seed_drill REFUSED: " + msg)


def run_tool(args, why):
    r = subprocess.run([PY] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       cwd=str(ahlib.ROOT))
    if r.returncode != 0:
        die(f"{why} failed:\n" + (r.stdout or "") + (r.stderr or ""))
    return r.stdout or ""


def new_key():
    hexd = "".join(RNG.choice("0123456789abcdef") for _ in range(32))
    return "ah1-" + "-".join(hexd[i:i + 4] for i in range(0, 32, 4))


def key_hash(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def legacy_words():
    wl = [w for w in (ahlib.ROOT / "tools" / "wordlists" /
                      "legacy_words.txt").read_text(encoding="utf-8")
          .splitlines() if w and not w.startswith("#")]
    return " ".join(RNG.sample(wl, 6))


def legacy_block(words, khash):
    fp = hashlib.pbkdf2_hmac("sha256", words.encode("utf-8"),
                             khash.encode("ascii"), 600000).hex()
    return {"method": "pbkdf2-sha256", "iterations": 600000,
            "salt": "continuity", "fingerprint": fp,
            "wordlist": "eff-short-2", "words": 6}


def enroll(name, answers, khash, legacy=None, email=None):
    sitting = {"chosen_name": name,
               "verification": {"tier": 2,
                                "era": "rehearsal era - seeded drill"},
               "answers": answers,
               "continuity": {"method": "sha256-preimage",
                              "key_hash": khash}}
    if legacy:
        sitting["legacy"] = legacy
    TMP.write_text(json.dumps(sitting, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    out = run_tool(["tools/enroll.py", str(TMP), "--email",
                    email or f"seed-{RNG.randrange(10**6)}@drill.invalid"],
                   f"enrolling {name!r}")
    TMP.unlink(missing_ok=True)
    for line in out.splitlines():
        if line.startswith("enrolled:"):
            return line.split("#")[-1].strip()
    die("could not read the assigned number from enroll output:\n" + out)


def pub(text):
    return {"text": text, "visibility": "public"}


def sealed(text):
    return {"text": text, "visibility": "sealed_until_death"}


def main():
    mode = ahlib.announce_ceremony("seed_drill")
    if mode != "drill":
        die("the rehearsal cast can only be seeded into a drill clone.")
    r = subprocess.run(["git", "-C", str(ahlib.ROOT), "remote"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.stdout.strip():
        die(f"this tree has a git remote ({r.stdout.strip()!r}) - a "
            "drill must have none. Was it made by make_drill.py?")
    if any(p.is_dir() for p in (ahlib.ROOT / "registry").glob("[0-9]*")):
        die("this drill already holds records. The cast is seeded once, "
            "into a fresh drill; drop and remake to reseed.")

    # the uniqueness ledger must be in service before any number is spent
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import anchors
    if not anchors.configured():
        run_tool(["tools/anchors.py", "init"], "anchors init")
        print("[seed_drill] drill anchor ledger initialized (in-repo "
              "custody/, drills only)")

    cast = []   # (rid, name, key, legacy words or "")

    # --- #2: the 1920 elder - the century door, already open ------------
    elder_key = new_key()
    ekh = key_hash(elder_key)
    p = ahlib.REGISTRY / "000000002"
    (p / "versions").mkdir(parents=True)
    entry = {"schema": "entry.v2", "registry_id": "000000002",
             "enrolled_at": "1920-01-01T00:00:00Z",
             "verification": {"tier": 2,
                              "era": "rehearsal era - seeded drill"},
             "status": "active", "chosen_name": "Elder of Nineteen Twenty",
             "continuity": {"method": "sha256-preimage", "key_hash": ekh}}
    (p / "entry.json").write_text(
        json.dumps(entry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    answers = {"q_name": pub("Elder of Nineteen Twenty"),
               "q_hardest": sealed("Words sealed in another century, "
                                   "opened by time alone."),
               "q_hope": pub("That someone reads this in a gentler age.")}
    version = {"schema": "version.v1", "registry_id": "000000002",
               "version": 1, "kind": "first", "questionnaire_version": 1,
               "entered_at": "1920-01-01T00:00:00Z", "status": "entered",
               "answers": answers, "content_hash": ahlib.hash_value(answers)}
    (p / "versions" / "1.json").write_text(
        json.dumps(version, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    ahlib.append_event("ENROLLED", {"verification": entry["verification"]},
                       registry_id="000000002")
    ahlib.append_event("VERSION_ENTERED",
                       {"version": 1, "kind": "first",
                        "content_hash": version["content_hash"]},
                       registry_id="000000002")
    cast.append(("000000002", entry["chosen_name"], elder_key, ""))
    print("[seed_drill] #000000002 Elder of Nineteen Twenty (century door "
          "open; also your return/withdraw rehearsal record)")

    # --- #3: plain and ordinary -----------------------------------------
    k = new_key()
    rid = enroll("Prima Ordinary",
                 {"q_name": pub("Prima Ordinary"),
                  "q_smile": pub("Fresh bread on a Sunday morning."),
                  "q_hope": pub("A quiet life, honestly told."),
                  "q_place": pub("A small town, on Earth.")},
                 key_hash(k))
    cast.append((rid, "Prima Ordinary", k, ""))

    # --- #4: sealed answers, both doors visible -------------------------
    k = new_key()
    kh = key_hash(k)
    words = legacy_words()
    rid = enroll("Keeper of Seals",
                 {"q_name": pub("Keeper of Seals"),
                  "q_hardest": sealed("A sealed grief, waiting for a "
                                      "trusted hand or for time."),
                  "q_regret": sealed("A sealed regret, same two doors."),
                  "q_smile": pub("Sunlight through winter windows.")},
                 kh, legacy=legacy_block(words, kh))
    cast.append((rid, "Keeper of Seals", k, words))

    # --- #5: silences ----------------------------------------------------
    k = new_key()
    rid = enroll("Quiet Person",
                 {"q_name": pub("Quiet Person"),
                  "q_smile": pub("Rain heard from under a warm roof."),
                  "q_hope": pub("That silence is also understood.")},
                 key_hash(k))
    cast.append((rid, "Quiet Person", k, ""))

    # --- #6: every cap ----------------------------------------------------
    name30 = "Maximiliana Konstantinopoulou"  # 29 chars + final 'x' = 30
    name30 = (name30 + "x")[:30]
    filler = ("Four hundred characters exactly, to prove the cap is the "
              "craft and the page holds the line. ")
    a400 = (filler * 6)[:400]
    k = new_key()
    rid = enroll(name30,
                 {"q_name": pub(name30),
                  "q_hardest": pub(a400),
                  "q_hope": pub(a400)},
                 key_hash(k))
    cast.append((rid, name30, k, ""))

    # --- #7: withdrawn - the tombstone ------------------------------------
    k = new_key()
    rid = enroll("Brief Candle",
                 {"q_name": pub("Brief Candle"),
                  "q_smile": pub("It burned briefly, and it was real."),
                  "q_hope": pub("To be allowed to change one's mind.")},
                 key_hash(k))
    run_tool(["tools/withdraw.py", rid, "1", "--key", k],
             f"withdrawing #{rid}")
    cast.append((rid, "Brief Candle (withdrawn)", k, ""))

    # --- #8: memorialized, through the real ceremony ----------------------
    k = new_key()
    kh = key_hash(k)
    words = legacy_words()
    rid = enroll("Remembered Light",
                 {"q_name": pub("Remembered Light"),
                  "q_hardest": sealed("Sealed words that a trusted hand "
                                      "opened, exactly as promised."),
                  "q_smile": pub("Being remembered kindly.")},
                 kh, legacy=legacy_block(words, kh))
    run_tool(["tools/unseal.py", rid, "--words", words, "--confirm"],
             f"memorializing #{rid}")
    cast.append((rid, "Remembered Light (memorialized)", k, words))

    # --- #9: hostile text - the escaping proof -----------------------------
    k = new_key()
    hostile_name = "<script>x</script> Bobby"
    rid = enroll(hostile_name,
                 {"q_name": pub(hostile_name),
                  "q_smile": pub("<script>alert('drill')</script> \"quotes\" "
                                 "& <tags> and 'apostrophes'"),
                  "q_hope": pub("unicode: مرحبا "
                                "‮RTL‬ emoji: \U0001f30d\U0001f56f "
                                "combining: é"),
                  "q_place": pub("</textarea><img src=x onerror=alert(1)>")},
                 key_hash(k))
    cast.append((rid, "Hostile Text Record", k, ""))

    # --- #10+: thirty plain lights ----------------------------------------
    for i in range(1, 31):
        k = new_key()
        rid = enroll(f"Light {i:02d}",
                     {"q_name": pub(f"Light {i:02d}"),
                      "q_smile": pub(f"Ordinary joy number {i}, plainly."),
                      "q_hope": pub("To be one light among many.")},
                     key_hash(k))
        cast.append((rid, f"Light {i:02d}", k, ""))
    print(f"[seed_drill] thirty plain lights enrolled")

    run_tool(["tools/verify.py"], "verify after seeding")
    print("[seed_drill] verify.py: OK")

    print()
    print("THE REHEARSAL CAST - keys are printed ONLY here, only for a drill")
    print("=" * 72)
    for rid, name, key, words in cast:
        print(f"#{rid}  {name}")
        print(f"    continuity key: {key}")
        if words:
            print(f"    legacy words:   {words}")
    print("=" * 72)
    print()
    print("Rebuild and redeploy the drill site to see the cast:")
    print("  PowerShell:  $env:AH_MODE='drill'; $env:AH_REGISTRY_OPEN='true'; "
          "python tools\\build_site.py; npx wrangler pages deploy "
          "--commit-dirty=true")
    print("  bash:        AH_MODE=drill AH_REGISTRY_OPEN=true python "
          "tools/build_site.py && npx wrangler pages deploy "
          "--commit-dirty=true")
    print()
    print("Rehearsable immediately: return/testify and withdraw against "
          "#000000002 (its year of spacing is a century past), invitations "
          "from any record above, legacy reports against #%s "
          "(Keeper of Seals)." % cast[2][0])


if __name__ == "__main__":
    main()
