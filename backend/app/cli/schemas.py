from pydantic import BaseModel
from typing import Optional


class CLIScanResult(BaseModel):
    operator_name: Optional[str] = None
    mcc: Optional[str] = None
    mnc: Optional[str] = None
    rat: Optional[str] = None
    status: Optional[str] = None


class CLIScanResponse(BaseModel):
    results: list[CLIScanResult]
    raw_output: str
