"""Founder-mediated enrollment ceremony (founding era).

Usage:
    python tools/enroll.py path/to/sitting.json
        [--email you@example.org]      anchor email when no envelope exists
        [--vouched-by NNN]             record the vouch edge (voucher's number)
        [--anchor-override "reason"]   enroll past an anchor match (recorded)

Uniqueness (one human, one record — schema/ANCHORS.md): before any
number is spent, the enrollment email — read from the submission's
sibling .envelope.json, or given with --email — is checked against
the private anchor ledger. A match refuses enrollment: the way back
to an existing record is the continuity key at the return page,
never a second number. Overrides exist for honest collisions
(shared family email) and are recorded privately in custody.

The sitting file is the reviewed, final testimony:

{
  "chosen_name": "…",            // optional; anonymity is first-class
  "birth_era": "…",              // optional, coarse
  "birth_place": "…",            // optional, coarse
  "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": {
    "q_name":  {"text": "…", "visibility": "public"},
    "q_smile": {"text": "…", "visibility": "sealed_until_death"},
    ...
  }
}

Assigns the next Registry number (starting at #000000002 — #1 is
reserved forever), writes entry.json and versions/1.json, and
appends ENROLLED + VERSION_ENTERED to the log. Then run
tools/verify.py and commit: the commit is the act of record.
"""
import json
import re
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib
import anchors


def load_questionnaire():
    q = json.loads((ahlib.ROOT / "questions" / "v1.json").read_text(encoding="utf-8"))
    return q, {item["id"]: item for item in q["questions"]}


def next_registry_id() -> str:
    existing = [int(d.name) for d in ahlib.REGISTRY.iterdir()
                if d.is_dir() and d.name.isdigit()] if ahlib.REGISTRY.exists() else []
    return f"{(max(existing) + 1) if existing else 2:09d}"


def validate(sitting, qmeta, qbyid):
    answers = sitting.get("answers") or {}
    cap = qmeta["answer_char_cap"]
    problems = []
    if "q_name" not in answers:
        problems.append("q_name is the one required answer")
    elif len(answers["q_name"].get("text", "")) > 30:
        problems.append("q_name: the name is capped at 30 characters (POLICY.md)")
    for qid, a in answers.items():
        if qid not in qbyid:
            problems.append(f"unknown question id: {qid}")
            continue
        if "first" not in qbyid[qid]["asked_in"]:
            problems.append(f"{qid} is not asked in a First Testimony")
        if not isinstance(a.get("text"), str) or not a["text"].strip():
            problems.append(f"{qid}: empty text")
        elif len(a["text"]) > cap:
            problems.append(f"{qid}: {len(a['text'])} chars exceeds cap of {cap}")
        if a.get("visibility") not in ("public", "sealed_until_death"):
            problems.append(f"{qid}: visibility must be public or sealed_until_death")
    v = sitting.get("verification") or {}
    if not isinstance(v.get("tier"), int) or not v.get("era"):
        problems.append("verification needs integer tier and era string")
    elif v["tier"] < 1:
        problems.append(
            "Tier 0 (verified email) grants no number — this is a draft. "
            "A record must be Tier 1 (verified phone) or Tier 2 (vouched) "
            "to be enrolled (POLICY.md, Verification).")
    return problems


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


def read_envelope(sitting_path: Path):
    """The sibling .envelope.json written by fetch_inbox.py, if any."""
    if sitting_path.name.endswith(".json"):
        env_path = sitting_path.with_name(sitting_path.name[:-5] + ".envelope.json")
        if env_path.exists():
            return json.loads(env_path.read_text(encoding="utf-8"))
    return None


def main():
    ahlib.announce_ceremony("enroll")
    args = sys.argv[1:]
    email = flag(args, "--email")
    vouched_by = flag(args, "--vouched-by")
    override = flag(args, "--anchor-override")
    ignore_env_vouch = "--ignore-envelope-vouch" in args
    if ignore_env_vouch:
        args.remove("--ignore-envelope-vouch")
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    sitting_path = Path(args[0])
    sitting = json.loads(sitting_path.read_text(encoding="utf-8"))
    qmeta, qbyid = load_questionnaire()
    problems = validate(sitting, qmeta, qbyid)
    if problems:
        for p in problems:
            print(f"REJECTED: {p}")
        sys.exit(1)

    # --- uniqueness gate (one human, one record; schema/ANCHORS.md) ---
    # The ledger must exist before any number is spent, in every era.
    envelope = read_envelope(sitting_path)
    acceptance = (envelope or {}).get("acceptance") or {}
    # EVERY email on the submission is an anchor: the acceptance email
    # from the envelope AND any --email — the flag adds, never replaces.
    emails = []
    for e in (acceptance.get("email"), email):
        if e and e not in emails:
            emails.append(e)
    sworn = len(acceptance.get("affirmed") or []) >= 5
    # In PRODUCTION a number is never spent against the implicit in-repo
    # fallback custody/ — a leftover rehearsal ledger there would
    # silently stand in for the real one. In a DRILL clone the fallback
    # is exactly right: the drill's custody lives and dies with the
    # clone. Mode is already resolved (marker + env agree) by the
    # announce at the top of main().
    if ahlib.resolve_mode() == "production" and not (
            os.environ.get("AH_CUSTODY_DIR", "").strip()
            or os.environ.get("AH_ANCHOR_PEPPER_FILE", "").strip()):
        print("REFUSED: AH_CUSTODY_DIR is not set. A number is never spent")
        print("against the implicit in-repo fallback custody/ — a leftover")
        print("drill ledger there would silently stand in for the real one.")
        print("Point this shell at the real custody and re-run.")
        sys.exit(1)
    if not anchors.configured():
        print("REFUSED: the anchor ledger is not in service (no pepper).")
        print("Run `python tools/anchors.py init` and see schema/ANCHORS.md —")
        print("no number is spent without the uniqueness check.")
        sys.exit(1)
    plausible, bogus = [], []
    for e in emails:
        try:
            anchors.normalize_email(e)
            plausible.append(e)
        except ValueError:
            bogus.append(e)
    if bogus and not override:
        print(f"REFUSED: {len(bogus)} enrollment email(s) on this submission")
        print("are not plausible addresses — nothing to anchor. Fix the")
        print('envelope or pass --email; to proceed anyway (rare):')
        print('  --anchor-override "reason the anchor is unavailable"')
        sys.exit(1)
    if not plausible and not override:
        print("REFUSED: no enrollment email to anchor — none in a sibling")
        print(".envelope.json and no --email given. Every enrollment binds")
        print("its anchors (POLICY.md, Uniqueness). To proceed anyway:")
        print('  --anchor-override "reason the anchor is unavailable"')
        sys.exit(1)
    if len(plausible) > 1:
        print(f"note : {len(plausible)} distinct emails on this submission — "
              "all will be checked and anchored")
    taken = anchors.check_emails(plausible)
    if taken and not override:
        print("REFUSED: an enrollment anchor on this submission already")
        print("belongs to a Registry record. If it is theirs, their")
        print("continuity key at the return page is the way home — a")
        print("second number is never the answer. For honest collisions")
        print('(shared family email): --anchor-override "reason".')
        sys.exit(1)
    if override:
        # An override never waives silently: an override given for one
        # gate (say, a malformed envelope email) must not hide that a
        # DIFFERENT gate — a positive duplicate match — also fired.
        if taken:
            print("=" * 64)
            print(f"  WARNING: this override is waiving a POSITIVE ANCHOR")
            print(f"  MATCH on {len(taken)} of {len(plausible)} email(s) —")
            print("  an identifier here already belongs to an enrolled")
            print("  record. Proceed only if you have confirmed this is a")
            print("  shared address between two distinct humans.")
            print("=" * 64)
        anchors.record_override(
            override,
            context=(f"enroll {sitting_path.name}; "
                     f"anchor_match={len(taken)}/{len(plausible)}; "
                     f"bogus={len(bogus)}"))
        print(f"anchor override recorded: {override}")
    # A vouch edge is a desk-side assertion: it is recorded ONLY from
    # the founder's own --vouched-by, never from the envelope — that
    # field arrives from the web and is unverified in this era. An
    # unconfirmed claim REFUSES (numbers are spent once; the edge
    # could never be attached afterward by re-running).
    env_vouch = (envelope or {}).get("vouched_by")
    if env_vouch and not vouched_by and not ignore_env_vouch:
        print(f"REFUSED: the envelope claims vouched_by #{env_vouch} — this is")
        print("web-supplied and UNVERIFIED. Confirm with the voucher, then")
        print(f"enroll with --vouched-by {env_vouch} to record the edge; or, if")
        print("the claim is false or moot, enroll with --ignore-envelope-vouch.")
        sys.exit(1)
    if vouched_by:
        vouched_by = anchors.valid_rid(vouched_by)
        # Checked BEFORE the number is spent: a typo'd voucher must not
        # surface only after enrollment, when nothing can be unwound.
        if not (ahlib.REGISTRY / vouched_by / "entry.json").exists():
            print(f"REFUSED: no enrolled record #{vouched_by} to vouch —")
            print("check the number (a vouch edge is permanent).")
            sys.exit(1)

    # Bind the anchors BEFORE the number is spent: a failure past this
    # point leaves a staged anchor (which fails CLOSED — it can only
    # block a duplicate), never an enrolled human missing from the
    # ledger (which would fail open, forever).
    staged_n = 0
    if plausible:
        pepper = anchors.load_pepper()
        staged_n = anchors.stage_anchors(
            [anchors.email_anchor(e, pepper) for e in plausible])

    rid = next_registry_id()
    ts = ahlib.now_utc()
    answers = sitting["answers"]
    content_hash = ahlib.hash_value(answers)

    # Continuity: if the sitting carries a key fingerprint, the key was
    # generated in the author's browser and NO ONE else has ever seen
    # it — the archive stores only the hash. A key is generated here
    # only for founder-mediated ceremonies without a browser.
    import re as _re
    provided = sitting.get("continuity") or {}
    key = None
    if provided.get("method") == "sha256-preimage" and \
            _re.fullmatch(r"[0-9a-f]{64}", provided.get("key_hash", "")):
        key_hash = provided["key_hash"]
    else:
        key = ahlib.new_continuity_key()
        key_hash = ahlib.continuity_key_hash(key)

    entry = {
        "schema": "entry.v2",
        "registry_id": rid,
        "enrolled_at": ts,
        "verification": sitting["verification"],
        "status": "active",
        "continuity": {
            "method": "sha256-preimage",
            "key_hash": key_hash,
        },
    }
    for opt in ("chosen_name", "birth_era", "birth_place"):
        if sitting.get(opt):
            entry[opt] = sitting[opt]

    # The Legacy Key (POLICY.md, The seal): if answers were sealed, the
    # author's browser minted six words and sent only their stretched
    # fingerprint. It is stored here — never published — so that one day
    # a trusted hand can open the seals. Without one, the seals still
    # open by time, one hundred years after enrollment.
    any_sealed = any(a.get("visibility") == "sealed_until_death"
                     for a in answers.values())
    lg = sitting.get("legacy")
    if lg:
        if not (lg.get("method") == "pbkdf2-sha256"
                and isinstance(lg.get("iterations"), int)
                and lg["iterations"] >= 600000
                and lg.get("salt") == "continuity"
                and _re.fullmatch(r"[0-9a-f]{64}", lg.get("fingerprint", ""))):
            print("REJECTED: the sitting carries a malformed legacy block")
            sys.exit(1)
        if not any_sealed:
            print("REJECTED: a legacy key belongs only to a sitting that seals")
            sys.exit(1)
        entry["legacy"] = {"method": "pbkdf2-sha256",
                          "iterations": lg["iterations"],
                          "salt": "continuity",
                          "fingerprint": lg["fingerprint"],
                          "wordlist": lg.get("wordlist", "eff-short-2"),
                          "words": lg.get("words", 6)}
    elif any_sealed:
        print("note : sealed answers with NO legacy key — the seals will open")
        print("       only by time, one hundred years after enrollment.")

    version = {
        "schema": "version.v1",
        "registry_id": rid,
        "version": 1,
        "kind": "first",
        "questionnaire_version": qmeta["questionnaire_version"],
        "entered_at": ts,
        "status": "entered",
        "answers": answers,
        "content_hash": content_hash,
    }

    d = ahlib.REGISTRY / rid
    (d / "versions").mkdir(parents=True)
    (d / "entry.json").write_text(
        json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (d / "versions" / "1.json").write_text(
        json.dumps(version, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    era_str = str((sitting.get("verification") or {}).get("era", ""))
    if re.search(r"#\s*\d", era_str):
        print(f"WARNING: the era string ({era_str!r}) looks like it names a")
        print("number. The public record must never say WHO vouched; keep the")
        print("era to the method only, e.g. 'founding era - vouched'.")
    ahlib.append_event("ENROLLED",
                       {"verification": sitting["verification"],
                        "uniqueness": {"anchors": (["email"] if plausible else []),
                                       "sworn": sworn}},
                       registry_id=rid)
    ahlib.append_event("VERSION_ENTERED",
                       {"version": 1, "kind": "first", "content_hash": content_hash},
                       registry_id=rid)

    if plausible:
        print(f"anchors: {staged_n} newly staged of {len(plausible)} bound "
              "(seal periodically with anchors.py seal)")
    if vouched_by:
        anchors.record_edge(vouched_by, rid)
        edge_n = anchors.edge_count(vouched_by)
        print(f"vouch edge recorded privately: #{vouched_by} -> #{rid} "
              f"(#{vouched_by}: {edge_n} edge(s) this year; POLICY throttle is 3)")
        if edge_n > 3:
            print("WARNING: this voucher is OVER the POLICY throttle of three per")
            print("rolling year. The edge is recorded either way; whether their")
            print("word should keep spending numbers is a governance judgment.")
    print(f"enrolled: #{rid}")
    if key is None:
        print("continuity: key was generated in the author's browser and shown")
        print("only to them; the archive holds its fingerprint. Nothing to send.")
    else:
        print()
        print("=" * 64)
        print("  CONTINUITY KEY — shown once, stored nowhere:")
        print()
        print(f"      {key}")
        print()
        print("  Give this to the human. It is their only proof of return:")
        print("  required to enter the Second and Final Testimonies and to")
        print("  request withdrawal. The archive keeps only its fingerprint.")
        print("  Lost keys cannot be regenerated (see POLICY.md).")
        print("=" * 64)
    print()
    print("next: python tools/verify.py && python tools/build_site.py && git add -A && git commit")
    # The letter comes AFTER the deploy, so the address in it already
    # answers when they click it. Printed, never sent from here: spending
    # a number and writing to a person are two separate acts, and the
    # second one must not be able to disturb the first.
    if emails:
        print(f"then, once deployed: python tools/notify_author.py {int(rid)} "
              f"--email {emails[0]} --send")


if __name__ == "__main__":
    main()
