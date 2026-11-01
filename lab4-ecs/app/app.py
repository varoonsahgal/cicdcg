"""Mission Control – a tiny web app that tells you *where* it is running.

Every page load shows the container's hostname (= the ECS task / Kubernetes pod),
the image version baked in at build time, uptime, a per-container request counter
and – when running on ECS – the task ID, cluster and availability zone read from the
task metadata endpoint. That makes rolling updates, scaling and load balancing visible.
"""
import json
import os
import random
import socket
import time
import urllib.request

from flask import Flask, Response, jsonify, render_template_string, request

APP_VERSION = os.environ.get("APP_VERSION", "dev")
APP_COLOR = os.environ.get("APP_COLOR", "#38BDF8")      # change me in a new task-definition revision
MISSION = os.environ.get("MISSION_NAME", "Artemis-NN")  # change me too
PORT = int(os.environ.get("PORT", "8080"))
STARTED = time.time()
HITS = 0

FACTS = [
    "A container image is just a stack of read-only layers plus a little metadata.",
    "`docker build` does not run your app. It runs each Dockerfile line in a throw-away container and keeps the result.",
    "Two tasks from the same image share nothing at runtime: no files, no memory, no counters. Look at the hit counter!",
    "Fargate bills per vCPU-second and GB-second, rounded up to one minute. This task is 0.25 vCPU / 0.5 GB.",
    "An ECS *task definition* is a versioned recipe. You never edit revision 3; you create revision 4.",
    "A rolling update starts new tasks before it stops old ones. Watch the hostname change when you refresh.",
    "`latest` is not a version. It is whatever was pushed last. Deploy immutable tags like v7.",
    "The task *execution* role pulls the image and ships logs. The task *role* is what your code uses at runtime. They are different robots.",
    "Kubernetes calls the same idea a Pod, a Deployment and a Service. Same physics, different vocabulary.",
    "Health checks turn 'the process is running' into 'the app is answering'. Deploy tools trust the second one.",
]

app = Flask(__name__)


def ecs_metadata():
    """Return a few fields from the ECS task metadata endpoint (empty dict elsewhere)."""
    uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if not uri:
        return {}
    try:
        with urllib.request.urlopen(uri + "/task", timeout=0.5) as r:
            data = json.load(r)
        return {
            "task_id": data.get("TaskARN", "").split("/")[-1],
            "cluster": data.get("Cluster", "").split("/")[-1],
            "az": data.get("AvailabilityZone", ""),
            "launch_type": data.get("LaunchType", ""),
            "family": f'{data.get("Family", "")}:{data.get("Revision", "")}',
        }
    except Exception:
        return {}


def info():
    up = int(time.time() - STARTED)
    return {
        "mission": MISSION,
        "version": APP_VERSION,
        "hostname": socket.gethostname(),
        "uptime_seconds": up,
        "hits_on_this_container": HITS,
        "node": os.environ.get("NODE_NAME", ""),          # set by the Kubernetes manifest in Lab 5
        "pod_namespace": os.environ.get("POD_NAMESPACE", ""),
        "ecs": ecs_metadata(),
    }


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{{ i.mission }} · Mission Control {{ i.version }}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root { --c: {{ color }}; }
  body { margin:0; min-height:100vh; display:grid; place-items:center; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: radial-gradient(1200px 600px at 20% -10%, color-mix(in srgb, var(--c) 35%, #0B1220), #0B1220 60%); color:#E2E8F0; }
  .card { width:min(680px, 92vw); background:rgba(15,24,41,.9); border:1px solid rgba(255,255,255,.08); border-radius:20px; padding:34px 38px; box-shadow:0 30px 80px rgba(0,0,0,.5); }
  h1 { margin:0 0 4px; font-size:34px; letter-spacing:-.01em; } h1 span { color:var(--c); }
  .sub { color:#94A3B8; margin:0 0 22px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px 22px; font-size:15px; }
  .k { color:#94A3B8; font-size:12px; letter-spacing:.08em; text-transform:uppercase; } .v { font-family: ui-monospace, Menlo, monospace; word-break:break-all; }
  .big { font-size:22px; color:var(--c); font-weight:700; }
  .fact { margin-top:24px; padding:14px 16px; border-left:4px solid var(--c); background:rgba(255,255,255,.04); border-radius:0 12px 12px 0; color:#CBD5E1; font-size:15px; }
  .badge { display:inline-block; padding:4px 10px; border-radius:999px; background:var(--c); color:#0B1220; font-weight:700; font-size:13px; }
  a { color:var(--c); }
</style></head><body><div class="card">
  <h1>🚀 <span>{{ i.mission }}</span> Mission Control</h1>
  <p class="sub">Served by one container, somewhere in us-west-2. <span class="badge">{{ i.version }}</span></p>
  <div class="grid">
    <div><div class="k">Container hostname</div><div class="v big">{{ i.hostname }}</div></div>
    <div><div class="k">Requests this container has seen</div><div class="v big">{{ i.hits_on_this_container }}</div></div>
    <div><div class="k">Uptime</div><div class="v">{{ i.uptime_seconds }} s</div></div>
    <div><div class="k">Colour (env APP_COLOR)</div><div class="v">{{ color }}</div></div>
    {% if i.ecs %}
    <div><div class="k">ECS task</div><div class="v">{{ i.ecs.task_id }}</div></div>
    <div><div class="k">Cluster · AZ · launch type</div><div class="v">{{ i.ecs.cluster }} · {{ i.ecs.az }} · {{ i.ecs.launch_type }}</div></div>
    <div><div class="k">Task definition</div><div class="v">{{ i.ecs.family }}</div></div>
    {% endif %}
    {% if i.node %}
    <div><div class="k">Kubernetes node</div><div class="v">{{ i.node }}</div></div>
    <div><div class="k">Namespace</div><div class="v">{{ i.pod_namespace }}</div></div>
    {% endif %}
  </div>
  <div class="fact">💡 {{ fact }}</div>
  <p class="sub" style="margin:18px 0 0">JSON: <a href="/api/info">/api/info</a> · health: <a href="/health">/health</a> · refresh me a few times.</p>
</div></body></html>"""


@app.route("/")
def index():
    global HITS
    HITS += 1
    return render_template_string(PAGE, i=info(), color=APP_COLOR, fact=random.choice(FACTS))


@app.route("/api/info")
def api_info():
    return jsonify(info())


@app.route("/health")
def health():
    return jsonify(status="ok", version=APP_VERSION)


@app.route("/crash")
def crash():
    """Used in a challenge: makes the health check fail so the orchestrator replaces the container."""
    os._exit(1)


if __name__ == "__main__":
    print(f"Mission Control {APP_VERSION} listening on :{PORT}", flush=True)
    app.run(host="0.0.0.0", port=PORT)
