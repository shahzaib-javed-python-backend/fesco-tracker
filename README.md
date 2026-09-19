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
- 🔒 **8-Layer Security** — rate limiting, CORS, headers, input validation

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

## 🚀 Quick Start

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/fesco-tracker.git
cd fesco-tracker

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload
Visit: http://127.0.0.1:8000