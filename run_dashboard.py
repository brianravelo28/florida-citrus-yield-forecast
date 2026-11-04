#!/usr/bin/env python3
"""
Run the US citrus industry dashboard.
Execute this to start the interactive dashboard at http://localhost:8050
"""

import os
import sys
from pathlib import Path

# Ensure we're in the right directory
os.chdir(Path(__file__).parent)

# Check if all required data files exist
required_files = [
    'data/citrus_by_state.csv',
    'data/county_features.csv',
    'data/stations.csv',
    'data/station_frost_summary.csv',
]

print("Checking required data files...")
for file in required_files:
    if not Path(file).exists():
        print(f"ERROR: Missing {file}")
        print("Please run the pipeline first (see the README):")
        print("  python src/fetch_industry_data.py")
        print("  python src/fetch_county_data.py")
        print("  python src/county_feature_engineering.py")
        sys.exit(1)

print("[OK] All data files present\n")

# Import and run the Dash app
try:
    from src.app import app
    print("=" * 60)
    print("US CITRUS INDUSTRY: ACREAGE, YIELD AND VALUE BY STATE")
    print("=" * 60)
    print("\nDashboard is starting...")
    print("Open your browser to: http://127.0.0.1:8050")
    print("Press Ctrl+C to stop the server\n")
    print("=" * 60)
    app.run(debug=False, port=8050, host="127.0.0.1")
except Exception as e:
    print(f"ERROR: Failed to start dashboard: {e}")
    sys.exit(1)
