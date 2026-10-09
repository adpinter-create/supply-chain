"""Roll the capacity model's 15-month plan horizon so it always starts at the current month.

Each month that has passed drops off the front; a new month is added at the end, built from
the same calendar month one year earlier with a small trend and deterministic noise (so
re-running in the same month changes nothing). The data is synthetic sample data either way.

  python scripts/roll_capacity.py            # roll to the current month
  python scripts/roll_capacity.py 2027-01    # roll to a given month (for testing)
"""
import json, random, re, sys
from datetime import date
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "capacity" / "index.html"
BLOCK = re.compile(r'(<script id="data" type="application/json">)(.*?)(</script>)', re.S)
TREND = 1.03  # +3% year over year


def next_month(ym):
    y, m = map(int, ym.split("-"))
    return f"{y + (m == 12)}-{(m % 12) + 1:02d}"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else date.today().strftime("%Y-%m")
    html = PAGE.read_text()
    m = BLOCK.search(html)
    data = json.loads(m.group(2))
    months, rolled = data["months"], 0
    while months[0] < target:
        new = next_month(months[-1])
        dropped = months.pop(0)
        for p in data["products"]:
            gone = p["dem"].pop(0)
            p["ltm"] = max(0, round(p["ltm"] + gone - p["ltm"] / 12))  # trailing-12 roughly absorbs the month
            base = p["dem"][len(p["dem"]) - 12]  # same calendar month, one year before `new`
            rng = random.Random(f'{p["i"]}|{new}')
            p["dem"].append(max(0, round(base * TREND * rng.uniform(0.95, 1.05))))
        months.append(new)
        rolled += 1
        print(f"dropped {dropped}, added {new}")
    if not rolled:
        print(f"horizon already starts at {months[0]}; nothing to do")
        return
    data["today"] = date.today().isoformat()
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    PAGE.write_text(html[:m.start(2)] + payload + html[m.end(2):])
    print(f"horizon now {months[0]} to {months[-1]}")


if __name__ == "__main__":
    main()
