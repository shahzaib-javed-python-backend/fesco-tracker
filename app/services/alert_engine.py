from datetime import date

def check_unit_alert(units: int) -> dict:
    if units <= 190:
        return {
            "status": "safe",
            "message": f"Safe zone. Aap ne {units} units use kiye.",
            "color": "green",
        }
    elif 191 <= units <= 200:
        return {
            "status": "warning",
            "message": f"Warning! {units} units - 200 ke qareeb.",
            "color": "orange",
        }
    elif 201 <= units <= 300:
        return {
            "status": "danger",
            "message": f"Alert! {units} units - 200 cross ho gaye.",
            "color": "red",
        }
    else:
        return {
            "status": "critical",
            "message": f"Critical! {units} units - 300+ cross, bill bohot zyada!",
            "color": "darkred",
        }

def get_units_stats(history: list) -> dict:
    """History se units ke statistics nikalta hai."""
    units_list = [item["units"] for item in history]

    total = sum(units_list)
    count = len(units_list)
    average = total / count
    maximum = max(units_list)
    minimum = min(units_list)

    return {
        "average_units": round(average, 2),
        "max_units": maximum,
        "min_units": minimum,
        "total_months": count,
        "total_units": total,
    }

def predict_monthly_units(current_units: int, reading_date: date) -> dict:
    """
    Current units aur reading date se month-end prediction.
    
    Formula:
    - days_passed = today - reading_date
    - daily_avg = current_units / days_passed
    - predicted = daily_avg * 30
    """
    today = date.today()
    days_passed = (today - reading_date).days

    if days_passed <= 0:
        return {
            "days_passed": 0,
            "daily_average": 0,
            "predicted_units": current_units,
            "message": "Reading date abhi aayi nahi.",
        }

    daily_avg = current_units / days_passed
    predicted = daily_avg * 30

    return {
        "days_passed": days_passed,
        "daily_average": round(daily_avg, 2),
        "predicted_units": round(predicted, 0),
    }

def smart_alert(current_units: int, predicted_units: float) -> dict:
    """
    Current aur predicted units dono dekh ke alert deta hai.
    
    Rules:
    - Agar current safe hai lekin prediction 200+ hai → "early warning"
    - Agar dono danger hain → "critical"
    """
    current_alert = check_unit_alert(current_units)

    # Agar current hi danger hai, to wahi return karo
    if current_alert["status"] in ("danger", "critical"):
        return current_alert

    # Agar prediction danger hai lekin current safe
    if predicted_units > 200:
        return {
            "status": "early_warning",
            "message": f"Early Warning! Abhi {current_units} units hain, lekin is raftar se {int(predicted_units)} tak ja sakte hain.",
            "color": "orange",
        }

    return current_alert

def compare_with_last_year(history: list, current_units: int, current_month: str) -> dict | None:
    """
    Current bill ke units ko pichle saal ke same month se compare karta hai.
    
    current_units: aaj ka actual units (bill se)
    current_month: "AUG 26" (bill se)
    history: 12-month ki list
    """
    if not history:
        return None

    # Current month ka naam nikalo — "AUG 26" -> "AUG"
    month_name = current_month.split()[0].upper() if current_month else None
    if not month_name:
        return None

    # History mein wahi month pichle saal ka dhundo
    # Jaise "AUG 26" current hai to "Aug25" dhundo
    last_year_entry = None
    for entry in history:
        # Entry format: "Aug25" — month + 2-digit year
        if len(entry["month"]) >= 5:
            entry_month = entry["month"][:3].upper()
            entry_year = entry["month"][3:]  # "25" for Aug25
            
            # Same month, previous year
            if entry_month == month_name and entry_year != current_month.split()[-1]:
                last_year_entry = entry
                break

    if not last_year_entry:
        return None

    last_year_units = last_year_entry["units"]
    if last_year_units == 0:
        return None

    change_pct = ((current_units - last_year_units) / last_year_units) * 100

    if change_pct > 5:
        direction = "up"
        message = f"⚠️ Aapki is month ({current_month}) ki consumption, pichle saal ({last_year_entry['month']}) se {abs(change_pct):.1f}% zyada hai."
        color = "orange"
    elif change_pct < -5:
        direction = "down"
        message = f"✅ Shabash! Aapki is month ({current_month}) ki consumption, pichle saal ({last_year_entry['month']}) se {abs(change_pct):.1f}% kam hai."
        color = "green"
    else:
        direction = "same"
        message = f"ℹ️ Aapki consumption pichle saal ({last_year_entry['month']}) ke qareeb hai."
        color = "blue"

    return {
        "current_month": current_month,
        "current_units": current_units,
        "last_year_month": last_year_entry["month"],
        "last_year_units": last_year_units,
        "change_percent": round(change_pct, 1),
        "direction": direction,
        "message": message,
        "color": color,
    }

def calculate_slab_savings(current_units: int) -> dict:
    """
    Current units ke hisaab se slab savings ka hint deta hai.
    User ko batata hai:
    - Current slab
    - Agle slab tak kitne units door
    - Kitna bacha sakta hai
    """
    slabs = [
        {"name": "Slab 1", "min": 1,   "max": 100, "rate": 22.0},
        {"name": "Slab 2", "min": 101, "max": 200, "rate": 30.0},
        {"name": "Slab 3", "min": 201, "max": 300, "rate": 37.0},
        {"name": "Slab 4", "min": 301, "max": 400, "rate": 43.0},
        {"name": "Slab 5", "min": 401, "max": 9999, "rate": 48.0},
    ]

    # Current slab dhundo
    current_slab_idx = None
    for i, slab in enumerate(slabs):
        if slab["min"] <= current_units <= slab["max"]:
            current_slab_idx = i
            break

    if current_slab_idx is None:
        return None

    current_slab = slabs[current_slab_idx]

    # Agar user last slab mein hai
    if current_slab_idx == len(slabs) - 1:
        return {
            "type": "max",
            "current_slab": current_slab["name"],
            "message": f"⚠️ Aap highest slab ({current_slab['name']}) mein hain. Har extra unit pe Rs {current_slab['rate']} lag rahe hain. Units kam karein to bohot bachat ho sakti hai.",
            "color": "orange",
        }

    # Next slab
    next_slab = slabs[current_slab_idx + 1]

    # Current slab ka max threshold
    threshold = current_slab["max"]

    # Rate difference
    rate_diff = next_slab["rate"] - current_slab["rate"]

    # User kitna door hai threshold se
    units_to_go = threshold - current_units  # Next slab mein jane ke liye

    # Agar user 30 units ke andar hai threshold se (i.e., next slab mein jane wala hai)
    if units_to_go <= 30 and units_to_go > 0:
        # Warning: Next slab mein jane wala hai
        potential_extra_cost = units_to_go * rate_diff
        return {
            "type": "warning",
            "current_slab": current_slab["name"],
            "threshold": threshold,
            "units_to_go": units_to_go,
            "message": f"⚠️ Aap {threshold} units se sirf {units_to_go} door hain! Agar {units_to_go} units zyada use kiye to aap {next_slab['name']} mein chale jayenge — har extra unit Rs {rate_diff:.0f} zyada mehnga hoga. {units_to_go} units kam karein to ~Rs {int(potential_extra_cost)} bachayein.",
            "savings_rs": int(potential_extra_cost),
            "color": "orange",
        }

    # Agar user threshold ke qareeb hai (recently crossed)
    prev_slab = slabs[current_slab_idx - 1] if current_slab_idx > 0 else None
    if prev_slab:
        units_over = current_units - prev_slab["max"]
        if units_over <= 30 and units_over > 0:
            # Recently crossed previous threshold
            prev_rate_diff = current_slab["rate"] - prev_slab["rate"]
            extra_cost = units_over * prev_rate_diff
            return {
                "type": "hint",
                "current_slab": current_slab["name"],
                "threshold": prev_slab["max"],
                "units_over": units_over,
                "message": f"💡 Aap ne abhi {prev_slab['max']} units cross kiye hain. {units_over} units zyada use karne pe aap {current_slab['name']} mein hain — Rs {int(extra_cost)} extra lag rahe hain. Agar {units_over} units kam karein to wapas {prev_slab['name']} mein aa jayenge.",
                "savings_rs": int(extra_cost),
                "color": "blue",
            }

    # Safe zone — user slab ke andar araam se hai
    return {
        "type": "safe",
        "current_slab": current_slab["name"],
        "message": f"✅ Aap {current_slab['name']} mein hain aur agle slab ({next_slab['name']}) se safe door hain. {units_to_go} units door hain.",
        "units_to_go": units_to_go,
        "color": "green",
    }