"""The return ceremony: enter a Second or Final Testimony.

Usage:
    python tools/testify.py <registry_id> path/to/sitting.json --key ah1-....

The sitting file contains only "answers" (same shape as enrollment).
The kind is determined by the record itself: one prior version means
this is the Second Testimony, two mean it is the Final. Three slots
is a lifetime total; withdrawn slots stay spent.

The continuity key is the human's proof of return. The archive holds
only its fingerprint; presenting the matching key is what entitles
this record to grow. No key, no testimony — including for the
operator (see POLICY.md for the loss policy).

Spacing: POLICY.md requires at least one year between testimonies.
A closer sitting is refused unless --waive-spacing "reason" is given
(founding-era governance override; the reason is recorded in the log
event).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

MIN_SPACING_DAYS = 365


def load_questionnaire():
    q = json.loads((ahlib.ROOT / "questions" / "v1.json").read_text(encoding="utf-8"))
    return q, {item["id"]: item for item in q["questions"]}


def validate(answers, kind, qmeta, qbyid):
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
        if kind not in qbyid[qid]["asked_in"]:
            problems.append(f"{qid} is not asked in a {kind.capitalize()} Testimony")
        if not isinstance(a.get("text"), str) or not a["text"].strip():
            problems.append(f"{qid}: empty text")
        elif len(a["text"]) > cap:
            problems.append(f"{qid}: {len(a['text'])} chars exceeds cap of {cap}")
        if a.get("visibility") not in ("public", "sealed_until_death"):
            problems.append(f"{qid}: visibility must be public or sealed_until_death")
    return problems


def main():
    ahlib.announce_ceremony("testify")
    args = sys.argv[1:]
    waive_reason = None
    if "--waive-spacing" in args:
        i = args.index("--waive-spacing")
        waive_reason = args[i + 1]
        del args[i:i + 2]
    if "--key" not in args or len(args) != 4:
        print(__doc__)
        sys.exit(2)
    i = args.index("--key")
    key = args[i + 1]
    del args[i:i + 2]
    rid, sitting_path = args[0].zfill(9), args[1]

    d = ahlib.REGISTRY / rid
    if not (d / "entry.json").exists():
        print(f"no such record: registry/{rid}")
        sys.exit(1)
    entry = json.loads((d / "entry.json").read_text(encoding="utf-8"))

    cont = entry.get("continuity")
    if not cont:
        print("this record predates continuity keys; a governance decision is required")
        sys.exit(1)
    if ahlib.continuity_key_hash(key) != cont["key_hash"]:
        print("REFUSED: continuity key does not match this record")
        sys.exit(1)
    if entry.get("status") == "memorialized":
        print("REFUSED: record is memorialized")
        sys.exit(1)

    vdir = d / "versions"
    existing = sorted(int(p.stem) for p in vdir.glob("*.json"))
    if len(existing) >= 3:
        print("REFUSED: all three testimony slots are spent (Constitution, Article IV)")
        sys.exit(1)
    n = (existing[-1] + 1) if existing else 1
    kind = {1: "first", 2: "second", 3: "final"}[n]
    if n == 1:
        print("REFUSED: this record has no First Testimony; use tools/enroll.py flow")
        sys.exit(1)

    last = json.loads((vdir / f"{existing[-1]}.json").read_text(encoding="utf-8"))
    last_ts = datetime.fromisoformat(last["entered_at"].replace("Z", "+00:00"))
    days = (datetime.now(timezone.utc) - last_ts).days
    if days < MIN_SPACING_DAYS and not waive_reason:
        print(f"REFUSED: only {days} days since the last testimony; POLICY.md requires "
              f"{MIN_SPACING_DAYS}. Use --waive-spacing \"reason\" only by governance decision.")
        sys.exit(1)

    sitting = json.loads(Path(sitting_path).read_text(encoding="utf-8"))
    answers = sitting["answers"]
    qmeta, qbyid = load_questionnaire()
    problems = validate(answers, kind, qmeta, qbyid)
    if problems:
        for p in problems:
            print(f"REJECTED: {p}")
        sys.exit(1)

    ts = ahlib.now_utc()
    content_hash = ahlib.hash_value(answers)
    version = {
        "schema": "version.v1",
        "registry_id": rid,
        "version": n,
        "kind": kind,
        "questionnaire_version": qmeta["questionnaire_version"],
        "entered_at": ts,
        "status": "entered",
        "answers": answers,
        "content_hash": content_hash,
    }
    (vdir / f"{n}.json").write_text(
        json.dumps(version, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    data = {"version": n, "kind": kind, "content_hash": content_hash,
            "continuity_proven": True}
    if waive_reason:
        data["spacing_waived"] = waive_reason
    ahlib.append_event("VERSION_ENTERED", data, registry_id=rid)
    label = {"second": "Second", "final": "Final"}[kind]
    print(f"entered: {label} Testimony for #{rid}")
    if kind == "final":
        print("this record's testimony is complete — three slots, a whole life.")
    print("next: python tools/verify.py && python tools/build_site.py && git add -A && git commit")


if __name__ == "__main__":
    main()
