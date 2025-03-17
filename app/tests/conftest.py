import os
from typing import AsyncGenerator

import debugpy
import httpx
import pytest
import pytest_asyncio

from server.config import Settings
from server.server import app as fastapi_app


@pytest.fixture(scope="session", autouse=True)
def setup_debugpy():
    if os.getenv("DEBUGPY", "False").lower() in ("true", "1", "yes"):
        debugpy.listen(("0.0.0.0", 3020))
        debugpy.wait_for_client()


@pytest.fixture(scope="session", autouse=True)
def settings():
    settings = Settings()
    settings.config_logger()
    return settings


@pytest_asyncio.fixture(scope="session")
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Fixture to provide an AsyncClient for FastAPI app."""

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fastapi_app),
        base_url="http://test.pixiee.io",
        headers={"X-API-KEY": os.getenv("UFILES_API_KEY")},
    ) as ac:
        yield ac
