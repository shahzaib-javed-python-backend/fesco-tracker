import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_absolute_error
import joblib
import os
from datetime import datetime


# Model save path
MODEL_DIR = "models_cache"
os.makedirs(MODEL_DIR, exist_ok=True)


def _prepare_features(history: list) -> pd.DataFrame:
    """
    History ko features mein convert karo.
    Simple features — no data leakage.
    """
    df = pd.DataFrame(history)

    # Month string to date (Aug25 -> 2025-08-01)
    def month_to_date(m):
        try:
            month_str = m[:3]
            year_str = m[3:]
            year = f"20{year_str}" if len(year_str) == 2 else year_str
            return pd.to_datetime(f"{year}-{month_str}-01", format="%Y-%b-%d")
        except Exception:
            return pd.NaT

    df["date"] = df["month"].apply(month_to_date)
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # Simple features (no leakage)
    df["month_num"] = df["date"].dt.month
    df["is_summer"] = df["month_num"].isin([5, 6, 7, 8, 9]).astype(int)
    df["time_idx"] = range(len(df))

    return df


def _train_models(df: pd.DataFrame) -> dict:
    """
    3 models train karo — saara data training ke liye use karo.
    R² score training data pe calculate hoga.
    """
    # Sirf 3 features — no leakage
    feature_cols = ["time_idx", "month_num", "is_summer"]

    X = df[feature_cols].values
    y = df["units"].values

    if len(X) < 3:
        return {"error": "Training ke liye kaafi data nahi (min 3 months)"}

    models = {
        "linear": LinearRegression(),
        "ridge": Ridge(alpha=1.0),
        "random_forest": RandomForestRegressor(
            n_estimators=100,
            max_depth=3,
            random_state=42,
            min_samples_split=2,
        ),
    }

    results = {}
    best_model = None
    best_score = -float("inf")
    best_name = None

    for name, model in models.items():
        try:
            # Saara data pe train karo
            model.fit(X, y)

            # Training data pe predict karo (R² ke liye)
            y_pred = model.predict(X)
            r2 = r2_score(y, y_pred)
            mae = mean_absolute_error(y, y_pred)

            results[name] = {
                "r2_score": round(r2, 3),
                "mae": round(mae, 2),
            }

            if r2 > best_score:
                best_score = r2
                best_model = model
                best_name = name
        except Exception as e:
            results[name] = {"error": str(e)}

    return {
        "models": results,
        "best_model": best_name,
        "best_model_obj": best_model,
        "best_score": best_score,
        "feature_cols": feature_cols,
        "df_clean": df,
    }


def _predict_next_month(df: pd.DataFrame, model, feature_cols: list) -> dict:
    """
    Next month ki prediction karo — proper features ke saath.
    """
    last_row = df.iloc[-1]
    next_month_num = (last_row["month_num"] % 12) + 1

    next_features = {
        "time_idx": last_row["time_idx"] + 1,
        "month_num": next_month_num,
        "is_summer": 1 if next_month_num in [5, 6, 7, 8, 9] else 0,
    }

    X_next = np.array([[next_features[col] for col in feature_cols]])
    prediction = float(model.predict(X_next)[0])

    # Confidence interval (based on residuals)
    y_pred_train = model.predict(df[feature_cols].values)
    residuals = df["units"].values - y_pred_train
    std_residual = float(np.std(residuals))

    ci_lower = max(0, prediction - 1.96 * std_residual)
    ci_upper = prediction + 1.96 * std_residual

    # Next month ka naam
    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
    }

    return {
        "predicted_units": round(prediction, 2),
        "confidence_interval": {
            "lower": round(ci_lower, 2),
            "upper": round(ci_upper, 2),
        },
        "next_month_num": int(next_month_num),
        "next_month_name": month_names[next_month_num],
    }


def predict_with_ml(history: list, ref_no: str) -> dict:
    """
    ML-based next month prediction.
    """
    if not history or len(history) < 6:
        return {"error": "ML prediction ke liye kam se kam 6 months chahiye"}

    try:
        # Features prepare karo
        df = _prepare_features(history)

        # Models train karo
        training = _train_models(df)
        if "error" in training:
            return training

        # Next month prediction
        prediction = _predict_next_month(
            training["df_clean"],
            training["best_model_obj"],
            training["feature_cols"],
        )

        # Model save karo
        model_path = os.path.join(MODEL_DIR, f"{ref_no}_model.pkl")
        joblib.dump(training["best_model_obj"], model_path)

        return {
            "models_compared": training["models"],
            "best_model": training["best_model"],
            "best_r2_score": round(training["best_score"], 3),
            "training_rows": len(training["df_clean"]),
            "prediction": prediction,
            "model_saved": model_path,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {"error": f"ML prediction failed: {str(e)}"}