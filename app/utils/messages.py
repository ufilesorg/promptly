from fastapi_mongo_base.core import exceptions
from fastapi_mongo_base.utils import aionetwork
from server.config import Settings


# @cached(ttl=24 * 3600)
async def get_prompt_list(keys: list[str], raise_exception=True) -> dict:
    if isinstance(keys, str):
        keys = [keys]
    params = {}
    for i, key in enumerate(keys):
        params[f"filters[$and][{i}][key][$contains]"] = key

    headers = {"Authorization": f"Bearer {Settings.STRAPI_TOKEN}"}
    response = await aionetwork.aio_request(
        url=Settings.STRAPI_URL,
        headers=headers,
        params=params,
        raise_exception=raise_exception,
    )
    return response


# @cached(ttl=24 * 3600)
async def get_prompt(key, raise_exception=True) -> dict:
    url = f"{Settings.STRAPI_URL}?filters[key][$eq]={key}"
    headers = {"Authorization": f"Bearer {Settings.STRAPI_TOKEN}"}
    res = await aionetwork.aio_request(
        url=url, headers=headers, raise_exception=raise_exception
    )
    data: list[dict] = res.get("data", [])
    if len(data) == 1:
        return data[0].get("attributes", {})
    if raise_exception:
        raise exceptions.BaseHTTPException(
            status_code=404, error="key_not_found", message=f"Key {key} not found"
        )
