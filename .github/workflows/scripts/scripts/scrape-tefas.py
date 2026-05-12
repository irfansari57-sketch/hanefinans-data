"""Hane Finans — TEFAS scraper (GitHub Actions)."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from tefas import Crawler
except ImportError:
    print("ERROR: tefas-crawler not installed", file=sys.stderr)
    sys.exit(1)

import pandas as pd

POPULAR_FUNDS = [
    "AAL", "AAS", "AAV", "AC1", "AC4", "AC5", "AC6", "ACC", "ACD", "ACU",
    "ADE", "ADP", "AED", "AES", "AEV", "AFA", "AFO", "AFS", "AFT", "AFV",
    "AGC", "AHI", "AHN", "AHU", "AHV", "AIS", "AJK", "AK2", "AK3",
    "TLY", "GHF", "YAY", "IJC", "IIH", "TI2", "MJG", "AKE",
]

START_DATE = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
END_DATE = datetime.now().strftime("%Y-%m-%d")


def calc_return(history, days):
    if not history or len(history) < 2:
        return None
    history = sorted(history, key=lambda x: x["date"])
    last = history[-1]
    target_date_str = (
        datetime.strptime(last["date"], "%Y-%m-%d") - timedelta(days=days)
    ).strftime("%Y-%m-%d")
    candidate = None
    for h in history:
        if h["date"] <= target_date_str:
            candidate = h
        else:
            break
    if not candidate or candidate["price"] == 0:
        return None
    return round(((last["price"] - candidate["price"]) / candidate["price"]) * 100, 2)


def calc_ytd(history):
    if not history:
        return None
    history = sorted(history, key=lambda x: x["date"])
    last = history[-1]
    year = last["date"][:4]
    for h in history:
        if h["date"].startswith(year):
            if h["price"] == 0:
                return None
            return round(((last["price"] - h["price"]) / h["price"]) * 100, 2)
    return None


def fetch_fund(crawler, code):
    try:
        df = crawler.fetch(start=START_DATE, end=END_DATE, name=code)
        if df is None or df.empty:
            return None
    except Exception as e:
        print(f"  ! {code}: fetch error: {e}", file=sys.stderr)
        return None

    df = df.sort_values("date")
    history = [
        {"date": str(row["date"])[:10], "price": float(row["price"])}
        for _, row in df.tail(100).iterrows()
        if pd.notna(row.get("price"))
    ]
    if not history:
        return None

    last_row = df.iloc[-1]
    return {
        "code": code,
        "name": str(last_row.get("title", "")).strip() or code,
        "category": str(last_row.get("fon_kategorisi", last_row.get("title_full", ""))).strip(),
        "nav": float(last_row["price"]),
        "date": str(last_row["date"])[:10],
        "marketCap": float(last_row.get("market_cap") or 0),
        "investorCount": int(last_row.get("number_of_investors") or 0),
        "shareCount": float(last_row.get("number_of_shares") or 0),
        "returns": {
            "1w": calc_return(history, 7),
            "1m": calc_return(history, 30),
            "3m": calc_return(history, 90),
            "6m": calc_return(history, 180),
            "ytd": calc_ytd(history),
            "1y": calc_return(history, 365),
        },
        "history": history[-30:],
    }


def main():
    crawler = Crawler()
    seen = set()
    funds = []
    failed = []
    for code in POPULAR_FUNDS:
        if code in seen:
            continue
        seen.add(code)
        print(f"Fetching {code}...")
        data = fetch_fund(crawler, code)
        if data:
            funds.append(data)
            r = data["returns"]
            print(f"  OK {code}: NAV={data['nav']:.4f}  1m={r.get('1m')}%  1y={r.get('1y')}%")
        else:
            failed.append(code)

    print(f"\nOK: {len(funds)} funds fetched.")
    if failed:
        print(f"FAILED: {len(failed)} - {', '.join(failed)}")

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(funds),
        "funds": funds,
        "failed": failed,
    }
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "funds.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWritten data/funds.json")


if __name__ == "__main__":
    main()
