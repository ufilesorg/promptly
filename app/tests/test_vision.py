import logging
import os

import httpx
import pytest

from apps.ai.services import answer_gemini_new, get_prompt
from server.config import Settings

ims = [
    "https://m.media-amazon.com/images/I/81D6xOyER2L._AC_SX679_.jpg",
    "https://dkstatics-public.digikala.com/digikala-products/1069347.jpg?x-oss-process=image/resize,m_lfit,h_800,w_800/format,webp/quality,q_90",
    "https://breville-production-aem-assets.s3.us-west-2.amazonaws.com/BES870/BES870USC_CAROUSEL4.png",
    "https://breville-production-aem-assets.s3.us-west-2.amazonaws.com/BES870/BES870USC_CAROUSEL5.png",
    "https://breville-production-aem-assets.s3.us-west-2.amazonaws.com/BES870/07_BES870_USCM_1300px+(1).jpg",
]
key = "product_image_validator"
summary = {
    "title_en": "Breville BES870 Espresso Maker",
    "title_fa": "اسپرسوساز برویل مدل BES870",
    "colors": [{"id": 61, "title": "استیل", "hex_code": "#ebebeb"}],
    "specifications": [
        {
            "title": "مشخصات",
            "attributes": [
                {
                    "title": "امکانات اسپرسوساز",
                    "values": ["آسیاب قهوه "],
                },
                {
                    "title": "قابلیت استفاده از",
                    "values": ["پودر قهوه "],
                },
                {
                    "title": "دستگاه نمایش وضعیت",
                    "values": ["نشان گر سطح آب "],
                },
                {"title": "فشار بخار", "values": ["15 "]},
                {"title": "ظرفیت مخزن", "values": ["2.2 "]},
                {"title": "پهنا", "values": ["300 "]},
                {
                    "title": "ارتفاع",
                    "values": ["370 سانتی\u200cمتر"],
                },
                {"title": "طول", "values": ["300 سانتی\u200cمتر"]},
                {"title": "وزن", "values": ["12.1 کیلوگرم"]},
            ],
        }
    ],
    "category_fa": "اسپرسو ساز",
    "category_en": "اسپرسو ساز",
    "brand_fa": "برویل",
    "brand_en": "Breville",
}
ims = [
    "https://dkstatics-public.digikala.com/digikala-products/3e81889a98eda49bcd297c0fd56aa061321d32c7_1722197824.jpg?x-oss-process=image/resize,m_lfit,h_800,w_800/quality,q_90",
    "https://media.pixiee.io/v1/f/75da3693-e8a8-44c2-b74a-0f9e4828524a/16218254.jpg",
    "https://media.pixiee.io/v1/f/5ef7207d-8181-4bb2-a7d8-9c906f5b2d39/16218254.jpg",
]
summary = {
    "title_en": "",
    "title_fa": "کابل تبدیل USB به USB-C اسپیگن مدل C10C0 طول 1 متر",
    "colors": [],
    "specifications": [
        {
            "title": "مشخصات",
            "attributes": [
                {"title": "نوع کابل شارژ و مبدل", "values": ["کابل شارژ "]},
                {"title": "نوع کابل", "values": ["USB Type-C "]},
                {"title": "نوع رابط", "values": ["USB Type-C "]},
            ],
        }
    ],
    "category_fa": "کابل شارژ و مبدل",
    "category_en": "کابل شارژ و مبدل",
    "brand_fa": "اسپیگن",
    "brand_en": "Spigen",
}


async def get_image(url: str, dir: str | None = None, filename: str | None = None):
    from fastapi_mongo_base.utils import imagetools

    if dir is None:
        dir = Settings.base_dir / "tests" / "images"
    if filename is None:
        filename = url.split("/")[-1]

    im = await imagetools.download_image(url)
    im.save(f"{dir}/{filename}")
    return im


async def get_image_bytes(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.content


@pytest.mark.asyncio
async def test_image_prompt(client: httpx.AsyncClient, settings: Settings):

    for i, im in enumerate(ims, start=1):
        if not os.path.exists(Settings.base_dir / "tests" / "images" / f"{i}.jpg"):
            await get_image(im, filename=f"{i}.jpg")

    response = await client.post(
        f"{settings.base_path}/ai/vision/{key}",
        json={
            "image_urls": [ims[1], ims[2]],
            "data": {"summary": summary},
        },
    )
    logging.info(response.json())
    assert response.status_code == 200
    assert response.json()


@pytest.mark.asyncio
async def test_gemini2_vision():
    import asyncio
    import itertools

    from google.genai import types

    ims_bytes = await asyncio.gather(*[get_image_bytes(im) for im in ims[:]])
    for i, j in itertools.combinations(range(len(ims_bytes)), 2):
        system, user, model_name = await get_prompt(key, summary=summary)
        model_name = "gemini-2.0-flash"
        messages = [system, user] if system else [user]
        im1 = types.Part.from_bytes(data=ims_bytes[i], mime_type="image/jpeg")
        im2 = types.Part.from_bytes(data=ims_bytes[j], mime_type="image/jpeg")
        messages.append(im1)
        messages.append(im2)

        answer = await answer_gemini_new(messages, image_count=2, model_name=model_name)
        logging.info(f"{i} and {j}: {answer}")
