from typing import Literal

from pydantic import BaseModel


class ProviderRead(BaseModel):
    id: Literal["gemini", "groq"]
    configured: bool
    active: bool
    model: str
    display_name: str | None = None
    listed: bool | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    prompt_usd_per_million: float | None = None
    completion_usd_per_million: float | None = None
    credits: str


class ProvidersRead(BaseModel):
    providers: list[ProviderRead]
