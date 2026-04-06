from strategies.base_strategy import BaseStrategy

class MovingAverageStrategy(BaseStrategy):

    def generate_signal(self, row):
        if row["SMA_20"] > row["SMA_50"]:
            return "BUY"

        elif row["SMA_20"] < row["SMA_50"]:
            return "SELL"

        return "HOLD"