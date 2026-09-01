"""
Train ARIMA baseline and LightGBM with walk-forward cross-validation.
"""

import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.arima.model import ARIMA
import warnings
import json
from pathlib import Path

warnings.filterwarnings('ignore')

Path("results").mkdir(exist_ok=True)


def load_model_data():
    """Load the engineered feature dataset."""
    df = pd.read_csv("data/df_model.csv")
    return df


def fit_arima_baseline(df):
    """
    Fit ARIMA(1, 1, 1) on historical yield (univariate).
    Forecast 2023-2024 and return metrics.
    """
    print("\n[*] ARIMA Baseline (Univariate Yield Only)")
    print("-" * 60)

    # Train on 1990-2022
    train = df[df['year'] <= 2022]['yield_lbs_acre'].values
    test = df[df['year'] >= 2023]['yield_lbs_acre'].values

    # Check stationarity (ADF test)
    adf_result = adfuller(train, autolag='AIC')
    print(f"ADF test p-value: {adf_result[1]:.4f}")

    # Fit ARIMA(1, 1, 1)
    model = ARIMA(train, order=(1, 1, 1))
    fitted = model.fit()

    # Forecast 2023-2024 (2 steps ahead)
    forecast = fitted.get_forecast(steps=2)
    arima_pred = np.array(forecast.predicted_mean)

    # Metrics
    arima_rmse = np.sqrt(mean_squared_error(test, arima_pred))
    arima_mae = mean_absolute_error(test, arima_pred)

    print(f"Train period: 1990-2022 ({len(train)} years)")
    print(f"Test period: 2023-2024 ({len(test)} years)")
    print(f"RMSE: {arima_rmse:,.0f} lbs/acre")
    print(f"MAE: {arima_mae:,.0f} lbs/acre")
    print(f"\nForecast:")
    for i, year in enumerate([2023, 2024]):
        print(f"  {year}: {arima_pred[i]:,.0f} lbs/acre")

    return {
        'model_name': 'ARIMA(1,1,1)',
        'rmse': arima_rmse,
        'mae': arima_mae,
        'forecast_2023': float(arima_pred[0]),
        'forecast_2024': float(arima_pred[1])
    }


def fit_lightgbm_wfcv(df):
    """
    Train LightGBM with walk-forward cross-validation.
    Features: weather + lag + trend features.
    """
    print("\n[*] LightGBM with Walk-Forward CV")
    print("-" * 60)

    # Feature set (exclude yield_lbs_acre and log_yield)
    feature_cols = [
        'tmax_mean_grow', 'tmin_mean_grow', 'frost_days_bloom',
        'precip_total_grow', 'precip_rolling_30', 'precip_rolling_60', 'precip_rolling_90',
        'temp_variance_grow', 'gdd_total_grow', 'precip_deviation',
        'yield_lag1', 'year_numeric'
    ]

    # Drop rows with NaN (first year has NaN lag)
    df_clean = df.dropna(subset=feature_cols + ['log_yield']).copy()

    # Scaler for features
    scaler = StandardScaler()

    # Walk-forward CV: train on expanding window, test on next year
    all_preds = []
    all_actuals = []
    fold_results = []

    # We'll test on 2023, 2024 (last 2 years)
    train_cutoff = 2022
    test_years = [2023, 2024]

    train_df = df_clean[df_clean['year'] <= train_cutoff]
    test_df = df_clean[df_clean['year'].isin(test_years)]

    if len(train_df) < 10 or len(test_df) < 2:
        print("[!] Insufficient data for modeling")
        return None

    X_train = train_df[feature_cols].values
    y_train = train_df['log_yield'].values

    X_test = test_df[feature_cols].values
    y_test = test_df['log_yield'].values

    # Scale features
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train LightGBM
    params = {
        'objective': 'regression',
        'metric': 'rmse',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'max_depth': 5,
        'min_data_in_leaf': 10,
        'verbose': -1
    }

    train_data = lgb.Dataset(X_train_scaled, label=y_train)
    model = lgb.train(params, train_data, num_boost_round=200)

    # Predict on test set
    y_pred_log = model.predict(X_test_scaled)
    y_pred = np.expm1(y_pred_log)  # Inverse log transform
    y_actual = np.expm1(y_test)

    # Metrics
    lgb_rmse = np.sqrt(mean_squared_error(y_actual, y_pred))
    lgb_mae = mean_absolute_error(y_actual, y_pred)

    print(f"Train period: 1991-2022 ({len(train_df)} years)")
    print(f"Test period: 2023-2024 ({len(test_df)} years)")
    print(f"RMSE: {lgb_rmse:,.0f} lbs/acre")
    print(f"MAE: {lgb_mae:,.0f} lbs/acre")

    # Feature importance
    feature_importance = model.feature_importance()
    feature_importance_dict = dict(zip(feature_cols, feature_importance))
    sorted_features = sorted(feature_importance_dict.items(), key=lambda x: x[1], reverse=True)

    print(f"\nTop 5 features (SHAP-like importance):")
    for i, (feat, imp) in enumerate(sorted_features[:5], 1):
        print(f"  {i}. {feat}: {imp:.2f}")

    # Predictions by year
    print(f"\nForecasts:")
    for i, year in enumerate(test_years):
        print(f"  {year}: {y_pred[i]:,.0f} lbs/acre (actual: {y_actual[i]:,.0f})")

    return {
        'model_name': 'LightGBM',
        'rmse': lgb_rmse,
        'mae': lgb_mae,
        'feature_importance': feature_importance_dict,
        'top_features': [f[0] for f in sorted_features[:5]],
        'forecast_2023': float(y_pred[0]) if len(y_pred) > 0 else None,
        'forecast_2024': float(y_pred[1]) if len(y_pred) > 1 else None
    }


def main():
    print("=" * 60)
    print("MODEL TRAINING")
    print("=" * 60)

    df = load_model_data()
    print(f"\n[OK] Loaded {len(df)} records")

    # ARIMA Baseline
    arima_results = fit_arima_baseline(df)

    # LightGBM
    lgb_results = fit_lightgbm_wfcv(df)

    # Save results
    results = {
        'arima': arima_results,
        'lightgbm': lgb_results
    }

    with open('results/model_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n[OK] Saved: results/model_results.json")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if lgb_results and arima_results:
        print(f"\nARIMA RMSE: {arima_results['rmse']:,.0f}")
        print(f"LightGBM RMSE: {lgb_results['rmse']:,.0f}")
        print(f"LightGBM RMSE improvement: {(1 - lgb_results['rmse']/arima_results['rmse'])*100:.1f}%")

    print("\nNext: Run src/stress_indicator.py to calculate climate stress scores")
    print("=" * 60)


if __name__ == "__main__":
    main()
