import logging

import httpx
import pytest

from server.config import Settings


@pytest.mark.asyncio
async def test_search(client: httpx.AsyncClient, settings: Settings):
    return
    response = await client.post(
        f"{settings.base_path}/ai/search",
        params={"key": "translate"},
    )
    assert response.status_code == 200
    key = response.json()[0]["key"]
    response = await client.get(f"{settings.base_path}/ai/{key}/fields")
    assert response.status_code == 200
    logging.info(response.json())


@pytest.mark.asyncio
async def test_translate(client: httpx.AsyncClient, settings: Settings):
    response = await client.post(
        f"{settings.base_path}/ai/translate",
        json={"text": "Hello, world!", "target_language": "Persian"},
    )
    assert response.status_code == 200
    logging.info(response.json())


@pytest.mark.asyncio
async def test_prompt(client: httpx.AsyncClient, settings: Settings):
    response = await client.post(
        f"{settings.base_path}/ai/raw",
        json={
            "system_prompt": "you are python developer",
            "user_prompt": "give me a hello world python code",
        },
    )
    logging.info(response.json())
    assert response.status_code == 200
