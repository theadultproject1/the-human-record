#!/usr/bin/env bash
# test_review.sh — guards the review desk's invariants:
#   (1) review.py is READ-ONLY (no number assigned, archive untouched);
#   (2) bot screen targets automation + harm-to-others, not the author:
#       SILENT on clean / non-English / sad testimony; FLAGS spam, mash,
#       duplicates, hateful terms, threats-to-others, and full names;
#   (3) Tier gating: Tier 0 = draft (no Assign button); Tier >= 1 = buttons.
# Runs in a throwaway /tmp copy. Usage: bash tools/test_review.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
. "$SCRIPT_DIR/_python.sh"   # sets $PY to a REAL interpreter (stub-proof)
SB="$(mktemp -d "${TMPDIR:-/tmp}/ah_review_test.XXXXXX")"
cp -r "$ROOT/." "$SB/" 2>/dev/null; rm -rf "$SB/.git"; cd "$SB"
find registry -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' -exec rm -rf {} + 2>/dev/null
mkdir -p inbox; rm -f inbox/*.json inbox/_review.html
PASS=0; FAIL=0
ok(){ echo "  PASS: $1"; PASS=$((PASS+1)); }
bad(){ echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
verdict(){ $PY tools/botscreen.py "inbox/$1" 2>/dev/null | grep -m1 verdict | sed 's/.*verdict: //'; }
has_code(){ $PY tools/botscreen.py "inbox/$1" 2>/dev/null | grep -q "$2"; }

cat > inbox/clean.json <<'JSON'
{ "chosen_name": "Mara", "verification": {"tier": 1, "era": "founding era — verified phone"},
  "answers": { "q_name": {"text": "Mara", "visibility": "public"},
    "q_hardest": {"text": "Losing my brother the winter I turned thirty.", "visibility": "public"},
    "q_regret": {"text": "That I waited so long to call him back.", "visibility": "sealed_until_death"} } }
JSON
cat > inbox/nonenglish.json <<'JSON'
{ "chosen_name": "山田", "verification": {"tier": 1, "era": "founding era — verified phone"},
  "answers": { "q_name": {"text": "山田", "visibility": "public"},
    "q_hardest": {"text": "父を早くに亡くしたこと。今でも夢に出てきます。", "visibility": "public"},
    "q_regret": {"text": "もっと素直になれば良かった。", "visibility": "public"} } }
JSON
cat > inbox/tier0_draft.json <<'JSON'
{ "chosen_name": "Draft Only", "verification": {"tier": 0, "era": "founding era — verified email"},
  "answers": { "q_name": {"text": "Draft Only", "visibility": "public"},
    "q_hope": {"text": "That the number I never received still meant something.", "visibility": "public"} } }
JSON
cat > inbox/spam.json <<'JSON'
{ "chosen_name": "BUY CHEAP MEDS", "verification": {"tier": 1, "era": "founding era — verified phone"},
  "answers": { "q_name": {"text": "BUY CHEAP MEDS", "visibility": "public"},
    "q_hardest": {"text": "Click here www.cheap-pillz.top act now limited offer!!!", "visibility": "public"},
    "q_regret": {"text": "send crypto to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh guaranteed % off", "visibility": "public"} } }
JSON
cat > inbox/mash.json <<'JSON'
{ "chosen_name": "asdf", "verification": {"tier": 1, "era": "founding era — verified phone"},
  "answers": { "q_name": {"text": "asdf", "visibility": "public"},
    "q_hardest": {"text": "aaaaaaaaaaaaaaaaaaaa", "visibility": "public"} } }
JSON
# A heavy, grief-laden testimony that mentions self-harm — must stay SILENT
# (author distress is the crisis protocol's domain, never a moderation flag).
cat > inbox/grief.json <<'JSON'
{ "chosen_name": "Jo", "verification": {"tier": 1, "era": "founding era — verified phone"},
  "answers": { "q_name": {"text": "Jo", "visibility": "public"},
    "q_hardest": {"text": "The night my father tried to kill himself, and the years of silence after.", "visibility": "public"},
    "q_regret": {"text": "I was so sad I did not want to be alive for a while.", "visibility": "public"} } }
JSON

echo "=== bot screen: automation + harm-to-others, not the author ==="
case "$(verdict clean.json)" in No\ signals*) ok "clean testimony: no signals";; *) bad "clean flagged";; esac
case "$(verdict nonenglish.json)" in No\ signals*) ok "non-English testimony: no signals (international-safe)";; *) bad "non-English wrongly flagged";; esac
case "$(verdict grief.json)" in No\ signals*) ok "grief + self-harm mention: NOT flagged (crisis domain, not moderation)";; *) bad "grief testimony wrongly flagged";; esac
case "$(verdict spam.json)" in REVIEW*) ok "spam: flagged for review";; *) bad "spam not flagged";; esac
case "$(verdict mash.json)" in REVIEW*) ok "keyboard mash: flagged for review";; *) bad "mash not flagged";; esac

cp inbox/clean.json inbox/clean_copy.json
V=$($PY tools/botscreen.py inbox/clean.json inbox/clean_copy.json 2>/dev/null | grep -c duplicate_pending || true)
[ "${V:-0}" -ge 1 ] && ok "duplicate pending submission: flagged" || bad "duplicate pending not flagged"
rm -f inbox/clean_copy.json inbox/grief.json

echo; echo "=== moderation advisories (flag for human eyes, never auto-reject) ==="
# hateful term proven via a benign sentinel added to the operator wordlist
# (no real slurs appear in this test) —
echo "zzzznotarealword" >> tools/wordlists/flagged_terms.txt
cat > inbox/hate.json <<'JSON'
{ "chosen_name":"T","verification":{"tier":1,"era":"x"},"answers":{"q_name":{"text":"T","visibility":"public"},"q_hardest":{"text":"they called me a zzzznotarealword every day at school","visibility":"public"}}}
JSON
has_code hate.json hateful_term && ok "flagged-term wordlist: hateful term surfaced" || bad "hateful term not surfaced"
cat > inbox/threat.json <<'JSON'
{ "chosen_name":"T","verification":{"tier":1,"era":"x"},"answers":{"q_name":{"text":"T","visibility":"public"},"q_regret":{"text":"I told him I will hurt you if you ever come near my family again","visibility":"public"}}}
JSON
has_code threat.json threat && ok "threat toward another person: flagged" || bad "threat not flagged"
cat > inbox/fullname.json <<'JSON'
{ "chosen_name":"T","verification":{"tier":1,"era":"x"},"answers":{"q_name":{"text":"T","visibility":"public"},"q_happiest":{"text":"The day my mentor Robert Langdon believed in me","visibility":"public"}}}
JSON
has_code fullname.json full_name && ok "full name of another: flagged (first-name-only rule)" || bad "full name not flagged"
cat > inbox/firstname.json <<'JSON'
{ "chosen_name":"T","verification":{"tier":1,"era":"x"},"answers":{"q_name":{"text":"T","visibility":"public"},"q_happiest":{"text":"The day my mentor Robert believed in me","visibility":"public"}}}
JSON
has_code firstname.json full_name && bad "first-name-only wrongly flagged" || ok "first-name-only: no name flag (correct)"
rm -f inbox/hate.json inbox/threat.json inbox/fullname.json inbox/firstname.json

echo; echo "=== review.py is read-only (assigns no number) ==="
BL=$(wc -l < log/registry.log.jsonl | tr -d ' ')
BR=$(find registry -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' | wc -l | tr -d ' ')
$PY tools/review.py >/dev/null 2>&1
AL=$(wc -l < log/registry.log.jsonl | tr -d ' ')
AR=$(find registry -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' | wc -l | tr -d ' ')
[ "$BL" = "$AL" ] && ok "review wrote nothing to the log ($BL events)" || bad "review changed the log"
[ "$BR" = "$AR" ] && ok "review created no registry directory" || bad "review created a registry dir"
[ -f inbox/_review.html ] && ok "review page rendered (inbox/_review.html)" || bad "no review page produced"

echo; echo "=== Tier gating in the review UI ==="
grep -q 'Assign number' inbox/_review.html && ok "Assign button shown for enrollable (Tier >= 1) submissions" || bad "no Assign button rendered"
grep -q 'Prompt rewrite' inbox/_review.html && ok "Prompt rewrite button shown" || bad "no rewrite button rendered"
grep -q 'not yet enrollable' inbox/_review.html && ok "Tier 0 submission shown as draft (no Assign button)" || bad "Tier 0 not marked as draft"

echo; echo "================ RESULT: $PASS passed, $FAIL failed ================"
rm -rf "$SB"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
