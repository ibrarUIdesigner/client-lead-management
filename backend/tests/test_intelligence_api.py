from unittest.mock import MagicMock, Mock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_session
from app.main import create_app
from app.models.lead import Lead
from tests.test_health import _settings


def _client(session: Mock) -> TestClient:
    app = create_app(_settings())

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def test_get_sales_playbooks_api():
    with _client(Mock()) as client:
        response = client.get("/api/v1/sales/playbooks")
    assert response.status_code == 200
    playbooks = response.json()["playbooks"]
    assert "EmailFrameworks.md" in playbooks

    with _client(Mock()) as client:
        response = client.get("/api/v1/sales/playbooks/EmailFrameworks.md")
    assert response.status_code == 200
    assert "Mockup-Led" in response.json()["content"]


def test_lead_intelligence_not_found():
    session = Mock()
    session.get.return_value = None
    lead_id = uuid4()

    with _client(session) as client:
        response = client.get(f"/api/v1/leads/{lead_id}/intelligence")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LEAD_NOT_FOUND"


def test_lead_intelligence_success():
    session = Mock()
    lead = Lead(
        id=uuid4(),
        business_name="Apex Roofing Co",
        industry="Roofing",
        website_url="https://apexroofs.test",
        email="contact@apexroofs.test",
        city="Austin",
        country="USA",
        lead_status="NEW",
    )
    session.get.return_value = lead
    # Mock scalars to return empty collections for related queries
    session.scalars.return_value.first.return_value = None
    session.scalars.return_value = []
    session.scalar.return_value = None

    with _client(session) as client:
        response = client.get(f"/api/v1/leads/{lead.id}/intelligence")

    assert response.status_code == 200
    data = response.json()
    assert data["business_name"] == "Apex Roofing Co"
    assert "opportunity_score" in data
    assert data["opportunity_score"]["total_score"] >= 0
    assert "signals" in data
    assert "strategy" in data
    assert "next_action" in data
