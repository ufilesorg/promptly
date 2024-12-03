from core.enums import Language
from pydantic import BaseModel, field_validator


class TranslateRequest(BaseModel):
    text: str
    target_language: Language = Language.English


class TranslateResponse(BaseModel):
    translated_text: str


class Prompt(BaseModel):
    key: str
    system: str | None
    user: str
    image_url: str | None = None

    def hash(self):
        return hash(self.key)

    @field_validator("system")
    def check_system(cls, value):
        return value or ""
