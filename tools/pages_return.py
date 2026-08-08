"""The return page (return.html): a human comes back with their
number and continuity key to enter their Second or Final
Testimony.

The gate is automatic. The site publishes each record's key
fingerprint at keys/{n}.json; VERIFY MY KEY hashes the entered key
in the browser and compares — a match reveals the questions, a
mismatch opens nothing. The worker re-verifies server-side on
submission, and tools/testify.py verifies a third time at the
ceremony. The key itself is never stored anywhere.

Which testimony this is (Second or Final) is decided by the record
itself: the published metadata carries the count of spent slots.
"""
import html

import brand
import pages


def render_return(qmeta):
    cap = qmeta["answer_char_cap"]
    name_cap = pages.NAME_CAP
    qbyid = {item["id"]: item for item in qmeta["questions"]}
    shared = [q for q in qmeta["testimony_order"]["second"]
              if q not in ("q_reflect_second", "q_letter")]

    parts = []
    parts.append('<div id="gate">')
    parts.append('<h1>Returning to my record</h1>')
    parts.append(
        '<p class="meta">A record grows only by the hand that holds its key. '
        'Enter your number and the continuity key shown to you once, '
        'when you left your First Testimony. Nothing can recover a lost key.</p>')
    parts.append(
        '<div class="q"><p class="prompt">My number is…</p>'
        '<textarea id="ret_id" maxlength="9" placeholder="e.g. 2"></textarea></div>')
    parts.append(
        '<div class="q"><p class="prompt">My continuity key is…</p>'
        '<textarea id="ret_key" maxlength="43" '
        'placeholder="ah1-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx"></textarea></div>')
    parts.append('<p><button class="finish" id="verify">VERIFY MY KEY</button></p>')
    parts.append('<p class="err" id="gate_err"></p>')
    parts.append('<p class="center quiet"><a href="index.html">return to the lights</a></p>')
    parts.append('</div>')

    parts.append('<div id="writing" class="hidden">')
    parts.append('<h1 id="kind_title">My Testimony</h1>')
    parts.append('<p class="meta">Your key opened your record. This sitting is '
                 'permanent once entered. Take your time. Every answer except '
                 'your name is optional; each holds at most %d characters, '
                 'your name at most %d.</p>' % (cap, name_cap))
    parts.append('<p class="err" id="errors"></p>')

    def question_block(qid, extra_cls=""):
        q = qbyid[qid]
        qcap = name_cap if qid == "q_name" else cap
        hidden = ' hidden' if extra_cls else ''
        out = ['<div class="q %s%s">' % (extra_cls, hidden)]
        out.append('<p class="prompt">%s</p>' % html.escape(q["prompt"]))
        if q.get("note"):
            out.append('<p class="note">%s</p>' % html.escape(q["note"]))
        out.append('<textarea id="%s" maxlength="%d"></textarea>' % (qid, qcap))
        out.append('<div class="under"><label class="seal">'
                   '<input type="checkbox" id="%s_seal"> seal this answer until my death'
                   '</label><span id="%s_count"></span></div>' % (qid, qid))
        if qid in ("q_hardest", "q_regret"):
            out.append('<p class="help">%s</p>' % pages.HELP_LINE)
        out.append('</div>')
        return "\n".join(out)

    for qid in shared:
        parts.append(question_block(qid))
    parts.append(question_block("q_reflect_second", "second-only"))
    parts.append(question_block("q_reflect_final", "final-only"))
    parts.append(question_block("q_letter"))

    parts.append('<p><button class="finish" id="finish">COMPLETE MY TESTIMONY</button></p>')
    parts.append('</div>')

    parts.append(
        '<div id="received">'
        '<h1>Your testimony has been received</h1>'
        '<p>Your key was verified against your record\'s fingerprint. Your '
        'words will be read by a person, as every testimony is in this era, '
        'and once accepted they will appear on your page. Your continuity '
        'key remains yours alone; it was not stored.</p>'
        '<p class="meta">__BRAND__ is free, for every human, always, kept '
        'alive by donations, every dollar public: '
        '<a href="' + brand.DONATE_URL + '" rel="noopener">help '
        'keep the lights on</a>.</p>'
        '<p><a href="index.html">Return to the lights</a></p>'
        '</div>')
    parts.append(
        '<div id="fallback">'
        '<h2>The Record could not be reached. Nothing was lost</h2>'
        '<p>Your testimony is safe on this page. Download it now, and submit '
        'it again when the Record is back online.</p>'
        '<p><a id="download" class="finish" href="#">DOWNLOAD MY TESTIMONY</a></p>'
        '<pre id="fjson"></pre>'
        '</div>')

    body = "\n".join(parts)
    js = (RETURN_JS
          .replace("__CAP__", str(cap))
          .replace("__NAME_CAP__", str(name_cap))
          )
    return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>Returning · ' + brand.BRAND + '</title>\n'
            '<style>' + pages.WRITE_CSS + '</style>\n</head>\n<body>\n' + body +
            '\n' + pages.MODAL_JS + '\n' + js + '\n</body>\n</html>').replace('__BRAND__', brand.BRAND)


RETURN_JS = """
<script>
(function(){
  var CAP = __CAP__, NAME_CAP = __NAME_CAP__;
  var KEY_RE = /^ah1-[0-9a-f]{4}(-[0-9a-f]{4}){7}$/;
  var state = null; // {rid, key, kind} once verified

  function sha256hex(s){
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s))
      .then(function(buf){
        return Array.prototype.map.call(new Uint8Array(buf), function(x){
          return ('0' + x.toString(16)).slice(-2); }).join('');
      });
  }

  var areas = document.querySelectorAll('#writing textarea');
  for (var i = 0; i < areas.length; i++) (function(ta){
    var cap = ta.id === 'q_name' ? NAME_CAP : CAP;
    var counter = document.getElementById(ta.id + '_count');
    function tick(){ counter.textContent = ta.value.length + ' / ' + cap; }
    ta.addEventListener('input', tick); tick();
  })(areas[i]);

  document.getElementById('verify').addEventListener('click', function(){
    var err = document.getElementById('gate_err');
    err.textContent = '';
    var rid = document.getElementById('ret_id').value.trim().replace(/^#/, '').replace(/^0+(?=[0-9])/, '');
    var key = document.getElementById('ret_key').value.trim().toLowerCase();
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
          if (meta.status === 'memorialized') throw { msg: 'This record is memorialized and can no longer grow.' };
          if (meta.versions >= 3) throw { msg: 'This record is complete: three testimonies, a whole life.' };
          if (meta.eligible_after && new Date() < new Date(meta.eligible_after)) throw { msg: 'There is at least a year between testimonies. Experience life and come back after ' + meta.eligible_after.slice(0, 10) + '.' };
          state = { rid: rid, key: key,
                    kind: meta.versions === 1 ? 'second' : 'final' };
          var label = state.kind === 'second' ? 'Second' : 'Final';
          document.getElementById('kind_title').textContent = 'My ' + label + ' Testimony';
          document.querySelector('.second-only').style.display = (state.kind === 'second') ? 'block' : 'none';
          document.querySelector('.final-only').style.display = (state.kind === 'final') ? 'block' : 'none';
          document.getElementById('gate').style.display = 'none';
          document.getElementById('writing').style.display = 'block';
          window.scrollTo(0,0);
        });
      })
      .catch(function(e){
        btn.disabled = false;
        err.textContent = (e && e.msg) ? e.msg : 'Verification failed. Please try again.';
      });
  });

  function build(){
    var name = document.getElementById('q_name').value.trim();
    if (!name) return { error: 'Your name is the one required answer.' };
    if (name.length > NAME_CAP) return { error: 'Your name can hold at most ' + NAME_CAP + ' characters.' };
    var skip = (state.kind === 'second') ? 'q_reflect_final' : 'q_reflect_second';
    var answers = {};
    for (var i = 0; i < areas.length; i++) {
      var ta = areas[i];
      if (ta.id === skip) continue;
      var text = ta.value.trim();
      if (!text) continue;
      var sealed = document.getElementById(ta.id + '_seal').checked;
      answers[ta.id] = { text: text, visibility: sealed ? 'sealed_until_death' : 'public' };
    }
    return { payload: { registry_id: state.rid, kind: state.kind, key: state.key,
                        sitting: { answers: answers },
                        submitted_at: new Date().toISOString() } };
  }

  function showFallback(p){
    var safe = { registry_id: p.registry_id, kind: p.kind, sitting: p.sitting };
    var jsonText = JSON.stringify(safe, null, 2);
    var blob = new Blob([jsonText], {type: 'application/json'});
    var dl = document.getElementById('download');
    dl.href = URL.createObjectURL(blob);
    dl.download = 'my-' + p.kind + '-testimony.json';
    document.getElementById('fjson').textContent = jsonText;
    document.getElementById('fallback').style.display = 'block';
    document.getElementById('fallback').scrollIntoView({behavior: 'smooth'});
  }

  document.getElementById('finish').addEventListener('click', function(){
    if (!state) return;
    var errbox = document.getElementById('errors');
    errbox.textContent = '';
    var built = build();
    if (built.error) { errbox.textContent = built.error; window.scrollTo(0,0); return; }
    var label = state.kind === 'final' ? 'Final' : 'Second';
    var btn = this;
    ahConfirm({
      title: 'Seal your ' + label + ' Testimony?',
      lines: [
        (state.kind === 'final'
          ? 'This is the last testimony your record can ever hold.'
          : 'This is your ' + label + ' Testimony.'),
        'Once you continue, it will be sealed in history. It can never be '
          + 'edited, only withdrawn.'
      ],
      ok: 'SEAL IT IN HISTORY', cancel: 'Not yet'
    }).then(function(go){
      if (!go) return;
    btn.disabled = true;
    fetch('/api/return', {method:'POST',
        headers:{'content-type':'application/json'},
        body: JSON.stringify(built.payload)})
      .then(function(r){ if (!r.ok) throw new Error('status ' + r.status); return r.json(); })
      .then(function(){
        document.getElementById('received').style.display = 'block';
        document.getElementById('writing').style.display = 'none';
        window.scrollTo(0,0);
      })
      .catch(function(){
        btn.disabled = false;
        showFallback(built.payload);
      });
    });
  });
})();
</script>
"""
