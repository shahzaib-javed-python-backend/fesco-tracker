import pandas as pd
import numpy as np
from datetime import datetime


def analyze_bill_history(history: list) -> dict:
    """
    Bill history ka pandas-based analysis.
    
    Args:
        history: List of dicts with keys: month, units, bill, payment
    
    Returns:
        Analysis results as dict.
    """
    if not history or len(history) < 3:
        return {"error": "Analysis ke liye kaafi data nahi hai (min 3 months)"}

    # DataFrame banao
    df = pd.DataFrame(history)

    # Month string ko date mein convert karo (Aug25 -> 2025-08)
    def month_to_date(m):
        try:
            # Format: "Aug25" -> "2025-08-01"
            month_str = m[:3]
            year_str = m[3:]
            year = f"20{year_str}" if len(year_str) == 2 else year_str
            return pd.to_datetime(f"{year}-{month_str}-01", format="%Y-%b-%d")
        except Exception:
            return pd.NaT

    df["date"] = df["month"].apply(month_to_date)
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    if len(df) < 3:
        return {"error": "Valid dates nahi mile"}

    # ============================================================
    # 1. BASIC STATS
    # ============================================================
    units = df["units"]
    bills = df["bill"]

    avg_units = float(units.mean())
    std_units = float(units.std())
    median_units = float(units.median())

    # ============================================================
    # 2. TREND ANALYSIS (Linear Regression)
    # ============================================================
    x = np.arange(len(units)).reshape(-1, 1)
    y = units.values

    # Simple slope calculation
    slope = float(np.polyfit(x.flatten(), y, 1)[0])

    if slope > 5:
        trend = "increasing"
        trend_msg = f"Aapki consumption badh rahi hai (~{abs(slope):.1f} units/month)"
    elif slope < -5:
        trend = "decreasing"
        trend_msg = f"Aapki consumption kam ho rahi hai (~{abs(slope):.1f} units/month)"
    else:
        trend = "stable"
        trend_msg = "Aapki consumption stable hai"

    # ============================================================
    # 3. MOVING AVERAGES
    # ============================================================
    df["ma_3"] = units.rolling(window=3).mean()
    df["ma_6"] = units.rolling(window=6).mean()

    last_ma_3 = float(df["ma_3"].iloc[-1]) if not pd.isna(df["ma_3"].iloc[-1]) else None
    last_ma_6 = float(df["ma_6"].iloc[-1]) if not pd.isna(df["ma_6"].iloc[-1]) else None

    # ============================================================
    # 4. GROWTH RATES
    # ============================================================
    # Month-over-month (last vs previous)
    mom_growth = None
    if len(units) >= 2:
        mom_growth = float(((units.iloc[-1] - units.iloc[-2]) / units.iloc[-2]) * 100)

    # Year-over-year (last vs same month last year)
    yoy_growth = None
    if len(units) >= 12:
        yoy_growth = float(((units.iloc[-1] - units.iloc[-12]) / units.iloc[-12]) * 100)

    # ============================================================
    # 5. SEASONAL ANALYSIS (Summer vs Winter)
    # ============================================================
    df["month_num"] = df["date"].dt.month

    summer_months = [5, 6, 7, 8, 9]   # May-Sep
    winter_months = [11, 12, 1, 2, 3] # Nov-Mar

    summer_avg = float(df[df["month_num"].isin(summer_months)]["units"].mean()) if not df[df["month_num"].isin(summer_months)].empty else None
    winter_avg = float(df[df["month_num"].isin(winter_months)]["units"].mean()) if not df[df["month_num"].isin(winter_months)].empty else None

    seasonal_ratio = None
    if summer_avg and winter_avg:
        seasonal_ratio = round(summer_avg / winter_avg, 2)

    # ============================================================
    # 6. OUTLIER DETECTION (Z-Score)
    # ============================================================
    if std_units > 0:
        df["z_score"] = (units - avg_units) / std_units
        outliers = df[df["z_score"].abs() > 1.5][["month", "units", "z_score"]].to_dict("records")
    else:
        outliers = []

    # ============================================================
    # 7. PEAK / LOW
    # ============================================================
    peak_idx = units.idxmax()
    low_idx = units.idxmin()

    peak_month = {
        "month": df.loc[peak_idx, "month"],
        "units": int(df.loc[peak_idx, "units"]),
    }
    low_month = {
        "month": df.loc[low_idx, "month"],
        "units": int(df.loc[low_idx, "units"]),
    }

    # ============================================================
    # 8. NEXT MONTH PREDICTION (Simple Linear Trend)
    # ============================================================
    next_x = len(units)
    next_prediction = float(np.polyfit(x.flatten(), y, 1)[0] * next_x + np.polyfit(x.flatten(), y, 1)[1])

    # Confidence interval (rough)
    if std_units > 0:
        ci_lower = max(0, next_prediction - 1.96 * std_units)
        ci_upper = next_prediction + 1.96 * std_units
    else:
        ci_lower = ci_upper = next_prediction

    # ============================================================
    # RETURN ANALYSIS
    # ============================================================
    return {
        "summary": {
            "total_months": len(df),
            "avg_units": round(avg_units, 2),
            "median_units": round(median_units, 2),
            "std_units": round(std_units, 2),
            "avg_bill": round(float(bills.mean()), 2),
            "total_units": int(units.sum()),
        },
        "trend": {
            "direction": trend,
            "slope": round(slope, 2),
            "message": trend_msg,
        },
        "moving_averages": {
            "ma_3": round(last_ma_3, 2) if last_ma_3 else None,
            "ma_6": round(last_ma_6, 2) if last_ma_6 else None,
        },
        "growth": {
            "mom_percent": round(mom_growth, 2) if mom_growth is not None else None,
            "yoy_percent": round(yoy_growth, 2) if yoy_growth is not None else None,
        },
        "seasonal": {
            "summer_avg": round(summer_avg, 2) if summer_avg else None,
            "winter_avg": round(winter_avg, 2) if winter_avg else None,
            "ratio": seasonal_ratio,
        },
        "outliers": outliers,
        "peak": peak_month,
        "low": low_month,
        "prediction": {
            "next_month_units": round(next_prediction, 2),
            "confidence_interval": {
                "lower": round(ci_lower, 2),
                "upper": round(ci_upper, 2),
            },
        },
    }