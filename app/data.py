from app.services.fesco_client import fetch_bill_html, parse_bill_html


# ============================================================
# MOCK DATA (Fallback — jab server down ho)
# ============================================================

MOCK_BILLS = {
    "19131331109052": {
        "reference_no": "19131331109052",
        "consumer_id": "1131721295",
        "name": "Mehnaz Fatima",
        "address": "W/O Shahid Mehmood, St No 5 Zia Town Ck No 204 Rb Fsd",
        "bill_month": "AUG 26",
        "reading_date": "2026-08-27",
        "current_units": 243,
        "current_bill": 11221,
        "grand_total": 24435,
        "due_date": "09 SEP 26",
        "disco": "FESCO",
        "history": [
            {"month": "Aug25", "units": 288, "bill": 11590, "payment": 0},
            {"month": "Sep25", "units": 225, "bill": 21303, "payment": 21303},
            {"month": "Oct25", "units": 177, "bill": 6431,  "payment": 6966},
            {"month": "Nov25", "units": 124, "bill": 4592,  "payment": 4987},
            {"month": "Dec25", "units": 92,  "bill": 2668,  "payment": 2907},
            {"month": "Jan26", "units": 96,  "bill": 2846,  "payment": 3096},
            {"month": "Feb26", "units": 80,  "bill": 2989,  "payment": 3237},
            {"month": "Mar26", "units": 94,  "bill": 4085,  "payment": 4412},
            {"month": "Apr26", "units": 61,  "bill": 1672,  "payment": 1801},
            {"month": "May26", "units": 224, "bill": 11066, "payment": 0},
            {"month": "Jun26", "units": 230, "bill": 22871, "payment": 23775},
            {"month": "Jul26", "units": 260, "bill": 12009, "payment": 0},
        ],
    }
}


# ============================================================
# HELPER: DATE CONVERTER
# ============================================================

def _convert_date(date_str: str | None) -> str | None:
    """
    '27 AUG 26' -> '2026-08-27' (ISO format)
    """
    if not date_str:
        return None

    months = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
        "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
        "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
    }

    parts = date_str.strip().split()
    if len(parts) != 3:
        return None

    day, month_name, year_short = parts
    month = months.get(month_name.upper())
    if not month:
        return None

    year = f"20{year_short}" if len(year_short) == 2 else year_short
    return f"{year}-{month}-{int(day):02d}"


# ============================================================
# MAIN FUNCTION: LIVE FETCH WITH FALLBACK
# ============================================================

def get_bill_by_reference(ref_no: str, disco: str = "fesco") -> dict | None:
    """
    1. Live fetch try karo with disco parameter
    2. Fail ho to mock data se fallback
    """
    print(f"[DATA] Fetching live bill from {disco.upper()} for {ref_no}...")

    # Try live fetch
    html = fetch_bill_html(ref_no, disco=disco)

    if html:
        data = parse_bill_html(html)
        if data:
            data["reading_date"] = _convert_date(data.get("reading_date"))
            data["disco"] = disco.upper()
            
            print(f"[DATA] ✅ Live data mila — Units: {data['current_units']}")
            return data

    # Fallback to mock
    print(f"[DATA] ⚠️ Live fetch fail — mock data use kar rahe hain")
    return MOCK_BILLS.get(ref_no)