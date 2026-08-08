"""Test client for the front-of-funnel gate (used by tools/test_gate.sh).

Talks to a locally-running `wrangler pages dev` worker: fetches a real
ceremony token, solves the proof of work with hashlib, and submits with
a chosen scenario. Prints one line: "STATUS <code> <body>". Standard
library only. Not part of the durable core — a test helper.

Usage: python tools/_gateclient.py <base_url> <scenario> <ip>
"""
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request

BASE, SCENARIO, IP = sys.argv[1], sys.argv[2], sys.argv[3]


def req(path, method="GET", body=None, ip=None):
    headers = {"content-type": "application/json",
               "user-agent": "ah-gate-test/1"}   # pages.dev filters blank UAs
    # CF-Connecting-IP may only be set against a LOCAL wrangler dev worker;
    # the real Cloudflare edge rightly refuses spoofed CF headers (error 1000).
    if ip and ("127.0.0.1" in BASE or "localhost" in BASE):
        headers["CF-Connecting-IP"] = ip
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def lzbits(bs):
    n = 0
    for x in bs:
        if x == 0:
            n += 8
            continue
        n += 8 - x.bit_length()
        break
    return n


def solve(seed, bits):
    nonce = 0
    while True:
        if lzbits(hashlib.sha256(f"{seed}.{nonce}".encode()).digest()) >= bits:
            return str(nonce)
        nonce += 1


def get_token():
    s, b = req("/api/ceremony")
    return json.loads(b)


def body(token, nonce, affirmed=5, answers=2, website="", thin=False):
    ans = {"q_name": {"text": "Test Human", "visibility": "public"}}
    pool = [("q_smile", "morning coffee and a quiet street at dawn"),
            ("q_hope", "that they are kinder than we managed to be"),
            ("q_place", "a small town on Earth, close to the sea")]
    for i in range(answers):
        k, t = pool[i]
        ans[k] = {"text": ("hi" if thin else t), "visibility": "public"}
    return {
        "acceptance": {"email": "gate@test.dev", "affirmed": ["a"] * affirmed,
                       "accepted_at": "2026-07-09T00:00:00Z", "page": "enter-v1"},
        "sitting": {"chosen_name": "Test Human",
                    "verification": {"tier": 0, "era": "founding era"},
                    "answers": ans,
                    "continuity": {"method": "sha256-preimage", "key_hash": "a" * 64}},
        "website": website,
        "ceremony": ({"ts": token["ts"], "seed": token["seed"],
                      "sig": token["sig"], "nonce": nonce} if token else None),
        "submitted_at": "2026-07-09T00:00:01Z",
    }


def gate_pass_token():
    """Fetch a token, solve the PoW, and wait past the min-time floor."""
    t = get_token()
    nonce = solve(t["seed"], t.get("pow_bits", 0)) if t.get("pow_bits") else "0"
    time.sleep(t.get("min_seconds", 1) + 0.4)
    return t, nonce


def main():
    if SCENARIO == "happy" or SCENARIO == "submit":
        t, nonce = gate_pass_token()
        s, b = req("/api/submit", "POST", body(t, nonce), IP)
    elif SCENARIO == "toofast":
        t = get_token()
        nonce = solve(t["seed"], t.get("pow_bits", 0)) if t.get("pow_bits") else "0"
        s, b = req("/api/submit", "POST", body(t, nonce), IP)   # no wait
    elif SCENARIO == "notoken":
        s, b = req("/api/submit", "POST", body(None, None), IP)
    elif SCENARIO == "badpow":
        t = get_token()
        time.sleep(t.get("min_seconds", 1) + 0.4)   # pass the timing floor first
        s, b = req("/api/submit", "POST", body(t, None), IP)    # nonce missing
    elif SCENARIO == "honeypot":
        t, nonce = gate_pass_token()
        s, b = req("/api/submit", "POST", body(t, nonce, website="http://spam.example"), IP)
    elif SCENARIO == "oath":
        t, nonce = gate_pass_token()
        s, b = req("/api/submit", "POST", body(t, nonce, affirmed=4), IP)
    elif SCENARIO == "oneanswer":
        t, nonce = gate_pass_token()
        s, b = req("/api/submit", "POST", body(t, nonce, answers=1), IP)
    elif SCENARIO == "thin":
        t, nonce = gate_pass_token()
        s, b = req("/api/submit", "POST", body(t, nonce, answers=2, thin=True), IP)
    elif SCENARIO == "accept":
        # a well-formed acceptance (front of the funnel, no token needed)
        s, b = req("/api/accept", "POST",
                   {"email": "accept@test.dev", "affirmed": ["a"] * 5,
                    "accepted_at": "2026-07-17T00:00:00Z", "page": "enter-v1"}, IP)
    elif SCENARIO.startswith("vouchsub:"):
        # a happy submission carrying a vouch code (test_vouch.sh)
        code = SCENARIO.split(":", 1)[1]
        t, nonce = gate_pass_token()
        pb = body(t, nonce)
        pb["vouch_code"] = code
        s, b = req("/api/submit", "POST", pb, IP)
    else:
        print("unknown scenario", SCENARIO)
        sys.exit(2)
    print(f"STATUS {s} {b}")


if __name__ == "__main__":
    main()
