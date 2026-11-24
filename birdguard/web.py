"""Small web dashboard: live view, status, event history, test buttons.

Open http://<pi-address>:8080 on your phone (via Tailscale when away).
"""

from __future__ import annotations

import logging
import time

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from .app import BirdGuard

log = logging.getLogger(__name__)

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BirdGuard</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--text:#1d2228;--muted:#69727d;--accent:#2f7d4f;--warn:#b3541e;--line:#e2e5e9}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--card:#1e2226;--text:#e8eaed;--muted:#9aa3ad;--accent:#5cc28a;--warn:#f0a35e;--line:#2c3237}}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--text)}
main{max-width:860px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0 14px}h2{font-size:15px;margin:0 0 10px;color:var(--muted);font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:14px}
.live{width:100%;border-radius:8px;display:block;background:#000;aspect-ratio:4/3;object-fit:contain}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}
.stat b{display:block;font-size:20px}.stat span{color:var(--muted);font-size:12px}
.ok{color:var(--accent)}.warn{color:var(--warn)}
.btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
button{font:inherit;padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--text);cursor:pointer}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.ev{display:flex;gap:10px;padding:8px 0;border-top:1px solid var(--line);align-items:center}
.ev:first-child{border-top:0}.ev img{width:96px;height:72px;object-fit:cover;border-radius:6px;flex:none}
.ev small{color:var(--muted)}#msg{color:var(--muted);min-height:1.4em;margin-top:8px}
</style></head><body><main>
<h1>&#128038; BirdGuard</h1>
<div class="card"><img class="live" src="stream.mjpg" alt="live camera"></div>
<div class="card"><h2>Status</h2>
 <div class="grid" id="stats"></div>
 <div class="btns">
  <button class="primary" onclick="post('api/test-sound')">&#128266; Test sound</button>
  <button id="toggle" onclick="toggle()">Pause</button>
  <button id="sim" style="display:none" onclick="post('api/simulate-bird')">&#128038; Simulate bird</button>
 </div><div id="msg"></div>
</div>
<div class="card"><h2>Recent events</h2><div id="events">Loading...</div></div>
</main><script>
let st={};
const $=id=>document.getElementById(id);
function stat(v,l,c){return `<div class="stat"><b class="${c||''}">${v}</b><span>${l}</span></div>`}
async function refresh(){
 try{
  st=await (await fetch('api/status')).json();
  $('stats').innerHTML=
   stat(!st.enabled?'Paused':st.active_hours?'Active':'Quiet hours','Mode ('+st.schedule+')',st.enabled&&st.active_hours?'ok':'warn')+
   stat(st.playing?'Playing':st.cooldown_remaining>0?st.cooldown_remaining.toFixed(0)+'s':'Ready','Cooldown')+
   stat(st.triggers_today,'Chased today')+
   stat(st.last_bird_seen?st.last_bird_seen.slice(11):'-','Last bird seen')+
   stat(st.fps,'Camera FPS')+
   stat(st.notifications?'On':'Off','Phone alerts');
  $('toggle').textContent=st.enabled?'Pause':'Resume';
  $('sim').style.display=st.can_simulate?'':'none';
  if(st.last_error)$('msg').textContent=st.last_error;
 }catch(e){$('msg').textContent='Connection lost...'}
}
async function events(){
 const ev=await (await fetch('api/events')).json();
 const names={triggered:'Bird chased away',quiet_hours:'Bird seen (quiet hours, no sound)',test:'Manual test'};
 $('events').innerHTML=ev.length?ev.map(e=>`<div class="ev">${e.snapshot?`<a href="snapshots/${e.snapshot}" target="_blank"><img src="snapshots/${e.snapshot}" loading="lazy"></a>`:''}
  <div><b>${names[e.type]||e.type}</b><br><small>${e.time.replace('T',' ')}${e.score?' &middot; '+Math.round(e.score*100)+'%':''}${e.sound?' &middot; '+e.sound.join(', '):''}</small></div></div>`).join(''):'No events yet.';
}
async function post(url,body){
 const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
 const j=await r.json();$('msg').textContent=j.ok?'Done.':(j.reason||'Failed');
 refresh();setTimeout(events,800);
}
function toggle(){post('api/enable',{enabled:!st.enabled})}
refresh();events();setInterval(refresh,2000);setInterval(events,10000);
</script></body></html>"""


def create_app(guard: BirdGuard) -> Flask:
    app = Flask(__name__)
    app.logger.setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    snap_dir = guard.events.snap_dir

    @app.get("/")
    def index():
        return Response(PAGE, mimetype="text/html")

    @app.get("/stream.mjpg")
    def stream():
        def frames():
            last = -1
            while True:
                if guard.frame_seq != last and guard.latest_jpeg:
                    last = guard.frame_seq
                    jpeg = guard.latest_jpeg
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                           + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                time.sleep(0.05)
        return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/snapshot.jpg")
    def snapshot():
        if not guard.latest_jpeg:
            abort(503)
        return Response(guard.latest_jpeg, mimetype="image/jpeg")

    @app.get("/snapshots/<path:name>")
    def snapshots(name: str):
        return send_from_directory(snap_dir, name)

    @app.get("/api/status")
    def status():
        return jsonify(guard.status())

    @app.get("/api/events")
    def events():
        return jsonify(guard.events.latest(50))

    @app.post("/api/test-sound")
    def test_sound():
        return jsonify(guard.test_deterrents())

    @app.post("/api/enable")
    def enable():
        guard.enabled = bool((request.get_json(silent=True) or {}).get("enabled", True))
        log.info("deterrent %s from web page", "enabled" if guard.enabled else "paused")
        return jsonify({"ok": True, "enabled": guard.enabled})

    @app.post("/api/simulate-bird")
    def simulate_bird():
        if not guard.detector.can_simulate:
            return jsonify({"ok": False, "reason": "only available with the simulated backend"})
        guard.detector.inject_bird()
        return jsonify({"ok": True})

    return app
