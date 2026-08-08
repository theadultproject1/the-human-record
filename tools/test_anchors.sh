#!/usr/bin/env bash
# test_anchors.sh — guards the uniqueness machinery (schema/ANCHORS.md):
#   (1) no pepper -> enroll.py REFUSES (the ledger is load-bearing);
#   (2) normalization: case, +tags, gmail dots collapse to one anchor;
#   (3) an enrolled email cannot enroll again; --anchor-override can,
#       and the override is recorded in the private ops log;
#   (4) the sealed ledger chain verifies, and tampering is detected;
#   (5) ENROLLED events carry uniqueness metadata (types only, no values);
#   (6) --vouched-by records a number->number edge, nothing else.
# Runs in a throwaway /tmp copy. Usage: bash tools/test_anchors.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/_python.sh"   # sets $PY to a REAL interpreter (stub-proof)
ROOT="$(dirname "$SCRIPT_DIR")"
SB="$(mktemp -d "${TMPDIR:-/tmp}/ah_anchor_test.XXXXXX")"
cp -r "$ROOT/." "$SB/" 2>/dev/null; rm -rf "$SB/.git"; cd "$SB"
# Start from the true founding state, even when the source tree is a
# populated twin: clear enrolled records AND reset the log to its genesis
# event and drop checkpoints, so verify() is not tripped by log entries
# whose registry directories we just removed.
find registry -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' -exec rm -rf {} + 2>/dev/null
head -n 1 log/registry.log.jsonl > log/registry.log.jsonl.tmp && mv log/registry.log.jsonl.tmp log/registry.log.jsonl
rm -rf custody checkpoints; mkdir -p inbox
export AH_CUSTODY_DIR="$SB/custody-test"
unset AH_ANCHOR_PEPPER_FILE 2>/dev/null || true
PASS=0; FAIL=0
ok(){ echo "  PASS: $1"; PASS=$((PASS+1)); }
bad(){ echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

cat > inbox/alice.json <<'JSON'
{ "chosen_name": "Alice", "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": { "q_name": {"text": "Alice", "visibility": "public"} } }
JSON
cat > inbox/alice.envelope.json <<'JSON'
{ "acceptance": { "email": "Alice.Smith+reg@GMAIL.com",
    "affirmed": ["a","b","c","d","e","f","g"] },
  "sitting": {} }
JSON

echo "1) enroll refuses without a pepper"
if $PY tools/enroll.py inbox/alice.json 2>&1 | grep -q "REFUSED.*not in service"; then
  ok "no ledger -> no number"
else bad "enroll proceeded without the anchor ledger"; fi

$PY tools/anchors.py init >/dev/null

echo "2) normalization folds equivalent emails to one anchor"
N1="$($PY tools/anchors.py normalize 'Alice.Smith+reg@GMAIL.com')"
N2="$($PY tools/anchors.py normalize 'alicesmith@gmail.com')"
if [ "$N1" = "$N2" ] && [ "$N1" = "em1|alicesmith@gmail.com" ]; then
  ok "case/+tag/gmail-dots collapse ($N1)"
else bad "normalization differs: $N1 vs $N2"; fi

echo "3) first enrollment succeeds and binds the anchor"
if $PY tools/enroll.py inbox/alice.json 2>&1 | grep -qE "enrolled: (Registry )?#000000002"; then
  ok "Alice enrolled as #000000002"
else bad "first enrollment failed"; fi
$PY tools/anchors.py check 'alicesmith@gmail.com' >/dev/null
if [ $? -eq 3 ]; then ok "anchor now matches (exit 3)"; else bad "anchor not found after enrollment"; fi

echo "4) the same email cannot enroll again"
cat > inbox/alice2.json <<'JSON'
{ "chosen_name": "Alice Again", "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": { "q_name": {"text": "Alice Again", "visibility": "public"} } }
JSON
cat > inbox/alice2.envelope.json <<'JSON'
{ "acceptance": { "email": "alicesmith@gmail.com",
    "affirmed": ["a","b","c","d","e","f","g"] }, "sitting": {} }
JSON
if $PY tools/enroll.py inbox/alice2.json 2>&1 | grep -q "REFUSED: an enrollment anchor"; then
  ok "duplicate refused, way home offered"
else bad "duplicate enrollment was not refused"; fi

echo "5) --anchor-override enrolls and records the reason privately"
if $PY tools/enroll.py inbox/alice2.json --anchor-override "shared family email, verified two humans" 2>&1 | grep -qE "enrolled: (Registry )?#000000003"; then
  ok "override enrolls (#000000003)"
else bad "override did not enroll"; fi
if grep -q "shared family email" "$AH_CUSTODY_DIR/ops-log.jsonl" 2>/dev/null; then
  ok "override reason recorded in custody ops log"
else bad "override reason not recorded"; fi

echo "6) ENROLLED events carry uniqueness types, never values"
if grep -q '"uniqueness":{"anchors":\["email"\],"sworn":true}' log/registry.log.jsonl; then
  ok "uniqueness metadata in the log"
else bad "uniqueness metadata missing from ENROLLED event"; fi
if grep -qi "alicesmith" log/registry.log.jsonl; then
  bad "an email leaked into the public log"
else ok "no anchor value anywhere in the log"; fi

echo "7) vouch edges are number->number only"
cat > inbox/bob.json <<'JSON'
{ "chosen_name": "Bob", "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": { "q_name": {"text": "Bob", "visibility": "public"} } }
JSON
$PY tools/enroll.py inbox/bob.json --email bob@example.org --vouched-by 2 >/dev/null 2>&1
if grep -q '"vouchee":"000000004"' "$AH_CUSTODY_DIR/edges/vouch-edges.jsonl" 2>/dev/null \
   && grep -q '"voucher":"000000002"' "$AH_CUSTODY_DIR/edges/vouch-edges.jsonl"; then
  ok "edge #000000002 -> #000000004 recorded"
else bad "vouch edge missing or malformed"; fi
if grep -q "bob@example.org" "$AH_CUSTODY_DIR/edges/vouch-edges.jsonl" 2>/dev/null; then
  bad "an email leaked into the edge file"
else ok "edge file holds numbers only"; fi

echo "8) seal, checkpoint witness, verify, tamper-detect"
$PY tools/anchors.py seal --allow-small >/dev/null
$PY tools/checkpoint.py >/dev/null 2>&1
if grep -q '"anchor_ledger"' checkpoints/checkpoints.jsonl 2>/dev/null; then
  ok "checkpoint witnesses the anchor ledger tip"
else bad "checkpoint carries no anchor_ledger"; fi
if $PY tools/anchors.py verify | grep -q "anchor ledger OK"; then
  ok "ledger chain verifies"
else bad "ledger chain does not verify"; fi
if $PY tools/verify.py | grep -q "^OK"; then
  ok "full verify.py passes with custody present"
else bad "verify.py fails with custody present"; fi
sed -i 's/"count":[0-9]*/"count":999/' "$AH_CUSTODY_DIR/anchors/ledger.jsonl"
if $PY tools/anchors.py verify 2>&1 | grep -q "ERROR"; then
  ok "tampered batch detected"
else bad "tampering went undetected"; fi

echo "9) googlemail.com folds into gmail.com (one mailbox, one anchor)"
N3="$($PY tools/anchors.py normalize 'Alice.Smith@googlemail.com')"
if [ "$N3" = "em1|alicesmith@gmail.com" ]; then
  ok "domain folded ($N3)"
else bad "googlemail not folded: $N3"; fi

echo "10) --email ADDS to the envelope email — both are checked"
cat > inbox/carol.json <<'JSON'
{ "chosen_name": "Carol", "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": { "q_name": {"text": "Carol", "visibility": "public"} } }
JSON
cat > inbox/carol.envelope.json <<'JSON'
{ "acceptance": { "email": "carol@example.org",
    "affirmed": ["a","b","c","d","e","f","g"] }, "sitting": {} }
JSON
if $PY tools/enroll.py inbox/carol.json --email alice.smith@googlemail.com 2>&1 | grep -q "REFUSED: an enrollment anchor"; then
  ok "duplicate via --email caught even with a fresh envelope email"
else bad "--email bypassed the gate"; fi

echo "11) envelope vouched_by is NOT auto-recorded (web-supplied)"
cat > inbox/dave.json <<'JSON'
{ "chosen_name": "Dave", "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": { "q_name": {"text": "Dave", "visibility": "public"} } }
JSON
cat > inbox/dave.envelope.json <<'JSON'
{ "acceptance": { "email": "dave@example.org",
    "affirmed": ["a","b","c","d","e","f","g"] }, "sitting": {},
  "vouched_by": "000000002" }
JSON
OUT=$($PY tools/enroll.py inbox/dave.json 2>&1); RC=$?
if [ $RC -ne 0 ] && echo "$OUT" | grep -q "UNVERIFIED"; then
  ok "unconfirmed web-claimed vouch REFUSES (number not spent)"
else bad "envelope vouched_by was trusted or enrolled anyway (rc=$RC)"; fi
OUT=$($PY tools/enroll.py inbox/dave.json --vouched-by 2 2>&1)
if echo "$OUT" | grep -q "vouch edge recorded privately: #000000002" \
   && echo "$OUT" | grep -qE "enrolled: (Registry )?#"; then
  ok "confirmed vouch enrolls and records the edge"
else bad "confirmed vouch flow failed"; fi

echo "12) implausible email refuses humanely (no traceback)"
cat > inbox/eve.json <<'JSON'
{ "chosen_name": "Eve", "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": { "q_name": {"text": "Eve", "visibility": "public"} } }
JSON
OUT=$($PY tools/enroll.py inbox/eve.json --email "not-an-email" 2>&1); RC=$?
if [ $RC -ne 0 ] && echo "$OUT" | grep -q "REFUSED" && ! echo "$OUT" | grep -q "Traceback"; then
  ok "bogus email -> REFUSED, no traceback"
else bad "bogus email handled badly (rc=$RC)"; fi

echo "13) a wrong pepper is refused loudly, never silently 'free'"
cp "$AH_CUSTODY_DIR/pepper-v1.txt" "$AH_CUSTODY_DIR/pepper-backup.txt"
$PY -c "import secrets;print(secrets.token_hex(32))" > "$AH_CUSTODY_DIR/pepper-v1.txt"
OUT=$($PY tools/anchors.py check alicesmith@gmail.com 2>&1); RC=$?
if [ $RC -ne 0 ] && echo "$OUT" | grep -q "DOES NOT MATCH THE LEDGER"; then
  ok "pepper-ledger mismatch detected"
else bad "wrong pepper went unnoticed (rc=$RC)"; fi
cp "$AH_CUSTODY_DIR/pepper-backup.txt" "$AH_CUSTODY_DIR/pepper-v1.txt"

echo "14) edge --count without an argument prints usage, no crash"
OUT=$($PY tools/anchors.py edge --count 2>&1); RC=$?
if [ $RC -eq 2 ] && ! echo "$OUT" | grep -q "Traceback"; then
  ok "usage message (exit 2)"
else bad "edge --count crashed or wrong exit (rc=$RC)"; fi
OUT=$($PY tools/anchors.py edge abc 2 2>&1); RC=$?
if [ $RC -ne 0 ] && ! echo "$OUT" | grep -q "Traceback"; then
  ok "non-numeric registry id refused"
else bad "non-numeric id accepted or crashed (rc=$RC)"; fi

echo "15) checkpoint witnesses a new batch even when the log tip is unchanged"
$PY tools/anchors.py stage f1@example.org f2@example.org >/dev/null
$PY tools/anchors.py seal >/dev/null
CPS_BEFORE=$(wc -l < checkpoints/checkpoints.jsonl)
$PY tools/checkpoint.py >/dev/null 2>&1
CPS_AFTER=$(wc -l < checkpoints/checkpoints.jsonl)
if [ "$CPS_AFTER" -gt "$CPS_BEFORE" ]; then
  ok "new anchor batch produced a new checkpoint"
else bad "anchor batch went unwitnessed (log tip unchanged)"; fi

echo "16) PRODUCTION enroll refuses without explicit custody env (no silent drill ledger)"
# The guard is mode-aware: a DRILL clone may use fallback custody (it
# lives and dies with the clone), production never may. This check
# asserts the PRODUCTION rule, so the sandbox simulates production for
# this one call: no drill marker, no AH_MODE. The marker is restored
# after, so the remaining checks run in whatever mode the suite runs in.
MARKED=0; [ -f DRILL_CLONE ] && MARKED=1
rm -f DRILL_CLONE
cat > inbox/frank.json <<'JSON'
{ "chosen_name": "Frank", "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": { "q_name": {"text": "Frank", "visibility": "public"} } }
JSON
NID_BEFORE=$($PY -c "import sys;sys.path.insert(0,'tools');import enroll;print(enroll.next_registry_id())")
OUT=$(env -u AH_CUSTODY_DIR -u AH_ANCHOR_PEPPER_FILE -u AH_MODE $PY tools/enroll.py inbox/frank.json --email frank@example.org 2>&1); RC=$?
NID_AFTER=$($PY -c "import sys;sys.path.insert(0,'tools');import enroll;print(enroll.next_registry_id())")
if [ $RC -ne 0 ] && echo "$OUT" | grep -q "AH_CUSTODY_DIR is not set" && [ "$NID_BEFORE" = "$NID_AFTER" ]; then
  ok "production + unset custody env -> REFUSED, number not spent"
else bad "enroll proceeded without explicit custody (rc=$RC): $OUT"; fi
[ "$MARKED" = "1" ] && echo "drill clone marker (restored by test_anchors check 16)" > DRILL_CLONE

echo "17) a nonexistent voucher refuses BEFORE the number is spent"
OUT=$($PY tools/enroll.py inbox/frank.json --email frank@example.org --vouched-by 99 2>&1); RC=$?
NID_AFTER=$($PY -c "import sys;sys.path.insert(0,'tools');import enroll;print(enroll.next_registry_id())")
if [ $RC -ne 0 ] && echo "$OUT" | grep -q "no enrolled record #000000099" && [ "$NID_BEFORE" = "$NID_AFTER" ]; then
  ok "typo'd voucher -> REFUSED, number not spent"
else bad "phantom voucher accepted (rc=$RC)"; fi

echo "18) an override never waives a positive match silently"
cat > inbox/gina.json <<'JSON'
{ "chosen_name": "Gina", "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "answers": { "q_name": {"text": "Gina", "visibility": "public"} } }
JSON
OUT=$($PY tools/enroll.py inbox/gina.json --email alicesmith@gmail.com --anchor-override "drill: shared family email" 2>&1)
if echo "$OUT" | grep -q "WARNING: this override is waiving a POSITIVE ANCHOR" \
   && echo "$OUT" | grep -qE "enrolled: (Registry )?#"; then
  ok "override enrolls but the match is announced loudly"
else bad "override hid the positive match"; fi
if grep -q "anchor_match=1/1" "$AH_CUSTODY_DIR/ops-log.jsonl"; then
  ok "match count recorded in the ops log"
else bad "ops log missing the match record"; fi

echo
echo "anchors: $PASS passed, $FAIL failed"
cd /; rm -rf "$SB"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
