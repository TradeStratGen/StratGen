from data.fetch_data import fetch_data
from indicators.indicators import add_indicators
from regime.regime import apply_regime
from strategies.ma_strategy import MovingAverageStrategy
from backtest.backtester import Backtester

def main():
    df = fetch_data()
    df = add_indicators(df)
    df = apply_regime(df)

    strategy = MovingAverageStrategy()

    bt = Backtester(df, strategy)
    equity, trades = bt.run()

    print("Final Portfolio Value:", equity[-1])
    print("Total Trades:", len(trades))
    print(df.head(5))
    print(df[["Close", "SMA_20", "SMA_50", "RSI", "regime"]].tail(10))
    print("First 10 trades:")
    print(trades[:10])

if __name__ == "__main__":
    main()