from fastapi import APIRouter, Body

from .services import answer_with_ai

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/{key}")
async def answer_with_ai_route(key: str, data: dict = Body(...)):
    return await answer_with_ai(key, **data)
