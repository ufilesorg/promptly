"""FastAPI server configuration."""

import dataclasses
from pathlib import Path

import dotenv
from fastapi_mongo_base.core.config import Settings as BaseSettings

dotenv.load_dotenv()


@dataclasses.dataclass
class Settings(BaseSettings):
    base_dir: Path = Path(__file__).resolve().parent.parent
    base_path: str = "/v1/apps/promptly"
