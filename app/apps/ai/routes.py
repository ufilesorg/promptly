from fastapi import APIRouter, Body, Request
from fastapi_mongo_base.utils.texttools import format_string_keys
from usso import UserData
from usso.fastapi import jwt_access_security

from .schemas import MultipleImagePrompt, Prompt, TranslateRequest, TranslateResponse
from .services import (
    answer_image_with_ai,
    answer_images_with_ai,
    answer_with_ai,
    get_prompt,
    get_prompt_list,
    translate,
)

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/search", response_model=list[Prompt])
async def search_ai_keys(key: str):
    prompts = await get_prompt_list(key)
    return prompts


@router.get("/{key}/fields", response_model=list[str])
async def get_ai_keys(key: str):
    prompt: Prompt = await get_prompt(key)
    format_keys = format_string_keys(prompt.system) | format_string_keys(prompt.user)

    return format_keys


@router.post("/translate", response_model=TranslateResponse)
async def translate_with_ai(request: Request, data: TranslateRequest):
    user: UserData = jwt_access_security(request)
    return await translate(**data.model_dump())


@router.post("/{key:str}", response_model=dict)
async def answer_with_ai_route(request: Request, key: str, data: dict = Body()):
    user: UserData = jwt_access_security(request)
    return await answer_with_ai(key, **data)


@router.post("/image/{key:str}", response_model=dict)
async def answer_image_ai_route(
    request: Request,
    key: str,
    image_url: str = Body(),
    data: dict = Body(default={}),
):
    # logging.info(f"{key} -> {json.dumps(data, ensure_ascii=False)}")
    user: UserData = jwt_access_security(request)
    return await answer_image_with_ai(key, image_url, **data)


@router.post("/images/{key:str}", response_model=dict)
async def answer_images_ai_route(request: Request, data: MultipleImagePrompt):
    # logging.info(f"{key} -> {json.dumps(data, ensure_ascii=False)}")
    user: UserData = jwt_access_security(request)
    return await answer_images_with_ai(data.key, data.image_urls, **data)


@router.post("/search/{key}", response_model=dict)
async def search_with_ai_route(request: Request, key: str, data: dict = Body()):
    user: UserData = jwt_access_security(request)
    return await answer_with_ai(key, engine="perplexity", **data)
