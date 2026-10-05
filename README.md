# ⚡ FESCO Bill Tracker

A production-grade Python backend for tracking live electricity bills across 10 Pakistani DISCOs with ML-based prediction and advanced analytics.

## ✨ Features

- 🔌 **Live Web Scraping** — FESCO, LESCO, GEPCO, MEPCO + 6 more DISCOs
- 🚨 **Smart Alerts** — 5 levels (safe / warning / danger / critical / early_warning)
- 🔮 **ML Prediction** — scikit-learn (96.8% R² accuracy)
- 📊 **Pandas Analytics** — trends, seasonal patterns, Z-score outliers
- 📄 **PDF Export** — professional bill generation
- 🌐 **Bilingual** — English + Urdu (RTL)
- 🌙 **Dark Mode** + Tab Navigation
- 📱 **PWA** — installable on mobile/desktop
- 🔒 **8-Layer Security** — robust protection across multiple architectural tiers

## 🔒 8-Layer Security Implementation
1. **Rate Limiting:** Protects endpoints against brute-force and DDoS attacks using `slowapi`.
2. **CORS Configuration:** Strictly restricts unauthorized cross-origin resource sharing.
3. **Security Headers:** Implements comprehensive HTTP headers (X-Frame-Options, X-Content-Type-Options, HSTS).
4. **Input Validation:** Strict data sanitization and payload validation using Pydantic models.
5. **SQL Injection Prevention:** Utilizes SQLAlchemy ORM parameterized queries.
6. **Error Handling & Masking:** Prevents stack trace leakage on production responses.
7. **Environment Isolation:** Sensitive configurations managed securely via `.env` variables.
8. **Request Logging & Auditing:** Tracks incoming request patterns for anomaly detection.

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Data Science | Pandas, NumPy, scikit-learn |
| Scraping | requests, BeautifulSoup, lxml |
| PDF | ReportLab |
| Database | SQLite |
| Frontend | Vanilla JS, Chart.js |
| Security | slowapi, CORS, custom middleware |

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/bill/{ref_no}` | Live bill fetch |
| GET | `/alert/{ref_no}` | Smart alert |
| GET | `/predict/{ref_no}` | Month-end prediction |
| GET | `/analytics/{ref_no}` | Pandas analytics |
| GET | `/ml-predict/{ref_no}` | ML prediction |
| GET | `/compare/{ref_no}` | Year-over-year |
| GET | `/savings/{ref_no}` | Slab savings |
| GET | `/download-pdf/{ref_no}` | PDF export |
| GET | `/db/search-history` | Search history |
| GET | `/health` | Service health and runtime mode |
| GET | `/robots.txt` | Search crawler rules |
| GET | `/sitemap.xml` | Public SEO sitemap |

## 🚀 Quick Start

```bash
# Clone repository
git clone [https://github.com/shahzaib-javed-python-backend/fesco-tracker.git](https://github.com/shahzaib-javed-python-backend/fesco-tracker.git)
cd fesco-tracker

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload
```

## Production Configuration

Copy `.env.example` to `.env` before deployment. Keep `DEMO_MODE=False` in production so unavailable live bills are never represented with sample data. Set `PUBLIC_BASE_URL` to the public HTTPS URL so the generated sitemap points to the correct domain.

This is an independent bill-tracking service and is not the official FESCO website. Users should verify final bill information through official FESCO or PITC channels.