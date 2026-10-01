import base64
from pathlib import Path

from app.core.errors import AppError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_SCREENSHOT_BYTES = 5_000_000


def save_screenshot(storage_dir: Path, relative: str, data: bytes) -> str:
    if not _valid_png(data):
        raise AppError(
            code="SCREENSHOT_INVALID",
            message="The screenshot could not be saved.",
            status_code=500,
        )
    target = resolve_storage_path(storage_dir, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return relative


def encode_png(data: bytes) -> str | None:
    if not _valid_png(data):
        return None
    return base64.b64encode(data).decode("ascii")


def decode_png(value: object) -> bytes | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        data = base64.b64decode(value, validate=True)
    except ValueError:
        return None
    if not _valid_png(data):
        return None
    return data


def read_screenshot(
    storage_dir: Path,
    relative: str | None,
    raw_analysis: object,
    variant: str,
) -> bytes | None:
    if relative:
        try:
            path = resolve_storage_path(storage_dir, relative)
        except AppError:
            path = None
        if path is not None and path.is_file():
            data = path.read_bytes()
            if _valid_png(data):
                return data
    if isinstance(raw_analysis, dict):
        return decode_png(raw_analysis.get(f"{variant}_png"))
    return None


def resolve_storage_path(storage_dir: Path, relative: str) -> Path:
    parts = Path(relative).parts
    if (
        not relative
        or relative.startswith(("/", "\\"))
        or ".." in parts
        or Path(relative).is_absolute()
    ):
        raise AppError(
            code="NOT_FOUND",
            message="That screenshot could not be found.",
            status_code=404,
        )
    root = storage_dir.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise AppError(
            code="NOT_FOUND",
            message="That screenshot could not be found.",
            status_code=404,
        )
    return target


def _valid_png(data: bytes) -> bool:
    return bool(data) and len(data) <= MAX_SCREENSHOT_BYTES and data.startswith(PNG_SIGNATURE)


def screenshot_key(lead_id: str, audit_id: str, variant: str) -> str:
    if variant not in {"desktop", "mobile"}:
        raise AppError(
            code="NOT_FOUND",
            message="That screenshot could not be found.",
            status_code=404,
        )
    return f"leads/{lead_id}/audits/{audit_id}/{variant}.png"
