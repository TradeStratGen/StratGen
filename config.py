import datetime

INITIAL_CAPITAL       = 100000
SYMBOL                = "^NSEI"
START_DATE            = "2020-01-01"
END_DATE              = datetime.date.today().isoformat()   # always today

VOLATILITY_PERCENTILE = 75     # top 25% rolling vol = Volatile regime
MIN_HOLD_BARS         = 10
POST_SELL_COOLDOWN    = 5
POSITION_SIZE_FRAC    = 0.25   # 25% of capital per trade (Q3: position sizing)
RISK_FREE_RATE        = 0.065  # Indian 10-yr gilt