"""
Daily Gold & Silver rate scraper — chandukakasaraf.in
Appends (or updates today's row in) gold_silver_history.csv in the same folder.
Designed to be run by a GitHub Actions cron job (see .github/workflows/scrape-gold-rate.yml).
"""

import re
import csv
import os
from datetime import datetime, timezone
import requests

URL = "https://chandukakasaraf.in/todays-gold-rate/"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gold_silver_history.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 GoldRateTracker/1.0"
    )
}

FIELDNAMES = [
    "date", "scraped_at_utc", "site_updated_at",
    "gold_24kt", "gold_22kt", "gold_18kt",
    "silver_per_gram", "platinum_950",
]


def fetch_page() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def extract_rates(html: str) -> dict:
    # Strip tags, collapse whitespace, then regex over plain text.
    # Robust to markup changes since it doesn't depend on table/div structure.
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    def grab(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return None
        return float(m.group(1).replace(",", ""))

    updated_match = re.search(
        r"Updated On:\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})", text
    )
    site_updated_at = (
        f"{updated_match.group(1)} {updated_match.group(2)}" if updated_match else None
    )

    g18 = grab(r"18\s*KT\s*Gold\D{0,15}?₹\s*([\d,]+(?:\.\d+)?)")
    g22 = grab(r"22\s*KT\s*Gold\D{0,15}?₹\s*([\d,]+(?:\.\d+)?)")
    g24 = grab(r"24\s*KT\s*Gold\D{0,15}?₹\s*([\d,]+(?:\.\d+)?)")
    platinum = grab(r"Platinum-?950\D{0,15}?₹\s*([\d,]+(?:\.\d+)?)")
    silver_kg = grab(r"Silver\D{0,15}?₹\s*([\d,]+(?:\.\d+)?)\s*PER\s*1\s*KG")

    missing = [name for name, val in
               [("18KT", g18), ("22KT", g22), ("24KT", g24), ("Silver/kg", silver_kg)]
               if val is None]
    if missing:
        raise ValueError(
            f"Could not extract: {', '.join(missing)}. "
            f"Site markup may have changed — inspect {URL} manually."
        )

    return {
        "site_updated_at": site_updated_at,
        "gold_24kt": g24,
        "gold_22kt": g22,
        "gold_18kt": g18,
        "platinum_950": platinum,
        "silver_per_gram": round(silver_kg / 1000, 2),
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
    }

    rows = load_existing_rows()
    if rows and rows[-1]["date"] == today:
        # Site updates multiple times a day — keep one row per day, refresh it.
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
