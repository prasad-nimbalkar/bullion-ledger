"""
Bullion Ledger — daily rate scraper (chandukakasaraf.in)
Appends / updates today's row in bullion_history.csv at the repo root.
Run by .github/workflows/scrape-rates.yml on a daily cron.

Uses WebSocket live metal rates instead of scraping the HTML page.
"""

import re
import csv
import os
import json
import asyncio
import ssl
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import certifi
import websockets

WS_URL = "wss://api.chandukakasaraf.in/ws/metal-rates"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bullion_history.csv")
IST = ZoneInfo("Asia/Kolkata")

# A new day's price may not differ from the last stored row by more than this
MAX_MOVE = 0.25

FIELDNAMES = [
    "date", "scraped_at_utc", "site_updated_at",
    "gold_24kt", "gold_22kt", "gold_18kt",
    "silver_per_gram", "platinum_950",
    "diamond_per_carat",
]


# ============================================================
# WEBSOCKET FETCH
# ============================================================

async def fetch_rates_payload():
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async with websockets.connect(
        WS_URL,
        open_timeout=15,
        ping_interval=20,
        ping_timeout=20,
        ssl=ssl_context,
    ) as ws:
        print("Connected to live metal rates stream")

        message = await asyncio.wait_for(ws.recv(), timeout=30)
        payload = json.loads(message)

        print("Received WebSocket payload:")
        print(json.dumps(payload, indent=2))

        return payload


# ============================================================
# RATE EXTRACTION
# ============================================================

def flatten_json(data, prefix=""):
    """Flatten nested JSON into a dictionary."""
    result = {}

    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{prefix}_{key}" if prefix else str(key)
            if isinstance(value, (dict, list)):
                result.update(flatten_json(value, new_key))
            else:
                result[new_key.lower()] = value

    elif isinstance(data, list):
        for index, value in enumerate(data):
            new_key = f"{prefix}_{index}"
            if isinstance(value, (dict, list)):
                result.update(flatten_json(value, new_key))
            else:
                result[new_key.lower()] = value

    return result


def normalize_key(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def find_value(flat_data, aliases):
    """Find values using normalized key names."""
    normalized_data = {normalize_key(key): value for key, value in flat_data.items()}
    normalized_aliases = [normalize_key(alias) for alias in aliases]

    # Exact matches first
    for alias in normalized_aliases:
        if alias in normalized_data:
            return normalized_data[alias]

    # Partial matches as fallback
    for key, value in normalized_data.items():
        for alias in normalized_aliases:
            if alias and alias in key:
                return value

    return None


def parse_price(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip().replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", value)
    return float(match.group()) if match else None


def extract_rates(payload):
    flat_data = flatten_json(payload)

    print("Flattened payload:")
    print(json.dumps(flat_data, indent=2))

    gold_24kt = parse_price(find_value(flat_data, [
        "gold_24kt", "gold24kt", "gold_24k", "gold24k",
        "24kt", "24k", "24karat", "gold24",
    ]))

    gold_22kt = parse_price(find_value(flat_data, [
        "gold_22kt", "gold22kt", "gold_22k", "gold22k",
        "22kt", "22k", "22karat", "gold22",
    ]))

    gold_18kt = parse_price(find_value(flat_data, [
        "gold_18kt", "gold18kt", "gold_18k", "gold18k",
        "18kt", "18k", "18karat", "gold18",
    ]))

    silver = parse_price(find_value(flat_data, [
        "silver_per_gram", "silvergram", "silver_rate",
        "silverprice", "silver",
    ]))

    platinum_950 = parse_price(find_value(flat_data, [
        "platinum_950", "platinum950", "950platinum",
        "platinum_rate", "platinum",
    ]))

    site_updated_at = find_value(flat_data, [
        "updated_at", "updatedat", "last_updated", "lastupdated",
        "timestamp", "datetime",
    ])

    required = {
        "18KT": gold_18kt,
        "22KT": gold_22kt,
        "24KT": gold_24kt,
        "Silver": silver,
    }

    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            f"Could not extract rates: {', '.join(missing)}. "
            "Check the actual WebSocket payload and update the aliases."
        )

    # Normalize the WebSocket silver value to ₹ per gram
    silver_per_gram = round(silver / 1_000_000, 3)

    # Assumes the WebSocket silver value is per gram; convert to per kg.
    return {
        "site_updated_at": site_updated_at or "",
        "gold_24kt": gold_24kt,
        "gold_22kt": gold_22kt,
        "gold_18kt": gold_18kt,
        "platinum_950": platinum_950,
        "silver_per_gram": silver_per_gram,
    }


# ============================================================
# VALIDATION
# ============================================================

def validate(rates: dict, previous_row: dict | None):
    g24, g22, g18 = rates["gold_24kt"], rates["gold_22kt"], rates["gold_18kt"]

    if not (g24 > g22 > g18 > 0):
        raise ValueError(
            f"Gold purities out of order (24K={g24}, 22K={g22}, 18K={g18}) "
            "— likely a mis-parse."
        )

    if previous_row and os.environ.get("BULLION_ALLOW_JUMP") != "1":
        for key in ("gold_24kt", "gold_22kt", "gold_18kt", "silver_per_kg"):
            try:
                prev = float(previous_row[key])
            except (KeyError, TypeError, ValueError):
                continue

            if prev > 0 and abs(rates[key] - prev) / prev > MAX_MOVE:
                raise ValueError(
                    f"{key} moved {rates[key]} vs previous {prev} (>{MAX_MOVE:.0%}). "
                    "If this is real, rerun with BULLION_ALLOW_JUMP=1; "
                    "otherwise check the parser."
                )


# ============================================================
# CSV MANAGEMENT
# ============================================================

def load_existing_rows() -> list:
    if not os.path.isfile(CSV_PATH):
        return []

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_rows(rows: list):
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def upsert_today(rates: dict) -> dict:
    now = datetime.now(timezone.utc)
    today = now.astimezone(IST).strftime("%Y-%m-%d")

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

    # Compare against the last row from an earlier day, not today's own earlier scrape.
    previous = next((r for r in reversed(rows) if r.get("date") != today), None)
    validate(rates, previous)

    if rows and rows[-1]["date"] == today:
        rows[-1] = row
    else:
        rows.append(row)

    save_rows(rows)
    return row


# ============================================================
# MAIN
# ============================================================

async def main():
    payload = await fetch_rates_payload()
    rates = extract_rates(payload)
    row = upsert_today(rates)
    print("Saved row:", row)


if __name__ == "__main__":
    asyncio.run(main())
