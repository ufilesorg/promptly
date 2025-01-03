import base64
import json
import logging
import os
from io import BytesIO

import langdetect
from aiocache import cached
from aiocache.serializers import PickleSerializer
from fastapi_mongo_base.core import enums, exceptions
from fastapi_mongo_base.utils.aionetwork import aio_request, aio_request_binary
from fastapi_mongo_base.utils.basic import retry_execution, try_except_wrapper
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
        return json.loads(resp_text)
    except json.JSONDecodeError:
        return {"answer": resp_text}


async def get_image(url: str):
    from PIL import Image

    from utils.imagetools import resize_image

    # add base64 check
    if url.startswith("data:image"):
        encoded = url.split(",")[1]
        buffered = BytesIO(base64.b64decode(encoded))
        image = Image.open(buffered)
    else:
        buffered = await aio_request_binary(url=url)
        image = Image.open(buffered)
        if image.mode == "RGBA":
            image = image.convert("RGB")
        image.save(buffered, format="JPEG")
        encoded = base64.b64encode(buffered.getvalue()).decode()

    while len(encoded) > 250 * 1024:
        image = resize_image(image, image.width * 4 // 5)
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        encoded = base64.b64encode(buffered.getvalue()).decode()

    return encoded


async def answer_image(system: str, user: str, image_url: str, low_res=True, **kwargs):
    encoded_image = await get_image(image_url)
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
                        {"url": f"data:image/jpeg;base64,{encoded_image}"}
                        | ({"detail": "low"} if low_res else {})
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
async def answer_image_with_ai(key, image_url, **kwargs) -> dict:
    try:
        kwargs["lang"] = kwargs.get("lang", "Persian")
        prompt: Prompt = await get_prompt(key)
        for k in list(
            format_string_keys(prompt.system) | format_string_keys(prompt.user)
        ):
            kwargs[k] = kwargs.get(k, "")

        # image = await aio_request_binary(url=image_url)

        return await answer_image(
            prompt.system.format(**kwargs),
            prompt.user.format(**kwargs),
            image_url,
            **kwargs,
        )
    except Exception as e:
        import traceback

        traceback_str = "".join(traceback.format_tb(e.__traceback__))
        logging.error(f"AI request failed for {key},\n{traceback_str}\n{e}")
        raise exceptions.BaseHTTPException(
            status_code=500,
            error="Bad Request",
            message="AI request failed. Please try again later.",
        )


@cached(ttl=24 * 3600, serializer=PickleSerializer())
async def answer_with_ai(key, engine="metis", **kwargs) -> dict:
    try:
        kwargs["lang"] = kwargs.get("lang", "Persian")
        prompt: Prompt = await get_prompt(key)
        for k in list(
            format_string_keys(prompt.system) | format_string_keys(prompt.user)
        ):
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
    except Exception as e:
        import traceback

        traceback_str = "".join(traceback.format_tb(e.__traceback__))
        logging.error(f"AI request failed for {key},\n{traceback_str}\n{e}")
        raise exceptions.BaseHTTPException(
            status_code=500,
            error="Bad Request",
            message="AI request failed. Please try again later.",
        )


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
