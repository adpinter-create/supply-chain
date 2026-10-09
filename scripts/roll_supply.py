"""Roll the supply planner forward so "Plan as of" is today and the horizon starts this month.

Layout per SKU (27 history months + 15 forward months, constant lengths):
  h  history (actual demand)      bk backlog/booked orders      cf customer forecast
  pl demand plan                  sp scheduled supply           oh on hand
  c  per-customer [name, ..., forward forecast array]
For each month that has passed: the oldest history month drops off, the elapsed month becomes
history (plan with deterministic noise, never below what was booked), the plan shifts left with a
new final month from the same month a year earlier (+3%), and booked orders, customer forecast,
supply and on-hand keep the same proportion to the plan at each position, so the page keeps the
same character (exception count, months of cover) as it moves forward. Deterministic, so a re-run in the same month changes nothing.
Synthetic sample data either way.

  python scripts/roll_supply.py            # roll to the current month
  python scripts/roll_supply.py 2027-01    # roll to a given month (testing)
"""
import json, random, re, sys
from datetime import date
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "supply-planner" / "index.html"
BLOCK = re.compile(r'(<script id="data" type="application/json">)(.*?)(</script>)', re.S)
TREND = 1.03
H = 27  # history months; must match `H` in the page script


def next_month(ym):
    y, m = map(int, ym.split("-"))
    return f"{y + (m == 12)}-{(m % 12) + 1:02d}"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else date.today().strftime("%Y-%m")
    html = PAGE.read_text(encoding="utf-8")
    m = BLOCK.search(html)
    data = json.loads(m.group(2))
    months, rolled = data["months"], 0
    while months[H] < target:  # months[H] is the first forward (current) month
        elapsed, new = months[H], next_month(months[-1])
        for s in data["skus"]:
            rng = random.Random(f'{s["i"]}|{s["e"]}|{elapsed}')
            old_pl = s["pl"]
            actual = max(s["bk"][0], round(old_pl[0] * rng.uniform(0.85, 1.15)))
            s["h"] = s["h"][1:] + [actual]
            base = old_pl[len(old_pl) - 12]  # plan for the same calendar month last year
            new_pl = old_pl[1:] + [max(0, round(base * TREND * rng.uniform(0.95, 1.05)))]

            # Keep each forward position's shape relative to the plan: month 1 keeps month 1's
            # share of booked orders, customer forecast and inbound supply, and so on.
            def reshape(arr):
                return [round(n * a / o) if o else a for a, o, n in zip(arr, old_pl, new_pl)]
            for k in ("bk", "cf", "sp"):
                s[k] = reshape(s[k])
            for cust in s.get("c", []):
                cust[-1] = reshape(cust[-1])
            # Same months of cover as before.
            s["oh"] = round(s["oh"] * new_pl[0] / old_pl[0]) if old_pl[0] else s["oh"]
            s["pl"] = new_pl
        months.pop(0)
        months.append(new)
        rolled += 1
        print(f"closed {elapsed}, added {new}")
    if not rolled:
        print(f"plan already starts at {months[H]}; nothing to do")
        return
    data["today"] = date.today().isoformat()
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    PAGE.write_text(html[:m.start(2)] + payload + html[m.end(2):], encoding="utf-8")
    print(f"plan now {months[H]} to {months[-1]}")


if __name__ == "__main__":
    main()
