import re
import requests
from bs4 import BeautifulSoup


DISCO_URLS = {
    "fesco": "https://bill.pitc.com.pk/fescobill",
    "lesco": "https://bill.pitc.com.pk/lescobill",
    "gepco": "https://bill.pitc.com.pk/gepcobill",
    "mepco": "https://bill.pitc.com.pk/mepcobill",
    "iesco": "https://bill.pitc.com.pk/iescobill",
    "pesco": "https://bill.pitc.com.pk/pescobill",
    "hesco": "https://bill.pitc.com.pk/hescobill",
    "qesco": "https://bill.pitc.com.pk/qescobill",
    "sepco": "https://bill.pitc.com.pk/sepcobill",
    "tesco": "https://bill.pitc.com.pk/tescobill",
}

# Backward compatibility ke liye
FESCO_HOME = DISCO_URLS["fesco"]
FESCO_SUBMIT = DISCO_URLS["fesco"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# STEP 1: FETCH HTML (POST + ASP.NET tokens)
# ============================================================

def _extract_hidden_fields(soup: BeautifulSoup) -> dict:
    """HTML se ASP.NET hidden fields nikalo."""
    fields = {}
    for name in [
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
        "__RequestVerificationToken",
        "__EVENTTARGET",
        "__EVENTARGUMENT",
        "__LASTFOCUS",
    ]:
        tag = soup.find("input", {"name": name})
        if tag and tag.get("value"):
            fields[name] = tag["value"]
    return fields


def fetch_bill_html(ref_no: str, disco: str = "fesco") -> str | None:
    """FESCO / LESCO / etc. PITC se bill ka HTML laata hai."""
    home_url = DISCO_URLS.get(disco.lower(), DISCO_URLS["fesco"])
    submit_url = home_url
    
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        # Step 1: Homepage GET
        home_response = session.get(home_url, timeout=15)
        home_response.raise_for_status()

        soup = BeautifulSoup(home_response.text, "lxml")
        hidden_fields = _extract_hidden_fields(soup)

        # Step 2: POST bill form
        form_data = {
            **hidden_fields,
            "rbSearchByList": "refno",
            "searchTextBox": ref_no,
            "ruCodeTextBox": "",
            "btnSearch": "Search",
        }

        bill_response = session.post(
            submit_url,
            data=form_data,
            headers={
                "Referer": home_url,
                "Origin": "https://bill.pitc.com.pk",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=15,
            allow_redirects=True,
        )
        bill_response.raise_for_status()
        return bill_response.text

    except requests.RequestException as e:
        print(f"[{disco.upper()}] Error: {e}")
        return None


# ============================================================
# STEP 2: PARSE HTML
# ============================================================

def _get_val(soup: BeautifulSoup, label: str) -> str | None:
    """
    Label dhundho (jaise 'REFERENCE NO') aur uska next .val-space return karo.
    """
    label_tag = soup.find("span", class_="en-lbl", string=re.compile(label, re.IGNORECASE))
    if not label_tag:
        return None

    parent_cell = label_tag.find_parent("div", class_="grid-col-cell") or \
                  label_tag.find_parent("div", class_="meter-info-cell") or \
                  label_tag.find_parent("div", class_="grid-col-cell")
    if not parent_cell:
        return None

    # Us cell mein label ke baad wala .val-space dhundo
    label_row = label_tag.find_parent("div", class_="label-row")
    if label_row:
        val = label_row.find_next_sibling("div", class_="val-space")
        if val:
            return val.get_text(strip=True)

    return None


def _get_charges_breakdown(soup: BeautifulSoup) -> dict:
    """
    charges-breakdown-card se saari values nikalo.
    """
    result = {}
    card = soup.find("div", class_="charges-breakdown-card")
    if not card:
        return result

    for row in card.find_all("div", class_="charges-bd-row"):
        label_span = row.find("span", class_="charges-bd-en")
        val_span = row.find("span", class_="charges-bd-val")
        if label_span and val_span:
            key = label_span.get_text(strip=True).lower().replace(" ", "_")
            value = val_span.get_text(strip=True)
            result[key] = value

    return result


def _get_history(soup: BeautifulSoup) -> list:
    """
    Bill history table parse karo.
    """
    history = []
    for row in soup.find_all("div", class_="history-row"):
        cells = row.find_all("div", class_="history-cell")
        if len(cells) >= 5:
            try:
                history.append({
                    "month": cells[0].get_text(strip=True),
                    "status": cells[1].get_text(strip=True),
                    "units": int(cells[2].get_text(strip=True)),
                    "bill": int(cells[3].get_text(strip=True)),
                    "payment": int(cells[4].get_text(strip=True)),
                })
            except ValueError:
                continue
    return history


def _parse_charges_textarea(soup: BeautifulSoup) -> dict:
    """
    #charges_qr_text_1 textarea se additional details nikalo.
    """
    textarea = soup.find("textarea", id=re.compile(r"^charges_qr_text_"))
    if not textarea:
        return {}

    text = textarea.get_text(strip=False)
    result = {}

    patterns = {
        "variable_chrg": r"VARIABLE CHRG\s*:\s*(-?[\d.]+)",
        "fixed_chrg": r"FIXED CHRG\s*:\s*(-?[\d.]+)",
        "meter_rent": r"METER RENT\s*:\s*(-?[\d.]+)",
        "service_rent": r"SERVICE RENT\s*:\s*(-?[\d.]+)",
        "fc_sur": r"F\.C\.\s*SUR\s*:\s*(-?[\d.]+)",
        "qta": r"QTA\s*:\s*(-?[\d.]+)",
        "ed": r"ED\s*:\s*(-?[\d.]+)",
        "gst": r"GST\s*:\s*(-?[\d.]+)",
        "itax": r"ITAX\s*:\s*(-?[\d.]+)",
        "fpa_energy": r"FPA_ENERGY\s*:\s*(-?[\d.]+)",
        "connection_date": r"CONN DATE\s*:\s*([\d-]+)",
        "san_load": r"SAN LOAD\s*:\s*(\d+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value_str = match.group(1)
            result[key] = value_str if "-" in value_str else float(value_str)

    return result


def parse_bill_html(html: str) -> dict | None:
    """
    Bill HTML ko parse karke structured dict return karta hai.
    """
    soup = BeautifulSoup(html, "lxml")

    # Check: actual bill page hai ya search page?
    if not soup.find("div", class_="consumer-detail-card--gbn"):
        print("[PARSER] Bill page nahi mila (search page hai)")
        return None

    # 1. Consumer details
    consumer = {
        "reference_no": _get_val(soup, "REFERENCE NO"),
        "consumer_id": _get_val(soup, "CONSUMER ID"),
        "name_address": _get_val(soup, "NAME & ADDRESS"),
        "feeder": _get_val(soup, "FEEDER"),
        "sub_division": _get_val(soup, "SUB DIVISION"),
        "tariff": _get_val(soup, "TARIFF"),
        "san_load": _get_val(soup, "SAN LOAD"),
    }

    # 2. Meter info
    meter = {
        "meter_no": _get_val(soup, "METER NO"),
        "previous_reading": _get_val(soup, "PREVIOUS READING"),
        "present_reading": _get_val(soup, "PRESENT READING"),
        "units": _get_val(soup, "UNITS"),
    }

    # 3. Bill charges breakdown
    charges = _get_charges_breakdown(soup)

    # 4. Dates (right sidebar)
    bill_month = None
    reading_date = None
    issue_date = None
    due_date = None

    bm = soup.find("div", class_="right-main-val")
    if bm:
        bill_month = bm.get_text(strip=True)

    for cell in soup.find_all("div", class_="right-grid-cell"):
        label = cell.find("span", class_="right-panel-en")
        val = cell.find("span", class_="right-panel-date-val")
        if label and val:
            lbl = label.get_text(strip=True).upper()
            if "READING" in lbl:
                reading_date = val.get_text(strip=True)
            elif "ISSUE" in lbl:
                issue_date = val.get_text(strip=True)

    due = soup.find("div", class_="right-main-val--due")
    if due:
        due_date = due.get_text(strip=True)

    # 5. History
    history = _get_history(soup)

    # 6. Charges textarea (additional)
    extra = _parse_charges_textarea(soup)

    # Units ko int mein convert karo
    try:
        current_units = int(meter["units"]) if meter["units"] else 0
    except (ValueError, TypeError):
        current_units = 0

    # Grand total int
    try:
        grand_total = int(charges.get("grand_total", "0").replace(",", ""))
    except ValueError:
        grand_total = 0

    # Current bill int
    try:
        current_bill = int(charges.get("current_bill", "0").replace(",", ""))
    except ValueError:
        current_bill = 0

    return {
        "reference_no": consumer["reference_no"],
        "consumer_id": consumer["consumer_id"],
        "name": consumer["name_address"],
        "address": consumer["name_address"],
        "feeder": consumer["feeder"],
        "sub_division": consumer["sub_division"],
        "tariff": consumer["tariff"],
        "san_load": consumer["san_load"],
        "meter_no": meter["meter_no"],
        "previous_reading": meter["previous_reading"],
        "present_reading": meter["present_reading"],
        "current_units": current_units,
        "bill_month": bill_month,
        "reading_date": reading_date,
        "issue_date": issue_date,
        "due_date": due_date,
        "current_bill": current_bill,
        "grand_total": grand_total,
        "charges": charges,
        "extra": extra,
        "history": history,
    }