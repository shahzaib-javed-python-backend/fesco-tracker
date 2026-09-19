from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Depends, Request
from datetime import date, datetime, timedelta
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
from dotenv import load_dotenv

from app.database import init_db, get_db, SessionLocal
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

# Database initialize karo
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

# CORS — sirf trusted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ============================================================
# VALIDATION HELPERS
# ============================================================

VALID_DISCOS = {"fesco", "lesco", "gepco", "mepco", "iesco",
                "pesco", "hesca", "qesco", "sepco", "tesco"}


def validate_inputs(ref_no: str, disco: str = "fesco") -> tuple:
    """Validate reference number and disco."""
    if not ref_no or not re.match(r"^\d{10,14}$", ref_no):
        raise HTTPException(
            status_code=400,
            detail="Invalid reference number — 10-14 digits required"
        )
    disco = disco.lower()
    if disco not in VALID_DISCOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid DISCO. Allowed: {', '.join(sorted(VALID_DISCOS))}"
        )
    return ref_no, disco


# ============================================================
# STATIC & HTML
# ============================================================

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/manifest.json")
def manifest():
    return FileResponse("static/manifest.json")


@app.get("/")
def root():
    return FileResponse("static/index.html")


# ============================================================
# DB ENDPOINTS
# ============================================================

@app.get("/db/search-history")
@limiter.limit("30/minute")
def get_search_history(request: Request, db: Session = Depends(get_db), limit: int = 20):
    """Recent search history."""
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


@app.get("/db/popular-searches")
@limiter.limit("30/minute")
def get_popular_searches(request: Request, db: Session = Depends(get_db), limit: int = 5):
    """Most searched reference numbers."""
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
    """Cache statistics."""
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
    """Bill fetch karo — cache check ke saath."""
    ref_no, disco = validate_inputs(ref_no, disco)

    cached = db.query(CachedBill).filter(
        CachedBill.reference_no == ref_no,
        CachedBill.disco == disco,
    ).first()

    if cached:
        age = datetime.utcnow() - cached.fetched_at.replace(tzinfo=None)
        if age < timedelta(minutes=10):
            print(f"[CACHE] ✅ Hit for {ref_no} (age: {age.seconds}s)")
            return json.loads(cached.bill_data)
        else:
            print(f"[CACHE] ⏰ Expired for {ref_no} — refetching...")

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

    if cached:
        cached.bill_data = json.dumps(bill, default=str)
        cached.fetched_at = datetime.utcnow()
    else:
        new_cache = CachedBill(
            reference_no=ref_no,
            disco=disco,
            bill_data=json.dumps(bill, default=str),
        )
        db.add(new_cache)

    history = SearchHistory(
        reference_no=ref_no,
        disco=disco,
        consumer_name=bill.get("name"),
        units=bill.get("current_units"),
        grand_total=bill.get("grand_total"),
    )
    db.add(history)
    db.commit()

    print(f"[CACHE] ❌ Miss for {ref_no} — fresh fetch, saved to DB")
    return bill


@app.get("/alert/{ref_no}", response_model=AlertResponse)
@limiter.limit("15/minute")
def get_alert(request: Request, ref_no: str, disco: str = "fesco"):
    """Smart alert (prediction ke saath)."""
    ref_no, disco = validate_inputs(ref_no, disco)

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

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
def get_history(request: Request, ref_no: str, disco: str = "fesco"):
    """Bill history."""
    ref_no, disco = validate_inputs(ref_no, disco)

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")
    return bill["history"]


@app.get("/stats/{ref_no}")
@limiter.limit("20/minute")
def get_stats(request: Request, ref_no: str, disco: str = "fesco"):
    """Units statistics."""
    ref_no, disco = validate_inputs(ref_no, disco)

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

    return get_units_stats(bill["history"])


@app.get("/predict/{ref_no}")
@limiter.limit("15/minute")
def get_prediction(request: Request, ref_no: str, disco: str = "fesco"):
    """Month-end prediction."""
    ref_no, disco = validate_inputs(ref_no, disco)

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

    reading_date = date.fromisoformat(bill["reading_date"])
    prediction = predict_monthly_units(bill["current_units"], reading_date)

    return {
        "reference_no": bill["reference_no"],
        "current_units": bill["current_units"],
        **prediction,
    }


@app.get("/compare/{ref_no}")
@limiter.limit("15/minute")
def get_comparison(request: Request, ref_no: str, disco: str = "fesco"):
    """Year-over-year comparison."""
    ref_no, disco = validate_inputs(ref_no, disco)

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

    comparison = compare_with_last_year(
        bill["history"],
        bill["current_units"],
        bill["bill_month"],
    )
    if not comparison:
        raise HTTPException(status_code=400, detail="Comparison ke liye kaafi data nahi hai")

    return comparison


@app.get("/savings/{ref_no}")
@limiter.limit("15/minute")
def get_savings(request: Request, ref_no: str, disco: str = "fesco"):
    """Slab savings hint."""
    ref_no, disco = validate_inputs(ref_no, disco)

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

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
def download_pdf(request: Request, ref_no: str, disco: str = "fesco"):
    """PDF generation."""
    ref_no, disco = validate_inputs(ref_no, disco)

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

    reading_date = date.fromisoformat(bill["reading_date"])
    prediction = predict_monthly_units(bill["current_units"], reading_date)
    alert = smart_alert(bill["current_units"], prediction["predicted_units"])
    stats = get_units_stats(bill["history"])
    comparison = compare_with_last_year(
        bill["history"], bill["current_units"], bill["bill_month"]
    )
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
def get_analytics(request: Request, ref_no: str, disco: str = "fesco"):
    """Advanced analytics (Pandas)."""
    ref_no, disco = validate_inputs(ref_no, disco)

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

    analysis = analyze_bill_history(bill["history"])
    if "error" in analysis:
        raise HTTPException(status_code=400, detail=analysis["error"])

    return {
        "reference_no": bill["reference_no"],
        "disco": disco,
        **analysis,
    }


@app.get("/ml-predict/{ref_no}")
@limiter.limit("5/minute")
def get_ml_prediction(request: Request, ref_no: str, disco: str = "fesco"):
    """ML prediction (scikit-learn)."""
    ref_no, disco = validate_inputs(ref_no, disco)

    bill = get_bill_by_reference(ref_no, disco=disco)
    if not bill:
        raise HTTPException(status_code=404, detail="Reference number nahi mila")

    result = predict_with_ml(bill["history"], ref_no)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "reference_no": bill["reference_no"],
        "disco": disco,
        **result,
    }