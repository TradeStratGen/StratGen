# ▶️ How to Run

### 1. Clone the repo
git clone
cd genai-trading-bot

### 2. Create virtual environment
python -m venv venv

### 3. Activate virtual environment

Windows:
venv\Scripts\activate

Mac/Linux:
source venv/bin/activate

### 4. Install dependencies
pip install -r requirements.txt

### 5. Run backtest (CLI)
python main.py

### 6. Run dashboard
streamlit run dashboard/app.py


Commands:
python3 main.py
python main.py --live          # just today's signal, no full backtest
python live_signal.py          # same thing standalone
python live_signal.py --order  # also places paper order on Dhan

## Daily routine (every market day)
Run this each morning after 9:15am IST (before or after market open — data is previous day's close):
Signal only (safe, no order placed)
```
python live_signal.py
```

# Signal + Dhan paper order
```
python live_signal.py --order
```

### Logs Saved
```
logs/
  signals/
    signal_Volatile_2026-04-18.json    ← today's regime + signal + reasoning
    signal_Neutral_2026-04-21.json     ← next trading day
  orders/
    order_SELL_Volatile_2026-04-18.json
    order_BUY_Neutral_2026-04-21.json
  reports/
    report_2026-04-18.json             ← full daily report with backtest metrics
  weekly/
    week_2026-W16.json                 ← auto-updated each day
```

### View trade history anytime
```
python live_signal.py --history
```

