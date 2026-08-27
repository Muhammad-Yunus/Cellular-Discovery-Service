from pydantic import BaseModel, field_validator, ValidationInfo
from typing import Optional, List
from datetime import datetime


class ScanResultFlatResponse(BaseModel):
    id: int
    scan_session_id: int
    scan_time: datetime
    band: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    mission_location_id: Optional[int] = None
    cellular_tower_id: Optional[str] = None
    cellular_tower_name: Optional[str] = None
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
    band: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    mission_location_id: Optional[int] = None
    created_at: datetime
    results: List[ScanResultResponse] = []

    class Config:
        from_attributes = True


class ScanRequest(BaseModel):
    band: int = 8

    @field_validator("band")
    @classmethod
    def validate_band(cls, v):
        valid_bands = [4, 5, 8, 20, 40]
        if v not in valid_bands:
            raise ValueError(f"band must be one of {valid_bands}")
        return v


class PaginatedResponse(BaseModel):
    items: List[ScanResultFlatResponse]
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

    @field_validator("value")
    @classmethod
    def validate_gps_provider_value(cls, v, info: ValidationInfo):
        data = info.data if hasattr(info, 'data') else {}
        key = data.get("key", "")
        if key == "gps_provider":
            valid = ("mock", "serial", "cli")
            if v not in valid:
                raise ValueError(f"Invalid GPS provider '{v}'. Must be one of: {valid}")
        return v


class ScanDeleteResponse(BaseModel):
    message: str
    id: int
