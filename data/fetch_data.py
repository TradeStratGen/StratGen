import yfinance as yf
from config import SYMBOL, START_DATE

def fetch_data():
    df = yf.download(SYMBOL, start=START_DATE)

    if isinstance(df.columns, tuple) or hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    df.dropna(inplace=True)
    return df