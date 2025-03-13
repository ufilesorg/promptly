import asyncio
import json
import logging
import os
import time

import langdetect
from aiocache import cached
from fastapi_mongo_base.core import enums
from fastapi_mongo_base.utils import basic, imagetools, texttools
from utils import messages

from .engines import AIEngine
from .schemas import Prompt


@cached(ttl=10 * 60)
async def get_prompt(key, raise_exception=True, **kwargs) -> tuple[str, str, str]:
    prompt_dict: dict = await messages.get_prompt(key, raise_exception=raise_exception)

    kwargs["lang"] = kwargs.get("lang", "Persian")
    for k in list(
        texttools.format_string_keys(prompt_dict.get("system") or "")
        | texttools.format_string_keys(prompt_dict.get("user") or "")
    ):
        kwargs[k] = kwargs.get(k, "")

    system: str = (prompt_dict.get("system") or "").format(**kwargs)
    user: str = (prompt_dict.get("user") or "").format(**kwargs)[:40000]
    model_name: str = prompt_dict.get("model_name", "gpt-4o")

    return system, user, model_name


async def get_prompt_list(keys: list[str], raise_exception=True) -> list[Prompt]:
    res: dict = await messages.get_prompt_list(keys, raise_exception=raise_exception)
    data: list[Prompt] = res.get("data", [])
    return [Prompt(**d.get("attributes", {})) for d in data]


def messages_gemini(system, user, encoded_images=[], **kwargs):
    res = [system, user] if system else [user]
    for encoded_image in encoded_images:
        res.append({"mime_type": "image/jpeg", "data": encoded_image})
    return res


def messages_openai(system, user, encoded_images, low_res=True, **kwargs):
    if not encoded_images:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user[:40000]},
        ]

    low_res_dict = {"detail": "low"} if low_res else {}
    images = [
        {"type": "image_url", "image_url": {"url": image, **low_res_dict}}
        for image in encoded_images
    ]
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [{"type": "text", "text": user[:40000]}, *images],
        },
    ]


async def make_messages(
    key: str, *, image_urls: list[str] = [], low_res: bool = True, **kwargs
) -> tuple[list[dict], str]:
    system, user, model_name = await get_prompt(key, **kwargs)

    encoded_images = await asyncio.gather(
        *[
            imagetools.download_image_base64(
                image_url,
                max_size_kb=100,
                format="JPEG",
                include_base64_header=False,
                timeout=30,
            )
            for image_url in image_urls
        ]
    )
    if model_name.startswith("gemini"):
        messages = messages_gemini(system, user, encoded_images, **kwargs)
        return messages, model_name

    messages = messages_openai(system, user, encoded_images, low_res=low_res, **kwargs)
    return messages, model_name


@basic.retry_execution(3, delay=5)
async def answer_openai(
    messages: list[dict], image_count: int, model_name: str, **kwargs
):
    import openai

    engine = AIEngine.get_by_name(model_name)

    # api_key=os.environ.get("OPENAI_API_KEY")
    openai_client = openai.AsyncOpenAI(**engine.get_dict())
    response = await openai_client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=kwargs.get("max_tokens"),
        temperature=kwargs.get("temperature", 0.1),
    )
    coins = engine.get_price(
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
        image_count=image_count,
    )
    try:
        resp = texttools.json_extractor(response.choices[0].message.content)
        return resp | {"coins": coins, "model": model_name}
    except json.JSONDecodeError:
        return {
            "answer": texttools.backtick_formatter(response.choices[0].message.content),
            "coins": coins,
            "model": model_name,
        }
    except Exception as e:
        logging.error(f"OpenAI request failed, {type(e)} {e}")
        raise


@basic.retry_execution(3, delay=5)
async def answer_gemini(
    messages: list[dict], image_count: int, model_name="gemini-1.5-flash", **kwargs
):
    import google.generativeai as genai
    from google.api_core.client_options import ClientOptions

    engine = AIEngine.get_by_name(model_name)
    genai.configure(
        api_key=os.getenv("METIS_API_KEY"),
        transport="rest",
        client_options=ClientOptions(api_endpoint="https://api.metisai.ir"),
    )
    # genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(messages)

        coins = engine.get_price(
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
            image_count=image_count,
        )
        resp = texttools.json_extractor(response.text)
        return resp | {"coins": coins, "model": model_name}
    except json.JSONDecodeError:
        return {
            "answer": texttools.backtick_formatter(response.text),
            "coins": coins,
            "model": model_name,
        }
    except Exception as e:
        import traceback

        traceback_str = "".join(traceback.format_tb(e.__traceback__))
        logging.error(f"Gemini request failed, {traceback_str}\n{type(e)} {e}")
        raise


@basic.retry_execution(3, delay=5)
async def answer_gemini_new(
    messages: list[dict], image_count: int, model_name="gemini-2.0-flash", **kwargs
):
    from google import genai
    from google.genai import types

    http_options = types.HttpOptions(base_url="https://api.metisai.ir")

    generation_config = {
        "temperature": kwargs.get("temperature", 0.1),
        "top_p": kwargs.get("top_p", 0.95),
        "top_k": kwargs.get("top_k", 64),
        "max_output_tokens": kwargs.get("max_output_tokens", 8192),
        "response_mime_type": "text/plain",
    }
    try:
        engine = AIEngine.get_by_name(model_name)
        client = genai.Client(
            api_key=os.getenv("METIS_API_KEY"), http_options=http_options
        )
        response = client.models.generate_content(model=model_name, contents=messages)
        coins = engine.get_price(
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
            image_count=image_count,
        )
        resp = texttools.json_extractor(response.text)
        return resp | {"coins": coins, "model": model_name}
    except json.JSONDecodeError:
        return {
            "answer": texttools.backtick_formatter(response.text),
            "coins": coins,
            "model": model_name,
        }
    except Exception as e:
        import traceback

        traceback_str = "".join(traceback.format_tb(e.__traceback__))
        logging.error(f"Gemini request failed, {traceback_str}\n{type(e)} {e}")
        raise


# @cached(ttl=24 * 3600)
async def answer_with_ai(key, *, image_urls: list[str] = [], **kwargs) -> dict:
    kwargs["lang"] = kwargs.get("lang", "Persian")

    # logging.info(f"{model_name=} {messages=}")

    try:
        messages, model_name = await make_messages(key, image_urls=image_urls, **kwargs)
        start_time = time.time()
        if model_name.startswith("gemini"):
            result = await answer_gemini(
                messages, len(image_urls), model_name, **kwargs
            )
        else:
            result = await answer_openai(
                messages, len(image_urls), model_name, **kwargs
            )
        logging.info(
            f"Time taken: {model_name=} {key=} {time.time() - start_time:0.2f} seconds"
        )
        return result

    except Exception as e:
        image_urls_str = "\n".join(image_urls)
        logging.error(f"AI request failed, {type(e)} {e} {key=}\n{image_urls_str}")
        raise


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
