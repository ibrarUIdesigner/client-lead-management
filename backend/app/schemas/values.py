import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def normalize_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        value = tag.strip()
        if not value or value in cleaned:
            continue
        cleaned.append(value[:50])
        if len(cleaned) == 20:
            break
    return cleaned


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (slug or "lead")[:255]
