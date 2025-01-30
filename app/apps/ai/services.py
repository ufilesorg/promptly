import json
import logging
import os

import langdetect
from aiocache import cached
from fastapi_mongo_base.core import enums
from fastapi_mongo_base.utils import basic, imagetools, texttools
from utils import messages

from .engines import AIEngine
from .schemas import Prompt


@cached(ttl=24 * 3600)
async def get_prompt(key, raise_exception=True, **kwargs) -> tuple[str, str]:
    prompt_dict = await messages.get_prompt(key, raise_exception=raise_exception)
    prompt = Prompt(**prompt_dict)

    kwargs["lang"] = kwargs.get("lang", "Persian")
    for k in list(
        texttools.format_string_keys(prompt.system)
        | texttools.format_string_keys(prompt.user)
    ):
        kwargs[k] = kwargs.get(k, "")

    system = prompt.system.format(**kwargs)
    user = prompt.user.format(**kwargs)

    return system, user


async def get_prompt_list(keys: list[str], raise_exception=True) -> list[Prompt]:
    res: dict = await messages.get_prompt_list(keys, raise_exception=raise_exception)
    data: list[Prompt] = res.get("data", [])
    return [Prompt(**d.get("attributes", {})) for d in data]


@basic.retry_execution(3, delay=5)
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
    resp_text = texttools.backtick_formatter(response.choices[0].message.content)
    coins = engine.get_price(
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
        image_count=kwargs.get("image_count", 0),
    )
    return resp_text, coins


@basic.retry_execution(3, delay=5)
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
    resp_text = texttools.backtick_formatter(response.content)
    return resp_text


async def answer_messages(messages: dict, engine="metis", **kwargs):
    # resp_text = await metis_chat(messages, **kwargs)
    try:
        resp_text, coins = await openai_chat(messages, engine, **kwargs)
        return json.loads(
            resp_text.replace("True", "true")
            .replace("False", "false")
            .replace("None", "null")
        ) | {"coins": coins}
    except json.JSONDecodeError:
        return {"answer": resp_text}


async def answer_image(system: str, user: str, image_url: str, low_res=True, **kwargs):
    encoded_image = await imagetools.download_image_base64(
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
        resp_text, coins = await openai_chat(
            messages, engine="metisvision", image_count=1, **kwargs
        )
        return json.loads(resp_text) | {"coins": coins}
    except json.JSONDecodeError:
        return {"answer": resp_text}
    except Exception as e:
        # logging.error(json.dumps(messages, ensure_ascii=False))
        logging.error(f"Metis request failed, {e}")
        raise


@cached(ttl=24 * 3600)
async def answer_with_ai(key, engine="metis", **kwargs) -> dict:
    kwargs["lang"] = kwargs.get("lang", "Persian")
    system, user = await get_prompt(key, **kwargs)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user[:40000]},
    ]
    return await answer_messages(messages, engine, **kwargs)


@cached(ttl=24 * 3600)
async def answer_image_with_ai(key, image_url, **kwargs) -> dict:
    kwargs["lang"] = kwargs.get("lang", "Persian")
    system, user = await get_prompt(key, **kwargs)
    return await answer_image(system, user, image_url, **kwargs)


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


async def answer_gemini(messages: list[dict], **kwargs):
    import google.generativeai as genai
    from google.api_core.client_options import ClientOptions

    model_name = "gemini-1.5-flash"
    genai.configure(
        api_key=os.getenv("METIS_API_KEY"),
        transport="rest",
        client_options=ClientOptions(api_endpoint="https://api.metisai.ir"),
    )
    # genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(messages)

    engine = AIEngine.get_by_name(model_name)
    coins = engine.get_price(
        response.usage_metadata.prompt_token_count,
        response.usage_metadata.candidates_token_count,
        image_count=kwargs.get("image_count", 0),
    )
    return texttools.backtick_formatter(response.text) | {"coins": coins}


async def answer_vision(system: str, user: str, image_urls: list[str], **kwargs):
    content = [f"{system}\n\n{user}"]
    for image_url in image_urls:
        encoded_image = await imagetools.download_image_base64(
            image_url,
            max_size_kb=100,
            format="JPEG",
            include_base64_header=False,
            timeout=30,
        )
        content.append({"mime_type": "image/jpeg", "data": encoded_image})

    try:
        resp_text = await answer_gemini(content, image_count=len(image_urls), **kwargs)
        return json.loads(resp_text)
    except json.JSONDecodeError:
        return {"answer": resp_text}
    except Exception as e:
        # logging.error(json.dumps(messages, ensure_ascii=False))
        logging.error(f"Metis request failed, {e}")
        raise


@cached(ttl=24 * 3600)
async def answer_vision_with_ai(key, image_urls, **kwargs) -> dict:
    kwargs["lang"] = kwargs.get("lang", "Persian")
    system, user = await get_prompt(key, **kwargs)
    return await answer_vision(system, user, image_urls, **kwargs)
