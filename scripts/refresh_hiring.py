"""Refresh hiring/data.json.

  python scripts/refresh_hiring.py live     # daily: job postings from Adzuna
  python scripts/refresh_hiring.py weekly   # Mondays: BLS headline numbers + "what changed" entry

Secrets (GitHub repo -> Settings -> Secrets and variables -> Actions):
  ADZUNA_APP_ID, ADZUNA_APP_KEY   free at https://developer.adzuna.com  (required for live)
  BLS_API_KEY                     free at https://data.bls.gov/registrationEngine/ (optional)
Standard library only, so the workflow needs no pip install.
"""
import json, os, sys, statistics, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "hiring"
DATA, ROLES = ROOT / "data.json", ROOT / "roles.json"
UA = {"User-Agent": "andreipinter-dashboards/1.0"}


def get_json(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(UA, **({"Content-Type": "application/json"} if data else {}))
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as r:
        return json.load(r)


def today():
    d = datetime.now(timezone.utc)
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")


# ---------------------------------------------------------------- live postings
def refresh_live(data):
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("ADZUNA_APP_ID / ADZUNA_APP_KEY not set; skipping live pull.")
        return False
    out = []
    for role in json.loads(ROLES.read_text())["roles"]:
        q = urllib.parse.urlencode({"app_id": app_id, "app_key": app_key, "what": role["what"],
                                    "where": role["where"], "results_per_page": 30, "sort_by": "date",
                                    "content-type": "application/json"})
        try:
            jobs = get_json(f"https://api.adzuna.com/v1/api/jobs/us/search/1?{q}").get("results", [])
        except Exception as e:  # keep yesterday's numbers for this role
            print(f"{role['title']}: {e}")
            prev = next((r for r in data.get("live", {}).get("roles", []) if r["title"] == role["title"]), None)
            if prev: out.append(prev)
            continue
        # Salary band: prefer advertised pay; fall back to Adzuna's predicted pay.
        paid = [j for j in jobs if j.get("salary_min") and not str(j.get("salary_is_predicted")) == "1"] \
            or [j for j in jobs if j.get("salary_min")]
        lows = sorted(j["salary_min"] for j in paid)
        highs = sorted(j.get("salary_max") or j["salary_min"] for j in paid)
        q1 = lambda xs: xs[int(0.25 * (len(xs) - 1))]
        q3 = lambda xs: xs[int(0.75 * (len(xs) - 1) + 0.5)]
        emps = []
        for j in jobs:
            n = (j.get("company") or {}).get("display_name")
            if n and n not in emps: emps.append(n)
        dates = sorted((j.get("created") or "")[:10] for j in jobs if j.get("created"))
        latest = datetime.strptime(dates[-1], "%Y-%m-%d").strftime("%b %d").replace(" 0", " ") if dates else ""
        out.append({"title": role["title"], "n": len(jobs),
                    "lo": round(q1(lows)) if lows else None, "hi": round(q3(highs)) if highs else None,
                    "emps": emps[:3], "latest": latest,
                    "apply": next((j["redirect_url"] for j in jobs if j.get("redirect_url")), "")})
        print(f"{role['title']}: {len(jobs)} postings")
    data["live"] = {"updated": today(), "roles": out}
    return True


# ---------------------------------------------------------------- weekly BLS
SERIES = {"ue": "LNS14000000",          # unemployment rate, %
          "unemp": "LNS13000000",       # unemployed persons, thousands
          "open": "JTS000000000000000JOL",  # job openings, thousands
          "hires": "JTS000000000000000HIR"}  # hires rate, %


def bls():
    key = os.environ.get("BLS_API_KEY")
    url = "https://api.bls.gov/publicAPI/" + ("v2" if key else "v1") + "/timeseries/data/"
    y = datetime.now(timezone.utc).year
    body = {"seriesid": list(SERIES.values()), "startyear": str(y - 2), "endyear": str(y)}
    if key: body["registrationkey"] = key
    res = get_json(url, body)
    if res.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(res.get("message"))
    out = {}
    for s in res["Results"]["series"]:
        name = next(k for k, v in SERIES.items() if v == s["seriesID"])
        pts = [p for p in s["data"] if p["period"].startswith("M") and p["period"] != "M13" and p["value"] not in ("-", "")]
        pts.sort(key=lambda p: (p["year"], p["period"]), reverse=True)
        out[name] = [{"label": f'{p["periodName"][:3]} {p["year"]}', "v": float(p["value"])} for p in pts[:13]]
    return out


def fmt_m(thousands): return f"{thousands / 1000:.1f}M"


def refresh_weekly(data):
    b = bls()
    prev = data.get("bls") or {}
    ue, op, un, hr = b["ue"], b["open"], b["unemp"], b["hires"]
    ratio = op[0]["v"] / un[0]["v"]
    yr_ago_ue = ue[12]["v"] if len(ue) > 12 else ue[-1]["v"]
    dir_ue = "▲" if ue[0]["v"] > yr_ago_ue else "▼" if ue[0]["v"] < yr_ago_ue else "■"
    dir_op = "▲" if op[0]["v"] > op[1]["v"] else "▼" if op[0]["v"] < op[1]["v"] else "■"
    w = data["weekly"]
    keep = w["kpis"][3] if len(w["kpis"]) > 3 else None  # response-time benchmark is research-sourced, not BLS
    w["kpis"] = [
        {"v": f'{ue[0]["v"]:.1f}%', "l": f'U.S. unemployment ({ue[0]["label"]})',
         "t": f'{dir_ue} {yr_ago_ue:.1f}% a year earlier', "cls": "down" if ue[0]["v"] > yr_ago_ue else "up"},
        {"v": fmt_m(op[0]["v"]), "l": f'Job openings ({op[0]["label"]})',
         "t": f'{dir_op} from {fmt_m(op[1]["v"])} prior month · hires rate {hr[0]["v"]:.1f}%',
         "cls": "up" if op[0]["v"] > op[1]["v"] else "down" if op[0]["v"] < op[1]["v"] else "flat"},
        {"v": f"{ratio:.1f}", "l": "Openings per unemployed worker",
         "t": ("▼ employer's market" if ratio < 1 else "▲ candidate's market"), "cls": "down" if ratio < 1 else "up"},
    ] + ([keep] if keep else [])

    # "What changed": only when a BLS release moved, so quiet weeks don't add noise.
    lines = []
    pu, po = (prev.get("ue") or [{}])[0], (prev.get("open") or [{}])[0]
    if pu.get("label") != ue[0]["label"]:
        lines.append(f'Unemployment for {ue[0]["label"]}: {ue[0]["v"]:.1f}% (previous month {ue[1]["v"]:.1f}%, a year earlier {yr_ago_ue:.1f}%).')
    if po.get("label") != op[0]["label"]:
        lines.append(f'JOLTS for {op[0]["label"]}: {fmt_m(op[0]["v"])} openings vs {fmt_m(op[1]["v"])} the month before; hires rate {hr[0]["v"]:.1f}%.')
        lines.append(f"Openings per unemployed worker now {ratio:.2f} — " + ("still an employer's market." if ratio < 1 else "tilting toward candidates."))
    live = data.get("live", {}).get("roles", [])
    if live:
        lines.append("Live postings sampled this week: " + ", ".join(f'{r["title"]} {r["n"]}' for r in live) + ".")
    if lines and (pu.get("label") != ue[0]["label"] or po.get("label") != op[0]["label"]):
        w["changelog"] = ([{"date": today(), "lines": lines}] + w.get("changelog", []))[:6]
    else:
        print("No new BLS release since last run; KPIs re-checked, changelog unchanged.")
    w["lastUpdated"] = today()
    data["bls"] = b


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    data = json.loads(DATA.read_text())
    if mode == "live":
        refresh_live(data)
    elif mode == "weekly":
        refresh_weekly(data)
    else:
        sys.exit("usage: refresh_hiring.py live|weekly")
    DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
