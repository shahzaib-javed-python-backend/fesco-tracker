import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.main import STATIC_DIR, app, root, validate_inputs
from app.schemas import BillRequest
from app.services.alert_engine import get_units_stats


def test_validate_inputs_accepts_supported_disco():
    assert validate_inputs("12345678901234", "HESCO") == (
        "12345678901234",
        "hesco",
    )


def test_validate_inputs_rejects_non_14_digit_reference():
    with pytest.raises(HTTPException) as error:
        validate_inputs("1234567890", "fesco")

    assert error.value.status_code == 400


def test_bill_request_matches_api_contract():
    request = BillRequest(reference_no="12345678901234", disco="hesco")

    assert request.disco == "hesco"


def test_root_uses_project_static_directory():
    assert root().path == STATIC_DIR / "index.html"


def test_empty_history_stats_are_safe():
    assert get_units_stats([]) == {
        "average_units": 0.0,
        "max_units": 0,
        "min_units": 0,
        "total_months": 0,
        "total_units": 0,
    }


def test_public_health_and_seo_endpoints():
    client = TestClient(app)

    health = client.get("/health")
    robots = client.get("/robots.txt")
    sitemap = client.get("/sitemap.xml")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert robots.status_code == 200
    assert "Sitemap:" in robots.text
    assert sitemap.status_code == 200
    assert "urlset" in sitemap.text

    for path in ("/privacy", "/terms", "/contact"):
        page = client.get(path)
        assert page.status_code == 200
        assert "Back to FESCO Bill Tracker" in page.text


def test_history_can_be_exported_as_csv(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    client = TestClient(app)
    reference_no = "12345678901237"
    assert client.get(f"/bill/{reference_no}?disco=fesco").status_code == 200

    export = client.get(f"/export-history/{reference_no}?disco=fesco")

    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    assert export.text.startswith("month,units,bill,payment")


def test_security_headers_and_private_history_default():
    client = TestClient(app)
    response = client.get("/health")

    assert response.headers["content-security-policy"].startswith("default-src")
    assert "strict-transport-security" not in response.headers
    assert client.get("/db/search-history").status_code == 403
    assert client.get("/db/popular-searches").status_code == 403
    assert client.get("/db/cache-stats").status_code == 403


def test_demo_bill_supports_analytics_and_ml(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    client = TestClient(app)
    reference_no = "12345678901236"

    analytics = client.get(f"/analytics/{reference_no}?disco=fesco")
    ml_prediction = client.get(f"/ml-predict/{reference_no}?disco=fesco")

    assert analytics.status_code == 200
    assert analytics.json()["summary"]["total_months"] >= 3
    assert ml_prediction.status_code == 200
    assert ml_prediction.json()["training_rows"] >= 6