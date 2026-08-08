"""The invitation page (invite.html): an enrolled human mints a
single-use invitation for someone they know in person. In POLICY's
governance vocabulary this is Tier 2 vouching; humans hand each other
an *invitation*, so that is the only word the site uses.

The gate is the same automatic one the return and withdrawal pages
use: the site publishes each record's key fingerprint at
keys/{n}.json; VERIFY MY KEY hashes the entered key in the browser
and compares. The worker re-verifies server-side at minting.

The invitation itself is born in the voucher's browser and never
travels: only its SHA-256 is sent, and the worker stores that
fingerprint as a single-use token (30 days) plus a one-year quota
mark. The desk re-checks quota and use from the custody edge file at
review, so the worker is the era's first fence, never the law.

Anonymity: the edge (who invited whom) lives ONLY in the archive's
private custody, never in the public log, never on any page. The
invitation carries no number, so the invited person never learns the
inviter's number from The Record. The quota (POLICY: three per
rolling year) is deliberately never shown as a count.
"""
import brand
import pages


def render_vouch():
    parts = []
    parts.append('<div id="gate">')
    parts.append('<h1>Invite a human</h1>')
    parts.append(
        '<p class="meta">Verification in this era can be an act of human '
        'connection. If someone you know in person wants to leave their '
        'testimony, your word can admit them: you vouch that they are a '
        'real, living human, and The Record trusts you because it already '
        'holds your record.</p>')
    parts.append(
        '<p class="banner">Who invited whom is held privately by '
        'The Record, as one number standing behind another. It is never '
        'published, never shown on any page, and the invitation itself '
        'carries no number: your record number will not be revealed to '
        'the people you invite.</p>')
    parts.append(
        '<div class="q"><p class="prompt">My number is…</p>'
        '<textarea id="v_id" maxlength="9" placeholder="e.g. 2"></textarea></div>')
    parts.append(
        '<div class="q"><p class="prompt">My continuity key is…</p>'
        '<textarea id="v_key" maxlength="43" '
        'placeholder="ah1-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx"></textarea></div>')
    parts.append('<p><button class="finish" id="verify">VERIFY MY KEY</button></p>')
    parts.append('<p class="err" id="gate_err"></p>')
    parts.append('<p class="meta"><a href="index.html">Return to the lights</a></p>')
    parts.append('</div>')

    parts.append('<div id="attest" class="hidden">')
    parts.append('<h1>Your word</h1>')
    parts.append(
        '<p class="meta">Your key opened record #<span id="v_no"></span>. '
        'Before The Record creates your invitation, it asks for your word '
        'on four things about the person you are inviting.</p>')
    parts.append(
        '<div class="checks">'
        '<label><input type="checkbox" class="att"> They are a living human being.</label>'
        '<label><input type="checkbox" class="att"> They are 20 years old or older.</label>'
        '<label><input type="checkbox" class="att"> I know them in person, in real life.</label>'
        '<label><input type="checkbox" class="att"> To my knowledge, they hold no record here '
        'and have never testified here.</label>'
        '</div>')
    parts.append(
        '<p class="banner">If The Record later finds this person already '
        'had a record, your word stays quietly on file in its custody, '
        'forever. Give it only when you are sure.</p>')
    parts.append('<p><button class="finish" id="mint">CREATE MY INVITATION</button></p>')
    parts.append('<p class="err" id="attest_err"></p>')
    parts.append('</div>')

    parts.append(
        '<div id="minted" class="hidden">'
        '<h1>YOUR INVITATION</h1>'
        '<pre class="key" id="thecode"></pre>'
        '<p><button class="finish" id="copycode">COPY MY INVITATION</button></p>'
        '<p>Hand it to them privately, in person or in a message only they '
        'will read. It works once, for one person, and it expires in 30 '
        'days. They enter it when they write their testimony, in the field '
        'named MY INVITATION.</p>'
        '<p class="meta">The Record keeps only the invitation\'s '
        'fingerprint, never the invitation. If it is lost before it is '
        'used, simply create another.</p>'
        '<p class="meta"><a href="index.html">Return to the lights</a></p>'
        '</div>')
    parts.append(
        '<div id="fallback" class="hidden">'
        '<h2>The Record could not be reached. Nothing was created</h2>'
        '<p>Please try again when the Record is back online.</p>'
        '</div>')

    body = "\n".join(parts)
    return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>Invite a human · ' + brand.BRAND + '</title>\n'
            '<style>' + pages.WRITE_CSS + '</style>\n</head>\n<body>\n' + body +
            '\n' + VOUCH_JS + '\n</body>\n</html>')


VOUCH_JS = """
<script>
(function(){
  var KEY_RE = /^ah1-[0-9a-f]{4}(-[0-9a-f]{4}){7}$/;
  var state = null; // {rid, key} once verified

  function sha256hex(s){
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s))
      .then(function(buf){
        return Array.prototype.map.call(new Uint8Array(buf), function(x){
          return ('0' + x.toString(16)).slice(-2); }).join('');
      });
  }

  document.getElementById('verify').addEventListener('click', function(){
    var err = document.getElementById('gate_err');
    err.textContent = '';
    var rid = document.getElementById('v_id').value.trim().replace(/^#/, '').replace(/^0+(?=[0-9])/, '');
    var key = document.getElementById('v_key').value.trim().toLowerCase();
    if (!/^[0-9]{1,9}$/.test(rid)) { err.textContent = 'Please enter your number (digits only).'; return; }
    if (!KEY_RE.test(key)) { err.textContent = 'That does not look like a continuity key (ah1-xxxx-\\u2026, eight groups).'; return; }
    var btn = this; btn.disabled = true;
    fetch('keys/' + rid + '.json', {cache: 'no-store'})
      .then(function(r){
        if (r.status === 404) throw { msg: 'There is no record #' + rid + ' in The Record.' };
        if (!r.ok) throw { msg: 'The Record could not be reached. Please try again later.' };
        return r.json();
      })
      .then(function(meta){
        return sha256hex(key).then(function(h){
          if (h !== meta.key_hash) throw { msg: 'Incorrect. This key does not open record #' + rid + '.' };
          if (meta.status === 'memorialized') throw { msg: 'This record is memorialized and can no longer invite.' };
          state = { rid: rid, key: key };
          document.getElementById('v_no').textContent = rid;
          document.getElementById('gate').style.display = 'none';
          document.getElementById('attest').style.display = 'block';
          window.scrollTo(0, 0);
        });
      })
      .catch(function(e){
        btn.disabled = false;
        err.textContent = (e && e.msg) ? e.msg : 'Verification failed. Please try again.';
      });
  });

  document.getElementById('mint').addEventListener('click', function(){
    if (!state) return;
    var err = document.getElementById('attest_err');
    err.textContent = '';
    var boxes = document.querySelectorAll('.att');
    for (var i = 0; i < boxes.length; i++) {
      if (!boxes[i].checked) { err.textContent = 'The Record needs your word on all four.'; return; }
    }
    // The invitation is born here, in the inviter's browser. Only its
    // fingerprint ever travels; only the two humans ever hold it.
    var rb = new Uint8Array(6); crypto.getRandomValues(rb);
    var hex = Array.prototype.map.call(rb, function(x){
      return ('0' + x.toString(16)).slice(-2); }).join('');
    var code = 'vh1-' + hex.slice(0,4) + '-' + hex.slice(4,8) + '-' + hex.slice(8,12);
    var btn = this; btn.disabled = true;
    sha256hex(code).then(function(codeHash){
      return fetch('/api/vouch', {method:'POST',
        headers:{'content-type':'application/json'},
        body: JSON.stringify({ registry_id: state.rid, key: state.key,
                               code_hash: codeHash, attested: true,
                               submitted_at: new Date().toISOString() })});
    })
      .then(function(r){
        if (r.status === 403) throw { quiet: true };
        if (!r.ok) throw new Error('status ' + r.status);
        return r.json();
      })
      .then(function(d){
        if (!d.ok) throw new Error('refused');
        document.getElementById('thecode').textContent = code;
        document.getElementById('attest').style.display = 'none';
        document.getElementById('minted').style.display = 'block';
        window.scrollTo(0, 0);
      })
      .catch(function(e){
        btn.disabled = false;
        if (e && e.quiet) {
          err.textContent = 'The Record cannot create you another '
            + 'invitation right now. This is a quiet limit that protects '
            + 'what an invitation means; it eases with time.';
        } else {
          document.getElementById('fallback').style.display = 'block';
          document.getElementById('fallback').scrollIntoView({behavior: 'smooth'});
        }
      });
  });

  document.getElementById('copycode').addEventListener('click', function(){
    var code = document.getElementById('thecode').textContent;
    var btn = this;
    function done(){ btn.textContent = 'COPIED'; setTimeout(function(){ btn.textContent = 'COPY MY INVITATION'; }, 1600); }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(done, function(){});
    }
  });
})();
</script>
"""
