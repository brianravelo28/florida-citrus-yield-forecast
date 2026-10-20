"""
Train and evaluate yield models on the statewide series.

Three evaluations, all on the same data (data/df_model.csv):
  1. Holdout: train on 1990-2022, predict 2023-24 (two test points).
     ARIMA forecasts both years from the end of training (two steps ahead);
     LightGBM uses each test year's actual lagged yield (one step ahead).
  2. Naive baselines: "yield stays at last year's value".
  3. Rolling origin: for each test year from 2008 on, train only on earlier
     years and predict that one year, for every method on equal footing.
     One-step-ahead, so each method sees the previous year's actual yield.
"""

import json
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

warnings.filterwarnings('ignore')

Path("results").mkdir(exist_ok=True)

FEATURE_COLS = [
    'tmax_mean_grow', 'tmin_mean_grow', 'frost_days_bloom',
    'precip_total_grow', 'precip_rolling_30', 'precip_rolling_60', 'precip_rolling_90',
    'temp_variance_grow', 'gdd_total_grow', 'precip_deviation',
    'yield_lag1', 'year_numeric'
]
TRAIN_CUTOFF = 2022
TEST_YEARS = [2023, 2024]
FIRST_ROLLING_TEST_YEAR = 2008
LGB_PARAMS = {
    'objective': 'regression',
    'metric': 'rmse',
    'learning_rate': 0.05,
    'num_leaves': 31,
    'max_depth': 5,
    'min_data_in_leaf': 10,
    'verbose': -1
}
LGB_ROUNDS = 200


def load_model_data():
    """Load the engineered feature dataset."""
    df = pd.read_csv("data/df_model.csv")
    return df


def rmse(actual, predicted):
    return float(np.sqrt(mean_squared_error(actual, predicted)))


def drop_incomplete_rows(df, verbose=True):
    """Drop rows with a missing model input or target; say which years and why.

    LightGBM cannot use a year whose weather features are NA (nothing is
    imputed), and the first year has no lagged yield. The dropped years are
    printed so rows never disappear silently.
    """
    cols = FEATURE_COLS + ['log_yield']
    missing = df[cols].isna()
    dropped = df[missing.any(axis=1)]
    if verbose:
        if dropped.empty:
            print(f"Rows dropped for missing inputs: none (of {len(df)})")
        else:
            detail = "; ".join(f"{int(row.year)} ({', '.join(c for c in cols if missing.loc[i, c])})"
                               for i, row in dropped.iterrows())
            print(f"Rows dropped for missing inputs: {len(dropped)} of {len(df)} - {detail}")
    return df.drop(index=dropped.index).copy()


def fit_arima_baseline(df):
    """
    Fit ARIMA(1, 1, 1) on historical yield (univariate).
    Forecast 2023-2024 and return metrics.
    """
    print("\n[*] ARIMA Baseline (Univariate Yield Only)")
    print("-" * 60)

    # Train on 1990-2022
    train = df[df['year'] <= TRAIN_CUTOFF]['yield_lbs_acre'].values
    test = df[df['year'] >= TEST_YEARS[0]]['yield_lbs_acre'].values

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
    arima_rmse = rmse(test, arima_pred)
    arima_mae = mean_absolute_error(test, arima_pred)

    print(f"Train period: 1990-2022 ({len(train)} years)")
    print(f"Test period: 2023-2024 ({len(test)} years)")
    print(f"RMSE: {arima_rmse:,.0f} lbs/acre")
    print(f"MAE: {arima_mae:,.0f} lbs/acre")
    print(f"\nForecast:")
    for i, year in enumerate(TEST_YEARS):
        print(f"  {year}: {arima_pred[i]:,.0f} lbs/acre")

    return {
        'model_name': 'ARIMA(1,1,1)',
        'rmse': arima_rmse,
        'mae': arima_mae,
        'forecast_2023': float(arima_pred[0]),
        'forecast_2024': float(arima_pred[1])
    }


def fit_lightgbm_holdout(df):
    """
    Train LightGBM on 1990-2022 (features + lagged yield + trend) and predict 2023-24.

    A single train/test split, not cross-validation. See rolling_origin_evaluation
    for the multi-fold evaluation.
    """
    print("\n[*] LightGBM (holdout: train 1991-2022, test 2023-24)")
    print("-" * 60)

    df_clean = drop_incomplete_rows(df)

    train_df = df_clean[df_clean['year'] <= TRAIN_CUTOFF]
    test_df = df_clean[df_clean['year'].isin(TEST_YEARS)]

    if len(train_df) < 10 or len(test_df) < 2:
        print("[!] Insufficient data for modeling")
        return None

    X_train = train_df[FEATURE_COLS].values
    y_train = train_df['log_yield'].values
    X_test = test_df[FEATURE_COLS].values
    y_test = test_df['log_yield'].values

    # Scale features (fit on training rows only)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    train_data = lgb.Dataset(X_train_scaled, label=y_train)
    model = lgb.train(LGB_PARAMS, train_data, num_boost_round=LGB_ROUNDS)

    # Predict on test set
    y_pred = np.expm1(model.predict(X_test_scaled))  # inverse log transform
    y_actual = np.expm1(y_test)

    lgb_rmse = rmse(y_actual, y_pred)
    lgb_mae = mean_absolute_error(y_actual, y_pred)

    print(f"Train period: 1991-2022 ({len(train_df)} years)")
    print(f"Test period: 2023-2024 ({len(test_df)} years)")
    print(f"RMSE: {lgb_rmse:,.0f} lbs/acre")
    print(f"MAE: {lgb_mae:,.0f} lbs/acre")

    # Feature importance: number of splits using each feature (cast numpy int32 -> int for JSON)
    feature_importance = model.feature_importance()
    feature_importance_dict = dict(zip(FEATURE_COLS, (int(x) for x in feature_importance)))
    sorted_features = sorted(feature_importance_dict.items(), key=lambda x: x[1], reverse=True)

    print(f"\nTop 5 features (by number of splits):")
    for i, (feat, imp) in enumerate(sorted_features[:5], 1):
        print(f"  {i}. {feat}: {imp}")

    print(f"\nPredictions:")
    for i, year in enumerate(TEST_YEARS):
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


def naive_baseline(df):
    """
    "Yield stays at last year's value", on the same 2023-24 holdout.

    one_step: each test year is predicted from the previous year's ACTUAL yield
              (2023 from 2022, 2024 from 2023). Same information as LightGBM.
    multi_step: both years are predicted from the last training year (2022).
              Same information as ARIMA.
    """
    print("\n[*] Naive baseline (yield stays at last year's value)")
    print("-" * 60)

    by_year = df.set_index('year')['yield_lbs_acre']
    actual = np.array([by_year[y] for y in TEST_YEARS])
    one_step = np.array([by_year[y - 1] for y in TEST_YEARS])
    multi_step = np.array([by_year[TRAIN_CUTOFF]] * len(TEST_YEARS))

    result = {
        'description': "Predict last year's yield. one_step uses the previous year's actual yield; "
                       "multi_step repeats the last training-year (2022) yield for both test years.",
        'one_step': {'rmse': rmse(actual, one_step), 'mae': mean_absolute_error(actual, one_step),
                     'forecast_2023': float(one_step[0]), 'forecast_2024': float(one_step[1])},
        'multi_step': {'rmse': rmse(actual, multi_step), 'mae': mean_absolute_error(actual, multi_step),
                       'forecast_2023': float(multi_step[0]), 'forecast_2024': float(multi_step[1])},
    }
    print(f"One-step  (last actual yield):  RMSE {result['one_step']['rmse']:,.0f}  MAE {result['one_step']['mae']:,.0f}")
    print(f"Multi-step (2022 repeated):     RMSE {result['multi_step']['rmse']:,.0f}  MAE {result['multi_step']['mae']:,.0f}")
    return result


def rolling_origin_evaluation(df, first_test_year=FIRST_ROLLING_TEST_YEAR):
    """
    One-step-ahead rolling-origin evaluation: for each year t from first_test_year
    through the last year, fit on years before t only and predict year t.

    Every method sees the previous year's actual yield, so they are compared on
    equal footing (unlike the 2023-24 holdout above). Returns (per-fold frame, summary).
    """
    print(f"\n[*] Rolling-origin evaluation ({first_test_year}-{int(df['year'].max())}, one step ahead)")
    print("-" * 60)

    df_clean = drop_incomplete_rows(df, verbose=False)  # same rows as the holdout fit above
    by_year = df.set_index('year')['yield_lbs_acre']
    rows, arima_warnings = [], 0

    for year in range(first_test_year, int(df['year'].max()) + 1):
        history = by_year[by_year.index < year]

        # Persistence: last year's actual yield
        persistence = float(by_year[year - 1])

        # ARIMA(1,1,1) refit on all earlier years, one step ahead
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            arima_pred = float(ARIMA(history.values, order=(1, 1, 1)).fit().forecast(steps=1)[0])
        arima_warnings += any(issubclass(w.category, ConvergenceWarning) for w in caught)

        # LightGBM on earlier years' rows, same features and settings as the holdout
        train_df = df_clean[df_clean['year'] < year]
        test_df = df_clean[df_clean['year'] == year]
        scaler = StandardScaler()
        model = lgb.train(LGB_PARAMS,
                          lgb.Dataset(scaler.fit_transform(train_df[FEATURE_COLS].values),
                                      label=train_df['log_yield'].values),
                          num_boost_round=LGB_ROUNDS)
        # A year whose weather features are NA cannot be scored by LightGBM (nothing is
        # imputed); it is left out of the comparison for every method, below.
        lgb_pred = (float(np.expm1(model.predict(scaler.transform(test_df[FEATURE_COLS].values))[0]))
                    if len(test_df) else float('nan'))

        rows.append({'year': year, 'actual': float(by_year[year]), 'persistence': persistence,
                     'arima': arima_pred, 'lightgbm': lgb_pred, 'train_rows_lightgbm': len(train_df)})

    folds = pd.DataFrame(rows)
    skipped = [int(y) for y in folds.loc[folds['lightgbm'].isna(), 'year']]
    folds = folds.dropna(subset=['lightgbm']).reset_index(drop=True)
    methods = ['persistence', 'arima', 'lightgbm']
    recent = folds[folds['year'] >= folds['year'].max() - 4]
    summary = {
        'description': f"One-step-ahead rolling origin, test years {first_test_year}-{int(folds['year'].max())} "
                       f"({len(folds)} folds); each fold trains only on earlier years."
                       + (f" Skipped for every method because the year's weather features are NA: {skipped}." if skipped else ""),
        'skipped_years': skipped,
        'first_test_year': first_test_year,
        'n_folds': len(folds),
        'rmse': {m: rmse(folds['actual'], folds[m]) for m in methods},
        'mae': {m: float(mean_absolute_error(folds['actual'], folds[m])) for m in methods},
        'rmse_last5': {m: rmse(recent['actual'], recent[m]) for m in methods},
        'folds_with_arima_convergence_warning': int(arima_warnings),
    }

    print(f"{len(folds)} folds, test years {first_test_year}-{int(folds['year'].max())}"
          + (f" (skipped, weather NA: {skipped})" if skipped else ""))
    print(f"{'method':<14}{'RMSE (all folds)':>18}{'MAE':>10}{'RMSE (last 5)':>16}")
    for m in methods:
        print(f"{m:<14}{summary['rmse'][m]:>18,.0f}{summary['mae'][m]:>10,.0f}{summary['rmse_last5'][m]:>16,.0f}")
    print(f"ARIMA convergence warnings in {summary['folds_with_arima_convergence_warning']} of {len(folds)} folds")
    return folds, summary


def main():
    print("=" * 60)
    print("MODEL TRAINING")
    print("=" * 60)

    df = load_model_data()
    print(f"\n[OK] Loaded {len(df)} records")

    arima_results = fit_arima_baseline(df)
    lgb_results = fit_lightgbm_holdout(df)
    naive_results = naive_baseline(df)
    folds, rolling_summary = rolling_origin_evaluation(df)

    results = {
        'arima': arima_results,
        'lightgbm': lgb_results,
        'naive': naive_results,
        'rolling_origin': rolling_summary,
    }
    with open('results/model_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    folds.to_csv('results/rolling_origin_folds.csv', index=False)

    print(f"\n[OK] Saved: results/model_results.json, results/rolling_origin_folds.csv")

    print("\n" + "=" * 60)
    print("SUMMARY (2023-24 holdout RMSE, lb/acre)")
    print("=" * 60)
    if lgb_results and arima_results:
        print(f"\nARIMA:                      {arima_results['rmse']:>8,.0f}")
        print(f"LightGBM:                   {lgb_results['rmse']:>8,.0f}")
        print(f"Naive, one-step:            {naive_results['one_step']['rmse']:>8,.0f}")
        print(f"Naive, multi-step:          {naive_results['multi_step']['rmse']:>8,.0f}")

    print("\nNext: Run src/stress_indicator.py to calculate climate stress scores")
    print("=" * 60)


if __name__ == "__main__":
    main()
