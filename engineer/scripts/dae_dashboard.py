#!/usr/bin/env python3
"""dae_dashboard.py — feature + component readiness, rendered.

Walks `features/*/` for pipeline state and reads the architecture layers +
`dae_arch` violations, then writes ONE self-contained HTML file (data inlined,
no server, no deps) you open in a browser. Bob's architecture viewer, plus a
feature-pipeline board, fed by the JSON the deterministic tools already emit.

  dae_dashboard.py [START_DIR]          -> write <root>/.engineer/dashboard.html
  dae_dashboard.py --json [START_DIR]   -> print the data blob to stdout

stdlib-only. Reuses dae_arch (layers + violations) and dae_resolve (root).
"""
import json
import os
import re
import sys

import dae_arch
import dae_resolve

# The DAE pipeline stops, in order. Index = position on the readiness bar.
CP_STAGES = [
    ("1", "Discuss"), ("1.5", "Init"), ("2", "ACs"), ("3", "Spec"),
    ("4", "Plan"), ("5", "Build"), ("6", "Refine"), ("7", "Verify"),
    ("8", "Ship"),
]
_CP_INDEX = {num: i for i, (num, _) in enumerate(CP_STAGES)}
_CP_RE = re.compile(r"(?:CP|[Cc]heckpoint[:\s])\s*(\d+(?:\.\d+)?)")


def _frontmatter(text):
    """Top-level scalar keys from a `--- ... ---` YAML block.
    ponytail: scalars only — nested lists (source_links, tags) are skipped
    because the dashboard needs none of them. PyYAML would be a dep for less.
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if km:
            val = km.group(2).strip().strip('"').strip("'")
            out[km.group(1)] = val
    return out


_PROSE_STATUS_RE = re.compile(r"(?im)^\**status\**\s*:?\s*\**\s*([A-Za-z-]+)")
_STATUS_ALIAS = {"shipped": "done", "complete": "done", "completed": "done"}


def _prose_status(text):
    """Legacy onboarded features carry `**Status**: Shipped` as prose, not YAML
    frontmatter. Read the first such line so they don't show as unknown/0%."""
    m = _PROSE_STATUS_RE.search(text or "")
    if not m:
        return None
    s = m.group(1).lower()
    return _STATUS_ALIAS.get(s, s)


def _reached_index(progress_text):
    """Highest checkpoint mentioned in progress.md → its stage index, or -1.
    ponytail: highest-CP-seen heuristic. Upgrade to reading an explicit
    `current_checkpoint:` field if progress.md ever grows one.
    """
    best = -1
    for num in _CP_RE.findall(progress_text or ""):
        best = max(best, _CP_INDEX.get(num, -1))
    return best


def collect_features(root):
    feats = []
    fdir = os.path.join(root, "features")
    if not os.path.isdir(fdir):
        return feats
    for name in sorted(os.listdir(fdir)):
        d = os.path.join(fdir, name)
        fm_path = os.path.join(d, "feature.md")
        if not os.path.isfile(fm_path):
            continue
        with open(fm_path, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        fm = _frontmatter(raw)
        prog_path = os.path.join(d, "progress.md")
        prog = ""
        if os.path.isfile(prog_path):
            with open(prog_path, encoding="utf-8", errors="replace") as fh:
                prog = fh.read()
        reached = _reached_index(prog)
        status = (fm.get("status") or _prose_status(raw) or "unknown").lower()
        if status == "done":
            pct = 1.0
        elif reached >= 0:
            pct = reached / (len(CP_STAGES) - 1)
        else:
            pct = 0.0
        feats.append({
            "slug": name,
            "title": fm.get("title") or fm.get("slug") or name,
            "status": status,
            "reached": reached,
            "checkpoint": CP_STAGES[reached][0] if reached >= 0 else None,
            "pct": round(pct, 3),
            "autonomy": fm.get("autonomy_level"),
            "size": fm.get("size"),
            "area": fm.get("area"),
            "owner": fm.get("owner"),
        })
    return feats


def collect_components(start_dir):
    """Layers (nodes) + arch violations mapped onto them. arch_supported is
    False when the project has no `architecture:` block."""
    root, rules, violations = dae_arch.audit(start_dir, True)
    if root is None or rules is None or not rules.get("layers"):
        return {"arch_supported": False, "layers": [], "violations": []}
    layers = rules["layers"]
    globs = [(l["name"], dae_arch._compile_globs(l.get("paths", []))) for l in layers]
    vlist = [{"file": f, "line": n, "kind": k, "message": m}
             for f, n, k, m in violations]
    counts = {l["name"]: 0 for l in layers}
    for v in vlist:
        for lname, compiled in globs:
            if dae_arch._match_any(v["file"], compiled):
                counts[lname] += 1
                break
    nodes = [{
        "name": l["name"],
        "paths": l.get("paths", []),
        "may_not_import": l.get("may_not_import", []),
        "violations": counts[l["name"]],
    } for l in layers]
    return {"arch_supported": True, "layers": nodes, "violations": vlist}


def build_data(start_dir):
    result = dae_resolve.resolve(start_dir)
    root = result["methodology_root"] if result else os.path.abspath(start_dir)
    project = os.path.basename(root.rstrip("/")) or "project"
    comp = collect_components(start_dir)
    return {
        "project": project,
        "root": root,
        "stages": [{"num": n, "label": l} for n, l in CP_STAGES],
        "features": collect_features(root),
        "components": comp,
    }


# --- HTML render (self-contained: data inlined, vanilla JS, no deps) ---------

_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__PROJECT__ · readiness</title>
<style>
:root{--bg:#0f1115;--card:#1a1d24;--line:#2a2f3a;--fg:#e6e9ef;--mut:#8b93a3;
--ok:#3fb950;--wip:#d29922;--empty:#30363d;--bad:#f85149;--blue:#58a6ff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:20px 24px;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:18px}.sub{color:var(--mut);font-size:13px;margin-top:2px}
nav{display:flex;gap:4px;padding:0 24px;border-bottom:1px solid var(--line)}
nav button{background:none;border:none;color:var(--mut);padding:12px 14px;
cursor:pointer;font-size:14px;border-bottom:2px solid transparent}
nav button.on{color:var(--fg);border-bottom-color:var(--blue)}
main{padding:20px 24px;max-width:1100px}
.row{display:grid;grid-template-columns:230px 1fr 90px;gap:14px;align-items:center;
padding:9px 0;border-bottom:1px solid var(--line)}
.row .t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .t b{font-weight:600}.row .t .m{color:var(--mut);font-size:12px}
.bar{display:flex;gap:3px}
.seg{flex:1;height:22px;border-radius:3px;background:var(--empty);position:relative}
.seg.done{background:var(--ok)}.seg.wip{background:var(--wip)}
.seg .lb{position:absolute;inset:0;display:flex;align-items:center;
justify-content:center;font-size:9px;color:#0008;font-weight:600}
.seg.done .lb,.seg.wip .lb{color:#0009}
.pill{font-size:11px;padding:2px 8px;border-radius:20px;text-align:center;font-weight:600}
.st-done{background:#1f6f2e;color:#d7ffd9}.st-ready{background:#1b436e;color:#cfe6ff}
.st-in-progress{background:#7a5a10;color:#ffe9b3}.st-parked,.st-unknown,.st-blocked{background:#333;color:#bbb}
.legend{color:var(--mut);font-size:12px;margin:10px 0 18px}
.legend span{margin-right:16px}.dot{display:inline-block;width:10px;height:10px;
border-radius:2px;vertical-align:-1px;margin-right:5px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:14px 16px;margin-bottom:12px}
.card h3{margin:0 0 6px;font-size:15px;display:flex;align-items:center;gap:10px}
.badge{font-size:11px;padding:2px 8px;border-radius:20px;font-weight:600}
.badge.ok{background:#1f6f2e;color:#d7ffd9}.badge.bad{background:#7a1d1d;color:#ffd7d7}
.card .paths{color:var(--mut);font-size:12px;font-family:ui-monospace,monospace}
.card .rule{font-size:12px;margin-top:6px}.card .rule b{color:var(--bad)}
.vio{margin-top:8px;font-size:12px;font-family:ui-monospace,monospace;color:var(--mut)}
.vio div{padding:2px 0;border-top:1px dashed var(--line)}
.empty{color:var(--mut);padding:40px 0;text-align:center}
details summary{cursor:pointer;color:var(--blue);font-size:12px}
.q{color:var(--mut)}
</style></head><body>
<header><h1>__PROJECT__ · readiness</h1><div class="sub" id="sub"></div></header>
<nav><button id="tabF" class="on">Features</button><button id="tabC">Components</button></nav>
<main id="app"></main>
<script>window.DATA=__DATA__;</script>
<script>
var D=window.DATA,S=D.stages;
document.getElementById('sub').textContent=D.features.length+' features · '+
 (D.components.arch_supported?D.components.layers.length+' layers':'no architecture rules');
function segClass(f,i){if(f.status==='done')return'done';if(i<f.reached)return'done';
 if(i===f.reached)return'wip';return'';}
function features(){
 var h='<div class="legend"><span><i class="dot" style="background:var(--ok)"></i>done</span>'+
  '<span><i class="dot" style="background:var(--wip)"></i>current</span>'+
  '<span><i class="dot" style="background:var(--empty)"></i>pending</span></div>';
 D.features.forEach(function(f){
  var bar=S.map(function(s,i){return '<div class="seg '+segClass(f,i)+'"><span class="lb">'+s.num+'</span></div>';}).join('');
  var pct=Math.round(f.pct*100);
  h+='<div class="row"><div class="t"><b>'+f.slug+'</b><div class="m">'+
   (f.area||'')+(f.size?' · '+f.size:'')+'</div></div><div class="bar">'+bar+'</div>'+
   '<div style="text-align:right"><span class="pill st-'+f.status+'">'+f.status+'</span>'+
   '<div class="m" style="color:var(--mut);font-size:12px">'+pct+'%</div></div></div>';
 });
 return h;
}
function components(){
 var c=D.components;
 if(!c.arch_supported)return '<div class="empty">No <code>architecture:</code> block in the manifest — '+
  'nothing to map. Add layers to <code>.engineer/manifest.yml</code> to light this up.</div>';
 var h='';
 c.layers.forEach(function(l){
  var ok=l.violations===0;
  h+='<div class="card"><h3>'+l.name+
   ' <span class="badge '+(ok?'ok':'bad')+'">'+(ok?'clean':l.violations+' violation'+(l.violations>1?'s':''))+'</span>'+
   ' <span class="badge q" title="not wired yet">crap ? · cov ? · mut ?</span></h3>'+
   '<div class="paths">'+l.paths.join('  ')+'</div>';
  if(l.may_not_import&&l.may_not_import.length)
   h+='<div class="rule">may not import → <b>'+l.may_not_import.join(', ')+'</b></div>';
  h+='</div>';
 });
 var vs=c.violations;
 if(vs.length){
  h+='<div class="card"><h3>Violations <span class="badge bad">'+vs.length+'</span></h3><div class="vio">'+
   vs.map(function(v){return '<div>['+v.kind+'] '+v.file+(v.line?':'+v.line:'')+' — '+v.message+'</div>';}).join('')+'</div></div>';
 }
 return h;
}
function draw(tab){
 document.getElementById('tabF').className=tab==='F'?'on':'';
 document.getElementById('tabC').className=tab==='C'?'on':'';
 document.getElementById('app').innerHTML=tab==='F'?features():components();
}
document.getElementById('tabF').onclick=function(){draw('F');};
document.getElementById('tabC').onclick=function(){draw('C');};
draw('F');
</script></body></html>"""


def render_html(data):
    return (_HTML
            .replace("__PROJECT__", data["project"])
            .replace("__DATA__", json.dumps(data)))


def main(argv):
    args = list(argv)
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    as_json = "--json" in args
    if as_json:
        args.remove("--json")
    start_dir = args[0] if args else os.getcwd()
    data = build_data(start_dir)
    if as_json:
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    out_dir = os.path.join(data["root"], ".engineer")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "dashboard.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render_html(data))
    sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
