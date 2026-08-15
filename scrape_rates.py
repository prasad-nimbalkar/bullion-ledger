"""
Bullion Ledger — daily rate scraper (chandukakasaraf.in)
Appends / updates today's row in bullion_history.csv at the repo root.
Run by .github/workflows/scrape-rates.yml on a daily cron.

Designed to be extended: add new metals/assets by adding a new `grab(...)`
call and a new column in FIELDNAMES + the row dict below.
"""

import re
import csv
import os
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

URL = "https://chandukakasaraf.in/todays-gold-rate/"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bullion_history.csv")

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


def fetch_page() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    print(f"HTTP status: {resp.status_code} | content-length: {len(resp.text)} chars")
    resp.raise_for_status()
    return resp.text


def extract_rates(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract plain text cleanly while preserving spaces between HTML nodes
    text = soup.get_text(separator=" ", strip=True)

    def grab(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return None
        return float(m.group(1).replace(",", ""))

    # Updated pattern to catch variants of updated timestamps
    updated_match = re.search(
        r"Updated\s*(?:On)?:?\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})?\s*(\d{2}:\d{2}:\d{2})?", 
        text, 
        re.IGNORECASE
    )
    site_updated_at = (
        f"{updated_match.group(1)} {updated_match.group(2)}".strip() 
        if updated_match and (updated_match.group(1) or updated_match.group(2)) 
        else None
    )

    # Robust flexible regex to match metal labels regardless of intervening HTML tags or symbols
    g18 = grab(r"18\s*(?:KT|K|Karat).*?(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)")
    g22 = grab(r"22\s*(?:KT|K|Karat).*?(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)")
    g24 = grab(r"24\s*(?:KT|K|Karat).*?(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)")
    platinum = grab(r"Platinum\s*(?:950)?.*?(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)")
    silver_kg = grab(r"Silver.*?(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:per|/)?\s*(?:1\s*kg|kg|1000\s*g)?")

    missing = [name for name, val in
               [("18KT", g18), ("22KT", g22), ("24KT", g24), ("Silver/kg", silver_kg)]
               if val is None]
               
    if missing:
        snippet = text[:800]
        print("---- DEBUG: first 800 chars of extracted text ----")
        print(snippet)
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
        "gold_24kt": g24,
        "gold_22kt": g22,
        "gold_18kt": g18,
        "platinum_950": platinum,
        "silver_per_gram": round(silver_kg / 1000, 2) if silver_kg else None,
    }


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
    today = now.strftime("%Y-%m-%d")
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