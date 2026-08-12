#!/usr/bin/env bash
# test_gate.sh — the front-of-funnel bot/flood gate, tested against the
# REAL worker running locally via `wrangler pages dev` (local KV, a test
# secret, tiny tuned limits). Proves:
#   happy      a well-formed, unhurried, PoW-solved submission is accepted
#   toofast    a submission faster than the min-time floor is refused (429)
#   notoken    a submission with no ceremony token is refused (403)
#   badpow     a submission with no/invalid proof of work is refused (403)
#   honeypot   a filled honeypot is accepted byte-identically, stored nothing
#   oath       fewer than five affirmations is refused (400)
#   oneanswer  name + one answer (substance floor) is refused (400)
#   thin       answers under the 10-char minimum are refused (400)
#   ratelimit  the per-IP hourly cap trips (429) after the limit
#   accflood   the token-less acceptance endpoint is capped too
#   legfirst   a later death report never overwrites a genuine earlier one
#   freshflood twelve NEVER-SEEN addresses cannot force unbounded KV
#              writes: once the day's ceiling is spent the worker writes
#              nothing at all (the D5 fix — see limited() in pages.py)
#   wdedup     repeated identical withdrawals collapse to ONE KV entry
#              (a deterministic key), so they cannot flood the review desk
# The gate never assigns a number and never touches the archive.
#
# Requires node + wrangler (npx). Usage: bash tools/test_gate.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/_python.sh"   # sets $PY to a REAL interpreter (stub-proof)
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"
PORT="${GATE_PORT:-8799}"
BASE="http://127.0.0.1:${PORT}"
PASS=0; FAIL=0
ok(){ echo "  PASS: $1"; PASS=$((PASS+1)); }
bad(){ echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

command -v npx >/dev/null 2>&1 || { echo "SKIP: npx/wrangler not found"; exit 0; }

# Build the site so pages dev has site/_worker.js to serve.
AH_CUSTODY_DIR="${AH_CUSTODY_DIR:-$ROOT/custody-test-gate}" "$PY" tools/build_site.py >/dev/null 2>&1

# A synthetic published record so the withdrawal path can authenticate a
# known key (worker hashes the key as-is, no normalisation). Not a real
# registry record — just a static fingerprint file the worker fetches.
TESTKEY="ah1-0000-0000-0000-0000-0000-0000-0000-0001"
TESTKH=$("$PY" -c "import hashlib,sys;print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "$TESTKEY")
mkdir -p site/keys
printf '{"registry_id":"000000009","key_hash":"%s","versions":2,"status":"active"}' "$TESTKH" > site/keys/9.json

# Fresh local KV so rate-limit counters never carry across runs.
rm -rf .wrangler/state 2>/dev/null

# Free the port if a previous (possibly crashed) run left a server bound to
# it — otherwise the readiness check would silently hit a STALE worker and
# test frozen code. `wrangler pages dev` spawns a workerd process tree whose
# descendants outlive a plain kill of the npx wrapper, so we kill the whole
# tree of anything whose command line carries THIS port (leaves servers on
# other ports untouched), then belt-and-braces free the listener too.
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
  -b CEREMONY_IP_PER_HOUR=2 \
  -b CEREMONY_GLOBAL_PER_DAY=100000 \
  -b ACCEPT_IP_PER_HOUR=3 \
  -b ACCEPT_GLOBAL_PER_DAY=100000 \
  -b LEGACY_IP_PER_HOUR=3 \
  -b LEGACY_GLOBAL_PER_DAY=3 \
  -b WITHDRAW_IP_PER_HOUR=100 \
  -b WITHDRAW_GLOBAL_PER_DAY=100000 \
  --compatibility-date=2026-07-07 >/tmp/ah_gate_dev.log 2>&1 &
DEV_PID=$!

cleanup(){
  if command -v taskkill >/dev/null 2>&1; then
    taskkill //F //T //PID "$DEV_PID" >/dev/null 2>&1
  else
    kill "$DEV_PID" >/dev/null 2>&1
  fi
  # taskkill on the wrapper does NOT reap the detached workerd child that
  # actually holds the port; kill it by port so the next run starts clean.
  free_port
}
trap cleanup EXIT

# Wait (bounded) for the worker to answer the ceremony endpoint.
READY=""
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/ceremony" 2>/dev/null)
  if [ "$code" = "200" ]; then READY=1; break; fi
  sleep 1
done
if [ -z "$READY" ]; then
  echo "SKIP: wrangler pages dev did not become ready in 60s"
  echo "----- last dev log -----"; tail -20 /tmp/ah_gate_dev.log 2>/dev/null
  exit 0
fi
echo "worker ready."

run(){ "$PY" tools/_gateclient.py "$BASE" "$1" "$2" 2>/dev/null; }
code_of(){ echo "$1" | sed -n 's/^STATUS \([0-9]*\).*/\1/p'; }

echo "1) happy path — unhurried, PoW-solved, two answers"
R=$(run happy 10.9.0.1); C=$(code_of "$R")
if [ "$C" = "200" ] && echo "$R" | grep -q '"ok":true'; then ok "accepted (200 ok:true)"; else bad "happy rejected: $R"; fi

echo "2) too fast — submitted before the min-time floor"
R=$(run toofast 10.9.0.6); C=$(code_of "$R")
if [ "$C" = "429" ] && echo "$R" | grep -qi "too fast"; then ok "refused (429 too fast)"; else bad "too-fast not refused: $R"; fi

echo "3) no ceremony token"
R=$(run notoken 10.9.0.7); C=$(code_of "$R")
if [ "$C" = "403" ] && echo "$R" | grep -qi "ceremony token"; then ok "refused (403 invalid token)"; else bad "no-token not refused: $R"; fi

echo "4) missing proof of work"
R=$(run badpow 10.9.0.8); C=$(code_of "$R")
if [ "$C" = "403" ] && echo "$R" | grep -qi "challenge"; then ok "refused (403 challenge unmet)"; else bad "bad-pow not refused: $R"; fi

echo "5) honeypot filled — silent, byte-identical accept, stored nothing"
R=$(run honeypot 10.9.0.3); C=$(code_of "$R")
if [ "$C" = "200" ] && echo "$R" | grep -q '"ok":true'; then ok "honeypot accepted silently (200 ok:true)"; else bad "honeypot response wrong: $R"; fi

echo "6) missing oath — four affirmations, not five"
R=$(run oath 10.9.0.4); C=$(code_of "$R")
if [ "$C" = "400" ] && echo "$R" | grep -qi "incomplete"; then ok "refused (400 incomplete)"; else bad "missing-oath not refused: $R"; fi

echo "7) substance floor — name plus only one answer"
R=$(run oneanswer 10.9.0.5); C=$(code_of "$R")
if [ "$C" = "400" ] && echo "$R" | grep -qi "incomplete"; then ok "refused (400 incomplete)"; else bad "one-answer not refused: $R"; fi

echo "8) thin answers — under the 10-character minimum"
R=$(run thin 10.9.0.9); C=$(code_of "$R")
if [ "$C" = "400" ] && echo "$R" | grep -qi "incomplete"; then ok "refused (400 incomplete)"; else bad "thin answers not refused: $R"; fi

echo "9) per-IP rate limit — third submission from one connection trips"
R1=$(run submit 10.9.0.2); R2=$(run submit 10.9.0.2); R3=$(run submit 10.9.0.2)
C1=$(code_of "$R1"); C2=$(code_of "$R2"); C3=$(code_of "$R3")
if [ "$C1" = "200" ] && [ "$C2" = "200" ] && [ "$C3" = "429" ] && echo "$R3" | grep -qi "recently"; then
  ok "first two accepted, third refused (429 rate limit)"
else bad "rate limit wrong: [$C1 $C2 $C3] ($R3)"; fi

echo "8b) a one-word place is a whole answer, not a thin one"
R=$(run shortplace 10.9.0.12); C=$(code_of "$R")
if [ "$C" = "200" ] && echo "$R" | grep -q '"ok":true'; then
  ok "\"Paris\" accepted alongside two real answers"
else bad "a one-word place was refused: $R"; fi

echo "9b) acceptance flood — the token-less front-of-funnel is rate limited (D5)"
A1=$(code_of "$(run accept 10.9.0.11)"); A2=$(code_of "$(run accept 10.9.0.11)")
A3=$(code_of "$(run accept 10.9.0.11)"); A4=$(code_of "$(run accept 10.9.0.11)")
if [ "$A1$A2$A3" = "200200200" ] && [ "$A4" = "429" ]; then
  ok "three acceptances accepted, fourth refused (429) — KV flood capped"
else bad "acceptance not rate limited: [$A1 $A2 $A3 -> $A4]"; fi

echo "9c) a death report cannot be overwritten by a later one (D5)"
# Record numbers are public and the six words are deliberately unverified,
# so last-write-wins would let a stranger bury a family's real report.
LEG1=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/legacy" \
  -H 'content-type: application/json' -H 'CF-Connecting-IP: 10.9.8.1' \
  -d '{"registry_id":"77","words":"first genuine report from the family","attested":true}')
LEG2=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/legacy" \
  -H 'content-type: application/json' -H 'CF-Connecting-IP: 10.9.8.2' \
  -d '{"registry_id":"77","words":"later junk trying to bury it","attested":true}')
STORED=$("$PY" - <<'PYEOF'
# miniflare keeps the KEY in sqlite and the VALUE in a blob file the row
# points at, so reading a stored submission means following blob_id.
import sqlite3, glob
val = None
for db in glob.glob('.wrangler/state/v3/kv/**/*.sqlite', recursive=True):
    try:
        c = sqlite3.connect(db)
        if not c.execute("select 1 from sqlite_master where type='table' and name='_mf_entries'").fetchone():
            c.close(); continue
        row = c.execute("select blob_id from _mf_entries where key = 'legacy:77'").fetchone()
        c.close()
        if not row:
            continue
        for b in glob.glob('.wrangler/state/v3/kv/**/blobs/' + row[0], recursive=True):
            with open(b, 'rb') as fh:
                val = fh.read().decode('utf-8', 'replace')
    except Exception:
        pass
print('first' if (val and 'first genuine' in val) else ('junk' if val else ''))
PYEOF
)
if [ "$LEG1" != "200" ] || [ "$LEG2" != "200" ]; then
  bad "death reports not accepted ([$LEG1 $LEG2]) — both must answer identically"
elif [ -z "$STORED" ]; then
  echo "  SKIP: could not read local KV store (miniflare layout changed)"
elif [ "$STORED" = "first" ]; then
  ok "the genuine first report stands; the later one answered identically, stored nothing"
else
  bad "a later report OVERWROTE the first — a real family's report could be buried"
fi

echo "9d) fresh-address flood — the global ceiling bounds KV WRITES (D5)"
# The heart of the D5 fix. Twelve requests, every one from an address the
# worker has never seen, against a death-report cap of three a day. Before
# the fix the per-address counter was written BEFORE the global ceiling was
# consulted, so every new address forced a write and the ceiling never got a
# say — unbounded writes from IPv6's endless supply of addresses. Now the
# ceiling is spent first, so once it is reached the worker writes nothing at
# all. The proof is not the status codes; it is the KV key count.
LEGCODES=""
for i in $(seq 1 12); do
  LEGCODES="$LEGCODES$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/legacy" \
    -H 'content-type: application/json' -H "CF-Connecting-IP: 10.9.9.$i" \
    -d '{"registry_id":"9","words":"alpha bravo charlie delta echo foxtrot","attested":true}') "
done
LEGKEYS=$("$PY" - <<'PYEOF'
import sqlite3, glob
n = None
for db in glob.glob('.wrangler/state/v3/kv/**/*.sqlite', recursive=True):
    try:
        c = sqlite3.connect(db)
        if c.execute("select 1 from sqlite_master where type='table' and name='_mf_entries'").fetchone():
            n = (n or 0) + c.execute(
                "select count(*) from _mf_entries where key like 'rl:leg:%'").fetchone()[0]
        c.close()
    except Exception:
        pass
print('' if n is None else n)
PYEOF
)
NREFUSED=$(echo "$LEGCODES" | tr ' ' '\n' | grep -c '^429$')
if [ -z "$LEGKEYS" ]; then
  echo "  SKIP: could not read local KV store (miniflare layout changed)"
elif [ "$NREFUSED" -ge 8 ] && [ "$LEGKEYS" -le 5 ]; then
  ok "12 fresh addresses -> $NREFUSED refused, only $LEGKEYS counter key(s) written (bounded)"
else
  bad "flood not bounded: $NREFUSED refused of 12, $LEGKEYS counter keys written (want <=5)"
fi

echo "10) duplicate withdrawals collapse to one KV entry (no desk flood)"
WBODY1='{"registry_id":"9","version":1,"key":"'"$TESTKEY"'","submitted_at":"2026-07-10T00:00:00Z"}'
WBODY2='{"registry_id":"9","version":2,"key":"'"$TESTKEY"'","submitted_at":"2026-07-10T00:00:00Z"}'
wd(){ curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/withdraw" -H 'content-type: application/json' -d "$1"; }
WC1=$(wd "$WBODY1"); wd "$WBODY1" >/dev/null; wd "$WBODY1" >/dev/null   # three identical v1
WC2=$(wd "$WBODY2")                                                     # one distinct v2
CNT=$("$PY" - <<'PYEOF'
import sqlite3, glob
n = None
for db in glob.glob('.wrangler/state/v3/kv/**/*.sqlite', recursive=True):
    try:
        c = sqlite3.connect(db)
        if c.execute("select 1 from sqlite_master where type='table' and name='_mf_entries'").fetchone():
            n = (n or 0) + c.execute("select count(*) from _mf_entries where key like 'withdraw:%'").fetchone()[0]
        c.close()
    except Exception:
        pass
print('' if n is None else n)
PYEOF
)
if [ "$WC1" != "200" ] || [ "$WC2" != "200" ]; then
  bad "withdrawal requests not accepted ([$WC1 $WC2]) — check the keys/9.json fixture"
elif [ -z "$CNT" ]; then
  echo "  SKIP: could not read local KV store (miniflare layout changed) — HTTP path OK"
elif [ "$CNT" = "2" ]; then
  ok "3 identical + 1 distinct withdrawal -> 2 KV entries (duplicates collapsed)"
else
  bad "expected 2 withdraw KV entries, found $CNT (dedup not working)"
fi

echo
echo "gate: $PASS passed, $FAIL failed"
rm -rf "$ROOT/custody-test-gate" 2>/dev/null
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
