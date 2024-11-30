import json
import logging

from fastapi import APIRouter, Body, Depends, Request
from fastapi_mongo_base._utils.texttools import format_string_keys
from usso import UserData
from usso.fastapi import jwt_access_security

from .services import (
    answer_with_ai,
    get_message_from_panel,
    get_messages_list,
    translate,
)
from .schemas import TranslateRequest

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/search")
async def search_ai_keys(key: str):
    return await get_messages_list(f"{key}")


@router.get("/{key}/fields")
async def get_ai_keys(key: str):
    system_prompt = await get_message_from_panel(f"pixiee_ai_system_{key}")
    user_prompt = await get_message_from_panel(f"pixiee_ai_user_{key}")
    format_keys = format_string_keys(system_prompt) | format_string_keys(user_prompt)

    return format_keys


@router.post("/translate")
async def translate_with_ai(request: Request, data: TranslateRequest):
    user: UserData = jwt_access_security(request)
    # return await answer_with_ai_route(request, "translate", data)
    return await translate(**data.model_dump())


@router.post("/{key:str}")
async def answer_with_ai_route(request: Request, key: str, data: dict = Body(...)):
    # logging.info(f"{key} -> {json.dumps(data, ensure_ascii=False)}")
    user: UserData = jwt_access_security(request)
    return await answer_with_ai(key, **data)
