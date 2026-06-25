#!/usr/bin/env python3
"""
app.py - a clean local web GUI for the tutor.

Reuses the retrieval logic and TUTOR_PERSONA from tutor.py (so that file stays
the one place you tune how it teaches). Run this instead of tutor.py when you
want the window instead of the terminal.

  pip install flask
  python app.py
  then open http://localhost:5000

Keep tutor.py and store.json in this same folder.
"""

from flask import Flask, request, Response, render_template_string
import ollama
from tutor import load_store, retrieve, build_context, TUTOR_PERSONA, CHAT_MODEL

app = Flask(__name__)

records, mat = load_store()
sources = sorted(set(r["source"] for r in records))
messages = [{"role": "system", "content": TUTOR_PERSONA}]

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Tutor</title>
<style>
:root{--bg:#14161b;--panel:#1a1d24;--panel2:#21262f;--line:#2a2f38;--text:#e4e8ef;
--muted:#8a92a0;--accent:#58a7bd;--mono:ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace;
--sans:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);
display:flex;flex-direction:column;height:100vh}
header{border-bottom:1px solid var(--line);padding:14px 20px;background:var(--panel)}
.title{font-family:var(--mono);font-size:18px;letter-spacing:.04em}
.sub{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:4px}
details{margin-top:6px}summary{font-family:var(--mono);font-size:12px;color:var(--accent);cursor:pointer}
.srcs{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:6px;line-height:1.6;max-height:120px;overflow:auto}
#log{flex:1;overflow-y:auto;padding:22px;max-width:820px;width:100%;margin:0 auto}
.msg{margin-bottom:18px;display:flex;flex-direction:column}
.who{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:5px}
.bubble{padding:12px 15px;border-radius:10px;border:1px solid var(--line);white-space:pre-wrap;line-height:1.55}
.user .bubble{background:var(--panel2);align-self:flex-end;max-width:80%}
.user .who{align-self:flex-end}
.tutor .bubble{background:var(--panel);border-left:3px solid var(--accent)}
footer{border-top:1px solid var(--line);background:var(--panel);padding:12px;display:flex;
gap:10px;max-width:820px;width:100%;margin:0 auto}
textarea{flex:1;resize:none;background:var(--bg);color:var(--text);border:1px solid var(--line);
border-radius:8px;padding:11px 13px;font-family:var(--sans);font-size:15px;height:46px;line-height:1.4}
textarea:focus{outline:none;border-color:var(--accent)}
button{background:var(--accent);color:#06222b;border:none;border-radius:8px;padding:0 18px;
font-weight:600;cursor:pointer;font-family:var(--sans);font-size:14px}
button.ghost{background:transparent;color:var(--muted);border:1px solid var(--line)}
button:disabled{opacity:.5;cursor:default}
</style></head><body>
<header>
  <div class="title">AI Tutor</div>
  <div class="sub">{{model}} &middot; {{count}} chunks indexed</div>
  <details><summary>{{sources|length}} sources loaded</summary>
    <div class="srcs">{% for s in sources %}{{s}}<br>{% endfor %}</div>
  </details>
</header>
<div id="log"></div>
<footer>
  <textarea id="q" placeholder="Ask about your material... (Enter to send, Shift+Enter for newline)"></textarea>
  <button id="send">Send</button>
  <button id="reset" class="ghost">New</button>
</footer>
<script>
const log=document.getElementById('log'), q=document.getElementById('q'),
      send=document.getElementById('send'), reset=document.getElementById('reset');

function add(who,cls){
  const m=document.createElement('div'); m.className='msg '+cls;
  const w=document.createElement('div'); w.className='who'; w.textContent=who;
  const b=document.createElement('div'); b.className='bubble';
  m.appendChild(w); m.appendChild(b); log.appendChild(m);
  log.scrollTop=log.scrollHeight; return b;
}
async function ask(){
  const text=q.value.trim(); if(!text) return;
  q.value=''; send.disabled=true;
  add('you','user').textContent=text;
  const out=add('tutor','tutor'); out.textContent='...';
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({question:text})});
    const reader=r.body.getReader(); const dec=new TextDecoder(); let acc='';
    while(true){const {done,value}=await reader.read(); if(done)break;
      acc+=dec.decode(value,{stream:true}); out.textContent=acc; log.scrollTop=log.scrollHeight;}
  }catch(e){out.textContent='[error talking to the model — is Ollama running?]';}
  send.disabled=false; q.focus();
}
send.onclick=ask;
q.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask();}});
reset.onclick=async()=>{await fetch('/reset',{method:'POST'}); log.innerHTML=''; q.focus();};
q.focus();
</script></body></html>"""


@app.route("/")
def index():
    return render_template_string(PAGE, model=CHAT_MODEL, count=len(records), sources=sources)


@app.route("/chat", methods=["POST"])
def chat():
    question = (request.json or {}).get("question", "").strip()
    if not question:
        return Response("", mimetype="text/plain")
    context = build_context(retrieve(question, records, mat))
    messages.append({"role": "user",
                     "content": "Relevant course material:\n%s\n\nMy question: %s" % (context, question)})

    def gen():
        reply = ""
        for part in ollama.chat(model=CHAT_MODEL, messages=messages, stream=True):
            piece = part["message"]["content"]
            reply += piece
            yield piece
        messages.append({"role": "assistant", "content": reply})

    return Response(gen(), mimetype="text/plain")


@app.route("/reset", methods=["POST"])
def reset():
    global messages
    messages = [{"role": "system", "content": TUTOR_PERSONA}]
    return "ok"


if __name__ == "__main__":
    print("Tutor GUI running -> open http://localhost:5000")
    app.run(port=5000, debug=False)
