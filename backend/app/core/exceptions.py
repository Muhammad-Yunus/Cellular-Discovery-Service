from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class AppException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=404, detail=detail)


class BadRequestException(AppException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=400, detail=detail)


class InternalServerErrorException(AppException):
    def __init__(self, detail: str = "Internal server error"):
        super().__init__(status_code=500, detail=detail)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.error(f"AppException: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


def _flatten_validation_message(field: str, error_type: str, msg: str, input_value) -> str:
    """Convert pydantic validation error into a flat human-readable message."""
    short_field = field.split(".")[-1] if field else "field"
    # Remove pydantic "Value error" prefix from custom validators
    if error_type == "value_error" and msg.startswith("Value error, "):
        msg = msg.replace("Value error, ", "", 1)
    if error_type in ("greater_than", "greater_than_equal"):
        op = ">=" if error_type == "greater_than_equal" else ">"
        return f"{short_field} must be {op} {msg.split()[-1]}"
    if error_type in ("less_than", "less_than_equal"):
        op = "<=" if error_type == "less_than_equal" else "<"
        return f"{short_field} must be {op} {msg.split()[-1]}"
    if error_type == "missing":
        return f"{short_field} is required"
    # For custom validators, msg is already clean
    if error_type == "value_error":
        return msg
    return f"{short_field}: {msg}"


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Flatten pydantic RequestValidationError into project-standard format.

    Output shape (single string detail to match other handlers):
        {"detail": "<message>"}

    If multiple errors exist, join them with "; ".
    """
    errors = exc.errors()
    messages: list[str] = []
    for err in errors:
        loc = ".".join(str(p) for p in err.get("loc", []))
        err_type = err.get("type", "")
        msg = err.get("msg", "")
        input_value = err.get("input")
        messages.append(_flatten_validation_message(loc, err_type, msg, input_value))

    flat = "; ".join(messages) if messages else "Validation error"
    logger.warning(f"Validation error on {request.url.path}: {flat}")
    return JSONResponse(
        status_code=422,
        content={"detail": flat},
    )
