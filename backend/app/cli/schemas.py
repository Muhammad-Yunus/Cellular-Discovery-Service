from pydantic import BaseModel
from typing import Optional


class CLIScanResult(BaseModel):
    operator_name: Optional[str] = None
    mcc: Optional[str] = None
    mnc: Optional[str] = None
    rat: Optional[str] = None
    status: Optional[str] = None
    # Additional fields from lte-scan CLI
    frequency_mhz: Optional[float] = None
    earfcn: Optional[int] = None
    band: Optional[str] = None
    pci: Optional[int] = None
    rsrp: Optional[float] = None
    rsrq: Optional[float] = None
    snr: Optional[float] = None


class CLIScanResponse(BaseModel):
    results: list[CLIScanResult]
    raw_output: str
