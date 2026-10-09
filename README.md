# Dashboards

Two portfolio dashboards for andreipinter.com, refreshed and published by GitHub Actions the same way as PulseNews.

| Page | What refreshes | When |
|---|---|---|
| `capacity/` Capacity & cost model | The 15-month plan horizon rolls forward so it always starts at the current month. A new final month is built from the same month a year earlier (+3% trend, small fixed noise). Still synthetic sample data. | Checked every morning; changes on the 1st run of each month |
| `hiring/` Hiring command center | Live postings for the four tracked roles (Adzuna jobs API) | Every morning |
| | Unemployment, job openings, hires rate, openings per unemployed worker (BLS), plus a new "What changed" entry when BLS publishes | Mondays (and any manual run) |

```
scheduled run (daily 11:43 UTC)
  ├─ scripts/roll_capacity.py        -> rewrites the data block inside capacity/index.html
  ├─ scripts/refresh_hiring.py live  -> hiring/data.json  (live postings)
  ├─ scripts/refresh_hiring.py weekly (Mondays) -> hiring/data.json (BLS + changelog)
  ├─ commit the refreshed files
  └─ publish to GitHub Pages
```

The hiring page reads `data.json` when it opens and falls back to its built-in snapshot if that file is missing. Each step is independent: if Adzuna or BLS is down, the last good numbers stay up.

## One-time setup

1. **Create the repo** on GitHub (public, empty, e.g. `dashboards`) and push this folder to `main`.
2. **Turn on Pages:** Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. **Add secrets:** Settings → Secrets and variables → Actions → New repository secret.
   - `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`: free at https://developer.adzuna.com (sign up, create an app, copy both values). Without them the live cards show the built-in snapshot.
   - `BLS_API_KEY` (optional): free at https://data.bls.gov/registrationEngine/. Works without it, but the keyless API has a small daily limit.
4. **Run it:** Actions → Refresh dashboards → Run workflow. About a minute.
5. **Open** `https://adpinter-create.github.io/dashboards/`.

### Custom domain (optional, recommended)

Like `pulse.andreipinter.com`:

1. Settings → Pages → Custom domain: `dashboards.andreipinter.com`.
2. In Squarespace DNS for andreipinter.com add a **CNAME**: host `dashboards`, value `adpinter-create.github.io`.
3. When GitHub shows it verified, tick **Enforce HTTPS**.

## Put it on the website

Use a Squarespace **Code block** with an iframe pointing at the hosted page. Do not paste the page HTML itself into Squarespace: a pasted copy never refreshes, and Squarespace's own styles bleed into it (that is what washed out the inputs and headings on the capacity page). The iframe keeps the dashboard's styles sealed off, and the small script sizes it to the page so there is no inner scrollbar.

Capacity model:

```html
<iframe id="apdash-capacity" src="https://dashboards.andreipinter.com/capacity/"
  style="width:100%;height:1400px;border:0;display:block" loading="lazy"
  title="Capacity & cost model"></iframe>
<script>
addEventListener('message',function(e){
  if(e.data&&e.data.type==='apdash-height'&&/capacity/.test(e.data.page)){
    document.getElementById('apdash-capacity').style.height=e.data.height+'px';}});
</script>
```

Hiring command center:

```html
<iframe id="apdash-hiring" src="https://dashboards.andreipinter.com/hiring/"
  style="width:100%;height:1800px;border:0;display:block" loading="lazy"
  title="Hiring command center"></iframe>
<script>
addEventListener('message',function(e){
  if(e.data&&e.data.type==='apdash-height'&&/hiring/.test(e.data.page)){
    document.getElementById('apdash-hiring').style.height=e.data.height+'px';}});
</script>
```

Swap `dashboards.andreipinter.com` for `adpinter-create.github.io/dashboards` if you skip the custom domain. In Squarespace, set the section holding the block to full width so the dashboard has room.

## Changing things

- **Tracked hiring roles:** edit `hiring/roles.json` (title, search terms, location). Keep the titles matching `LIVE_ROLES` in `hiring/index.html`, which holds each card's tag and fallback numbers.
- **Capacity trend:** `TREND` in `scripts/roll_capacity.py`.
- **Schedule:** the `cron` line in `.github/workflows/refresh.yml` (UTC).
- **Test locally:** `python scripts/roll_capacity.py 2027-01` rolls to a given month; `python -m http.server` and open `localhost:8000/hiring/` to preview.
