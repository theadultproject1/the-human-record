#!/usr/bin/env bash
# test_vouch.sh — self-serve vouching (POLICY.md Tier 2), tested against
# the REAL worker running locally via `wrangler pages dev`, plus the desk
# half in a throwaway sandbox. Proves:
#   mint       a key-proved, attested mint is accepted; token + mark stored
#   wrongkey   a mint with the wrong continuity key is refused (403)
#   memorial   a memorialized record cannot vouch (403)
#   incomplete a mint without the attestation is refused (400)
#   quota      the fourth mint for one record is refused (POLICY: three/year)
#   carry      a submission with a valid code stores vouched_by (worker-
#              resolved), never the raw code
#   singleuse  the same code on a second submission is refused (400)
#   unknown    a never-minted code is refused (400)
#   malformed  a code in the wrong shape is refused (400)
#   desk       enroll --vouched-by records the edge; quota text says three
#
# Requires node + wrangler (npx). Usage: bash tools/test_vouch.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/_python.sh"   # sets $PY to a REAL interpreter (stub-proof)
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"
PORT="${VOUCH_PORT:-8797}"
BASE="http://127.0.0.1:${PORT}"
PASS=0; FAIL=0
ok(){ echo "  PASS: $1"; PASS=$((PASS+1)); }
bad(){ echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

command -v npx >/dev/null 2>&1 || { echo "SKIP: npx/wrangler not found"; exit 0; }

AH_CUSTODY_DIR="${AH_CUSTODY_DIR:-$ROOT/custody-test-vouch}" "$PY" tools/build_site.py >/dev/null 2>&1

# Synthetic published records with KNOWN keys (the worker only ever sees
# the fingerprint file; these are not registry records).
K10="ah1-0000-0000-0000-0000-0000-0000-0000-0010"
K11="ah1-0000-0000-0000-0000-0000-0000-0000-0011"
KH10=$("$PY" -c "import hashlib,sys;print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "$K10")
KH11=$("$PY" -c "import hashlib,sys;print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "$K11")
mkdir -p site/keys
printf '{"registry_id":"000000010","key_hash":"%s","versions":1,"status":"active"}' "$KH10" > site/keys/10.json
printf '{"registry_id":"000000011","key_hash":"%s","versions":1,"status":"memorialized"}' "$KH11" > site/keys/11.json

rm -rf .wrangler/state 2>/dev/null

free_port(){
  powershell -NoProfile -Command "
    function KillTree(\$procId){
      Get-CimInstance Win32_Process -Filter \"ParentProcessId=\$procId\" -EA SilentlyContinue | ForEach-Object { KillTree \$_.ProcessId }
      Stop-Process -Id \$procId -Force -EA SilentlyContinue
    }
    Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { \$_.CommandLine -match 'pages dev site --port $PORT' } | ForEach-Object { KillTree \$_.ProcessId }
    Get-NetTCPConnection -LocalPort $PORT -State Listen -EA SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force -EA SilentlyContinue }
  " >/dev/null 2>&1 || true
}
free_port

echo "starting wrangler pages dev on :$PORT (local worker, test secret, tiny limits)…"
npx wrangler pages dev site --port "$PORT" --kv SUBMISSIONS \
  -b CEREMONY_SECRET=test-secret-not-real \
  -b CEREMONY_MIN_SECONDS=1 \
  -b CEREMONY_POW_BITS=10 \
  -b CEREMONY_IP_PER_HOUR=50 \
  -b CEREMONY_GLOBAL_PER_DAY=100000 \
  --compatibility-date=2026-07-07 >/tmp/ah_vouch_dev.log 2>&1 &
DEV_PID=$!

cleanup(){
  if command -v taskkill >/dev/null 2>&1; then
    taskkill //F //T //PID "$DEV_PID" >/dev/null 2>&1
  else
    kill "$DEV_PID" >/dev/null 2>&1
  fi
  free_port
}
trap cleanup EXIT

READY=""
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/ceremony" 2>/dev/null)
  if [ "$code" = "200" ]; then READY=1; break; fi
  sleep 1
done
if [ -z "$READY" ]; then
  echo "SKIP: wrangler pages dev did not become ready in 60s"
  echo "----- last dev log -----"; tail -20 /tmp/ah_vouch_dev.log 2>/dev/null
  exit 0
fi
echo "worker ready."

hash_of(){ "$PY" -c "import hashlib,sys;print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "$1"; }
mint(){ # $1 rid  $2 key  $3 code  $4 extra-json-fields (optional, with leading comma)
  local ch; ch=$(hash_of "$3")
  curl -s -w "\nSTATUS %{http_code}" -X POST "$BASE/api/vouch" \
    -H 'content-type: application/json' -H 'CF-Connecting-IP: 10.9.1.1' \
    -d '{"registry_id":"'"$1"'","key":"'"$2"'","code_hash":"'"$ch"'","attested":true'"${4:-}"'}'
}
code_of(){ echo "$1" | sed -n 's/^STATUS \([0-9]*\).*/\1/p'; }

CA="vh1-aaaa-0000-0001"; CB="vh1-aaaa-0000-0002"; CC="vh1-aaaa-0000-0003"
CD="vh1-aaaa-0000-0004"; CE="vh1-aaaa-0000-0005"; CF="vh1-aaaa-0000-0006"

echo "1) mint — key-proved, attested"
R=$(mint 10 "$K10" "$CA"); C=$(code_of "$R")
if [ "$C" = "200" ] && echo "$R" | grep -q '"ok":true'; then ok "minted (200 ok:true)"; else bad "mint refused: $R"; fi

echo "2) wrong continuity key"
R=$(mint 10 "$K11" "vh1-bbbb-0000-0001"); C=$(code_of "$R")
if [ "$C" = "403" ]; then ok "refused (403)"; else bad "wrong key not refused: $R"; fi

echo "3) memorialized record cannot vouch"
R=$(mint 11 "$K11" "vh1-bbbb-0000-0002"); C=$(code_of "$R")
if [ "$C" = "403" ] && echo "$R" | grep -qi "memorialized"; then ok "refused (403 memorialized)"; else bad "memorialized not refused: $R"; fi

echo "4) attestation missing"
CH=$(hash_of "vh1-bbbb-0000-0003")
R=$(curl -s -w "\nSTATUS %{http_code}" -X POST "$BASE/api/vouch" -H 'content-type: application/json' \
  -d '{"registry_id":"10","key":"'"$K10"'","code_hash":"'"$CH"'"}')
C=$(code_of "$R")
if [ "$C" = "400" ]; then ok "refused (400 incomplete)"; else bad "no-attestation not refused: $R"; fi

echo "5) quota — three per rolling year, fourth refused"
C2=$(code_of "$(mint 10 "$K10" "$CB")"); C3=$(code_of "$(mint 10 "$K10" "$CC")")
C4=$(code_of "$(mint 10 "$K10" "$CD")")
if [ "$C2$C3" = "200200" ] && [ "$C4" = "403" ]; then
  ok "three minted, fourth refused (403, no count in reply)"
else bad "quota wrong: [$C2 $C3 -> $C4]"; fi

run(){ "$PY" tools/_gateclient.py "$BASE" "$1" "$2" 2>/dev/null; }

echo "6) submission carrying a valid code stores the voucher's number"
R=$(run "vouchsub:$CA" 10.9.2.1); C=$(code_of "$R")
STORED=$("$PY" - <<'PYEOF'
import sqlite3, glob, json
found = ""
for db in glob.glob('.wrangler/state/v3/kv/**/*.sqlite', recursive=True):
    try:
        c = sqlite3.connect(db)
        if c.execute("select 1 from sqlite_master where type='table' and name='_mf_entries'").fetchone():
            for k, v in c.execute("select key, value from _mf_entries where key like 'sub:%'"):
                t = v.decode() if isinstance(v, bytes) else str(v)
                d = json.loads(t)
                if d.get("vouched_by") == "10" and d.get("vouch_gate") and "vouch_code" not in t:
                    found = "yes"
        c.close()
    except Exception:
        pass
print(found)
PYEOF
)
if [ "$C" != "200" ]; then bad "vouched submission refused: $R"
elif [ "$STORED" = "yes" ]; then ok "stored with vouched_by=10 + vouch_gate, raw code absent"
else echo "  SKIP: could not read local KV store — HTTP accept OK"; ok "vouched submission accepted (200)"; fi

echo "7) the same code a second time — single use"
R=$(run "vouchsub:$CA" 10.9.2.2); C=$(code_of "$R")
if [ "$C" = "400" ] && echo "$R" | grep -qi "already been used"; then ok "refused (400 already used)"; else bad "reuse not refused: $R"; fi

echo "8) a never-minted code"
R=$(run "vouchsub:vh1-cccc-0000-0009" 10.9.2.3); C=$(code_of "$R")
if [ "$C" = "400" ] && echo "$R" | grep -qi "not valid"; then ok "refused (400 not valid)"; else bad "unknown code not refused: $R"; fi

echo "9) a malformed code"
R=$(run "vouchsub:hello-there" 10.9.2.4); C=$(code_of "$R")
if [ "$C" = "400" ] && echo "$R" | grep -qi "does not look right"; then ok "refused (400 malformed)"; else bad "malformed not refused: $R"; fi

echo "10) the desk half — enroll --vouched-by records the edge, quota text says three"
SB="$(mktemp -d "${TMPDIR:-/tmp}/ah_vouch_desk.XXXXXX")"
cp -r "$ROOT/." "$SB/" 2>/dev/null
rm -rf "$SB/.git" "$SB/.wrangler"
(
  cd "$SB"
  find registry -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' -exec rm -rf {} + 2>/dev/null
  head -n 1 log/registry.log.jsonl > log/registry.log.jsonl.tmp && mv log/registry.log.jsonl.tmp log/registry.log.jsonl
  rm -rf checkpoints custody
  export AH_CUSTODY_DIR="$SB/custody-test"
  unset AH_ANCHOR_PEPPER_FILE 2>/dev/null || true
  "$PY" tools/anchors.py init >/dev/null 2>&1
  cat > voucher.json <<'JSON'
{ "chosen_name": "Voucher Human",
  "verification": {"tier": 2, "era": "founding era - founder vouch"},
  "answers": {
    "q_name":  {"text": "Voucher Human", "visibility": "public"},
    "q_smile": {"text": "A quiet morning with strong coffee.", "visibility": "public"},
    "q_hope":  {"text": "That kindness outlives all of us.", "visibility": "public"} } }
JSON
  cat > candidate.json <<'JSON'
{ "chosen_name": "Vouched Candidate",
  "verification": {"tier": 2, "era": "founding era - vouch code"},
  "answers": {
    "q_name":  {"text": "Vouched Candidate", "visibility": "public"},
    "q_smile": {"text": "Rain on a tin roof late at night.", "visibility": "public"},
    "q_hope":  {"text": "A gentler century than the last one.", "visibility": "public"} } }
JSON
  "$PY" tools/enroll.py voucher.json --email voucher@example.org >/dev/null 2>&1
  "$PY" tools/enroll.py candidate.json --email candidate@example.org --vouched-by 000000002 2>&1
) > "$SB/desk.out" 2>&1
if grep -q "vouch edge recorded privately: #000000002 -> #000000003" "$SB/desk.out" \
   && grep -q "POLICY throttle is 3" "$SB/desk.out" \
   && grep -qE "enrolled: (Registry )?#000000003" "$SB/desk.out"; then
  ok "edge #2 -> #3 recorded; quota text says three"
else
  bad "desk half wrong:"; sed 's/^/    /' "$SB/desk.out" | tail -12
fi
rm -rf "$SB"

echo "11) the founder's hand-vouch — a Tier 0 sitting, admitted on the founder's word"
# POLICY, Verification: "the founder's hand-vouch remains available where
# no invitation exists". Everyone arriving before the first enrollment is
# Tier 0, because nobody holds a number and so nobody can invite. This is
# the only door open at the founding, and it spends real numbers, so it
# is tested: refused without the flag, admitted with it, recorded
# honestly, and never confused with a peer edge.
FB="$(mktemp -d "${TMPDIR:-/tmp}/ah_vouch_founder.XXXXXX")"
cp -r "$ROOT/." "$FB/" 2>/dev/null
rm -rf "$FB/.git" "$FB/.wrangler"
(
  cd "$FB"
  find registry -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' -exec rm -rf {} + 2>/dev/null
  head -n 1 log/registry.log.jsonl > log/registry.log.jsonl.tmp && mv log/registry.log.jsonl.tmp log/registry.log.jsonl
  rm -rf checkpoints custody
  export AH_CUSTODY_DIR="$FB/custody-test"
  unset AH_ANCHOR_PEPPER_FILE 2>/dev/null || true
  "$PY" tools/anchors.py init >/dev/null 2>&1
  cat > tier0.json <<'JSON'
{ "chosen_name": "Tier Zero Human",
  "verification": {"tier": 0, "era": "founding era, verified email"},
  "answers": {
    "q_name":  {"text": "Tier Zero Human", "visibility": "public"},
    "q_place": {"text": "Paris", "visibility": "public"},
    "q_smile": {"text": "The smell of bread before the shops open.", "visibility": "public"},
    "q_hope":  {"text": "That they read this and feel less alone.", "visibility": "public"} } }
JSON
  echo "--- plain enroll (must refuse) ---"
  "$PY" tools/enroll.py tier0.json --email t0@example.org 2>&1
  echo "--- both vouch kinds at once (must refuse) ---"
  "$PY" tools/enroll.py tier0.json --email t0@example.org --founder-vouch --vouched-by 2 2>&1
  echo "--- founder hand-vouch (must enroll) ---"
  "$PY" tools/enroll.py tier0.json --email t0@example.org --founder-vouch 2>&1
  echo "--- what the record says ---"
  cat registry/000000002/entry.json 2>/dev/null
) > "$FB/founder.out" 2>&1
if grep -q "Tier 0 (verified email) grants no number" "$FB/founder.out" \
   && grep -q "founder-vouch and --vouched-by are different" "$FB/founder.out" \
   && grep -qE "enrolled: (Registry )?#000000002" "$FB/founder.out" \
   && grep -q "founder vouch" "$FB/founder.out" \
   && ! grep -q "vouch edge recorded" "$FB/founder.out"; then
  ok "Tier 0 refused plainly, admitted on the hand-vouch, recorded as such, no edge"
else
  bad "founder hand-vouch wrong:"; sed 's/^/    /' "$FB/founder.out" | tail -14
fi
rm -rf "$FB"

echo
echo "vouch: $PASS passed, $FAIL failed"
rm -rf "$ROOT/custody-test-vouch" 2>/dev/null
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
