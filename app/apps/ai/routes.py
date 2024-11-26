import logging
from fastapi import APIRouter, Body, Depends
from fastapi_mongo_base._utils.texttools import format_string_keys
from usso.fastapi import jwt_access_security
from usso import UserData
from .services import (
    answer_with_ai,
    translate,
    get_message_from_panel,
    get_messages_list,
)

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/translate")
async def translate_with_ai(
    data: dict = Body(...), user: UserData = Depends(jwt_access_security)
):
    return await translate(**data)


@router.get("/search")
async def search_ai_keys(key: str):
    return await get_messages_list(f"{key}")


@router.get("/{key}/fields")
async def get_ai_keys(key: str):
    system_prompt = await get_message_from_panel(f"pixiee_ai_system_{key}")
    user_prompt = await get_message_from_panel(f"pixiee_ai_user_{key}")
    format_keys = format_string_keys(system_prompt) | format_string_keys(user_prompt)

    return format_keys


@router.post("/{key}")
async def answer_with_ai_route(
    key: str, data: dict = Body(...), user: UserData = Depends(jwt_access_security)
):
    return await answer_with_ai(key, **data)
