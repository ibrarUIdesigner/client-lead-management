import csv
import re
from dataclasses import dataclass
from io import StringIO

from pydantic import ValidationError

from app.core.errors import AppError
from app.schemas.leads import CsvPreviewRow, InvalidCsvRow, LeadCreate

MAX_CSV_ROWS = 500
ALLOWED_COLUMNS = {
    "business_name",
    "industry",
    "city",
    "country",
    "website",
    "website_url",
    "email",
    "phone",
    "source",
    "tags",
    "notes",
}


@dataclass
class ParsedCsvRow:
    preview: CsvPreviewRow
    lead: LeadCreate


def parse_lead_csv(content: str) -> tuple[list[ParsedCsvRow], list[InvalidCsvRow]]:
    if not content.strip():
        raise AppError(
            code="CSV_INVALID",
            message="The file is empty.",
            status_code=400,
        )

    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        raise AppError(
            code="CSV_INVALID",
            message="Add a header row with a business_name column.",
            status_code=400,
        )

    headers = _headers(reader.fieldnames)
    unknown = [name for name in headers if name not in ALLOWED_COLUMNS]
    if unknown:
        raise AppError(
            code="CSV_INVALID",
            message="The file has columns this import does not use.",
            status_code=400,
            details={"columns": unknown},
        )
    if "business_name" not in headers:
        raise AppError(
            code="CSV_INVALID",
            message="Add a business_name column.",
            status_code=400,
        )

    valid: list[ParsedCsvRow] = []
    invalid: list[InvalidCsvRow] = []
    data_rows = 0
    for row_number, raw in enumerate(reader, start=2):
        record = _record(raw)
        if not any(record.values()):
            continue
        data_rows += 1
        if data_rows > MAX_CSV_ROWS:
            raise AppError(
                code="CSV_INVALID",
                message=f"Import up to {MAX_CSV_ROWS} leads at a time.",
                status_code=400,
            )
        parsed = _parse_row(row_number, record)
        if isinstance(parsed, InvalidCsvRow):
            invalid.append(parsed)
        else:
            valid.append(parsed)
    return valid, invalid


def _headers(fieldnames: list[str | None]) -> list[str]:
    headers: list[str] = []
    for field in fieldnames:
        if field is None or not field.strip():
            raise AppError(
                code="CSV_INVALID",
                message="Each column needs a name in the header row.",
                status_code=400,
            )
        name = field.strip().lower()
        if name in headers:
            raise AppError(
                code="CSV_INVALID",
                message=f"The column {name} is repeated.",
                status_code=400,
            )
        headers.append(name)
    return headers


def _record(raw: dict[str | None, str | None]) -> dict[str, str]:
    record: dict[str, str] = {}
    for key, value in raw.items():
        if key is None:
            continue
        record[key.strip().lower()] = (value or "").strip()
    return record


def _parse_row(row_number: int, record: dict[str, str]) -> ParsedCsvRow | InvalidCsvRow:
    business_name = record.get("business_name", "")
    if not business_name:
        return InvalidCsvRow(row_number=row_number, message="Enter a business name.")

    website = record.get("website_url") or record.get("website") or ""
    other_website = record.get("website", "")
    explicit_website = record.get("website_url", "")
    if explicit_website and other_website and explicit_website != other_website:
        return InvalidCsvRow(
            row_number=row_number,
            message="Use one website address for the row.",
        )

    source = record.get("source") or "csv"
    try:
        lead = LeadCreate(
            business_name=business_name,
            industry=record.get("industry") or None,
            city=record.get("city") or None,
            country=record.get("country") or None,
            website_url=website or None,
            email=record.get("email") or None,
            phone=record.get("phone") or None,
            source=source,
            tags=_split_tags(record.get("tags", "")),
            notes=record.get("notes") or None,
        )
    except ValidationError as exc:
        return InvalidCsvRow(row_number=row_number, message=_validation_message(exc))

    preview = CsvPreviewRow(
        row_number=row_number,
        business_name=lead.business_name,
        industry=lead.industry,
        city=lead.city,
        country=lead.country,
        website_url=lead.website_url,
        email=lead.email,
        phone=lead.phone,
        source=lead.source,
        tags=lead.tags,
        notes=lead.notes,
    )
    return ParsedCsvRow(preview=preview, lead=lead)


def _split_tags(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[,|]", value) if part.strip()]


def _validation_message(exc: ValidationError) -> str:
    message = str(exc.errors()[0].get("msg", "This row could not be imported."))
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message
