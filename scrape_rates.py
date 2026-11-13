"""
Bullion Ledger — daily rate scraper (chandukakasaraf.in)
Appends / updates today's row in bullion_history.csv at the repo root.
Run by .github/workflows/scrape-rates.yml on a daily cron.

Designed to be extended: add new metals/assets by adding an entry to LABELS
and a new column in FIELDNAMES + the row dict below.
"""

import re
import csv
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://chandukakasaraf.in/todays-gold-rate/"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bullion_history.csv")
IST = ZoneInfo("Asia/Kolkata")

# A new day's price may not differ from the last stored row by more than this
# (guards against a mis-parsed number silently entering your history).
# To accept a genuine big move, run with  BULLION_ALLOW_JUMP=1.
MAX_MOVE = 0.25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://chandukakasaraf.in/",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

FIELDNAMES = [
    "date", "scraped_at_utc", "site_updated_at",
    "gold_24kt", "gold_22kt", "gold_18kt",
    "silver_per_gram", "platinum_950",
    "diamond_per_carat",  # placeholder column — populate once a diamond price source is added
]

# Each label must be followed *immediately* by "<currency><amount> PER 1 <unit>".
# Anchoring on that (instead of an open-ended ".*?") means a product name such as
# "24kt Gold Vedhani Plain 5 gm", or a menu item such as "Silver", can never be
# mistaken for a rate.
CUR = r"(?:₹|Rs\.?|INR)"
NUM = r"([\d,]+(?:\.\d+)?)"
UNIT = r"(?:PER|/)\s*1?\s*(GM|G|GRAM|KG)\b"
LABELS = {
    "gold_18kt":    r"18\s*(?:KT|K|Karat)\s*Gold",
    "gold_22kt":    r"22\s*(?:KT|K|Karat)\s*Gold",
    "gold_24kt":    r"24\s*(?:KT|K|Karat)\s*Gold",
    "platinum_950": r"Platinum[\s\-]*950",
    "silver":       r"Silver",
}


def fetch_page() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    print(f"HTTP status: {resp.status_code} | content-length: {len(resp.text)} chars")
    resp.raise_for_status()
    return resp.text


def _per_gram(text: str, label: str):
    """First '<label> <currency><amount> PER 1 <unit>' in the text, as ₹ per gram."""
    m = re.search(rf"{label}\W{{0,12}}?{CUR}\s*{NUM}\s*{UNIT}", text, re.IGNORECASE)
    if not m:
        return None
    amount = float(m.group(1).replace(",", ""))
    unit = m.group(2).upper()
    return amount / 1000 if unit == "KG" else amount   # the site quotes silver per KG


def extract_rates(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    # separator keeps neighbouring cells apart; get_text() already skips <script>/<style>
    text = soup.get_text(separator=" ", strip=True)

    ts = re.search(r"Updated\s*On\s*:?\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})", text, re.IGNORECASE)
    site_updated_at = f"{ts.group(1)} {ts.group(2)}" if ts else None

    found = {key: _per_gram(text, pattern) for key, pattern in LABELS.items()}

    required = {"18KT": "gold_18kt", "22KT": "gold_22kt", "24KT": "gold_24kt", "Silver": "silver"}
    missing = [name for name, key in required.items() if found[key] is None]
    if missing:
        print("---- DEBUG: first 800 chars of extracted text ----")
        print(text[:800])
        print("---- END DEBUG ----")
        debug_path = os.path.join(os.path.dirname(CSV_PATH), "debug_last_response.html")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        raise ValueError(
            f"Could not extract: {', '.join(missing)}. "
            f"Site markup may have changed, or the request was blocked/served a different "
            f"page (bot protection, redirect, etc). See the DEBUG output above and the "
            f"'debug_last_response.html' artifact uploaded from this run."
        )

    return {
        "site_updated_at": site_updated_at,
        "gold_24kt": found["gold_24kt"],
        "gold_22kt": found["gold_22kt"],
        "gold_18kt": found["gold_18kt"],
        "platinum_950": found["platinum_950"],
        "silver_per_gram": round(found["silver"], 2),
    }


def validate(rates: dict, previous_row: dict | None) -> None:
    """Refuse to store numbers that are structurally impossible or wildly off."""
    g24, g22, g18 = rates["gold_24kt"], rates["gold_22kt"], rates["gold_18kt"]
    if not (g24 > g22 > g18 > 0):
        raise ValueError(f"Gold purities out of order (24K={g24}, 22K={g22}, 18K={g18}) — likely a mis-parse.")

    if previous_row and os.environ.get("BULLION_ALLOW_JUMP") != "1":
        for key in ("gold_24kt", "gold_22kt", "gold_18kt", "silver_per_gram"):
            try:
                prev = float(previous_row[key])
            except (KeyError, TypeError, ValueError):
                continue
            if prev > 0 and abs(rates[key] - prev) / prev > MAX_MOVE:
                raise ValueError(
                    f"{key} moved {rates[key]} vs previous {prev} (>{MAX_MOVE:.0%}). "
                    f"If this is real, rerun with BULLION_ALLOW_JUMP=1; otherwise check the parser."
                )


def load_existing_rows() -> list:
    if not os.path.isfile(CSV_PATH):
        return []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_rows(rows: list) -> None:
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def upsert_today(rates: dict) -> dict:
    now = datetime.now(timezone.utc)
    today = now.astimezone(IST).strftime("%Y-%m-%d")   # Indian rates -> Indian calendar date
    row = {
        "date": today,
        "scraped_at_utc": now.isoformat(timespec="seconds"),
        "site_updated_at": rates["site_updated_at"],
        "gold_24kt": rates["gold_24kt"],
        "gold_22kt": rates["gold_22kt"],
        "gold_18kt": rates["gold_18kt"],
        "silver_per_gram": rates["silver_per_gram"],
        "platinum_950": rates["platinum_950"],
        "diamond_per_carat": "",
    }

    rows = load_existing_rows()
    # compare against the last row from an *earlier* day, not today's own earlier scrape
    previous = next((r for r in reversed(rows) if r.get("date") != today), None)
    validate(rates, previous)

    if rows and rows[-1]["date"] == today:
        rows[-1] = row
    else:
        rows.append(row)

    save_rows(rows)
    return row


def main():
    html = fetch_page()
    rates = extract_rates(html)
    row = upsert_today(rates)
    print("Saved row:", row)


if __name__ == "__main__":
    main()
