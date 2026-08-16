# Bullion Ledger

A free, fully automated pipeline that scrapes daily gold & silver rates and
displays them on a live dashboard — no server, no PC left running.

**Pipeline:**
`GitHub Actions (daily cron)` → scrapes chandukakasaraf.in → writes/updates
`bullion_history.csv` → commits it back to this repo → `GitHub Pages`
serves `index.html`, which fetches that CSV directly (same-origin) and
renders the charts, valuation, and encrypted purchase tracker in your browser.

## 1. Create the repo

Create a new GitHub repository named `bullion-ledger` (public — GitHub Pages
is free and unlimited for public repos). Upload all files from this folder,
keeping the exact structure:
```text
bullion-ledger/
├── index.html
├── scrape_rates.py
├── requirements.txt
├── bullion_history.csv
├── README.md
└── .github/
    └── workflows/
        ├── scrape-rates.yml
        └── ingest-price-entry.yml

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

## 6. Add a manual weekly price update

The **History** tab has an "Add Weekly Price Update" form. Since GitHub Pages
is static and can't hold a write credential safely, it doesn't commit
directly — instead:

1. Fill in date + the four prices, click **Add Entry via GitHub**.
2. A new tab opens with a pre-filled GitHub Issue titled `Price Update: YYYY-MM-DD`.
You need to be logged into GitHub. Click **Submit new issue**.
3. The `ingest-price-entry.yml` workflow fires automatically, parses the
issue body, writes/updates that date's row in `bullion_history.csv`,
commits it, comments "✅ done" on the issue, and closes it.
4. Reload the dashboard ~20–30 seconds later — the new entry is in the chart
and history table.

You can also file that issue by hand (skip the dashboard) as long as the
title starts with `Price Update:` and the body has these lines:

```text
date: 2026-08-23
gold_24kt: 15400
gold_22kt: 14250
gold_18kt: 11800
silver_per_gram: 238

```

If a submission is malformed, the workflow comments on the issue explaining
what it expected, instead of closing it silently.

## 7. Purchase Tracking & Encryption

The **Purchases** tab allows you to log, edit, and track your physical bullion portfolio against live historical valuation and return analytics:

* **Client-Side AES-256 Encryption:** All purchase entries are encrypted locally in your browser using PBKDF2 key derivation and AES-GCM 256-bit encryption before being written to `localStorage`. Your private financial data is never exposed in plain text.
* **Master Password:** You will set a master password upon first access. If you lock the tab or refresh the page, you must re-enter your password to decrypt and view your portfolio.
* **Interactive Editing & Auto-Fill:** You can edit or delete existing purchase records at any time. The **Edit Purchase Modal** automatically looks up historical CSV rate data based on the selected date/asset and recalculates total costs and quantities dynamically.
* **Automatic Migration:** Legacy unencrypted records in `localStorage` are automatically detected and prompted for migration into encrypted storage upon setting up a master password.

## Notes

* **Local File System Restriction:** Web browsers block direct `fetch()` calls to local files (`file://`). If testing locally on your PC, serve the repository directory using a local web server (e.g., `python3 -m http.server 8000`).
* **Purchases Privacy:** Encrypted purchases stay inside your browser's local storage per device and are never committed to your GitHub repository.
* **Diamonds / other metals**: `bullion_history.csv` already has a
`diamond_per_carat` placeholder column. Once you have a scrapeable
source for diamond or other precious-metal prices, extend
`scrape_rates.py` with another `grab(...)` pattern and add the metal to
the `METAL_LABELS` / `COLORS` objects in `index.html`.
* If the source site changes its markup and the scraper starts failing,
the workflow run will show a red ✗ in the Actions tab with the error
message from `extract_rates()` telling you which field it couldn't find.