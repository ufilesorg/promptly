import json
import logging
import os

import langdetect

# import openai
from aiocache import cached
from aiocache.serializers import PickleSerializer
from fastapi_mongo_base._utils.aionetwork import aio_request
from fastapi_mongo_base._utils.basic import retry_execution
from fastapi_mongo_base._utils.texttools import backtick_formatter, format_string_keys
from metisai.async_metis import AsyncMetisBot

from core import exceptions

# openai_client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
metis_client = AsyncMetisBot(
    api_key=os.getenv("METIS_API_KEY"), bot_id=os.getenv("METIS_BOT_ID")
)


async def openai_chat(messages: dict, **kwargs):
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=4095,
        temperature=0.1,
        # response_format={"type": "json_object"},
    )
    resp_text = backtick_formatter(response.choices[0].message.content)
    return resp_text


@retry_execution(3, delay=5)
async def metis_chat(messages: dict, **kwargs):
    try:
        user_id = kwargs.get("user_id")
        session = await metis_client.create_session(user_id)
        prompt = "\n\n".join([message["content"] for message in messages])
        response = await metis_client.send_message(session, prompt[:30_000])
        await metis_client.delete_session(session)
        resp_text = backtick_formatter(response.content)
        return resp_text
    except Exception as e:
        logging.error(json.dumps(messages, ensure_ascii=False))
        logging.error(f"Metis request failed, {e}")
        raise


async def answer_messages(messages: dict, **kwargs):
    # resp_text = await openai_chat(messages, **kwargs)
    resp_text = await metis_chat(messages, **kwargs)
    try:
        return json.loads(resp_text)
    except json.JSONDecodeError:
        return {"answer": resp_text}


@cached(ttl=24 * 3600, serializer=PickleSerializer())
async def answer_with_ai(key, **kwargs):
    try:
        kwargs["lang"] = kwargs.get("lang", "Persian")
        system_prompt: str = await get_message_from_panel(f"pixiee_ai_system_{key}")
        user_prompt: str = await get_message_from_panel(f"pixiee_ai_user_{key}")
        for k in list(
            format_string_keys(system_prompt) | format_string_keys(user_prompt)
        ):
            kwargs[k] = kwargs.get(k, "")

        messages = [
            {
                "role": "system",
                "content": system_prompt.format(**kwargs),
            },
            {
                "role": "user",
                "content": user_prompt.format(**kwargs)[:40000],
            },
        ]

        return await answer_messages(messages, **kwargs)
    except Exception as e:
        logging.error(f"AI request failed for {key}, {e}")
        raise exceptions.BaseHTTPException(
            status_code=500,
            error="Bad Request",
            message="AI request failed. Please try again later.",
        )


async def translate(query: str, to: str = "en"):
    try:
        lang = langdetect.detect(query)
    except:
        lang = "en"

    if lang == to:
        return query

    languages = {
        "en": "English",
        "fa": "Persian",
    }
    if not languages.get(to):
        to = "en"
    prompt = f"Translate the following text to '{to}': \"{query}\""

    logging.warning(f"process_task {query}")

    session = await metis_client.create_session()
    message = await metis_client.send_message(session, prompt)
    await metis_client.delete_session(session)
    resp = message.content
    return resp.strip('"')


@cached(ttl=24 * 3600, serializer=PickleSerializer())
async def get_config_from_panel(key, raise_exception=True) -> list[str]:
    url = f"https://message.bot.inbeet.tech/api/messages?filters[key][$eq]=pixiee_config_{key}"
    headers = {
        "Authorization": "Bearer " + os.getenv("STRAPI_TOKEN"),
    }
    res = await aio_request(url=url, headers=headers)
    data: list[dict] = res.get("data", [])
    if len(data) == 1:
        return data[0]
    if raise_exception:
        raise exceptions.BaseHTTPException(status_code=404, error="key_not_found")


@cached(ttl=24 * 3600, serializer=PickleSerializer())
async def list_config_from_panel(raise_exception=True) -> list[str]:
    url = f"https://message.bot.inbeet.tech/api/messages?filters[key][$startsWith]=pixiee_config_"
    headers = {
        "Authorization": "Bearer " + os.getenv("STRAPI_TOKEN"),
    }
    res = await aio_request(url=url, headers=headers)
    data: list[dict] = res.get("data", [])
    return data


@cached(ttl=24 * 3600, serializer=PickleSerializer())
async def get_message_from_panel(key, raise_exception=True) -> list[str]:
    url = f"https://message.bot.inbeet.tech/api/messages?filters[key][$eq]={key}"
    headers = {
        "Authorization": "Bearer " + os.getenv("STRAPI_TOKEN"),
    }
    res = await aio_request(url=url, headers=headers)
    data: list[dict] = res.get("data", [])
    if len(data) == 1:
        return data[0].get("attributes", {}).get("body", {})
    if raise_exception:
        raise exceptions.BaseHTTPException(
            status_code=404, error="key_not_found", message=f"Key {key} not found"
        )


@cached(ttl=24 * 3600, serializer=PickleSerializer())
async def get_messages_list(keys: list[str], raise_exception=True) -> list[str]:
    if isinstance(keys, str):
        keys = [keys]
    params = {}
    for i, key in enumerate(keys):
        params[f"filters[$and][{i}][key][$contains]"] = key

    url = f"https://message.bot.inbeet.tech/api/messages"
    headers = {
        "Authorization": "Bearer " + os.getenv("STRAPI_TOKEN"),
    }
    res = await aio_request(url=url, headers=headers, params=params)
    data: list[dict] = res.get("data", [])
    return {
        "_".join(d.get("attributes", {}).get("key", {}).split("_")[3:]) for d in data
    }
