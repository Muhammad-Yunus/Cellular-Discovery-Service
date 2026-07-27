import pytest
from unittest.mock import MagicMock
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.exceptions import (
    AppException,
    NotFoundException,
    BadRequestException,
    InternalServerErrorException,
    app_exception_handler,
    generic_exception_handler,
)


class TestAppExceptions:
    def test_app_exception(self):
        exc = AppException(status_code=400, detail="Bad request")

        assert exc.status_code == 400
        assert exc.detail == "Bad request"

    def test_not_found_exception(self):
        exc = NotFoundException()

        assert exc.status_code == 404
        assert exc.detail == "Resource not found"

    def test_not_found_exception_custom(self):
        exc = NotFoundException(detail="Custom not found")

        assert exc.status_code == 404
        assert exc.detail == "Custom not found"

    def test_bad_request_exception(self):
        exc = BadRequestException()

        assert exc.status_code == 400
        assert exc.detail == "Bad request"

    def test_bad_request_exception_custom(self):
        exc = BadRequestException(detail="Custom bad request")

        assert exc.status_code == 400
        assert exc.detail == "Custom bad request"

    def test_internal_server_error_exception(self):
        exc = InternalServerErrorException()

        assert exc.status_code == 500
        assert exc.detail == "Internal server error"

    def test_internal_server_error_exception_custom(self):
        exc = InternalServerErrorException(detail="Custom error")

        assert exc.status_code == 500
        assert exc.detail == "Custom error"


class TestExceptionHandlers:
    @pytest.mark.asyncio
    async def test_app_exception_handler(self):
        mock_request = MagicMock(spec=Request)
        exc = AppException(status_code=422, detail="Validation error")

        response = await app_exception_handler(mock_request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_generic_exception_handler(self):
        mock_request = MagicMock(spec=Request)
        exc = Exception("Unexpected error")

        response = await generic_exception_handler(mock_request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
