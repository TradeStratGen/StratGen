"""
data/fetch_data.py
Always fetches up to TODAY dynamically.
Run now, run 1 hour later — you automatically get newer data.
NSE data on yfinance has ~15 min delay during market hours.
"""
import datetime
import yfinance as yf
from config import SYMBOL, START_DATE


def fetch_data():
    end = datetime.date.today().isoformat()   # "2026-04-12" — updates every run
    df  = yf.download(SYMBOL, start=START_DATE, end=end, progress=False)

    # Flatten MultiIndex columns (yfinance >= 0.2)
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    df.dropna(inplace=True)
    print(
        f"[Data] {len(df)} rows  "
        f"{START_DATE} → {df.index[-1].date()}  "
        f"(fetched at {datetime.datetime.now().strftime('%H:%M:%S')})"
    )
    return df