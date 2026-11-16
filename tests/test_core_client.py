import asyncio

import httpx

from app.core_client import SpringRatingStore


def test_spring_rating_store_forwards_session_and_parses_wrapped_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["cookie"] == f"BGSESSION={'a' * 43}"
        return httpx.Response(
            200,
            json={
                "success": True,
                "code": "COMMON-200",
                "message": "요청에 성공했습니다.",
                "result": [
                    {
                        "datasetItemId": 15,
                        "rating": 8.5,
                        "updatedAt": "2026-11-16T10:00:00",
                    }
                ],
            },
        )

    async def run():
        async with httpx.AsyncClient(
            base_url="http://core",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await SpringRatingStore(client, "BGSESSION").get_ratings("a" * 43)

    ratings = asyncio.run(run())

    assert ratings[0].dataset_item_id == 15
    assert ratings[0].rating == 8.5
