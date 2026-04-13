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
