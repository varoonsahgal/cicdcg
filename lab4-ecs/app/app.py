"""Mission Control – a tiny web app that tells you *where* and *how* it is running.

Every page load shows the container's hostname (= the ECS task / Kubernetes pod), the
image version baked in at build time, uptime, a per-container request counter, the
CPU/memory limits the orchestrator gave this container, who the process runs as, and
– on ECS – the task ID and availability zone from the task metadata endpoint. It can
also show a "message of the day" read from a file (a Kubernetes ConfigMap, Lab 5) or
from SSM Parameter Store using the task role (Lab 4). That makes rolling updates,
scaling, load balancing, configuration, IAM and resource limits *visible*.

Endpoints
  /            the page                      /api/info    the same data as JSON
  /health      liveness: 200 while alive     /ready       readiness: 200 or 503 (toggle below)
  /ready/off   make this container NOT ready /ready/on    make it ready again
  /crash       exit(1) on purpose            /hog?mb=N    eat N MiB of memory on purpose
"""
import json
import logging
import os
import pwd
import random
import socket
import sys
import time
import urllib.request
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string, request

APP_VERSION = os.environ.get("APP_VERSION", "dev")
APP_COLOR = os.environ.get("APP_COLOR", "#38BDF8")      # change me in a new task-definition revision / ConfigMap
MISSION = os.environ.get("MISSION_NAME", "Artemis-NN")  # change me too
PORT = int(os.environ.get("PORT", "8080"))
MOTD_FILE = os.environ.get("MOTD_FILE", "")             # Lab 5: a ConfigMap mounted as a file
MOTD_PARAMETER = os.environ.get("MOTD_PARAMETER", "")   # Lab 4: an SSM Parameter Store name, read with the task role
HOG_CAP_MB = int(os.environ.get("HOG_CAP_MB", "2048"))  # /hog never allocates more than this
STARTED = time.time()
HITS = 0
READY = True

FACTS = [
    "A container image is just a stack of read-only layers plus a little metadata.",
    "`docker build` does not run your app. It runs each Dockerfile line in a throw-away container and keeps the result.",
    "Two tasks from the same image share nothing at runtime: no files, no memory, no counters. Look at the hit counter!",
    "Fargate bills per vCPU-second and GB-second, rounded up to one minute. This task is 0.25 vCPU / 0.5 GB.",
    "An ECS *task definition* is a versioned recipe. You never edit revision 3; you create revision 4.",
    "A rolling update starts new tasks before it stops old ones. Watch the hostname change when you refresh.",
    "`latest` is not a version. It is whatever was pushed last. Deploy immutable tags like v7, or a digest.",
    "Tags move; digests do not. image@sha256:… is the only reference that means exactly one image, forever.",
    "The task *execution* role pulls the image and ships logs. The task *role* is what your code uses at runtime. They are different robots.",
    "Kubernetes calls the same idea a Pod, a Deployment and a Service. Same physics, different vocabulary.",
    "Health checks turn 'the process is running' into 'the app is answering'. Deploy tools trust the second one.",
    "A failing readiness probe takes a Pod out of the Service. A failing liveness probe restarts it. Two probes, two jobs.",
    "Exit code 137 = 128 + 9: the kernel sent SIGKILL. Nine times out of ten that is the memory limit.",
    "A ConfigMap mounted as a file updates inside running Pods within about a minute. An env var does not: it was copied at start.",
    "This image carries no credentials. On ECS the task role appears as a tiny HTTP endpoint; on EKS it would be Pod Identity.",
]

app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.ERROR)   # we write our own one-line-per-request JSON log below


# ── helpers ──────────────────────────────────────────────────────────────────
def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _user():
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        return f"uid {os.getuid()}"


def limits():
    """What the orchestrator allows this container, read from cgroups (v2 first, then v1)."""
    out = {}
    mem = _read("/sys/fs/cgroup/memory.max") or _read("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if mem and mem != "max" and int(mem) < (1 << 50):
        out["memory_limit_mib"] = int(mem) // (1024 * 1024)
    used = _read("/sys/fs/cgroup/memory.current") or _read("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    if used:
        out["memory_used_mib"] = int(used) // (1024 * 1024)
    cpu = _read("/sys/fs/cgroup/cpu.max")
    if cpu:
        quota, period = cpu.split()
        if quota != "max":
            out["cpu_limit_vcpu"] = round(int(quota) / int(period), 2)
    else:
        q, p = _read("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"), _read("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
        if q and p and int(q) > 0:
            out["cpu_limit_vcpu"] = round(int(q) / int(p), 2)
    return out


def ecs_metadata():
    """A few fields from the ECS task metadata endpoint (empty dict anywhere else)."""
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


_ssm = None


def motd():
    """Message of the day: from a mounted file (Kubernetes ConfigMap) or from SSM Parameter Store (ECS task role)."""
    if MOTD_FILE:
        text = _read(MOTD_FILE)
        if text is None:
            return {"source": f"file {MOTD_FILE}", "error": "file not found – is the volume mounted?"}
        return {"source": f"file {MOTD_FILE}", "text": text}
    if MOTD_PARAMETER:
        global _ssm
        src = f"SSM parameter {MOTD_PARAMETER}"
        try:
            import boto3
            from botocore.config import Config
            if _ssm is None:
                region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2"
                _ssm = boto3.client("ssm", region_name=region,
                                    config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 1}))
            value = _ssm.get_parameter(Name=MOTD_PARAMETER, WithDecryption=True)["Parameter"]["Value"]
            return {"source": src, "text": value}
        except Exception as e:  # show the error on the page: that *is* the lesson
            return {"source": src, "error": f"{type(e).__name__}: {e}"}
    return {}


def mask(value):
    if not value:
        return ""
    return value[:4] + "…" + "•" * max(0, min(8, len(value) - 4))


def info():
    now = time.time()
    return {
        "mission": MISSION,
        "version": APP_VERSION,
        "color": APP_COLOR,
        "hostname": socket.gethostname(),
        "pod_name": os.environ.get("POD_NAME", ""),           # set by the Kubernetes manifest (Downward API)
        "node": os.environ.get("NODE_NAME", ""),
        "pod_namespace": os.environ.get("POD_NAMESPACE", ""),
        "started_at": datetime.fromtimestamp(STARTED, timezone.utc).isoformat(timespec="seconds"),
        "uptime_seconds": int(now - STARTED),
        "hits_on_this_container": HITS,
        "ready": READY,
        "pid": os.getpid(),
        "user": _user(),
        "limits": limits(),
        "launch_code": mask(os.environ.get("LAUNCH_CODE")),  # Lab 5: injected from a Secret, shown masked
        "motd": motd(),
        "ecs": ecs_metadata(),
    }


def log(event, **fields):
    line = {"time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": event,
            "hostname": socket.gethostname(), "version": APP_VERSION, **fields}
    print(json.dumps(line), flush=True)


@app.after_request
def access_log(resp):
    # One JSON line per request. Query it with CloudWatch Logs Insights (Lab 4) or read it with kubectl logs (Lab 5).
    log("request", method=request.method, path=request.path, status=resp.status_code,
        probe=request.path in ("/health", "/ready"), remote=request.remote_addr)
    return resp


# ── the page ─────────────────────────────────────────────────────────────────
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{{ i.mission }} · Mission Control {{ i.version }}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root { --c: {{ i.color }}; }
  body { margin:0; min-height:100vh; display:grid; place-items:center; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: radial-gradient(1200px 600px at 20% -10%, color-mix(in srgb, var(--c) 35%, #0B1220), #0B1220 60%); color:#E2E8F0; }
  .card { width:min(720px, 92vw); background:rgba(15,24,41,.9); border:1px solid rgba(255,255,255,.08); border-radius:20px; padding:34px 38px; box-shadow:0 30px 80px rgba(0,0,0,.5); }
  h1 { margin:0 0 4px; font-size:34px; letter-spacing:-.01em; } h1 span { color:var(--c); }
  .sub { color:#94A3B8; margin:0 0 22px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px 22px; font-size:15px; }
  .k { color:#94A3B8; font-size:12px; letter-spacing:.08em; text-transform:uppercase; } .v { font-family: ui-monospace, Menlo, monospace; word-break:break-all; }
  .big { font-size:22px; color:var(--c); font-weight:700; }
  .fact { margin-top:24px; padding:14px 16px; border-left:4px solid var(--c); background:rgba(255,255,255,.04); border-radius:0 12px 12px 0; color:#CBD5E1; font-size:15px; }
  .motd { margin-top:16px; padding:14px 16px; border-radius:12px; background:rgba(34,197,94,.10); border:1px solid rgba(34,197,94,.35); color:#DCFCE7; font-size:15px; }
  .motd.err { background:rgba(239,68,68,.10); border-color:rgba(239,68,68,.45); color:#FECACA; font-family: ui-monospace, Menlo, monospace; font-size:13px; }
  .motd .k { margin-bottom:4px; }
  .badge { display:inline-block; padding:4px 10px; border-radius:999px; background:var(--c); color:#0B1220; font-weight:700; font-size:13px; }
  .badge.off { background:#EF4444; color:#fff; }
  .badge.ok { background:#22C55E; color:#0B1220; }
  a { color:var(--c); }
</style></head><body><div class="card">
  <h1>🚀 <span>{{ i.mission }}</span> Mission Control</h1>
  <p class="sub">Served by one container, somewhere in us-west-2. <span class="badge">{{ i.version }}</span>
     {% if i.ready %}<span class="badge ok">READY</span>{% else %}<span class="badge off">NOT READY</span>{% endif %}</p>
  <div class="grid">
    <div><div class="k">Container hostname</div><div class="v big">{{ i.hostname }}</div></div>
    <div><div class="k">Requests this container has seen</div><div class="v big">{{ i.hits_on_this_container }}</div></div>
    <div><div class="k">Uptime</div><div class="v">{{ i.uptime_seconds }} s · started {{ i.started_at }}</div></div>
    <div><div class="k">Running as</div><div class="v">{{ i.user }} · pid {{ i.pid }}</div></div>
    <div><div class="k">Memory (cgroup)</div><div class="v">{% if i.limits.memory_limit_mib %}{{ i.limits.memory_used_mib }} MiB used of {{ i.limits.memory_limit_mib }} MiB limit{% else %}{{ i.limits.memory_used_mib or '?' }} MiB used · no container limit visible{% endif %}</div></div>
    <div><div class="k">CPU limit</div><div class="v">{% if i.limits.cpu_limit_vcpu %}{{ i.limits.cpu_limit_vcpu }} vCPU{% else %}none visible{% endif %}</div></div>
    <div><div class="k">Colour (env APP_COLOR)</div><div class="v">{{ i.color }}</div></div>
    {% if i.launch_code %}<div><div class="k">Launch code (from a Secret)</div><div class="v">{{ i.launch_code }}</div></div>{% endif %}
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
  {% if i.motd %}
    {% if i.motd.text %}<div class="motd"><div class="k">Message of the day · {{ i.motd.source }}</div>{{ i.motd.text }}</div>
    {% else %}<div class="motd err"><div class="k">Message of the day · {{ i.motd.source }}</div>{{ i.motd.error }}</div>{% endif %}
  {% endif %}
  <div class="fact">💡 {{ fact }}</div>
  <p class="sub" style="margin:18px 0 0">JSON: <a href="/api/info">/api/info</a> · liveness: <a href="/health">/health</a> · readiness: <a href="/ready">/ready</a> · refresh me a few times.</p>
</div></body></html>"""


# ── routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    global HITS
    HITS += 1
    return render_template_string(PAGE, i=info(), fact=random.choice(FACTS))


@app.route("/api/info")
def api_info():
    return jsonify(info())


@app.route("/health")
def health():
    """Liveness: answers 200 as long as the process can serve a request at all."""
    return jsonify(status="ok", version=APP_VERSION)


@app.route("/ready")
def ready():
    """Readiness: 200 when this container wants traffic, 503 when it does not."""
    return jsonify(ready=READY, hostname=socket.gethostname()), (200 if READY else 503)


@app.route("/ready/<state>", methods=["GET", "POST"])
def set_ready(state):
    """Used in Lab 5: /ready/off makes the readiness probe fail without killing the process."""
    global READY
    if state not in ("on", "off"):
        return jsonify(error="use /ready/on or /ready/off"), 400
    READY = state == "on"
    log("readiness-changed", ready=READY)
    return jsonify(ready=READY, hostname=socket.gethostname(),
                   note="readiness probes decide whether this container receives traffic; the process keeps running")


@app.route("/crash")
def crash():
    """Used in an exercise: the essential process exits, so the orchestrator must replace or restart the container."""
    log("crash", note="exiting with code 1 on purpose")
    os._exit(1)


@app.route("/hog")
def hog():
    """Used in an exercise: allocate memory until the orchestrator's limit kills us (exit code 137).
    Outside a container (no limit) it stops at min(?mb, HOG_CAP_MB) and frees the memory again."""
    want = min(int(request.args.get("mb", "1024")), HOG_CAP_MB)
    chunk = 32 * 1024 * 1024
    held, got = [], 0
    log("hog-start", target_mib=want)
    while got < want * 1024 * 1024:
        held.append(bytearray(b"\xAA") * chunk)   # really touch the pages, or the kernel will not count them
        got += chunk
        if (got // chunk) % 4 == 0:
            log("hog-progress", allocated_mib=got // (1024 * 1024), **limits())
        time.sleep(0.05)
    held.clear()
    log("hog-survived", allocated_mib=got // (1024 * 1024))
    return jsonify(allocated_mib=got // (1024 * 1024), survived=True,
                   message="No memory limit stopped me. Inside a limited container you would never see this response.")


if __name__ == "__main__":
    log("startup", port=PORT, user=_user(), **limits())
    print(f"Mission Control {APP_VERSION} listening on :{PORT}", flush=True)
    app.run(host="0.0.0.0", port=PORT, threaded=True)
