import logging

import httpx
import pytest

from server.config import Settings


@pytest.mark.asyncio
async def test_image_prompt(client: httpx.AsyncClient, settings: Settings):
    im_test = "https://m.media-amazon.com/images/I/81D6xOyER2L._AC_SX679_.jpg"
    im_original = "https://dkstatics-public.digikala.com/digikala-products/1069347.jpg?x-oss-process=image/resize,m_lfit,h_800,w_800/format,webp/quality,q_90"
    # im_test = Image.open(httpx.get(im_test).content)
    # im_original = Image.open(httpx.get(im_original).content)

    response = await client.post(
        f"{settings.base_path}/ai/vision/product_image_validator",
        json={
            "image_urls": [im_test, im_original],
            "data": {
                "summary": {
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
                },
            },
        },
    )
    logging.info(response.json())
    assert response.status_code == 200
    assert response.json()
