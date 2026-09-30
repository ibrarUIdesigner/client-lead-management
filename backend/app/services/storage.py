from pathlib import Path

from app.core.errors import AppError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_SCREENSHOT_BYTES = 5_000_000


def save_screenshot(storage_dir: Path, relative: str, data: bytes) -> str:
    if len(data) > MAX_SCREENSHOT_BYTES or not data.startswith(PNG_SIGNATURE):
        raise AppError(
            code="SCREENSHOT_INVALID",
            message="The screenshot could not be saved.",
            status_code=500,
        )
    target = resolve_storage_path(storage_dir, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return relative


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


def screenshot_key(lead_id: str, audit_id: str, variant: str) -> str:
    if variant not in {"desktop", "mobile"}:
        raise AppError(
            code="NOT_FOUND",
            message="That screenshot could not be found.",
            status_code=404,
        )
    return f"leads/{lead_id}/audits/{audit_id}/{variant}.png"
