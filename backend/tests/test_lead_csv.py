from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.errors import AppError
from app.schemas.leads import BulkLeadUpdate, LeadCreate
from app.services.lead_csv import parse_lead_csv


def test_blank_email_and_website_are_stored_as_empty() -> None:
    lead = LeadCreate(business_name="Northwind", email="  ", website_url="")

    assert lead.email is None
    assert lead.website_url is None
    assert lead.lead_status.value == "NEW"


def test_tags_are_trimmed_and_unique() -> None:
    lead = LeadCreate(business_name="Northwind", tags=[" Cafe ", "cafe", "Cafe", ""])

    assert lead.tags == ["Cafe", "cafe"]


def test_lead_create_rejects_a_bad_email() -> None:
    with pytest.raises(ValidationError):
        LeadCreate(business_name="Northwind", email="not-an-email")


def test_lead_create_rejects_a_website_without_a_scheme() -> None:
    with pytest.raises(ValidationError, match="http://"):
        LeadCreate(business_name="Northwind", website_url="northwind.example")


def test_bulk_update_requires_a_change() -> None:
    with pytest.raises(ValidationError):
        BulkLeadUpdate(ids=[uuid4()])


def test_csv_keeps_invalid_rows_beside_valid_rows() -> None:
    content = "\n".join(
        [
            "business_name,industry,city,country,website,email,phone,source,tags,notes",
            "Northwind Cafe,Cafe,Portland,USA,https://northwind.example,"
            "hello@northwind.example,555-0100,maps,cafe|warm,Owner replied",
            ",Cafe,Portland,USA,https://missing.example,hello@missing.example,,,",
            "Broken Site,Cafe,Portland,USA,not-a-url,hello@broken.example,,,",
            "Bad Email,Cafe,Portland,USA,https://bad.example,not-an-email,,,",
        ]
    )

    valid, invalid = parse_lead_csv(content)

    assert len(valid) == 1
    assert valid[0].lead.business_name == "Northwind Cafe"
    assert valid[0].lead.tags == ["cafe", "warm"]
    assert valid[0].lead.source == "maps"
    assert [row.row_number for row in invalid] == [3, 4, 5]
    assert invalid[0].message == "Enter a business name."
    assert "http://" in invalid[1].message
    assert invalid[2].message == "Enter a valid email."


def test_csv_requires_the_business_name_column() -> None:
    try:
        parse_lead_csv("email\nhello@northwind.example\n")
    except AppError as error:
        assert error.code == "CSV_INVALID"
        assert "business_name" in error.message
        return

    raise AssertionError("expected a CSV error")


def test_csv_rejects_unknown_columns() -> None:
    try:
        parse_lead_csv("business_name,owner\nNorthwind,Ada\n")
    except AppError as error:
        assert error.details["columns"] == ["owner"]
        return

    raise AssertionError("expected a CSV error")


def test_csv_rejects_more_than_500_leads() -> None:
    lines = ["business_name", *[f"Business {index}" for index in range(501)]]

    try:
        parse_lead_csv("\n".join(lines))
    except AppError as error:
        assert error.code == "CSV_INVALID"
        assert "500" in error.message
        return

    raise AssertionError("expected a CSV error")
