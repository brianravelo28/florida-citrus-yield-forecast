# Contributing Guidelines

Thank you for interest in improving the Florida Citrus Yield Forecasting System! This guide explains how to contribute.

## Getting Started

### 1. Fork & Clone
```bash
git clone https://github.com/yourusername/florida-citrus-yield-forecast.git
cd florida-citrus-yield-forecast
git checkout -b feature/your-feature-name
```

### 2. Set Up Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pytest-cov black flake8  # Dev dependencies
```

### 3. Run Tests
```bash
pytest tests/
pytest --cov=src/  # Coverage report
```

## Areas for Contribution

### 🛰️ Satellite Data Integration
- **Task**: Add NDVI (Normalized Difference Vegetation Index) from Sentinel-2
- **Impact**: Crop health proxy, improve yield predictions
- **Skills**: GIS, rasterio, geospatial data
- **File**: `src/fetch_satellite.py`

### 📊 Multi-County Expansion
- **Task**: Generalize pipeline to Orange, Citrus, Lake, DeSoto counties
- **Impact**: Regional forecasting capability
- **Skills**: Data engineering, SQL
- **File**: `src/config_counties.py`

### 🔔 Real-Time Alerts
- **Task**: SMS/email notifications for stress level changes
- **Impact**: Grower decision support
- **Skills**: Twilio API, scheduling
- **File**: `src/alerts.py`

### 📱 Mobile App
- **Task**: React Native frontend for on-farm access
- **Impact**: Field-side decision support
- **Skills**: React Native, mobile UX
- **File**: `mobile/` (new)

### 🌍 HLB Disease Model
- **Task**: Integrate Citrus Greening disease pressure index
- **Impact**: Better explain yield drivers, improve forecasts
- **Skills**: Epidemiology, disease modeling
- **File**: `src/disease_model.py`

### 📈 Bayesian Uncertainty
- **Task**: Replace point forecasts with credible intervals
- **Impact**: Better risk quantification
- **Skills**: Bayesian inference, PyMC3
- **File**: `src/uncertainty_quantification.py`

---

## Contribution Workflow

### Step 1: Create Feature Branch
```bash
git checkout -b feature/descriptive-name
```

### Step 2: Make Changes
- Write code following style guide (see below)
- Add tests for new functionality
- Update documentation
- Run tests: `pytest tests/`

### Step 3: Code Quality
```bash
# Format code
black src/

# Check style
flake8 src/ --max-line-length=120

# Type hints (optional but encouraged)
mypy src/
```

### Step 4: Commit
```bash
git add .
git commit -m "Add feature: Brief description"
# Example: "Add feature: NDVI satellite data fetcher"
```

### Step 5: Push & Create PR
```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub with:
- **Title**: Brief description
- **Description**: What problem does it solve? How does it work?
- **Tests**: Link to test results
- **Related Issues**: Reference any related issues (#123)

---

## Code Style Guide

### Python (PEP 8)
```python
# Imports: standard lib, third-party, local
import pandas as pd
import numpy as np
from src.utils import parse_date

# Classes: CapitalCase
class WeatherPreprocessor:
    """Docstring in triple quotes."""

    def __init__(self, config: dict) -> None:
        """Initialize with config dict."""
        self.config = config

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process weather data.
        
        Args:
            df: Input weather DataFrame
            
        Returns:
            Cleaned DataFrame
        """
        return df.dropna()

# Functions: snake_case
def fetch_yield_data(year_min: int, year_max: int) -> pd.DataFrame:
    """Fetch yield data for range."""
    pass

# Variables: snake_case
nass_api_key = "YOUR_KEY"
weather_data = fetch_yield_data(1990, 2024)
```

### Naming Conventions
| Type | Style | Example |
|------|-------|---------|
| Classes | CapitalCase | `WeatherProcessor` |
| Functions | snake_case | `fetch_yield_data()` |
| Variables | snake_case | `nass_api_key` |
| Constants | UPPER_CASE | `DEFAULT_LEARNING_RATE` |
| Private | _snake_case | `_internal_helper()` |

### Docstrings
```python
def calculate_gdd(tmax: float, tmin: float, base: float = 50.0) -> float:
    """Calculate Growing Degree Days.
    
    Args:
        tmax: Maximum temperature (°F)
        tmin: Minimum temperature (°F)
        base: Base temperature (default: 50°F for citrus)
        
    Returns:
        GDD value (0 if below base)
        
    Example:
        >>> calculate_gdd(85, 65)
        15.0
    """
    return max(0, (tmax + tmin) / 2 - base)
```

---

## Testing

### Test Structure
```
tests/
├── test_fetch_data.py
├── test_feature_engineering.py
├── test_models.py
└── test_stress_indicator.py
```

### Writing Tests
```python
import pytest
import pandas as pd
from src.feature_engineering import calculate_gdd

def test_gdd_calculation():
    """Test GDD calculation with known values."""
    gdd = calculate_gdd(85, 65)
    assert gdd == 15.0

def test_gdd_below_base():
    """Test GDD is 0 below base temperature."""
    gdd = calculate_gdd(40, 30)
    assert gdd == 0.0

@pytest.fixture
def sample_weather():
    """Fixture: sample weather DataFrame."""
    return pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=10),
        'tmax': [85] * 10,
        'tmin': [65] * 10
    })

def test_weather_processing(sample_weather):
    """Test weather preprocessing."""
    result = process_weather(sample_weather)
    assert len(result) == 10
```

### Running Tests
```bash
# All tests
pytest

# Specific file
pytest tests/test_models.py

# Verbose output
pytest -v

# Coverage report
pytest --cov=src/ --cov-report=html
```

---

## Documentation

### Adding to Docs
- **Schema changes**: Update `docs/SCHEMA.md`
- **Methodology changes**: Update `docs/METHODOLOGY.md`
- **New APIs**: Add to `docs/API_SOURCES.md`
- **New features**: Update `README.md`

### Example Docstring
```python
"""
Add satellite NDVI as a feature.

This function fetches Sentinel-2 NDVI data for Polk County,
aggregates to monthly resolution, and merges with yield data.

Requires: Copernicus API credentials in .env

Performance:
  - 35 years of data: ~2 min fetch time
  - Processing: ~30 sec
  - Storage: ~50 MB (monthly NDVI grids)
"""
```

---

## Git Workflow

### Branch Naming
```
feature/descriptive-name          # New feature
bugfix/issue-description          # Bug fix
docs/update-section              # Documentation
refactor/module-improvement      # Refactoring
```

### Commit Messages
```
# Good
feature: Add satellite NDVI integration
bugfix: Fix frost day calculation for Feb edge case
docs: Update API reference with CDO v1 examples

# Avoid
"Updates"
"Fix stuff"
"WIP"
```

### Before Submitting PR
```bash
git fetch origin
git rebase origin/main
git push --force-with-lease
```

---

## Code Review Process

1. **Automated Checks**
   - CI/CD pipeline runs tests
   - Linting & type checking pass
   - Coverage doesn't decrease

2. **Peer Review**
   - At least 1 maintainer review
   - Address feedback constructively
   - Re-request review after changes

3. **Merge**
   - Squash commits if requested
   - Maintainer merges to main
   - CI/CD runs full suite

---

## Reporting Issues

### Bug Reports
Include:
- Reproducible steps
- Expected vs. actual behavior
- Python/package versions
- Error traceback (if applicable)

Example:
```
Title: Frost days calculation incorrect for leap years

Steps:
1. Run `python src/feature_engineering.py` with 2024 (leap year)
2. Check frost_days_bloom for February

Expected: Frost days counted for all Feb days (1-29)
Actual: Only Feb 1-28 counted

Error:
  IndexError: date out of range
```

### Feature Requests
Include:
- Use case (why is this needed?)
- Proposed approach
- Estimated effort
- Related research/references

Example:
```
Title: Multi-county yield forecasting

Use Case: Forecast for all 7 major FL citrus counties simultaneously

Approach:
1. Generalize county loop in fetch_data.py
2. Add hierarchical model (county-level random effects)
3. Create county dropdown in dashboard

References:
- Singerman & Useche (2016) on multi-county economics
- https://github.com/issue/XXX
```

---

## Development Setup (Advanced)

### Docker
```bash
docker build -t citrus-forecast .
docker run -it citrus-forecast bash
```

### Pre-commit Hooks
```bash
pip install pre-commit
pre-commit install  # Install hooks

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/flake8
    hooks:
      - id: flake8
```

### GitHub Codespaces
```bash
# Codespaces auto-opens in browser
# Pre-configured with Python, git, etc.
# Useful for external contributors
```

---

## Questions?

- **Documentation**: See README.md, docs/
- **Issues**: https://github.com/yourusername/florida-citrus-yield-forecast/issues
- **Discussions**: https://github.com/yourusername/florida-citrus-yield-forecast/discussions
- **Email**: brian.blitz28@gmail.com

---

## Code of Conduct

Be respectful, inclusive, and professional. We welcome contributions from all backgrounds.

---

**Thank you for contributing!** 🎉

Your improvements help make agricultural forecasting accessible and impactful for Florida's citrus community.

