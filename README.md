# Bhavcopy — NSE 50-Session Market Intelligence Engine

This repository downloads completed NSE equity bhavcopy sessions, keeps a rolling
50-session raw ledger, calculates breadth/EMA/volume metrics, and generates an HTML
dashboard.

## Data integrity
- Raw market data is downloaded from NSE archive endpoints.
- The supplied dashboard HTML is a visual template only; its old numerical arrays
  are never used as market data.
- Derived metrics are calculated from raw security-level observations.
- If a metric cannot be calculated, the engine records a validation failure rather
  than inventing a number.

## Run locally
```bash
pip install -r requirements.txt
python download_nse_50_sessions.py
python calculate_market_intelligence.py
python generate_dashboard.py
```

The GitHub Action runs the same pipeline on schedule and commits generated output.
