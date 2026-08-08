#!/usr/bin/env bash
# test_seal.sh — the seal's two doors (POLICY.md, The seal):
#   (1) an enrolled sealed answer renders CLOSED, with the Legacy line
#       and the open year (enrollment + 100y);
#   (2) wrong six words REFUSE (exit 3), and nothing changes;
#   (3) right six words verify; --confirm memorializes, appends a
#       MEMORIALIZED event, and the rebuilt page shows the words open;
#   (4) the century door: a record enrolled >100 years ago renders its
#       sealed words OPEN by pure arithmetic, no ceremony at all;
#   (5) verify.py holds after the ceremony.
# Runs in a throwaway /tmp copy. Usage: bash tools/test_seal.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/_python.sh"   # sets $PY to a REAL interpreter (stub-proof)
ROOT="$(dirname "$SCRIPT_DIR")"
SB="$(mktemp -d "${TMPDIR:-/tmp}/ah_seal_test.XXXXXX")"
cp -r "$ROOT/." "$SB/" 2>/dev/null; rm -rf "$SB/.git"; cd "$SB"
# true founding state: no records, log reset to genesis, no checkpoints
find registry -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' -exec rm -rf {} + 2>/dev/null
head -n 1 log/registry.log.jsonl > log/registry.log.jsonl.tmp && mv log/registry.log.jsonl.tmp log/registry.log.jsonl
rm -rf custody checkpoints; mkdir -p inbox
export AH_CUSTODY_DIR="$SB/custody-test"
unset AH_ANCHOR_PEPPER_FILE 2>/dev/null || true
"$PY" tools/anchors.py init >/dev/null
PASS=0; FAIL=0
ok(){ echo "  PASS: $1"; PASS=$((PASS+1)); }
bad(){ echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

WORDS="ember harvest quiet door lantern sparrow"
KEYHASH="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
LFP=$("$PY" -c "import hashlib,sys;print(hashlib.pbkdf2_hmac('sha256',sys.argv[1].encode(),sys.argv[2].encode(),600000).hex())" "$WORDS" "$KEYHASH")

cat > inbox/sealer.json <<JSON
{ "chosen_name": "Sealer",
  "verification": {"tier": 2, "era": "founding era — founder vouch"},
  "continuity": {"method": "sha256-preimage", "key_hash": "$KEYHASH"},
  "legacy": {"method": "pbkdf2-sha256", "iterations": 600000, "salt": "continuity",
             "fingerprint": "$LFP", "wordlist": "eff-short-2", "words": 6},
  "answers": {
    "q_name":    {"text": "Sealer", "visibility": "public"},
    "q_hardest": {"text": "A thing carried quietly for years.", "visibility": "sealed_until_death"},
    "q_hope":    {"text": "That these words wait patiently.", "visibility": "public"} } }
JSON

echo "1) enroll a sitting with a sealed answer and a legacy fingerprint"
OUT=$("$PY" tools/enroll.py inbox/sealer.json --email sealer@example.org 2>&1)
if echo "$OUT" | grep -q "enrolled: .*#000000002"; then ok "enrolled (#000000002)"; else bad "enroll failed: $OUT"; fi
if "$PY" -c "import json,sys;e=json.load(open('registry/000000002/entry.json',encoding='utf-8'));sys.exit(0 if e.get('legacy',{}).get('fingerprint')=='$LFP' else 1)"; then
  ok "entry carries the legacy fingerprint"
else bad "legacy fingerprint missing from entry"; fi

echo "2) the sealed answer renders closed, with the year"
"$PY" tools/build_site.py >/dev/null 2>&1
OPENYEAR=$("$PY" -c "import json;from datetime import datetime,timedelta;e=json.load(open('registry/000000002/entry.json',encoding='utf-8'));print((datetime.strptime(e['enrolled_at'][:10],'%Y-%m-%d')+timedelta(days=36525)).year)")
if grep -q "sealed: opens with a" site/2/index.html && grep -q "or in $OPENYEAR" site/2/index.html; then
  ok "renders 'opens with a Legacy Key, or in $OPENYEAR'"
else bad "sealed rendering wrong"; fi
if grep -q "A thing carried quietly" site/2/index.html; then
  bad "SEALED TEXT LEAKED to the public page"
else ok "sealed text absent from the public page"; fi

echo "3) wrong words refuse; right words verify; --confirm memorializes"
"$PY" tools/unseal.py 2 --words "wrong words entirely here now six" >/dev/null 2>&1
[ $? -eq 3 ] && ok "wrong words -> exit 3, nothing opened" || bad "wrong words not refused with exit 3"
OUT=$("$PY" tools/unseal.py 2 --words "$WORDS" 2>&1)
if echo "$OUT" | grep -q "The key opens record" && echo "$OUT" | grep -qi "mourning ceremony"; then
  ok "right words verify; unsealing waits for the mourning ceremony"
else bad "verification message wrong: $OUT"; fi
OUT=$("$PY" tools/unseal.py 2 --words "$WORDS" --confirm 2>&1)
if echo "$OUT" | grep -q "memorialized: record #000000002"; then ok "--confirm memorializes"; else bad "confirm failed: $OUT"; fi
if grep -q '"type":"MEMORIALIZED"' log/registry.log.jsonl; then ok "MEMORIALIZED event in the log"; else bad "no MEMORIALIZED event"; fi

echo "4) the rebuilt page shows the words, open"
"$PY" tools/build_site.py >/dev/null 2>&1
if grep -q "A thing carried quietly" site/2/index.html && grep -q "opened at memorialization" site/2/index.html; then
  ok "sealed words now open on the page"
else bad "unsealed rendering wrong"; fi

echo "5) the century door needs no ceremony at all"
"$PY" - <<'PYEOF'
import json, pathlib
p = pathlib.Path('registry/000000003'); (p/'versions').mkdir(parents=True)
entry = {"schema":"entry.v2","registry_id":"000000003","enrolled_at":"1920-01-01T00:00:00Z",
  "verification":{"tier":2,"era":"founding era — founder vouch"},"status":"active",
  "continuity":{"method":"sha256-preimage","key_hash":"b"*64}}
(p/'entry.json').write_text(json.dumps(entry,indent=2)+"\n",encoding="utf-8")
import sys; sys.path.insert(0,'tools'); import ahlib
answers={"q_name":{"text":"Elder","visibility":"public"},
         "q_hardest":{"text":"Words from another century.","visibility":"sealed_until_death"}}
version={"schema":"version.v1","registry_id":"000000003","version":1,"kind":"first",
  "questionnaire_version":1,"entered_at":"1920-01-01T00:00:00Z","status":"entered",
  "answers":answers,"content_hash":ahlib.hash_value(answers)}
(p/'versions'/'1.json').write_text(json.dumps(version,indent=2)+"\n",encoding="utf-8")
ahlib.append_event("ENROLLED",{"verification":entry["verification"]},registry_id="000000003")
ahlib.append_event("VERSION_ENTERED",{"version":1,"kind":"first","content_hash":version["content_hash"]},registry_id="000000003")
PYEOF
"$PY" tools/build_site.py >/dev/null 2>&1
if grep -q "Words from another century." site/3/index.html && grep -q "opened by time" site/3/index.html; then
  ok "1920 record's seal opened by time, no ceremony"
else bad "century door did not open"; fi

echo "6) verify.py holds after everything"
if "$PY" tools/verify.py 2>&1 | grep -q "^OK"; then ok "verify passes"; else bad "verify failed"; fi

echo
echo "seal: $PASS passed, $FAIL failed"
cd /; rm -rf "$SB"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
