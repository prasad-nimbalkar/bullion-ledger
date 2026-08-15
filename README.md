# Bullion Ledger

A free, fully automated pipeline that scrapes daily gold & silver rates and
displays them on a live dashboard — no server, no PC left running.

**Pipeline:**
`GitHub Actions (daily cron)` → scrapes chandukakasaraf.in → writes/updates
`bullion_history.csv` → commits it back to this repo → `GitHub Pages`
serves `index.html`, which fetches that CSV directly (same-origin) and
renders the charts, valuation, and purchase tracker in your browser.

## 1. Create the repo

Create a new GitHub repository named `bullion-ledger` (public — GitHub Pages
is free and unlimited for public repos). Upload all files from this folder,
keeping the exact structure:

```
bullion-ledger/
├── index.html
├── scrape_rates.py
├── requirements.txt
├── bullion_history.csv
└── .github/
    └── workflows/
        └── scrape-rates.yml
```

## 2. Let Actions write to the repo

Settings → Actions → General → Workflow permissions →
select **Read and write permissions** → Save.
(Without this, the scraper can fetch data but can't commit it back.)

## 3. Turn on GitHub Pages

Settings → Pages → Build and deployment → Source: **Deploy from a branch**
→ Branch: **main**, folder **/(root)** → Save.
GitHub will give you a URL like `https://yourusername.github.io/bullion-ledger/`.
That's your live dashboard.

## 4. Run the scraper once manually

Actions tab → "Daily Bullion Rate Scrape" → **Run workflow**.
Check that `bullion_history.csv` gets a new/updated row committed.
Then open your Pages URL — it should show that data.

## 5. Sit back

The workflow runs automatically every day at 06:00 UTC (11:30 AM IST).
Each run overwrites *today's* row if the site's already been scraped once
that day, so you always get one clean row per date — never duplicates.

## Notes

- **Purchases** you log on the dashboard are saved in your browser's
  `localStorage` — they're per-browser/device, not synced to GitHub. That's
  intentional (keeps personal investment amounts out of a public repo). If
  you'd rather have them versioned too, say so and this can be switched to
  a second CSV committed by a small "log purchase" GitHub Action instead.
- **Diamonds / other metals**: `bullion_history.csv` already has a
  `diamond_per_carat` placeholder column. Once you have a scrapeable
  source for diamond or other precious-metal prices, extend
  `scrape_rates.py` with another `grab(...)` pattern and add the metal to
  the `METAL_LABELS` / `COLORS` objects in `index.html`.
- If the source site changes its markup and the scraper starts failing,
  the workflow run will show a red ✗ in the Actions tab with the error
  message from `extract_rates()` telling you which field it couldn't find.
