"""Lab 6 lifecycle hook: before any customer sees the new release, order EVERY pizza on its menu
through the ALB's test listener (which only the new, "green" tasks receive). One bad pizza = FAILED,
and ECS rolls the deployment back before production traffic moves.

ECS calls this function at POST_TEST_TRAFFIC_SHIFT with the test URL in hookDetails, e.g.
  {"lifecycleStage": "POST_TEST_TRAFFIC_SHIFT", "hookDetails": {"testUrl": "http://my-alb-123.us-west-2.elb.amazonaws.com:8080"}, ...}
It must answer {"hookStatus": "SUCCEEDED" | "FAILED" | "IN_PROGRESS"}.
"""
import json
import urllib.error
import urllib.request

ROUNDS = 3   # each pizza several times: green has several tasks behind the test listener


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, {}
    except Exception as e:  # timeouts, refused connections
        return 0, {"error": str(e)}


def handler(event, context):
    print(json.dumps({"stage": event.get("lifecycleStage"), "deployment": event.get("resourceArn")}))
    base = (event.get("hookDetails") or {}).get("testUrl", "").rstrip("/")
    if not base:
        print("no testUrl in hookDetails"); return {"hookStatus": "FAILED"}

    status, menu = get(f"{base}/api/menu")
    if status != 200:
        print(f"menu unavailable on the test listener: {status} {menu}"); return {"hookStatus": "FAILED"}
    release, failures, ok = menu.get("release"), [], 0
    for _ in range(ROUNDS):
        for pizza in menu["menu"]:
            code, body = get(f"{base}/api/order?src=menu-walker&pizza={pizza}")
            if code == 200:
                ok += 1
            else:
                failures.append(f"{pizza}: HTTP {code} {body.get('error', '')}")
    print(json.dumps({"release": release, "ordered": ok + len(failures), "ok": ok, "failures": failures}, ensure_ascii=False))
    return {"hookStatus": "FAILED" if failures else "SUCCEEDED"}
