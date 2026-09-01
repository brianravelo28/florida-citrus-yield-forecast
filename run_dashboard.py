#!/usr/bin/env python3
"""
Run the Citrus Yield Forecasting Dash app.
Execute this to start the interactive dashboard at http://localhost:8050
"""

import os
import sys
from pathlib import Path

# Ensure we're in the right directory
os.chdir(Path(__file__).parent)

# Check if all required data files exist
required_files = [
    'data/df_model.csv',
    'results/stress_indicator.csv',
    'results/model_results.json'
]

print("Checking required data files...")
for file in required_files:
    if not Path(file).exists():
        print(f"ERROR: Missing {file}")
        print("Please run the full pipeline first:")
        print("  python src/fetch_data.py")
        print("  python src/feature_engineering.py")
        print("  python src/train_models.py")
        print("  python src/stress_indicator.py")
        sys.exit(1)

print("[OK] All data files present\n")

# Import and run the Dash app
try:
    from src.app import app
    print("=" * 60)
    print("FLORIDA CITRUS YIELD FORECASTING DASHBOARD")
    print("=" * 60)
    print("\nDashboard is starting...")
    print("Open your browser to: http://127.0.0.1:8050")
    print("Press Ctrl+C to stop the server\n")
    print("=" * 60)
    app.run(debug=False, port=8050, host="127.0.0.1")
except Exception as e:
    print(f"ERROR: Failed to start dashboard: {e}")
    sys.exit(1)
