from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_session
from app.main import create_app
from tests.test_health import _settings


def _client(session: Mock) -> TestClient:
    app = create_app(_settings())

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def test_create_lead_rejects_an_empty_body() -> None:
    with _client(Mock()) as client:
        response = client.post("/api/v1/leads", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_missing_lead_returns_a_stable_error() -> None:
    session = Mock()
    session.get.return_value = None
    lead_id = uuid4()

    with _client(session) as client:
        response = client.get(f"/api/v1/leads/{lead_id}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "LEAD_NOT_FOUND"
    assert body["error"]["details"] == {}


def test_list_leads_returns_an_empty_page_without_postgres() -> None:
    session = Mock()
    session.scalar.return_value = 0
    session.scalars.return_value = []

    with _client(session) as client:
        response = client.get("/api/v1/leads")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "limit": 25,
        "total": 0,
        "has_next": False,
    }


def test_csv_preview_reports_invalid_rows_without_writing() -> None:
    content = "\n".join(
        [
            "business_name,email",
            "Northwind Cafe,hello@northwind.example",
            ",missing@northwind.example",
        ]
    )

    with _client(Mock()) as client:
        response = client.post(
            "/api/v1/leads/import",
            params={"dry_run": "true"},
            files={"file": ("leads.csv", content, "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["created"] == 0
    assert len(body["valid_rows"]) == 1
    assert body["invalid_rows"] == [{"row_number": 3, "message": "Enter a business name."}]


def test_delete_lead_deletes_record() -> None:
    session = Mock()
    lead = Mock(id=uuid4())
    session.get.return_value = lead
    with _client(session) as client:
        response = client.delete(f"/api/v1/leads/{lead.id}")
    assert response.status_code == 204
    session.delete.assert_called_once_with(lead)
    session.commit.assert_called_once()


def test_bulk_delete_leads_deletes_records() -> None:
    session = Mock()
    id1, id2 = uuid4(), uuid4()
    lead1, lead2 = Mock(id=id1), Mock(id=id2)
    session.get.side_effect = lambda model, lid: lead1 if lid == id1 else lead2
    with _client(session) as client:
        response = client.post("/api/v1/leads/bulk-delete", json={"ids": [str(id1), str(id2)]})
    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    session.commit.assert_called_once()
