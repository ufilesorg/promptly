import json
import logging
import os

import langdetect
from aiocache import cached
from aiocache.serializers import PickleSerializer
from fastapi_mongo_base.core import enums, exceptions
from fastapi_mongo_base.utils import basic
from fastapi_mongo_base.utils.aionetwork import aio_request
from fastapi_mongo_base.utils.basic import retry_execution, try_except_wrapper
from fastapi_mongo_base.utils.imagetools import download_image_base64
from fastapi_mongo_base.utils.texttools import backtick_formatter, format_string_keys

from .engines import AIEngine
from .schemas import Prompt


@retry_execution(3, delay=5)
async def openai_chat(messages: list[dict], engine="metis", **kwargs):
    import openai

    engine = AIEngine.get_by_name(engine)

    # api_key=os.environ.get("OPENAI_API_KEY")
    openai_client = openai.AsyncOpenAI(**engine.get_dict())
    response = await openai_client.chat.completions.create(
        model=engine.model,
        messages=messages,
        max_tokens=kwargs.get("max_tokens"),
        temperature=kwargs.get("temperature", 0.1),
    )
    resp_text = backtick_formatter(response.choices[0].message.content)
    return resp_text


@try_except_wrapper
@retry_execution(3, delay=5)
async def metis_chat(messages: list[dict], **kwargs):
    from metisai.async_metis import AsyncMetisBot

    metis_client = AsyncMetisBot(
        api_key=os.getenv("METIS_API_KEY"), bot_id=os.getenv("METIS_BOT_ID")
    )
    user_id = kwargs.get("user_id")
    session = await metis_client.create_session(user_id)
    prompt = "\n\n".join([message["content"] for message in messages])
    response = await metis_client.send_message(session, prompt[:30_000])
    await metis_client.delete_session(session)
    resp_text = backtick_formatter(response.content)
    return resp_text


async def answer_messages(messages: dict, engine="metis", **kwargs):
    resp_text = await openai_chat(messages, engine, **kwargs)
    # resp_text = await metis_chat(messages, **kwargs)
    try:
        return json.loads(
            resp_text.replace("True", "true")
            .replace("False", "false")
            .replace("None", "null")
        )
    except json.JSONDecodeError:
        return {"answer": resp_text}


async def answer_image(system: str, user: str, image_url: str, low_res=True, **kwargs):
    encoded_image = await download_image_base64(
        image_url, max_width=768, max_size_kb=240
    )
    messages = [
        {
            "role": "system",
            "content": system,
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user},
                {
                    "type": "image_url",
                    "image_url": (
                        {"url": encoded_image} | ({"detail": "low"} if low_res else {})
                    ),
                },
            ],
        },
    ]
    try:
        resp_text = await openai_chat(messages, engine="metisvision", **kwargs)
        return json.loads(resp_text)
    except json.JSONDecodeError:
        return {"answer": resp_text}
    except Exception as e:
        # logging.error(json.dumps(messages, ensure_ascii=False))
        logging.error(f"Metis request failed, {e}")
        raise

    from metisai.async_metis import AsyncMetisBot

    metis_client = AsyncMetisBot(
        api_key=os.getenv("METIS_API_KEY"), bot_id=os.getenv("METIS_BOT_ID")
    )

    try:
        session = await metis_client.create_session()
        prompt = "\n\n".join([system, user])
        response = await metis_client.send_message_with_attachment(
            session, prompt[:30_000], image_url
        )
        await metis_client.delete_session(session)
        resp_text = backtick_formatter(response.content)
        return json.loads(resp_text)
    except json.JSONDecodeError:
        return {"answer": resp_text}
    except Exception as e:
        # logging.error(json.dumps(messages, ensure_ascii=False))
        logging.error(f"Metis request failed, {e}")
        raise


@cached(ttl=24 * 3600, serializer=PickleSerializer())
@basic.try_except_wrapper
async def answer_image_with_ai(key, image_url, **kwargs) -> dict:
    kwargs["lang"] = kwargs.get("lang", "Persian")
    prompt: Prompt = await get_prompt(key)
    for k in list(format_string_keys(prompt.system) | format_string_keys(prompt.user)):
        kwargs[k] = kwargs.get(k, "")

    # image = await aio_request_binary(url=image_url)

    return await answer_image(
        prompt.system.format(**kwargs),
        prompt.user.format(**kwargs),
        image_url,
        **kwargs,
    )


@cached(ttl=24 * 3600, serializer=PickleSerializer())
@basic.try_except_wrapper
async def answer_with_ai(key, engine="metis", **kwargs) -> dict:
    kwargs["lang"] = kwargs.get("lang", "Persian")
    prompt: Prompt = await get_prompt(key)
    for k in list(format_string_keys(prompt.system) | format_string_keys(prompt.user)):
        kwargs[k] = kwargs.get(k, "")

    messages = [
        {
            "role": "system",
            "content": prompt.system.format(**kwargs),
        },
        {
            "role": "user",
            "content": prompt.user.format(**kwargs)[:40000],
        },
    ]
    return await answer_messages(messages, engine, **kwargs)


async def translate(
    text: str, target_language: enums.Language = enums.Language.English, **kwargs
):
    try:
        lang = langdetect.detect(text)
    except:
        lang = "en"

    if lang == target_language:
        return text

    if not enums.Language.has_value(target_language):
        target_language = enums.Language.English

    return await answer_with_ai(
        "translate", text=text, target_language=target_language, **kwargs
    )


@cached(ttl=24 * 3600, serializer=PickleSerializer())
async def get_prompt(key, raise_exception=True) -> Prompt:
    url = f"https://message.bot.inbeet.tech/api/prompts?filters[key][$eq]={key}"
    headers = {
        "Authorization": "Bearer " + os.getenv("STRAPI_TOKEN"),
    }
    res = await aio_request(url=url, headers=headers)
    data: list[dict] = res.get("data", [])
    if len(data) == 1:
        return Prompt(**data[0].get("attributes", {}))
    if raise_exception:
        raise exceptions.BaseHTTPException(
            status_code=404, error="key_not_found", message=f"Key {key} not found"
        )


@cached(ttl=24 * 3600, serializer=PickleSerializer())
async def get_prompt_list(keys: list[str], raise_exception=True) -> list[Prompt]:
    if isinstance(keys, str):
        keys = [keys]
    params = {}
    for i, key in enumerate(keys):
        params[f"filters[$and][{i}][key][$contains]"] = key

    url = f"https://message.bot.inbeet.tech/api/prompts"
    headers = {
        "Authorization": "Bearer " + os.getenv("STRAPI_TOKEN"),
    }
    res = await aio_request(url=url, headers=headers, params=params)
    data: list[Prompt] = res.get("data", [])
    logging.info(data)
    return [Prompt(**d.get("attributes", {})) for d in data]


async def answer_images(
    system: str, user: str, image_urls: str, low_res=True, **kwargs
):
    content = [{"type": "text", "text": user}]
    for image_url in image_urls:
        encoded_image = await download_image_base64(image_url, max_size_kb=100)
        content.append(
            {
                "type": "image_url",
                "image_url": (
                    {"url": encoded_image} | ({"detail": "low"} if low_res else {})
                ),
            }
        )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]
    try:
        resp_text = await openai_chat(messages, engine="metisvision", **kwargs)
        return json.loads(resp_text)
    except json.JSONDecodeError:
        return {"answer": resp_text}
    except Exception as e:
        # logging.error(json.dumps(messages, ensure_ascii=False))
        logging.error(f"Metis request failed, {e}")
        raise


@basic.try_except_wrapper
@cached(ttl=24 * 3600, serializer=PickleSerializer())
async def answer_images_with_ai(key, image_urls, **kwargs) -> dict:
    kwargs["lang"] = kwargs.get("lang", "Persian")
    prompt: Prompt = await get_prompt(key)
    for k in list(format_string_keys(prompt.system) | format_string_keys(prompt.user)):
        kwargs[k] = kwargs.get(k, "")

    return await answer_images(
        prompt.system.format(**kwargs),
        prompt.user.format(**kwargs),
        image_urls,
        **kwargs,
    )
