"""Galactic Pizza – a small pizza shop whose only real job is to make *release strategies* visible.

Every order is baked by one container and the answer says which release baked it, on which task,
in which availability zone, reached through which load-balancer listener. Open /rush and the
browser fires a steady stream of orders at the load balancer and draws, live, which release
answered and how many pizzas came back burnt. That turns blue/green, canary and linear
deployments into something you can watch.

The release is baked into the image at build time (--build-arg RELEASE=1.2). Each release has its
own oven settings; read RELEASES below. Like most real bugs, the one in this shop is not in any
single line: it is in how two harmless-looking numbers meet.

Endpoints
  /                  the shop                       /rush            rush-hour traffic board
  /api/order?pizza=  bake one pizza (JSON)          /api/menu        today's menu
  /api/info          where this container runs      /health          liveness for the load balancer
"""
import json
import os
import random
import signal
import socket
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string, request

RELEASE = os.environ.get("RELEASE", "1.0")
PORT = int(os.environ.get("PORT", "8080"))
SHOP = os.environ.get("SHOP_NAME", "Galactic Pizza")
STARTED = time.time()

# ── the product ──────────────────────────────────────────────────────────────
# sugar: grams of sugar on the pizza. Caramelising sugar is what scorches an oven.
PIZZAS = {
    "margherita":       {"name": "Moon Margherita",   "emoji": "🌕", "sugar": 3,  "since": "1.0"},
    "meteor-pepperoni": {"name": "Meteor Pepperoni",  "emoji": "☄️", "sugar": 4,  "since": "1.0"},
    "nebula-veggie":    {"name": "Nebula Veggie",     "emoji": "🌌", "sugar": 6,  "since": "1.0"},
    "pineapple-pulsar": {"name": "Pineapple Pulsar",  "emoji": "🍍", "sugar": 14, "since": "1.0"},
    "saturn-rings":     {"name": "Saturn Rings",      "emoji": "🪐", "sugar": 5,  "since": "1.1"},
}

# Each release ships different oven settings. Read the notes: they are the release notes the team wrote.
RELEASES = {
    "1.0": {"name": "Grand Opening",    "color": "#F97316", "oven_c": 420, "bake_ms": (150, 350),
            "notes": "First light. Four pizzas, one wood-fired oven."},
    "1.1": {"name": "Saturn Rings",     "color": "#A855F7", "oven_c": 450, "bake_ms": (90, 220),
            "notes": "New pizza: Saturn Rings (onion rings, obviously). Ovens upgraded: ~40% faster."},
    "1.2": {"name": "Hyperdrive Dough", "color": "#06B6D4", "oven_c": 900, "bake_ms": (40, 110),
            "notes": "Hyperdrive dough bakes at 900 °C: orders are 2-3x faster. All smoke tests green."},
    "1.3": {"name": "Lower Rack",       "color": "#22C55E", "oven_c": 900, "bake_ms": (40, 110),
            "notes": "Keeps hyperdrive speed; sugary pizzas now bake on a lower rack."},
}
R = RELEASES.get(RELEASE, RELEASES["1.0"])
SCORCH_POINT = 10_000            # oven °C × sugar g above this sets fire to the pizza (and the oven)
LOWER_RACK = RELEASE >= "1.3"    # the 1.3 fix: sugary pizzas go on a cooler rack

HITS = {"orders": 0, "burnt": 0}
LOCK = threading.Lock()
DRAINING = False


def menu():
    return {k: v for k, v in PIZZAS.items() if v["since"] <= RELEASE}


def where():
    """Task ID, AZ and task definition from the ECS task metadata endpoint (empty outside ECS)."""
    uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if not uri:
        return {}
    try:
        with urllib.request.urlopen(uri + "/task", timeout=0.5) as r:
            d = json.load(r)
        return {"task": d.get("TaskARN", "").split("/")[-1], "az": d.get("AvailabilityZone", ""),
                "taskdef": f'{d.get("Family", "")}:{d.get("Revision", "")}', "cluster": d.get("Cluster", "").split("/")[-1]}
    except Exception:
        return {}


WHERE = {}


def listener():
    """Which load-balancer listener this request came through. The ALB adds X-Forwarded-Port."""
    port = request.headers.get("X-Forwarded-Port")
    if not port:
        return {"port": None, "kind": "direct", "label": "direct (no load balancer)"}
    kind = "test" if port != "80" else "production"
    return {"port": port, "kind": kind, "label": f"{kind.upper()} listener :{port}"}


def log(event, **fields):
    print(json.dumps({"time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": event,
                      "release": RELEASE, "host": socket.gethostname(), **fields}), flush=True)


def info():
    global WHERE
    if not WHERE:
        WHERE = where()
    return {"shop": SHOP, "release": RELEASE, "release_name": R["name"], "color": R["color"], "notes": R["notes"],
            "oven_c": R["oven_c"], "host": socket.gethostname(), **WHERE, "uptime_s": int(time.time() - STARTED),
            "orders_here": HITS["orders"], "burnt_here": HITS["burnt"], "draining": DRAINING}


app = Flask(__name__)
import logging  # noqa: E402
logging.getLogger("werkzeug").setLevel(logging.ERROR)


# ── API ──────────────────────────────────────────────────────────────────────
@app.route("/api/order")
def order():
    key = request.args.get("pizza", "margherita")
    src = request.args.get("src", "shop")
    lst = listener()
    base = {"release": RELEASE, "release_name": R["name"], "color": R["color"], "host": socket.gethostname(),
            "task": WHERE.get("task", ""), "az": WHERE.get("az", ""), "listener": lst["label"]}
    pizza = menu().get(key)
    if not pizza:
        log("order", pizza=key, status=404, src=src, listener=lst["kind"])
        return jsonify(ok=False, error=f"'{key}' is not on the {RELEASE} menu", **base), 404

    bake_ms = random.randint(*R["bake_ms"])
    time.sleep(bake_ms / 1000)
    heat = R["oven_c"] * pizza["sugar"]
    if LOWER_RACK and pizza["sugar"] > 10:
        heat //= 2
    with LOCK:
        HITS["orders"] += 1
        if heat > SCORCH_POINT:
            HITS["burnt"] += 1
    if heat > SCORCH_POINT:
        msg = f"OVEN FIRE: {pizza['sugar']} g of sugar at {R['oven_c']} °C caramelised and ignited"
        log("order", pizza=key, status=500, bake_ms=bake_ms, src=src, listener=lst["kind"], error=msg)
        return jsonify(ok=False, error=msg, pizza=pizza["name"], emoji="🔥", bake_ms=bake_ms, **base), 500
    log("order", pizza=key, status=200, bake_ms=bake_ms, src=src, listener=lst["kind"])
    return jsonify(ok=True, pizza=pizza["name"], emoji=pizza["emoji"], bake_ms=bake_ms, **base)


@app.route("/api/menu")
def api_menu():
    return jsonify(release=RELEASE, menu=menu())


@app.route("/api/info")
def api_info():
    return jsonify(info())


@app.route("/health")
def health():
    # Liveness only: "the process answers HTTP". It says nothing about whether pizzas come out right.
    return jsonify(status="ok", release=RELEASE)


# ── pages ────────────────────────────────────────────────────────────────────
STYLE = """
:root { --c: {{ i.color }}; --bg:#0B1020; --card:#121A2E; --ink:#E5E7EB; --mute:#94A3B8; }
* { box-sizing:border-box } body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; color:var(--ink);
  background: radial-gradient(900px 500px at 15% -10%, color-mix(in srgb, var(--c) 30%, var(--bg)), var(--bg) 65%); min-height:100vh }
.wrap { max-width:1040px; margin:0 auto; padding:28px 22px 40px }
header { display:flex; align-items:center; gap:16px; flex-wrap:wrap }
h1 { margin:0; font-size:34px; letter-spacing:-.02em } h1 b { color:var(--c) }
.pill { display:inline-flex; align-items:center; gap:6px; padding:5px 12px; border-radius:999px; font-weight:700; font-size:13px; background:var(--c); color:#0B1020 }
.pill.lst { background:rgba(255,255,255,.08); color:var(--ink); border:1px solid rgba(255,255,255,.14) } .pill.test { background:#FACC15; color:#0B1020 }
.sub { color:var(--mute); margin:6px 0 20px } .mono { font-family: ui-monospace, Menlo, monospace; font-size:13px }
.card { background:var(--card); border:1px solid rgba(255,255,255,.07); border-radius:16px; padding:18px 20px }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:14px }
.pz { text-align:center; padding:18px 12px; cursor:pointer; transition:transform .12s, border-color .12s } .pz:hover { transform:translateY(-2px); border-color:var(--c) }
.pz .e { font-size:44px } .pz .n { font-weight:700; margin-top:6px } .pz .s { color:var(--mute); font-size:12px; margin-top:2px }
.pz button { margin-top:10px; background:var(--c); color:#0B1020; border:0; border-radius:10px; padding:7px 14px; font-weight:700; cursor:pointer }
.row { display:grid; grid-template-columns:1.2fr 1fr; gap:16px; margin-top:18px } @media (max-width:760px){ .row { grid-template-columns:1fr } }
.k { color:var(--mute); font-size:11px; letter-spacing:.09em; text-transform:uppercase } .v { font-family: ui-monospace, Menlo, monospace; font-size:13px; word-break:break-all }
.facts { display:grid; grid-template-columns:1fr 1fr; gap:10px 18px }
ol.log { list-style:none; margin:0; padding:0; max-height:260px; overflow:auto } ol.log li { padding:7px 0; border-bottom:1px solid rgba(255,255,255,.06); font-size:14px }
ol.log li.bad { color:#FCA5A5 } .tag { display:inline-block; min-width:38px; text-align:center; border-radius:6px; padding:1px 6px; font-weight:700; font-size:12px; color:#0B1020; margin-right:6px }
a { color:var(--c) }
"""

SHOP_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ i.shop }} · release {{ i.release }}</title><style>""" + STYLE + """</style></head><body><div class="wrap">
<header><h1>🍕 <b>{{ i.shop }}</b></h1>
  <span class="pill">release {{ i.release }} · {{ i.release_name }}</span>
  <span class="pill lst {{ 'test' if l.kind == 'test' else '' }}">{{ l.label }}</span></header>
<p class="sub">{{ i.notes }} · <a href="/rush">Open the rush-hour board →</a></p>
<div class="grid">
{% for key, p in m.items() %}
  <div class="card pz" onclick="order('{{ key }}')"><div class="e">{{ p.emoji }}</div><div class="n">{{ p.name }}</div>
  <div class="s">{{ p.sugar }} g sugar{% if p.since == i.release and i.release != '1.0' %} · <b style="color:var(--c)">NEW</b>{% endif %}</div><button>Order</button></div>
{% endfor %}
</div>
<div class="row">
  <div class="card"><div class="k" style="margin-bottom:8px">Your orders (each one may be baked by a different container)</div><ol class="log" id="log"><li class="mono" style="color:var(--mute)">Click a pizza.</li></ol></div>
  <div class="card facts">
    <div><div class="k">Container</div><div class="v">{{ i.host }}</div></div>
    <div><div class="k">Availability zone</div><div class="v">{{ i.az or '–' }}</div></div>
    <div><div class="k">ECS task</div><div class="v">{{ i.task or '–' }}</div></div>
    <div><div class="k">Task definition</div><div class="v">{{ i.taskdef or '–' }}</div></div>
    <div><div class="k">Oven</div><div class="v">{{ i.oven_c }} °C</div></div>
    <div><div class="k">Orders on this container</div><div class="v">{{ i.orders_here }} ({{ i.burnt_here }} burnt)</div></div>
  </div>
</div>
<p class="sub mono" style="margin-top:18px">This page was served by {{ i.host }} (release {{ i.release }}). Refresh: the load balancer may pick another container.</p>
</div>
<script>
async function order(p){
  const li=document.createElement('li'); const log=document.getElementById('log');
  if(log.firstElementChild && !log.firstElementChild.dataset.o) log.innerHTML='';
  try{ const r=await fetch('/api/order?pizza='+p,{cache:'no-store'}); const j=await r.json();
    li.dataset.o=1; li.className=j.ok?'':'bad';
    li.innerHTML=`<span class="tag" style="background:${j.color||'#64748B'}">${j.release||'?'}</span>${j.emoji||'❔'} ${j.pizza||p} · `+
      (j.ok?`baked in ${j.bake_ms} ms by <span class="mono">${j.host}</span>`:`<b>${j.error}</b>`);
  }catch(e){ li.className='bad'; li.textContent='No answer: '+e; }
  log.prepend(li);
}
</script></body></html>"""

RUSH_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rush hour · {{ i.shop }}</title><style>""" + STYLE + """
.ctl { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin:6px 0 18px } .ctl button { background:var(--card); color:var(--ink); border:1px solid rgba(255,255,255,.15); border-radius:10px; padding:8px 14px; font-weight:700; cursor:pointer }
.ctl button.on { background:var(--c); color:#0B1020; border-color:var(--c) } .ctl .go { background:#22C55E; color:#0B1020; border-color:#22C55E } .ctl .stop { background:#EF4444; color:#fff; border-color:#EF4444 }
.split { display:flex; height:46px; border-radius:12px; overflow:hidden; background:rgba(255,255,255,.05); margin:8px 0 6px } .split div { display:flex; align-items:center; justify-content:center; font-weight:800; color:#0B1020; font-size:15px; transition:width .4s; white-space:nowrap; overflow:hidden }
table { width:100%; border-collapse:collapse; font-size:14px } th,td { text-align:right; padding:8px 10px; border-bottom:1px solid rgba(255,255,255,.07) } th:first-child,td:first-child { text-align:left } th { color:var(--mute); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.06em }
td.bad { color:#FCA5A5; font-weight:700 }
.tl { display:flex; align-items:flex-end; gap:3px; height:170px; margin-top:10px; border-bottom:1px solid rgba(255,255,255,.15) } .tl .col { flex:1; display:flex; flex-direction:column-reverse; min-width:4px; height:100% } .tl .col div { width:100% }
.tl.share { height:110px; gap:2px } .tl.share .col { flex-direction:column-reverse }
.big { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px } .big .card .n { font-size:30px; font-weight:800; margin-top:4px } @media (max-width:760px){ .big { grid-template-columns:1fr 1fr } }
.legend span { display:inline-flex; align-items:center; gap:6px; margin-right:14px; font-size:13px; color:var(--mute) } .legend i { width:12px; height:12px; border-radius:3px; display:inline-block }
</style></head><body><div class="wrap">
<header><h1>🚦 Rush hour · <b>{{ i.shop }}</b></h1><span class="pill lst {{ 'test' if l.kind == 'test' else '' }}">{{ l.label }}</span></header>
<p class="sub">Your browser orders pizzas through the load balancer and records which release baked each one. Leave this tab open while you deploy.</p>
<div class="ctl"><b>Orders per second:</b>
  <button data-r="2">2</button><button data-r="5">5</button><button data-r="10" class="on">10</button><button data-r="20">20</button>
  <button id="go" class="go">▶ Start rush</button><button id="reset">Reset</button>
  <span class="mono" id="mix" style="color:var(--mute)"></span></div>
<div class="big">
  <div class="card"><div class="k">Orders (30 s)</div><div class="n" id="n30">0</div></div>
  <div class="card"><div class="k">🔥 Burnt · 5xx (30 s)</div><div class="n" id="b30">0</div></div>
  <div class="card"><div class="k">Not on menu · 404 (30 s)</div><div class="n" id="s30">0</div></div>
  <div class="card"><div class="k">Failure rate (30 s)</div><div class="n" id="r30">0 %</div></div>
</div>
<div class="card"><div class="k">Who baked the last 30 seconds of orders</div><div class="split" id="split"></div>
  <div class="k" style="margin-top:16px">Last 90 seconds, one column per second</div><div class="tl" id="tl"></div>
  <div class="legend" id="legend" style="margin-top:10px"></div>
  <div class="k" style="margin-top:18px">Traffic share by release, last 6 minutes (one column per 10 s) — watch the shape of each strategy</div><div class="tl share" id="share"></div></div>
<div class="card" style="margin-top:16px"><div class="k" style="margin-bottom:6px">Since you pressed Start · <span id="up">0 s</span></div>
<table><thead><tr><th>Release</th><th>Orders</th><th>Share</th><th>🔥 Burnt</th><th>Not on menu</th><th>Failure rate</th><th>Avg bake</th><th>Containers seen</th></tr></thead><tbody id="tbl"></tbody></table></div>
<p class="sub mono" id="last" style="margin-top:14px"></p>
</div>
<script>
// Customers only order pizzas they have heard of: the board starts with the 1.0 menu and adds a pizza
// as soon as ANY container's menu offers it. During a rolling update that is exactly how version skew bites.
const WEIGHT={"margherita":30,"meteor-pepperoni":25,"nebula-veggie":15,"pineapple-pulsar":20,"saturn-rings":10};
const known=new Set(["margherita","meteor-pepperoni","nebula-veggie","pineapple-pulsar"]);
function showMix(){const W=[...known].reduce((a,k)=>a+(WEIGHT[k]||10),0);document.getElementById('mix').textContent='mix: '+[...known].map(k=>k.split('-')[0]+' '+Math.round(100*(WEIGHT[k]||10)/W)+'%').join(' · ')}
async function learn(){try{const j=await (await fetch('/api/menu',{cache:'no-store'})).json();for(const k in j.menu)known.add(k);showMix()}catch(e){}}
function pick(){const ks=[...known];let x=Math.random()*ks.reduce((a,k)=>a+(WEIGHT[k]||10),0);for(const k of ks){if((x-=(WEIGHT[k]||10))<0)return k}return ks[0]}
let rate=10, timer=null, t0=0, inflight=0; const buckets=new Map(), tot={}, colors={}, tens=new Map();
document.querySelectorAll('[data-r]').forEach(b=>b.onclick=()=>{rate=+b.dataset.r;document.querySelectorAll('[data-r]').forEach(x=>x.classList.toggle('on',x===b));if(timer){stop();start()}});
function sec(){return Math.floor(Date.now()/1000)}
const Z=()=>({n:0,ok:0,burnt:0,skew:0,err:0});
function rec(rel,kind,ms,host){const s=sec(), d=Math.floor(s/10);if(!tens.has(d))tens.set(d,{});tens.get(d)[rel]=(tens.get(d)[rel]||0)+1;if(!buckets.has(s))buckets.set(s,{});const b=buckets.get(s);b[rel]=b[rel]||Z();b[rel].n++;b[rel][kind]++;
  const t=tot[rel]=tot[rel]||Object.assign(Z(),{ms:0,hosts:new Set()});t.n++;t[kind]++;if(ms&&kind==='ok')t.ms+=ms;if(host)t.hosts.add(host)}
async function fire(){ if(inflight>60) return; inflight++; const p=pick();
  try{ const r=await fetch('/api/order?src=rush&pizza='+p,{cache:'no-store'}); let j={}; try{j=await r.json()}catch(e){}
    const rel=j.release||('ALB '+r.status); if(j.color)colors[rel]=j.color;
    const kind=r.ok?'ok':(j.release&&r.status===404)?'skew':(j.release&&r.status===500)?'burnt':'err';
    rec(rel,kind,j.bake_ms,j.host);
    document.getElementById('last').textContent=`last: ${r.status} · release ${rel} · ${j.host||''} · ${j.ok?(j.emoji+' '+j.pizza):(j.error||'')}`;
  }catch(e){ rec('network','err') } finally{ inflight-- } }
let menuTimer=null;
function start(){ if(!t0)t0=Date.now(); timer=setInterval(fire,1000/rate); menuTimer=menuTimer||setInterval(learn,2000); const g=document.getElementById('go'); g.textContent='■ Stop'; g.className='stop' }
function stop(){ clearInterval(timer); timer=null; const g=document.getElementById('go'); g.textContent='▶ Start rush'; g.className='go' }
document.getElementById('go').onclick=()=>timer?stop():start();
document.getElementById('reset').onclick=()=>{buckets.clear();tens.clear();for(const k in tot)delete tot[k];t0=timer?Date.now():0;render()};
function col(rel){return colors[rel]||'#64748B'}
const HATCH={burnt:'repeating-linear-gradient(45deg,#EF4444 0 4px,#7F1D1D 4px 8px)',skew:'repeating-linear-gradient(45deg,#FACC15 0 4px,#713F12 4px 8px)',err:'#475569'};
function render(){ const now=sec(), last={}; let n=0,burnt=0,skew=0,fail=0;
  for(const [s,b] of buckets){ if(s<now-90)buckets.delete(s); else if(s>now-30) for(const r in b){last[r]=last[r]||Z();for(const k in b[r])last[r][k]+=b[r][k];n+=b[r].n;burnt+=b[r].burnt;skew+=b[r].skew;fail+=b[r].n-b[r].ok} }
  document.getElementById('n30').textContent=n; document.getElementById('b30').textContent=burnt; document.getElementById('s30').textContent=skew;
  document.getElementById('r30').textContent=(n?(100*fail/n).toFixed(1):0)+' %';
  document.getElementById('b30').style.color=burnt?'#FCA5A5':''; document.getElementById('s30').style.color=skew?'#FDE047':'';
  document.getElementById('up').textContent=t0?Math.round((Date.now()-t0)/1000)+' s':'0 s';
  const rels=Object.keys(last).sort(); document.getElementById('split').innerHTML=rels.map(r=>{const p=100*last[r].n/n;return `<div style="width:${p}%;background:${col(r)}">${p>=6?r+' · '+Math.round(p)+'%':''}</div>`}).join('');
  let max=1; for(let s=now-89;s<=now;s++){const b=buckets.get(s)||{};let t=0;for(const r in b)t+=b[r].n;max=Math.max(max,t)}
  let h=''; for(let s=now-89;s<=now;s++){const b=buckets.get(s)||{};let c='';for(const r of Object.keys(b).sort()){
      if(b[r].ok)c+=`<div style="height:${100*b[r].ok/max}%;background:${col(r)}"></div>`;
      for(const k of ['skew','burnt','err']) if(b[r][k])c+=`<div style="height:${100*b[r][k]/max}%;background:${HATCH[k]}"></div>`}
    h+=`<div class="col">${c}</div>`}
  document.getElementById('tl').innerHTML=h;
  const nd=Math.floor(now/10); let sh=''; for(let d=nd-35;d<=nd;d++){const b=tens.get(d)||{};const t=Object.values(b).reduce((a,x)=>a+x,0);let c='';
      if(t)for(const r of Object.keys(b).sort())c+=`<div style="height:${100*b[r]/t}%;background:${col(r)}"></div>`; sh+=`<div class="col">${c}</div>`}
  for(const d of tens.keys()) if(d<nd-40) tens.delete(d);
  document.getElementById('share').innerHTML=sh;
  const all=Object.keys(tot).sort(), N=all.reduce((a,r)=>a+tot[r].n,0);
  document.getElementById('legend').innerHTML=all.map(r=>`<span><i style="background:${col(r)}"></i>${r}</span>`).join('')+
    `<span><i style="background:${HATCH.burnt}"></i>burnt (5xx from the app)</span><span><i style="background:${HATCH.skew}"></i>not on that release's menu (404)</span><span><i style="background:${HATCH.err}"></i>load balancer / network error</span>`;
  document.getElementById('tbl').innerHTML=all.map(r=>{const t=tot[r],f=t.n-t.ok;return `<tr><td><span class="tag" style="background:${col(r)}">${r}</span></td><td>${t.n}</td><td>${N?(100*t.n/N).toFixed(1):0} %</td>
    <td class="${t.burnt?'bad':''}">${t.burnt}</td><td style="${t.skew?'color:#FDE047;font-weight:700':''}">${t.skew}</td><td class="${f?'bad':''}">${(100*f/t.n).toFixed(1)} %</td><td>${t.ok?Math.round(t.ms/t.ok)+' ms':'–'}</td><td>${t.hosts.size}</td></tr>`}).join('');
}
showMix(); learn(); setInterval(render,500); render();
if(location.hash==='#go')start();
</script></body></html>"""


@app.route("/")
def shop():
    return render_template_string(SHOP_PAGE, i=info(), l=listener(), m=menu())


@app.route("/rush")
def rush():
    return render_template_string(RUSH_PAGE, i=info(), l=listener())


# ── graceful shutdown ────────────────────────────────────────────────────────
def on_sigterm(signum, frame):
    """ECS sends SIGTERM when it stops a task (after the load balancer has drained it), then SIGKILL after stopTimeout."""
    global DRAINING
    DRAINING = True
    log("sigterm", note="ECS asked this container to stop; finishing in-flight orders",
        orders=HITS["orders"], burnt=HITS["burnt"], uptime_s=int(time.time() - STARTED))
    threading.Timer(2.0, lambda: os._exit(0)).start()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, on_sigterm)
    WHERE = where()
    log("startup", port=PORT, release_name=R["name"], oven_c=R["oven_c"], **WHERE)
    app.run(host="0.0.0.0", port=PORT, threaded=True)
