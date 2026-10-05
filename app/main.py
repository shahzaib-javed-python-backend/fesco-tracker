from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Depends, Request
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import json
import os
import re
import socket
import csv
import io
from pathlib import Path
from dotenv import load_dotenv

from app.database import init_db, get_db, SessionLocal
from app.config import settings
from app.models.search import SearchHistory, CachedBill
from app.data import get_bill_by_reference
from app.models import BillResponse, AlertResponse
from app.services.alert_engine import (
    check_unit_alert,
    get_units_stats,
    predict_monthly_units,
    smart_alert,
    compare_with_last_year,
    calculate_slab_savings,
)
from app.services.pdf_generator import generate_bill_pdf
from app.services.analytics import analyze_bill_history
from app.services.ml_predictor import predict_with_ml


# ============================================================
# CONFIGURATION
# ============================================================
load_dotenv()

DEBUG = os.getenv("DEBUG", "False").lower() == "true"


def _is_local() -> bool:
    """Detect if running locally (development)."""
    if DEBUG:
        return True
    hostname = socket.gethostname().lower()
    local_hosts = ("localhost", "127.0.0.1", "::1")
    return hostname in local_hosts or hostname.startswith("desktop") or hostname.startswith("laptop")


IS_LOCAL = _is_local()

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000"
).split(",")


# ============================================================
# APP INIT
# ============================================================
app = FastAPI(
    title="FESCO Bill Tracker",
    description="FESCO bill check karo aur unit alerts pao",
    version="0.1.0",
    docs_url="/docs" if IS_LOCAL else None,
    redoc_url="/redoc" if IS_LOCAL else None,
    openapi_url="/openapi.json" if IS_LOCAL else None,
)

init_db()


# ============================================================
# SECURITY MIDDLEWARE
# ============================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ============================================================
# VALIDATION & HELPERS
# ============================================================

VALID_DISCOS = {"fesco", "lesco", "gepco", "mepco", "iesco",
                "pesco", "hesco", "qesco", "sepco", "tesco"}


def validate_inputs(ref_no: str, disco: str = "fesco") -> tuple:
    """Validate reference number and disco."""
    if not ref_no or not re.match(r"^\d{14}$", ref_no):
        raise HTTPException(
            status_code=400,
            detail="Invalid reference number — exactly 14 digits required"
        )
    disco = disco.lower()
    if disco not in VALID_DISCOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid DISCO. Allowed: {', '.join(sorted(VALID_DISCOS))}"
        )
    return ref_no, disco


# 🔥 ADDED: Database se fast history nikalne ka function
def get_history_from_db(db: Session, ref_no: str, disco: str) -> list:
    searches = db.query(SearchHistory)\
        .filter(SearchHistory.reference_no == ref_no, SearchHistory.disco == disco)\
        .order_by(SearchHistory.searched_at.asc())\
        .all()
    
    if not searches:
        return []

    history_dict = {}
    for s in searches:
        if not s.searched_at: continue
        month_key = s.searched_at.strftime("%b%y") 
        history_dict[month_key] = {
            "month": month_key,
            "units": s.units or 0,
            "bill": s.grand_total or 0,
            "payment": s.grand_total or 0
        }
    
    return list(history_dict.values())


# 🔥 ADDED: FESCO se slow fetch ki bajaye Cache se fast fetch karo
def get_bill_data(db: Session, ref_no: str, disco: str) -> dict:
    """
    Pehle cache check karo. Agar data 30 min se purana nahi hai, 
    to FESCO ko request bhejne ke bajaye Cache se dedo (Ultra Fast!).
    """
    cached = db.query(CachedBill).filter(
        CachedBill.reference_no == ref_no,
        CachedBill.disco == disco,
    ).first()

    # Cache lifetime is configurable so deployments can choose freshness.
    if cached:
        age = datetime.now(timezone.utc).replace(tzinfo=None) - cached.fetched_at.replace(tzinfo=None)
        cached_bill = json.loads(cached.bill_data)
        if age < timedelta(minutes=settings.cache_ttl_minutes) and (
            settings.demo_mode or not cached_bill.get("is_demo", False)
        ):
            print(f"[CACHE] ✅ Fast Hit for {ref_no}")
            return cached_bill

    # Agar cache nahi hai ya 30 min se purana hai, to FESCO se fetch karo (Slow)
    print(f"[CACHE] ❌ Miss for {ref_no} — Fetching from FESCO...")
    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

    # FESCO se aya hua data cache mein save karo taake next time fast ho
    if cached:
        cached.bill_data = json.dumps(bill, default=str)
        cached.fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        new_cache = CachedBill(
            reference_no=ref_no,
            disco=disco,
            bill_data=json.dumps(bill, default=str),
        )
        db.add(new_cache)
    
    db.commit()
    return bill


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


# ============================================================
# STATIC & HTML
# ============================================================

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/manifest.json")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.json")


@app.get("/privacy")
def privacy_page():
    return FileResponse(STATIC_DIR / "privacy.html")


@app.get("/terms")
def terms_page():
    return FileResponse(STATIC_DIR / "terms.html")


@app.get("/contact")
def contact_page():
    return FileResponse(STATIC_DIR / "contact.html")


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "demo_mode": settings.demo_mode,
    }


@app.get("/robots.txt", response_class=Response)
def robots():
    return Response(
        content=(
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /db/\n"
            f"Sitemap: {settings.public_base_url.rstrip('/')}/sitemap.xml\n"
        ),
        media_type="text/plain",
    )


@app.get("/sitemap.xml", response_class=Response)
def sitemap():
    base_url = settings.public_base_url.rstrip("/")
    return Response(
        content=(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{base_url}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>"
            f"<url><loc>{base_url}/#bill-search</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>"
            f"<url><loc>{base_url}/#services</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>"
            "</urlset>"
        ),
        media_type="application/xml",
    )


# ============================================================
# DB ENDPOINTS
# ============================================================

@app.get("/db/search-history")
@limiter.limit("30/minute")
def get_search_history(request: Request, db: Session = Depends(get_db), limit: int = 20):
    limit = min(max(1, limit), 100)
    searches = db.query(SearchHistory)\
        .order_by(SearchHistory.searched_at.desc())\
        .limit(limit)\
        .all()

    return [
        {
            "id": s.id,
            "reference_no": s.reference_no,
            "disco": s.disco,
            "consumer_name": s.consumer_name,
            "units": s.units,
            "grand_total": s.grand_total,
            "searched_at": s.searched_at.isoformat() if s.searched_at else None,
        }
        for s in searches
    ]


@app.get("/export-history/{ref_no}")
@limiter.limit("10/minute")
def export_history(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    ref_no, disco = validate_inputs(ref_no, disco)
    history = get_history_from_db(db, ref_no, disco)
    if not history:
        raise HTTPException(status_code=404, detail="No history available for this reference")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["month", "units", "bill", "payment"])
    writer.writeheader()
    writer.writerows(history)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{disco}-{ref_no}-history.csv"'},
    )


@app.get("/db/popular-searches")
@limiter.limit("30/minute")
def get_popular_searches(request: Request, db: Session = Depends(get_db), limit: int = 5):
    from sqlalchemy import func

    limit = min(max(1, limit), 20)
    popular = db.query(
        SearchHistory.reference_no,
        func.count(SearchHistory.reference_no).label("count")
    ).group_by(SearchHistory.reference_no)\
     .order_by(func.count(SearchHistory.reference_no).desc())\
     .limit(limit)\
     .all()

    return [{"reference_no": p[0], "count": p[1]} for p in popular]


@app.get("/db/cache-stats")
@limiter.limit("30/minute")
def get_cache_stats(request: Request, db: Session = Depends(get_db)):
    total_cached = db.query(CachedBill).count()
    total_searches = db.query(SearchHistory).count()

    return {
        "total_cached_bills": total_cached,
        "total_searches": total_searches,
    }


# ============================================================
# BILL ENDPOINTS
# ============================================================

@app.get("/bill/{ref_no}", response_model=BillResponse)
@limiter.limit("10/minute")
def get_bill(
    request: Request,
    ref_no: str,
    disco: str = "fesco",
    db: Session = Depends(get_db),
):
    """Bill fetch karo — Cache check ke saath."""
    ref_no, disco = validate_inputs(ref_no, disco)
    
    # 🔥 Use new helper function
    bill = get_bill_data(db, ref_no, disco)

    # Search history mein save karo (sirf jab user explicitly search kare)
    # Cache se data aya ho, tab bhi history save honi chahiye
    history = SearchHistory(
        reference_no=ref_no,
        disco=disco,
        consumer_name=bill.get("name"),
        units=bill.get("current_units"),
        grand_total=bill.get("grand_total"),
    )
    db.add(history)
    db.commit()

    return bill


@app.get("/alert/{ref_no}", response_model=AlertResponse)
@limiter.limit("15/minute")
def get_alert(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    """Smart alert (prediction ke saath)."""
    ref_no, disco = validate_inputs(ref_no, disco)
    
    # 🔥 Slow scraper ki bajaye fast cache use karo
    bill = get_bill_data(db, ref_no, disco)

    reading_date = date.fromisoformat(bill["reading_date"])
    prediction = predict_monthly_units(bill["current_units"], reading_date)
    alert = smart_alert(bill["current_units"], prediction["predicted_units"])

    return {
        "reference_no": bill["reference_no"],
        "current_units": bill["current_units"],
        "status": alert["status"],
        "message": alert["message"],
        "color": alert["color"],
    }


@app.get("/history/{ref_no}")
@limiter.limit("20/minute")
def get_history(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    ref_no, disco = validate_inputs(ref_no, disco)
    history = get_history_from_db(db, ref_no, disco)
    return history


@app.get("/stats/{ref_no}")
@limiter.limit("20/minute")
def get_stats(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    ref_no, disco = validate_inputs(ref_no, disco)
    history = get_history_from_db(db, ref_no, disco)
    if not history:
        return {"avg": 0, "max": 0, "min": 0, "months": 0}
    return get_units_stats(history)


@app.get("/predict/{ref_no}")
@limiter.limit("15/minute")
def get_prediction(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    ref_no, disco = validate_inputs(ref_no, disco)
    
    # 🔥 Fast cache use karo
    bill = get_bill_data(db, ref_no, disco)

    reading_date = date.fromisoformat(bill["reading_date"])
    prediction = predict_monthly_units(bill["current_units"], reading_date)

    return {
        "reference_no": bill["reference_no"],
        "current_units": bill["current_units"],
        **prediction,
    }


@app.get("/compare/{ref_no}")
@limiter.limit("15/minute")
def get_comparison(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    ref_no, disco = validate_inputs(ref_no, disco)
    
    # 🔥 Fast cache use karo
    bill = get_bill_data(db, ref_no, disco)
    history = get_history_from_db(db, ref_no, disco)

    comparison = compare_with_last_year(
        history,
        bill["current_units"],
        bill["bill_month"],
    )
    if not comparison:
        raise HTTPException(status_code=400, detail="Comparison ke liye kaafi data nahi hai")

    return comparison


@app.get("/savings/{ref_no}")
@limiter.limit("15/minute")
def get_savings(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    ref_no, disco = validate_inputs(ref_no, disco)
    
    # 🔥 Fast cache use karo
    bill = get_bill_data(db, ref_no, disco)

    savings = calculate_slab_savings(bill["current_units"])
    if not savings:
        raise HTTPException(status_code=400, detail="Savings calculate nahi ho saki")

    return {
        "reference_no": bill["reference_no"],
        "current_units": bill["current_units"],
        **savings,
    }


@app.get("/download-pdf/{ref_no}")
@limiter.limit("5/minute")
def download_pdf(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    ref_no, disco = validate_inputs(ref_no, disco)
    
    # 🔥 Fast cache use karo
    bill = get_bill_data(db, ref_no, disco)
    history = get_history_from_db(db, ref_no, disco)

    reading_date = date.fromisoformat(bill["reading_date"])
    prediction = predict_monthly_units(bill["current_units"], reading_date)
    alert = smart_alert(bill["current_units"], prediction["predicted_units"])
    
    stats = get_units_stats(history) if history else {}
    comparison = compare_with_last_year(
        history, bill["current_units"], bill["bill_month"]
    ) if history else None
    savings = calculate_slab_savings(bill["current_units"])

    pdf_bytes = generate_bill_pdf(bill, alert, prediction, stats, comparison, savings)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="fesco-bill-{ref_no}.pdf"'
        },
    )


@app.get("/analytics/{ref_no}")
@limiter.limit("20/minute")
def get_analytics(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    ref_no, disco = validate_inputs(ref_no, disco)
    bill = get_bill_data(db, ref_no, disco)
    history = bill.get("history") or get_history_from_db(db, ref_no, disco)

    analysis = analyze_bill_history(history)
    if "error" in analysis:
        raise HTTPException(status_code=400, detail=analysis["error"])

    return {
        "reference_no": ref_no,
        "disco": disco,
        **analysis,
    }


@app.get("/ml-predict/{ref_no}")
@limiter.limit("5/minute")
def get_ml_prediction(request: Request, ref_no: str, disco: str = "fesco", db: Session = Depends(get_db)):
    ref_no, disco = validate_inputs(ref_no, disco)
    bill = get_bill_data(db, ref_no, disco)
    history = bill.get("history") or get_history_from_db(db, ref_no, disco)

    result = predict_with_ml(history, ref_no)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "reference_no": ref_no,
        "disco": disco,
        **result,
    }
    