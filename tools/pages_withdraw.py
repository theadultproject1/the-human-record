"""The withdrawal page (withdraw.html): a human comes back with their
number and continuity key to withdraw one testimony.

The gate is the same automatic one the return page uses: the site
publishes each record's key fingerprint at keys/{n}.json; VERIFY MY
KEY hashes the entered key in the browser and compares — a match
reveals the record's testimonies, a mismatch opens nothing. The
worker re-verifies server-side on submission.

Withdrawal cannot be self-executing: the archive is append-only
files rebuilt and committed by the operator, and the worker can only
write to KV. So this page captures an *authenticated withdrawal
request*; a steward completes it with tools/withdraw.py. The words
then go from every copy of the archive; the tombstone, and the
number, stay. (Lost-key withdrawal stays out of band, by design.)
"""
import brand
import pages


def render_withdraw():
    parts = []
    parts.append('<div id="gate">')
    parts.append('<h1>Withdraw a testimony</h1>')
    parts.append(
        '<p class="meta">Withdrawal belongs to you, and only you: it needs the '
        'continuity key shown to you once, when you left a testimony. Enter your '
        'number and your key to continue. Nothing can recover a lost '
        'key: if yours is gone, it is gone, and a withdrawal cannot '
        'proceed. The Record keeps no other way in.</p>')
    parts.append(
        '<p class="banner">What withdrawal does: the words of the testimony you '
        'choose are permanently removed from every copy of the archive. A marker '
        'remains, showing that a testimony once existed here and was withdrawn, '
        'alongside the fingerprint of what was once said. Your number '
        'stays yours and is never reused. This cannot be undone.</p>')
    parts.append(
        '<div class="q"><p class="prompt">My number is…</p>'
        '<textarea id="w_id" maxlength="9" placeholder="e.g. 2"></textarea></div>')
    parts.append(
        '<div class="q"><p class="prompt">My continuity key is…</p>'
        '<textarea id="w_key" maxlength="43" '
        'placeholder="ah1-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx"></textarea></div>')
    parts.append('<p><button class="finish" id="verify">VERIFY MY KEY</button></p>')
    parts.append('<p class="err" id="gate_err"></p>')
    parts.append('<p class="meta"><a href="return.html">Leaving your next '
                 'testimony instead?</a> · <a href="index.html">Return to the '
                 'lights</a></p>')
    parts.append('</div>')

    parts.append('<div id="choose" class="hidden">')
    parts.append('<h1>Which testimony to withdraw</h1>')
    parts.append('<p class="meta">Your key opened record #<span id="rec_no"></span>. '
                 'Choose the testimony to withdraw. Take your time; nothing happens '
                 'until you confirm.</p>')
    parts.append('<div id="versions"></div>')
    parts.append('<p class="err" id="choose_err"></p>')
    parts.append('<p><button class="finish" id="withdraw">WITHDRAW THIS TESTIMONY</button></p>')
    parts.append('</div>')

    parts.append(
        '<div id="received" class="hidden">'
        '<h1>Your withdrawal request has been received</h1>'
        '<p>Your key was verified against your record\'s fingerprint. A person '
        'will complete the withdrawal; in this era, every one is done by hand. '
        'When it is done, the words will be gone from every copy of the archive '
        'and a tombstone will remain in their place. Your number stays '
        'yours and is never reused.</p>'
        '<p><a href="index.html">Return to the lights</a></p>'
        '</div>')
    parts.append(
        '<div id="fallback" class="hidden">'
        '<h2>The Record could not be reached. Nothing was lost</h2>'
        '<p>Your withdrawal was not sent, and nothing changed. Please try '
        'again when the Record is back online.</p>'
        '</div>')

    body = "\n".join(parts)
    return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>Withdraw a testimony · ' + brand.BRAND + '</title>\n'
            '<style>' + pages.WRITE_CSS + '</style>\n</head>\n<body>\n' + body +
            '\n' + pages.MODAL_JS + '\n' + WITHDRAW_JS + '\n</body>\n</html>')


WITHDRAW_JS = """
<script>
(function(){
  var KEY_RE = /^ah1-[0-9a-f]{4}(-[0-9a-f]{4}){7}$/;
  var LABEL = {1: 'First', 2: 'Second', 3: 'Final'};
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
    var rid = document.getElementById('w_id').value.trim().replace(/^#/, '').replace(/^0+(?=[0-9])/, '');
    var key = document.getElementById('w_key').value.trim().toLowerCase();
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
          if (!meta.versions) throw { msg: 'This record holds no testimony to withdraw.' };
          state = { rid: rid, key: key };
          document.getElementById('rec_no').textContent = rid;
          // Built with createElement + textContent, never innerHTML:
          // nothing here is user text today, and this keeps it safe on
          // the day someone adds a field that is.
          var box = document.getElementById('versions');
          while (box.firstChild) box.removeChild(box.firstChild);
          for (var v = 1; v <= meta.versions; v++) {
            var lab = document.createElement('label');
            lab.className = 'wv';
            var radio = document.createElement('input');
            radio.type = 'radio'; radio.name = 'wv'; radio.value = String(v);
            if (v === 1) radio.checked = true;
            lab.appendChild(radio);
            lab.appendChild(document.createTextNode(' ' + LABEL[v] + ' Testimony'));
            box.appendChild(lab);
          }
          document.getElementById('gate').style.display = 'none';
          document.getElementById('choose').style.display = 'block';
          window.scrollTo(0, 0);
        });
      })
      .catch(function(e){
        btn.disabled = false;
        err.textContent = (e && e.msg) ? e.msg : 'Verification failed. Please try again.';
      });
  });

  document.getElementById('withdraw').addEventListener('click', function(){
    if (!state) return;
    var err = document.getElementById('choose_err');
    err.textContent = '';
    var sel = document.querySelector('input[name=wv]:checked');
    if (!sel) { err.textContent = 'Please choose which testimony to withdraw.'; return; }
    var version = Number(sel.value);
    var label = LABEL[version];
    var btn = this;
    ahConfirm({
      title: 'Withdraw your ' + label + ' Testimony?',
      lines: [
        'Its words will be permanently removed from the archive. A tombstone '
          + 'will remain, showing a testimony once existed here and was withdrawn.',
        'Your number stays spent. This cannot be undone.'
      ],
      ok: 'WITHDRAW IT', cancel: 'Keep it'
    }).then(function(go){
      if (!go) return;
    btn.disabled = true;
    fetch('/api/withdraw', {method:'POST',
        headers:{'content-type':'application/json'},
        body: JSON.stringify({ registry_id: state.rid, version: version,
                               key: state.key, submitted_at: new Date().toISOString() })})
      .then(function(r){ if (!r.ok) throw new Error('status ' + r.status); return r.json(); })
      .then(function(){
        document.getElementById('received').style.display = 'block';
        document.getElementById('choose').style.display = 'none';
        window.scrollTo(0, 0);
      })
      .catch(function(){
        btn.disabled = false;
        document.getElementById('fallback').style.display = 'block';
        document.getElementById('fallback').scrollIntoView({behavior: 'smooth'});
      });
    });
  });
})();
</script>
"""
