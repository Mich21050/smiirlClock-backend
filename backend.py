#!/usr/bin/env python3

import json, os, re, datetime, threading
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

SP = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.environ.get("STATE_FILE", os.path.join(SP, "state.json"))
VERSION = "smiirl_2.0.7-1"
POLL_INTERVAL = 20
RECOVERY_TOKEN = "v2qP0mMGzKN6"
VALID = re.compile(r"^[0-9a-zA-Z]{1,20}$")   # digits + separator letters (JSON-safe)

STATE = {"mode": "number", "value": "0"}
_lock = threading.Lock()

def load_state():
    try:
        s = json.load(open(STATE_FILE))
        STATE["mode"] = s["mode"] if s.get("mode") in ("number", "clock") else "number"
        STATE["value"] = str(s.get("value", "0"))
    except Exception:
        pass

def save_state():
    tmp = STATE_FILE + ".tmp"
    with _lock:
        with open(tmp, "w") as f:
            json.dump(STATE, f)
        os.replace(tmp, STATE_FILE)

def display_value():
    if STATE["mode"] == "clock":
        now = datetime.datetime.now()
        return f"{now.hour:02d}b{now.minute:02d}"      # 14:30 -> "14b30"
    v = STATE["value"]
    return int(v) if v.isdigit() else v                # plain digits -> int; else string

def config_for(mac, extra=None):
    d = {"result": True}
    if extra: d.update(extra)
    d.update({"v": VERSION, "attribute": "number",
              "url": f"http://api.smiirl.com/{mac}/number",
              "interval": POLL_INTERVAL, "code": 200})
    return d

load_state()

app = FastAPI(title="Smiirl backend")

@app.middleware("http")
async def clocklike_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["connection"] = "close"
    resp.headers["server"] = "nginx"
    resp.headers["access-control-allow-origin"] = "*"
    return resp

# ---------- clock protocol ----------
@app.get("/number")
def bare_number():
    return {"number": 1}

@app.get("/v1.0/register/{mac}")
def register(mac: str):
    return {"result": True}

@app.get("/v1.0/recover/{code}/{mac}")
def recover(code: str, mac: str):
    return {"result": True, "recovery": True, "id": mac, "token": RECOVERY_TOKEN}

@app.get("/v1.0/{mac}/{token}")
def cfg(mac: str, token: str):
    return config_for(mac)

@app.post("/v1.0/{mac}/{token}/status")
async def status(mac: str, token: str):
    return config_for(mac, {"status": True})

@app.get("/{mac}/number")
def mac_number(mac: str):
    return {"number": display_value()}

# ---------- control API ----------
@app.get("/api/state")
def api_state():
    return {"mode": STATE["mode"], "value": STATE["value"], "display": display_value()}

@app.post("/api/config")
async def api_config(req: Request):
    body = await req.json()
    changed = False
    if "mode" in body:
        if body["mode"] not in ("number", "clock"):
            return JSONResponse({"ok": False, "error": "mode must be 'number' or 'clock'"}, 400)
        STATE["mode"] = body["mode"]; changed = True
    if "value" in body:
        v = str(body["value"]).strip()
        if not VALID.match(v):
            return JSONResponse({"ok": False, "error": "value must be digits/letters e.g. 1234 or 01b20"}, 400)
        STATE["value"] = v; STATE["mode"] = "number"; changed = True
    if changed: save_state()
    return {"ok": True, "mode": STATE["mode"], "value": STATE["value"], "display": display_value()}

@app.get("/set/{value}")
def set_value(value: str):
    v = value.strip()
    if not VALID.match(v):
        return JSONResponse({"ok": False, "error": "value must be digits/letters e.g. 1234 or 01b20"}, 400)
    STATE["value"] = v; STATE["mode"] = "number"; save_state()
    return {"ok": True, "mode": "number", "value": v, "display": display_value()}

@app.get("/mode/{mode}")
def set_mode(mode: str):
    if mode not in ("number", "clock"):
        return JSONResponse({"ok": False, "error": "mode must be 'number' or 'clock'"}, 400)
    STATE["mode"] = mode; save_state()
    return {"ok": True, "mode": mode, "display": display_value()}

# ---------- web UI ----------
@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

HTML = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Clock Webui</title>
<style>
:root{color-scheme:light dark}
body{font-family:system-ui,sans-serif;max-width:26rem;margin:3rem auto;text-align:center;padding:0 1rem}
.disp{font-size:3.2rem;font-weight:800;letter-spacing:.05em;margin:.4rem 0}
.modes{display:flex;gap:.5rem;justify-content:center;margin:1rem 0}
.modes button{flex:1;font-size:1.1rem;padding:.6rem;border:2px solid #8884;border-radius:.6rem;background:#8881;cursor:pointer}
.modes button.on{border-color:#3b82f6;background:#3b82f633;font-weight:700}
input{font-size:1.8rem;width:9rem;text-align:center;padding:.2rem}
.set button{font-size:1.1rem;padding:.5rem 1.2rem;margin-left:.4rem}
small{color:#888}
</style></head><body>
<h1>Clock Webui</h1>
<div class=disp id=disp>—</div>
<div class=modes>
  <button id=m-number onclick="setMode('number')">Number</button>
  <button id=m-clock  onclick="setMode('clock')">Clock</button>
</div>
<div class=set id=numbox>
  <input id=val type=text placeholder="1234 or 01b20">
  <button onclick="save()">Set</button>
  <p><small>digits, or add a separator letter: <code>01b20</code></small></p>
</div>
<script>
async function refresh(){
  const s = await (await fetch('/api/state')).json();
  document.getElementById('disp').textContent = s.display;
  document.getElementById('m-number').classList.toggle('on', s.mode==='number');
  document.getElementById('m-clock').classList.toggle('on', s.mode==='clock');
  document.getElementById('numbox').style.opacity = s.mode==='number' ? 1 : .45;
  if(document.activeElement.id!=='val') document.getElementById('val').value = s.mode==='number'? s.value : '';
}
async function setMode(m){ await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:m})}); refresh(); }
async function save(){
  const v=document.getElementById('val').value.trim(); if(!v) return;
  const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:v})});
  if(!r.ok){ alert((await r.json()).error); return; } refresh();
}
document.getElementById('val').addEventListener('keydown',e=>{ if(e.key==='Enter') save(); });
refresh(); setInterval(refresh, 3000);
</script></body></html>"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "80"))
    uvicorn.run(app, host="0.0.0.0", port=port, server_header=False, log_level="info")
