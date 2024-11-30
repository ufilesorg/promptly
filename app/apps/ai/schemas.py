from pydantic import BaseModel
from core.enums import Language


class TranslateRequest(BaseModel):
    text: str
    source_language: Language = Language.Persian
    target_language: Language = Language.English
