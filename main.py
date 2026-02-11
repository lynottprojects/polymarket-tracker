#!/usr/bin/env python3
"""
Polymarket Daily Volume Tracker for Render
Fetches daily volume from DefiLlama and appends new days to Google Sheet
"""
import os
import sys
from datetime import datetime, timezone
import requests
from google.oauth2.credentials import Credentials

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '10hbDf0u2TQ1OHkjXBvp9tekF41-CkzhL1vAiQBZPnL4')
GOOGLE_REFRESH_TOKEN = os.getenv('GOOGLE_REFRESH_TOKEN')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

SHEET_NAME = 'Daily Volume'
DEFILLAMA_URL = 'https://api.llama.fi/summary/dexs/polymarket'


def get_access_token():
    if not all([GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET]):
        raise ValueError("Missing Google OAuth credentials in environment variables")

    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )

    from google.auth.transport.requests import Request
    creds.refresh(Request())
    return creds.token


def fetch_daily_volume():
    """Fetch daily volume time series from DefiLlama"""
    print("Fetching Polymarket volume data from DefiLlama...", flush=True)
    response = requests.get(DEFILLAMA_URL, timeout=60)
    response.raise_for_status()
    data = response.json()

    chart = data.get('totalDataChart', [])
    if not chart:
        raise ValueError("No totalDataChart in DefiLlama response")

    # Convert to list of (date_str, volume) tuples
    results = []
    for ts, vol in chart:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        date_str = dt.strftime('%Y-%m-%d')
        results.append((date_str, vol))

    results.sort(key=lambda r: r[0])  # oldest first
    print(f"Got {len(results)} total days from DefiLlama", flush=True)
    return results


def get_existing_dates(token):
    """Get dates already in the Google Sheet"""
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{SHEET_NAME}!A:A'
    headers = {'Authorization': f'Bearer {token}'}

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    values = response.json().get('values', [])

    # Skip header row, return set of date strings
    dates = set()
    for row in values[1:]:
        if row:
            dates.add(row[0])
    return dates


def append_to_sheet(token, new_rows):
    """Append new rows to the Google Sheet"""
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{SHEET_NAME}!A:C:append'
    headers = {'Authorization': f'Bearer {token}'}
    body = {'values': new_rows}
    params = {'valueInputOption': 'RAW'}

    response = requests.post(url, headers=headers, json=body, params=params)
    response.raise_for_status()
    print(f"Appended {len(new_rows)} new row(s) to Google Sheet", flush=True)


def main():
    print(f"=== Polymarket Daily Volume Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n", flush=True)

    # Fetch all volume data from DefiLlama
    all_volume = fetch_daily_volume()

    # Get Google token and check which dates already exist
    token = get_access_token()
    existing_dates = get_existing_dates(token)
    print(f"Sheet already has {len(existing_dates)} date(s)", flush=True)

    # Find new rows to append (only dates not already in sheet)
    new_rows = []
    for date_str, vol in all_volume:
        if date_str not in existing_dates:
            new_rows.append([date_str, vol, round(vol / 1_000_000, 2)])

    if not new_rows:
        print("\nNo new data. Sheet is up to date.", flush=True)
        return

    # Sort oldest first before appending
    new_rows.sort(key=lambda r: r[0])
    print(f"\nFound {len(new_rows)} new day(s) to add", flush=True)
    print(f"  From: {new_rows[0][0]}", flush=True)
    print(f"  To:   {new_rows[-1][0]}", flush=True)

    append_to_sheet(token, new_rows)
    print("\nDone!", flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
