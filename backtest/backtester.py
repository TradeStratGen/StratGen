from config import INITIAL_CAPITAL

class Backtester:

    def __init__(self, df, strategy):
        self.df = df
        self.strategy = strategy
        self.capital = INITIAL_CAPITAL
        self.position = 0
        self.trades = []
        self.equity_curve = []

    def run(self):
        for index, row in self.df.iterrows():
            price = row["Close"]
            signal = self.strategy.generate_signal(row)

            # BUY
            if signal == "BUY" and self.position == 0:
                self.position = self.capital / price
                self.capital = 0
                self.trades.append((index, "BUY", price))

            # SELL
            elif signal == "SELL" and self.position > 0:
                self.capital = self.position * price
                self.position = 0
                self.trades.append((index, "SELL", price))

            total_value = self.capital + (self.position * price)
            self.equity_curve.append(total_value)
        return self.equity_curve, self.trades