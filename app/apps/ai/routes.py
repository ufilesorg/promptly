from fastapi import APIRouter, Body

from .services import answer_with_ai, translate

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/translate")
async def translate_with_ai(data: dict = Body(...)):
    return await translate(**data)


@router.post("/{key}")
async def answer_with_ai_route(key: str, data: dict = Body(...)):
    return await answer_with_ai(key, **data)
