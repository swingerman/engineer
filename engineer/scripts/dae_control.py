#!/usr/bin/env python3
"""dae_control.py — served, live control surface (read-only, v1).

A local web view of the project: a feature x checkpoint PIPELINE board and an
ARCHITECTURE map (layer nodes + import edges + health). Reads the same artifacts
the pipeline already writes, reusing dae_dashboard + dae_arch. No writes, no
dispatch, nothing sensitive leaves 127.0.0.1.

  dae_control.py [START_DIR] [--port N] [--window N]   serve at http://127.0.0.1:PORT
  dae_control.py --json [START_DIR]                    print the state blob and exit (headless)

stdlib-only. Ctrl-C to stop.
"""
import http.server
import json
import os
import re
import sys
import time

import dae_arch
import dae_dashboard
import dae_metrics
import dae_resolve

DEFAULT_PORT = 8770
_WINDOW = 90  # DORA operational window (days); set by main via --window
_CACHE_TTL = 5.0  # ponytail: rebuild state at most every 5s; the import graph is
                  # the expensive part and a polling page doesn't need it fresher.

_CP_NUM_RE = re.compile(r"(?m)^checkpoint:\s*([0-9.]+)\s*$")


def _handoff_checkpoint(feature_dir):
    """Highest `checkpoint:` across a feature's handoffs -> stage index, or -1.
    Features tracked via handoffs/ (not progress.md) are invisible to the
    dashboard's progress.md heuristic; this recovers their pipeline position."""
    hdir = os.path.join(feature_dir, "handoffs")
    if not os.path.isdir(hdir):
        return -1
    best = -1
    for name in os.listdir(hdir):
        try:
            with open(os.path.join(hdir, name), encoding="utf-8", errors="replace") as fh:
                for m in _CP_NUM_RE.findall(fh.read()):
                    best = max(best, dae_dashboard._CP_INDEX.get(m, -1))
        except OSError:
            continue
    return best


def build_state(start_dir):
    """The single source of truth feeding both the JSON API and the page.
    Reuses dae_dashboard.build_data (features + component violations) and
    dae_arch.graph (layer nodes + import edges)."""
    data = dae_dashboard.build_data(start_dir)
    root = data.get("root") or os.path.abspath(start_dir)

    # Recover checkpoint for in-flight features that use handoffs/ not progress.md
    for f in data.get("features", []):
        if f.get("reached", -1) < 0 and f.get("status") not in ("done",):
            idx = _handoff_checkpoint(os.path.join(root, "features", f["slug"]))
            if idx >= 0:
                f["reached"] = idx
                f["checkpoint"] = dae_dashboard.CP_STAGES[idx][0]
                f["pct"] = round(idx / (len(dae_dashboard.CP_STAGES) - 1), 3)

    g = dae_arch.graph(start_dir)
    comps = data.get("components", {})
    vio_by_layer = {l["name"]: l.get("violations", 0) for l in comps.get("layers", [])}
    for l in g["layers"]:
        l["violations"] = vio_by_layer.get(l["name"], 0)
    data["components"] = {
        "arch_supported": g["arch_supported"],
        "layers": g["layers"],
        "edges": g["edges"],
        "violations": comps.get("violations", []),
    }
    try:
        data["metrics"] = dae_metrics.compute(start_dir, _WINDOW)
    except Exception as e:  # metrics are a bonus panel, never a hard failure
        data["metrics"] = {"error": str(e), "dora": None, "governance": []}
    data["generated_at"] = int(time.time())
    return data


_cache = {"t": 0.0, "dir": None, "data": None}


def cached_state(start_dir):
    now = time.time()
    if (_cache["data"] is None or _cache["dir"] != start_dir
            or now - _cache["t"] > _CACHE_TTL):
        _cache.update(t=now, dir=start_dir, data=build_state(start_dir))
    return _cache["data"]


def _make_handler(start_dir):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the terminal quiet
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, _PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/state":
                body = json.dumps(cached_state(start_dir)).encode("utf-8")
                self._send(200, body, "application/json")
            else:
                self._send(404, b"not found", "text/plain; charset=utf-8")

    return Handler


def serve(start_dir, port):
    handler = _make_handler(start_dir)
    try:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)  # port taken -> ephemeral
    url = "http://127.0.0.1:%d/" % httpd.server_address[1]
    sys.stdout.write("control surface: %s  (Ctrl-C to stop)\n" % url)
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
    return url


def main(argv):
    args = list(argv)
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    as_json = "--json" in args
    if as_json:
        args.remove("--json")
    port = DEFAULT_PORT
    if "--port" in args:
        i = args.index("--port")
        try:
            port = int(args[i + 1])
        except (IndexError, ValueError):
            sys.stderr.write("--port needs an integer\n")
            return 3
        del args[i:i + 2]
    if "--window" in args:
        i = args.index("--window")
        try:
            global _WINDOW
            _WINDOW = int(args[i + 1])
        except (IndexError, ValueError):
            sys.stderr.write("--window needs an integer\n")
            return 3
        del args[i:i + 2]
    start_dir = args[0] if args else os.getcwd()
    if as_json:
        json.dump(build_state(start_dir), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    serve(start_dir, port)
    return 0


# --- the served page (vanilla JS, no deps, fetches /api/state, polls live) ----

_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>engineer · control</title>
<style>
:root{--bg:#0f1115;--card:#1a1d24;--line:#2a2f3a;--fg:#e6e9ef;--mut:#8b93a3;
--ok:#3fb950;--wip:#d29922;--empty:#30363d;--bad:#f85149;--blue:#58a6ff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:16px 24px;border-bottom:1px solid var(--line);display:flex;
align-items:baseline;gap:14px;flex-wrap:wrap}
h1{margin:0;font-size:17px}.sub{color:var(--mut);font-size:13px}
.live{margin-left:auto;color:var(--mut);font-size:12px}
.live b{color:var(--ok)}
nav{display:flex;gap:4px;padding:0 24px;border-bottom:1px solid var(--line)}
nav button{background:none;border:none;color:var(--mut);padding:12px 14px;
cursor:pointer;font-size:14px;border-bottom:2px solid transparent}
nav button.on{color:var(--fg);border-bottom-color:var(--blue)}
main{padding:18px 24px;max-width:1200px}
.legend{color:var(--mut);font-size:12px;margin:0 0 14px}
.legend span{margin-right:16px}.dot{display:inline-block;width:10px;height:10px;
border-radius:2px;vertical-align:-1px;margin-right:5px}
.row{display:grid;grid-template-columns:230px 1fr 96px;gap:14px;align-items:center;
padding:8px 0;border-bottom:1px solid var(--line);cursor:pointer}
.row:hover{background:#ffffff08}
.row .t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .t b{font-weight:600}.row .t .m{color:var(--mut);font-size:12px}
.bar{display:flex;gap:3px}
.seg{flex:1;height:20px;border-radius:3px;background:var(--empty);position:relative}
.seg.done{background:var(--ok)}.seg.wip{background:var(--wip)}
.seg .lb{position:absolute;inset:0;display:flex;align-items:center;
justify-content:center;font-size:9px;color:#0009;font-weight:600}
.pill{font-size:11px;padding:2px 8px;border-radius:20px;text-align:center;font-weight:600}
.st-done{background:#1f6f2e;color:#d7ffd9}.st-ready{background:#1b436e;color:#cfe6ff}
.st-in-progress{background:#7a5a10;color:#ffe9b3}
.st-parked,.st-unknown,.st-merged-unverified{background:#333;color:#bbb}
.detail{background:var(--card);border:1px solid var(--line);border-radius:6px;
padding:8px 12px;margin:-2px 0 8px;font-size:12px;color:var(--mut)}
.detail b{color:var(--fg)}
.archwrap{display:flex;gap:20px;flex-wrap:wrap}
svg{background:var(--card);border:1px solid var(--line);border-radius:8px}
.side{flex:1;min-width:240px}
.node rect{cursor:pointer}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:12px 14px;margin-bottom:10px}
.card h3{margin:0 0 4px;font-size:14px}
.card .paths{color:var(--mut);font-size:12px;font-family:ui-monospace,monospace;
word-break:break-all}
.badge{font-size:11px;padding:1px 7px;border-radius:20px;font-weight:600;margin-left:6px}
.badge.ok{background:#1f6f2e;color:#d7ffd9}.badge.bad{background:#7a1d1d;color:#ffd7d7}
.empty{color:var(--mut);padding:36px 0;text-align:center}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.tile .tv{font-size:26px;font-weight:700}.tile .tv .u{font-size:14px;color:var(--mut);font-weight:600;margin-left:2px}
.tile .tl{font-size:13px;margin-top:2px}.tile .ts{font-size:11px;color:var(--mut);margin-top:4px}
.sec{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.05em;margin:20px 0 8px}
table.gov{border-collapse:collapse;width:100%;max-width:560px}
table.gov th{text-align:left;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em;padding:4px 10px;border-bottom:1px solid var(--line)}
table.gov td{padding:5px 10px;border-bottom:1px solid var(--line);font-size:13px}
.slug{font-family:ui-monospace,monospace;font-size:13px}.idle{padding:8px 0}
.vio{margin-top:8px;font-size:12px;font-family:ui-monospace,monospace;color:var(--mut)}
.vio div{padding:2px 0;border-top:1px dashed var(--line)}
</style></head><body>
<header><h1>engineer · control</h1><div class="sub" id="sub"></div>
<div class="live" id="live"></div></header>
<nav><button id="tabP" class="on">Pipeline</button><button id="tabA">Architecture</button><button id="tabM">Metrics</button></nav>
<main id="app"></main>
<script>
var D=null, TAB='P', OPEN={}, ONODE=null;
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
function segClass(f,i){if(f.status==='done')return'done';if(i<f.reached)return'done';if(i===f.reached)return'wip';return'';}
function pipeline(){
 var S=D.stages;
 var h='<div class="legend"><span><i class="dot" style="background:var(--ok)"></i>done</span>'+
  '<span><i class="dot" style="background:var(--wip)"></i>current</span>'+
  '<span><i class="dot" style="background:var(--empty)"></i>pending</span></div>';
 D.features.forEach(function(f){
  var bar=S.map(function(s,i){return '<div class="seg '+segClass(f,i)+'"><span class="lb">'+s.num+'</span></div>';}).join('');
  var pct=Math.round((f.pct||0)*100);
  h+='<div class="row" data-slug="'+esc(f.slug)+'"><div class="t"><b>'+esc(f.slug)+'</b>'+
   '<div class="m">'+esc(f.area||'')+(f.size?' · '+esc(f.size):'')+'</div></div>'+
   '<div class="bar">'+bar+'</div>'+
   '<div style="text-align:right"><span class="pill st-'+esc(f.status)+'">'+esc(f.status)+'</span>'+
   '<div class="m" style="color:var(--mut);font-size:12px">'+pct+'%</div></div></div>';
  if(OPEN[f.slug]){
   h+='<div class="detail"><b>'+esc(f.title||f.slug)+'</b>'+
    ' — checkpoint '+esc(f.checkpoint||'—')+' · autonomy '+esc(f.autonomy||'—')+
    ' · owner '+esc(f.owner||'—')+'</div>';
  }
 });
 return h;
}
function architecture(){
 var c=D.components;
 if(!c.arch_supported) return '<div class="empty">No <code>architecture:</code> layers in the manifest — nothing to map.</div>';
 var L=c.layers, E=c.edges;
 var W=340, gap=92, pad=40, boxW=200, boxH=52;
 var H=pad*2+(L.length-1)*gap+boxH;
 var pos={}; L.forEach(function(l,i){pos[l.name]={x:W/2,y:pad+i*gap+boxH/2};});
 var svg='<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">';
 svg+='<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'+
  '<path d="M0,0 L7,3 L0,6 Z" fill="#8b93a3"/></marker>'+
  '<marker id="ab" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'+
  '<path d="M0,0 L7,3 L0,6 Z" fill="#f85149"/></marker></defs>';
 // edges first (under nodes)
 E.forEach(function(e){
  var s=pos[e.src], d=pos[e.dst]; if(!s||!d) return;
  var bad=e.kind==='forbidden'&&e.count>0;
  var rule=e.kind==='forbidden'&&e.count===0;
  var col=bad?'#f85149':(rule?'#3a3f4b':'#8b93a3');
  var bend=(s.x)+ (s.y<d.y?70:-70);
  var y1=s.y+(d.y>s.y?boxH/2:-boxH/2), y2=d.y+(d.y>s.y?-boxH/2:boxH/2);
  var mk=bad?'url(#ab)':'url(#a)';
  svg+='<path d="M'+s.x+','+y1+' C'+bend+','+y1+' '+bend+','+y2+' '+d.x+','+y2+'" '+
   'fill="none" stroke="'+col+'" stroke-width="'+(bad?2:1.3)+'" '+
   (rule?'stroke-dasharray="4 4" ':'')+'marker-end="'+mk+'"/>';
  if(e.count>0){var mx=bend,my=(y1+y2)/2; svg+='<text x="'+mx+'" y="'+my+'" fill="'+col+'" font-size="10" text-anchor="middle">'+e.count+'</text>';}
 });
 L.forEach(function(l){
  var p=pos[l.name], bad=l.violations>0||l.in_cycle;
  var stroke=bad?'#f85149':'#2a2f3a';
  svg+='<g class="node" data-name="'+esc(l.name)+'">'+
   '<rect x="'+(p.x-boxW/2)+'" y="'+(p.y-boxH/2)+'" width="'+boxW+'" height="'+boxH+'" rx="8" '+
   'fill="#1a1d24" stroke="'+stroke+'" stroke-width="1.5"/>'+
   '<text x="'+p.x+'" y="'+(p.y-4)+'" fill="#e6e9ef" font-size="13" font-weight="600" text-anchor="middle">'+esc(l.name)+'</text>'+
   '<text x="'+p.x+'" y="'+(p.y+13)+'" fill="#8b93a3" font-size="10" text-anchor="middle">'+
   l.file_count+' files · '+l.violations+' viol'+(l.in_cycle?' · cycle':'')+'</text></g>';
 });
 svg+='</svg>';
 var side='<div class="side">';
 var n=ONODE&&L.filter(function(l){return l.name===ONODE;})[0];
 if(n){
  side+='<div class="card"><h3>'+esc(n.name)+
   '<span class="badge '+(n.violations?'bad':'ok')+'">'+(n.violations?n.violations+' violations':'clean')+'</span>'+
   (n.in_cycle?'<span class="badge bad">in cycle</span>':'')+'</h3>'+
   '<div class="paths">'+n.paths.map(esc).join('<br>')+'</div>';
  if(n.may_not_import&&n.may_not_import.length) side+='<div style="font-size:12px;margin-top:6px">may not import → <b style="color:var(--bad)">'+n.may_not_import.map(esc).join(', ')+'</b></div>';
  side+='</div>';
 } else side+='<div class="card" style="color:var(--mut)">Click a layer to inspect its paths, rules and health.</div>';
 // legend + global violations
 side+='<div class="legend" style="margin-top:4px"><span><i class="dot" style="background:#8b93a3"></i>import</span>'+
  '<span><i class="dot" style="background:#f85149"></i>forbidden (violated)</span>'+
  '<span><i class="dot" style="background:#3a3f4b"></i>rule (holding)</span></div>';
 if(c.violations.length){
  side+='<div class="card"><h3>Violations <span class="badge bad">'+c.violations.length+'</span></h3><div class="vio">'+
   c.violations.slice(0,40).map(function(v){return '<div>['+esc(v.kind)+'] '+esc(v.file)+(v.line?':'+v.line:'')+'</div>';}).join('')+
   (c.violations.length>40?'<div>… +'+(c.violations.length-40)+' more</div>':'')+'</div></div>';
 }
 side+='</div>';
 return '<div class="archwrap">'+svg+side+'</div>';
}
function metrics(){
 var m=D.metrics;
 if(!m||!m.dora) return '<div class="empty">metrics unavailable'+(m&&m.error?': '+esc(m.error):'')+'</div>';
 var d=m.dora;
 function tile(label,val,sub){return '<div class="tile"><div class="tv">'+val+'</div><div class="tl">'+esc(label)+'</div><div class="ts">'+esc(sub||'')+'</div></div>';}
 var h='<div class="mut" style="margin-bottom:10px">DORA · deploy frequency & change-fail rate over last '+m.window_days+' days · lead time & MTTR all-time</div><div class="tiles">';
 h+=tile('Deploy frequency', d.deploy_frequency.per_week+'<span class="u">/wk</span>', d.deploy_frequency.count+' in window');
 h+=tile('Lead time', d.lead_time_days.median==null?'—':d.lead_time_days.median+'<span class="u">d</span>', 'median · n='+d.lead_time_days.n);
 h+=tile('Change failure rate', d.change_failure_rate.rate==null?'—':Math.round(d.change_failure_rate.rate*100)+'<span class="u">%</span>', d.change_failure_rate.fixes+' fixes / '+d.change_failure_rate.deploys+' deploys');
 h+=tile('MTTR', d.mttr_days.median==null?'—':d.mttr_days.median+'<span class="u">d</span>', 'median · n='+d.mttr_days.n);
 h+='</div><div class="sec">Governance — artifact versions per feature</div>';
 if(!m.governance.length) return h+'<div class="idle mut">no handoff history yet</div>';
 h+='<table class="gov"><thead><tr><th>feature</th><th>versions</th><th>last touched</th></tr></thead><tbody>';
 h+=m.governance.slice(0,30).map(function(r){return '<tr><td class="slug">'+esc(r.feature)+'</td><td>'+r.artifact_versions+'</td><td class="mut">'+esc(r.last_touched)+'</td></tr>';}).join('');
 return h+'</tbody></table>';
}
function draw(){
 if(!D){document.getElementById('app').innerHTML='<div class="empty">loading…</div>';return;}
 document.getElementById('sub').textContent=D.project+' · '+D.features.length+' features'+
  (D.components.arch_supported?' · '+D.components.layers.length+' layers':'');
 document.getElementById('tabP').className=TAB==='P'?'on':'';
 document.getElementById('tabA').className=TAB==='A'?'on':'';
 document.getElementById('tabM').className=TAB==='M'?'on':'';
 document.getElementById('app').innerHTML=TAB==='P'?pipeline():TAB==='A'?architecture():metrics();
}
document.getElementById('tabP').onclick=function(){TAB='P';draw();};
document.getElementById('tabA').onclick=function(){TAB='A';draw();};
document.getElementById('tabM').onclick=function(){TAB='M';draw();};
document.getElementById('app').addEventListener('click',function(e){
 var row=e.target.closest('.row');
 if(row){var s=row.getAttribute('data-slug');OPEN[s]=!OPEN[s];draw();return;}
 var node=e.target.closest('.node');
 if(node){ONODE=node.getAttribute('data-name');draw();}
});
function tick(){
 fetch('/api/state').then(function(r){return r.json();}).then(function(j){
  D=j;draw();
  document.getElementById('live').innerHTML='<b>●</b> live · updated '+new Date().toLocaleTimeString();
 }).catch(function(){document.getElementById('live').textContent='disconnected';});
}
tick(); setInterval(tick,5000);
</script></body></html>"""


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
