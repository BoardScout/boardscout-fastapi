"""API 예외와 공통 오류 응답 처리입니다."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHttpException

from app.schemas import ApiResponse, ErrorDetail


logger = logging.getLogger(__name__)


class ApiError(Exception):
    """예상 가능한 API 오류를 HTTP 상태와 서비스 코드로 표현합니다."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _field_name(location: tuple[object, ...]) -> str:
    """Pydantic의 ('body', 'field') 위치를 화면에서 쓸 경로로 바꿉니다."""

    visible_parts = (part for part in location if part not in {"body", "query", "path"})
    return ".".join(str(part) for part in visible_parts) or "request"


def install_exception_handlers(app: FastAPI) -> None:
    """모든 라우터가 같은 오류 JSON을 반환하도록 처리기를 등록합니다."""

    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, error: ApiError) -> JSONResponse:
        payload = ApiResponse[ErrorDetail](
            success=False,
            code=error.code,
            message=error.message,
            result=None,
        )
        return JSONResponse(
            status_code=error.status_code,
            content=payload.model_dump(mode="json", by_alias=True),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # 같은 필드에 오류가 여러 개여도 가장 먼저 발견한 원인만 전달합니다.
        errors: dict[str, str] = {}
        for item in error.errors():
            errors.setdefault(_field_name(item["loc"]), item["msg"])
        payload = ApiResponse[ErrorDetail](
            success=False,
            code="COMMON-422",
            message="요청 값이 올바르지 않습니다.",
            result=ErrorDetail(errors=errors),
        )
        return JSONResponse(status_code=422, content=payload.model_dump(mode="json", by_alias=True))

    @app.exception_handler(StarletteHttpException)
    async def handle_http_error(_request: Request, error: StarletteHttpException) -> JSONResponse:
        # 존재하지 않는 경로와 허용되지 않은 HTTP 메서드도 공통 계약으로 맞춥니다.
        payload = ApiResponse[ErrorDetail](
            success=False,
            code=f"COMMON-{error.status_code}",
            message=str(error.detail),
            result=None,
        )
        return JSONResponse(
            status_code=error.status_code,
            content=payload.model_dump(mode="json", by_alias=True),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        # 상세 예외는 서버 로그에만 남기고 응답에는 내부 정보를 노출하지 않습니다.
        logger.exception(
            "처리되지 않은 오류: %s %s",
            request.method,
            request.url.path,
            exc_info=error,
        )
        payload = ApiResponse[ErrorDetail](
            success=False,
            code="COMMON-500",
            message="서버 내부 오류가 발생했습니다.",
            result=None,
        )
        return JSONResponse(status_code=500, content=payload.model_dump(mode="json", by_alias=True))
