#!/usr/bin/env bash
# test_crisis.sh — crisis-response protocol invariant test.
#
# Proves that a HELD, REJECTED, or REWRITTEN submission never consumes a
# Registry number, and that enrollment leaves no gaps in the sequence.
# See POLICY.md, "Crisis of the author (crisis-response protocol)".
#
# Runs against a throwaway copy of the repo in /tmp — the real registry
# and log are never touched. Usage:  bash tools/test_crisis.sh
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
. "$SCRIPT_DIR/_python.sh"   # sets $PY to a REAL interpreter (stub-proof)                 # repo root = parent of tools/
SB="$(mktemp -d "${TMPDIR:-/tmp}/ah_crisis_test.XXXXXX")"
# copy everything except .git and any existing sandbox artifacts
cp -r "$ROOT/." "$SB/" 2>/dev/null
rm -rf "$SB/.git"
cd "$SB"
# start from the true founding state: no enrolled humans in the sandbox.
# On a populated twin, also reset the log to its genesis event and drop
# checkpoints, so verify() is not tripped by log entries whose registry
# directories we just removed.
find registry -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' -exec rm -rf {} + 2>/dev/null
head -n 1 log/registry.log.jsonl > log/registry.log.jsonl.tmp && mv log/registry.log.jsonl.tmp log/registry.log.jsonl
rm -rf checkpoints
# the uniqueness ledger must be in service before any number is spent
# (POLICY.md, Uniqueness; schema/ANCHORS.md)
rm -rf custody
export AH_CUSTODY_DIR="$SB/custody-test"
unset AH_ANCHOR_PEPPER_FILE 2>/dev/null || true
$PY tools/anchors.py init >/dev/null

PASS=0; FAIL=0
ok(){ echo "  PASS: $1"; PASS=$((PASS+1)); }
bad(){ echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
next_id(){ $PY -c "import sys;sys.path.insert(0,'tools');import enroll;print(enroll.next_registry_id())"; }
log_len(){ wc -l < log/registry.log.jsonl | tr -d ' '; }
reg_dirs(){ find registry -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' | wc -l | tr -d ' '; }
mksitting(){
cat > "$1" <<JSON
{ "chosen_name": "$2",
  "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": {
    "q_name":    {"text": "$2", "visibility": "public"},
    "q_hardest": {"text": "Something heavy, written plainly.", "visibility": "public"},
    "q_regret":  {"text": "A thing I would do differently.", "visibility": "sealed_until_death"},
    "q_hope":    {"text": "That those after me are gentler.", "visibility": "public"} } }
JSON
}

echo "=== Founding state ==="
echo "  next id = $(next_id) | log events = $(log_len) | registry dirs = $(reg_dirs)"
[ "$(next_id)" = "000000002" ] && ok "first number available is #2 (#1 reserved)" || bad "expected next id #2"

echo; echo "=== Scenario A: submission HELD under crisis review, never enrolled ==="
mksitting held.json "Held Author"
BID=$(next_id); BLOG=$(log_len); BREG=$(reg_dirs)
echo "  (author's words sit in the review queue; operator does not run enroll.py)"
[ "$(next_id)" = "$BID" ] && ok "held submission left next id unchanged ($BID)" || bad "held changed next id"
[ "$(log_len)" = "$BLOG" ] && ok "held submission wrote nothing to the log" || bad "held wrote to log"
[ "$(reg_dirs)" = "$BREG" ] && ok "held submission created no registry directory" || bad "held created a dir"

echo; echo "=== Scenario B: author REWRITES after the humane pause, then enrolls ==="
mksitting rewrite.json "Rewritten Author"
OUT=$($PY tools/enroll.py rewrite.json --email rewrite@example.org 2>&1); RC=$?
echo "$OUT" | grep -E "enrolled|REJECT" | sed 's/^/    /'
[ $RC -eq 0 ] && ok "rewrite enrolled (exit 0)" || bad "rewrite enroll failed"
echo "$OUT" | grep -qE "(Registry )?#000000002" && ok "rewrite got #2 — the held attempt consumed no number" || bad "rewrite did not get #2"

echo; echo "=== Scenario C: submission REJECTED at review (invalid), consumes nothing ==="
cat > bad.json <<'JSON'
{ "verification": {"tier": 0, "era": "founding era — verified email"},
  "answers": { "q_smile": {"text": "no name given", "visibility": "public"} } }
JSON
BID=$(next_id); BLOG=$(log_len); BREG=$(reg_dirs)
OUT=$($PY tools/enroll.py bad.json 2>&1); RC=$?
echo "$OUT" | sed 's/^/    /'
[ $RC -ne 0 ] && ok "invalid submission rejected (exit $RC)" || bad "invalid submission accepted"
[ "$(next_id)" = "$BID" ] && ok "rejection left next id unchanged ($BID)" || bad "rejection changed next id"
[ "$(log_len)" = "$BLOG" ] && ok "rejection wrote nothing to the log" || bad "rejection wrote to log"
[ "$(reg_dirs)" = "$BREG" ] && ok "rejection created no registry directory" || bad "rejection created a dir"

echo; echo "=== Scenario T0: a Tier 0 submission is never granted a number ==="
cat > tier0.json <<'JSON'
{ "chosen_name": "Tier Zero",
  "verification": {"tier": 0, "era": "founding era — verified email"},
  "answers": { "q_name": {"text": "Tier Zero", "visibility": "public"} } }
JSON
BID=$(next_id); BLOG=$(log_len); BREG=$(reg_dirs)
OUT=$($PY tools/enroll.py tier0.json 2>&1); RC=$?
echo "$OUT" | grep -iE "tier 0|REJECT" | sed 's/^/    /'
[ $RC -ne 0 ] && ok "Tier 0 submission refused a number (exit $RC)" || bad "Tier 0 was granted a number"
[ "$(next_id)" = "$BID" ] && ok "Tier 0 attempt left next id unchanged ($BID)" || bad "Tier 0 changed next id"
[ "$(reg_dirs)" = "$BREG" ] && ok "Tier 0 attempt created no registry directory" || bad "Tier 0 created a dir"

echo; echo "=== Scenario D: next real enrollment has NO gap ==="
mksitting second.json "Second Human"
OUT=$($PY tools/enroll.py second.json --email second@example.org 2>&1); RC=$?
echo "$OUT" | grep -E "(Registry )?#[0-9]" | sed 's/^/    /'
[ $RC -eq 0 ] && ok "second human enrolled" || bad "second enroll failed"
echo "$OUT" | grep -qE "(Registry )?#000000003" && ok "second human got #3 — no gap from held/rejected attempts" || bad "number gap detected"

echo; echo "=== Scenario E: independent verifier confirms number integrity ==="
OUT=$($PY tools/verify.py 2>&1); RC=$?
echo "$OUT" | sed 's/^/    /'
[ $RC -eq 0 ] && ok "verify.py passes (chain + numbers-never-reused + #1-never-assigned)" || bad "verify.py failed"

echo; echo "=== Guard: a scrapped/partial number is CAUGHT, never silently skipped ==="
mkdir -p registry/000000009/versions
OUT=$($PY tools/verify.py 2>&1); RC=$?
echo "$OUT" | grep -E "ERROR|FAILED" | sed 's/^/    /'
[ $RC -ne 0 ] && ok "verifier catches a partial/scrapped number (does not hide it)" || bad "verifier missed a partial number"
rm -rf registry/000000009

echo; echo "================ RESULT: $PASS passed, $FAIL failed ================"
rm -rf "$SB"
[ $FAIL -eq 0 ] && exit 0 || exit 1
