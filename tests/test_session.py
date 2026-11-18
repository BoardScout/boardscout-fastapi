import asyncio
import json

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import UserSessionResponse
from app.session import RedisSessionStore, get_session_store


SESSION_ID = "a" * 43


class FakeSessionStore:
    def __init__(self, user: UserSessionResponse | None = None, ready: bool = True) -> None:
        self.user = user
        self.ready = ready
        self.received_session_id: str | None = None

    async def ping(self) -> bool:
        return self.ready

    async def find_and_refresh(self, session_id: str) -> UserSessionResponse | None:
        self.received_session_id = session_id
        return self.user


class FakeRedis:
    def __init__(self, value: str | None) -> None:
        self.value = value
        self.getex_calls: list[tuple[str, int]] = []
        self.deleted: list[str] = []

    async def getex(self, key: str, ex: int) -> str | None:
        self.getex_calls.append((key, ex))
        return self.value

    async def delete(self, key: str) -> None:
        self.deleted.append(key)


def test_me_reads_shared_session_cookie() -> None:
    store = FakeSessionStore(
        UserSessionResponse(
            userId=1,
            email="player@example.com",
            nickname="플레이어",
            role="USER",
        )
    )
    app.dependency_overrides[get_session_store] = lambda: store
    try:
        client = TestClient(app)
        client.cookies.set("BGSESSION", SESSION_ID)
        response = client.get("/api/v1/recommendations/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert store.received_session_id == SESSION_ID
    assert response.json()["result"]["userId"] == 1


def test_me_rejects_missing_session_cookie() -> None:
    app.dependency_overrides[get_session_store] = lambda: FakeSessionStore()
    try:
        response = TestClient(app).get("/api/v1/recommendations/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH-401-001"


def test_ready_checks_session_store() -> None:
    app.dependency_overrides[get_session_store] = lambda: FakeSessionStore(ready=True)
    try:
        response = TestClient(app).get("/api/v1/recommendations/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "READY"


def test_redis_session_store_refreshes_ttl_and_maps_contract() -> None:
    redis = FakeRedis(
        json.dumps(
            {
                "userId": 7,
                "email": "player@example.com",
                "nickname": "플레이어",
                "role": "USER",
                "createdAt": "2026-11-05T12:00:00Z",
            }
        )
    )
    store = RedisSessionStore(redis, ttl_seconds=1800)  # type: ignore[arg-type]

    user = asyncio.run(store.find_and_refresh(SESSION_ID))

    assert user is not None
    assert user.user_id == 7
    assert redis.getex_calls == [(f"session:{SESSION_ID}", 1800)]


def test_redis_session_store_deletes_broken_json() -> None:
    redis = FakeRedis("not-json")
    store = RedisSessionStore(redis, ttl_seconds=1800)  # type: ignore[arg-type]

    user = asyncio.run(store.find_and_refresh(SESSION_ID))

    assert user is None
    assert redis.deleted == [f"session:{SESSION_ID}"]
