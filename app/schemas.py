"""추천 API에서 사용하는 응답 모델입니다."""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: str
    status: str
    timestamp: datetime

