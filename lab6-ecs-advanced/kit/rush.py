#!/usr/bin/env python3
"""Rush hour from the command line. Orders pizzas through your load balancer and prints, every
5 seconds, which release baked them and how many came back burnt.

  python3 ~/lab6/rush.py                      # production listener, 10 orders/second
  python3 ~/lab6/rush.py --port 8080 --rate 4 # the test listener
Ctrl+C to stop.
"""
import argparse, collections, json, os, random, threading, time, urllib.error, urllib.request

WEIGHT = {"margherita": 30, "meteor-pepperoni": 25, "nebula-veggie": 15, "pineapple-pulsar": 20, "saturn-rings": 10}
known = ["margherita", "meteor-pepperoni", "nebula-veggie", "pineapple-pulsar"]   # customers learn new pizzas from any menu
ap = argparse.ArgumentParser()
ap.add_argument("--host", default=os.environ.get("ALB_DNS"))
ap.add_argument("--port", type=int, default=80)
ap.add_argument("--rate", type=float, default=10)
a = ap.parse_args()
base = f"http://{a.host}:{a.port}"
win, lock = collections.Counter(), threading.Lock()


def learn():
    try:
        with urllib.request.urlopen(f"{base}/api/menu", timeout=3) as r:
            for k in json.load(r)["menu"]:
                if k not in known:
                    known.append(k)
    except Exception:
        pass


def order():
    pizza = random.choices(known, weights=[WEIGHT.get(k, 10) for k in known])[0]
    try:
        with urllib.request.urlopen(f"{base}/api/order?src=rush-cli&pizza={pizza}", timeout=5) as r:
            key = (json.load(r)["release"], "ok")
    except urllib.error.HTTPError as e:
        try:
            key = (json.load(e)["release"], {500: "burnt", 404: "not on menu"}.get(e.code, str(e.code)))
        except Exception:
            key = ("ALB", str(e.code))           # e.g. 503 from the load balancer itself
    except Exception:
        key = ("network", "error")
    with lock:
        win[key] += 1


learn()
print(f"Ordering from {base} at {a.rate}/s. Ctrl+C to stop.")
nxt = time.time() + 5
try:
    while True:
        threading.Thread(target=order, daemon=True).start()
        time.sleep(1 / a.rate)
        if time.time() >= nxt:
            nxt += 5
            threading.Thread(target=learn, daemon=True).start()
            with lock:
                snap, total = dict(win), sum(win.values()); win.clear()
            rel = collections.Counter()
            for (r, _), n in snap.items():
                rel[r] += n
            parts = []
            for r in sorted(rel):
                bad = {s: n for (rr, s), n in snap.items() if rr == r and s != "ok"}
                parts.append(f"{r}: {100 * rel[r] / total:5.1f}%" + "".join(f" · {n} {s}" for s, n in bad.items()))
            print(time.strftime("%H:%M:%S"), f"{total:3d} orders |", "  ".join(parts), flush=True)
except KeyboardInterrupt:
    pass
