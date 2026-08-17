# Bullion Ledger

An open-source, private gold and silver portfolio tracker powered by automated daily price feeds and client-side encryption. Built with static HTML/JS and hosted on GitHub Pages, Bullion Ledger requires no backend servers or database infrastructure.

---

## Architecture & How It Works

Bullion Ledger uses a zero-server pipeline to fetch, store, and visualize precious metal rates while keeping personal investment records completely private.

```text
[ Daily Cron / GitHub Action ]
             │
             ▼
    [ scrape_rates.py ] ──────► Scraped daily rates
             │
             ▼
   [ bullion_history.csv ] ────► Committed back to repository
             │
             ▼
     [ GitHub Pages ] ─────────► Serves index.html to client browser
                                       │
                                       ▼
                       [ Browser LocalStorage ] (AES-256 Encrypted Holdings)

```

1. **Daily Web Scraper:** A Python script (`scrape_rates.py`) runs every morning via GitHub Actions, scraping gold (24K, 22K, 18K) and silver prices.
2. **Automated Commit:** The scraped data is appended or updated in `bullion_history.csv` and committed back to the repository.
3. **Static Dashboard:** GitHub Pages serves `index.html`, which fetches `bullion_history.csv` directly in the browser to render live charts, historical tables, and valuation analytics.
4. **Client-Side Portfolio:** Personal purchase entries are decrypted and computed exclusively inside your browser's memory using `localStorage`.

---

## Key Features

* **Automated Rate Ingestion:** Daily scheduled runs keep historical gold and silver prices up to date without manual intervention.
* **AES-256 Client-Side Encryption:** Portfolio records are encrypted locally using PBKDF2 key derivation and AES-GCM 256-bit encryption before saving to browser storage.
* **Interactive Purchase Management:** Modal dialogs allow adding, editing, and deleting physical holdings with automatic calculations for unit price, total cost, and weight.
* **Historical Rate Auto-Fill:** Selecting a purchase date automatically queries `bullion_history.csv` to auto-populate historical market rates.
* **Issue-Based Price Updates:** Submit missing historical rates through the dashboard using automated GitHub Issues parsed by a secondary workflow (`ingest-price-entry.yml`).

---

## Step-by-Step Setup Guide

### 1. Repository File Structure

Ensure your repository contains the following files:

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

### 2. Configure Workflow Permissions

GitHub Actions requires write access to commit updated CSV price data back to your repository:

1. Navigate to **Settings** → **Actions** → **General**.
2. Scroll down to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

### 3. Enable GitHub Pages

1. Navigate to **Settings** → **Pages**.
2. Under **Build and deployment** → **Source**, select **Deploy from a branch**.
3. Set the branch to **`main`** and the directory to **`/(root)`**.
4. Click **Save**.

GitHub will generate your live dashboard URL (e.g., `https://<username>.github.io/bullion-ledger/`).

### 4. Trigger the Initial Scrape

1. Go to the **Actions** tab in your repository.
2. Select the **Daily Bullion Rate Scrape** workflow on the left sidebar.
3. Click **Run workflow** → **Run workflow**.
4. Once completed, verify that `bullion_history.csv` has been updated and open your GitHub Pages URL.

---

## Manual Price Updates via GitHub Issues

If a historical date is missing from the CSV, you can submit an update directly through GitHub without manually editing files:

1. Open the **History** tab on your live dashboard and fill out the **Add Weekly Price Update** form.
2. Click **Add Entry via GitHub** to open a pre-filled GitHub Issue titled `Price Update: YYYY-MM-DD`.
3. Submit the issue. The `ingest-price-entry.yml` workflow will automatically parse the issue body, append the entry to `bullion_history.csv`, commit the change, and close the issue.

---

## Privacy & Security

Your financial records, purchase quantities, and purchase costs are **never** committed to GitHub or transmitted to any external server.

* All personal holding data remains strictly inside your browser's `localStorage`.
* Data is protected using a master password with AES-256 bit encryption.
* Even if your GitHub repository is set to public, your portfolio values remain private to your local device and master password.

---

## Local Development Note

Web browsers block standard `fetch()` API calls to local file paths (`file://`) due to CORS security policies. When developing or testing locally on your machine, serve the project folder through a local HTTP server:

```bash
# Navigate to project directory
cd bullion-ledger

# Start a local Python HTTP server
python3 -m http.server 8000

```

Open `http://localhost:8000` in your browser to view and test the application locally.
