from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ScanResultFlatResponse(BaseModel):
    id: int
    scan_session_id: int
    scan_time: datetime
    tty_port: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime
    operator_name: Optional[str] = None
    mcc: Optional[str] = None
    mnc: Optional[str] = None
    rat: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


class ScanResultResponse(BaseModel):
    id: int
    operator_name: Optional[str] = None
    mcc: Optional[str] = None
    mnc: Optional[str] = None
    rat: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


class ScanSessionResponse(BaseModel):
    id: int
    scan_time: datetime
    tty_port: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime
    results: list[ScanResultResponse] = []

    class Config:
        from_attributes = True


class ScanRequest(BaseModel):
    tty: str = "/dev/ttyUSB0"


class PaginatedResponse(BaseModel):
    items: list[ScanResultFlatResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SettingResponse(BaseModel):
    key: str
    value: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class SettingUpdateRequest(BaseModel):
    key: str
    value: str


class ScanDeleteResponse(BaseModel):
    message: str
    id: int
