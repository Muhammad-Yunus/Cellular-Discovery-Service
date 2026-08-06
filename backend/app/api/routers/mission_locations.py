import mimetypes
from io import StringIO
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services import LocationService
from app.schemas.mission_location import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    DeleteLocationResponse,
    LocationListResponse,
    MissionLocationResponse,
    UploadLocationResponse,
)

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])

# ---------------------------------------------------------------------------
# CSV validation helpers
# ---------------------------------------------------------------------------
_ACCEPTED_CONTENT_TYPES = {"text/csv", "application/vnd.ms-excel", "application/csv"}
_CSV_EXTENSIONS = {".csv"}


def _read_and_validate_csv(file: UploadFile) -> bytes:
    """Validate the uploaded file's metadata, then return its bytes."""
    if file is None:
        raise HTTPException(status_code=422, detail="No file uploaded")

    # Check filename extension (lowercased)
    filename = file.filename or ""
    ext = ""
    if filename:
        dot_pos = filename.rfind(".")
        if dot_pos >= 0:
            ext = filename[dot_pos:].lower()
    # Fallback to mime guess if no extension
    if not ext:
        ext = (mimetypes.guess_extension(file.content_type or "") or "").lower()
    if ext not in _CSV_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail="Only .csv files are accepted",
        )

    # Check Content-Type (if provided)
    ct = (file.content_type or "").lower()
    if ct and ct not in _ACCEPTED_CONTENT_TYPES and not ct.startswith("text/"):
        raise HTTPException(
            status_code=422,
            detail="File must be a CSV (text-based) file",
        )

    # Read content once
    file_content = file.file.read()
    if not file_content:
        raise HTTPException(status_code=422, detail="CSV file is empty")

    return file_content


@router.post("/{mission_id}/locations/upload", response_model=UploadLocationResponse)
def upload_locations(
    mission_id: int,
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    file_content = _read_and_validate_csv(file)
    service = LocationService(db)
    return service.upload(mission_id, file_content)


# ---------------------------------------------------------------------------
# CSV template (5 sample Jabodetabek locations, 3-5 km apart)
# ---------------------------------------------------------------------------
_TEMPLATE_HEADER = (
    "cellular_tower_id,cellular_tower_name,latitude,longitude"
)
_TEMPLATE_ROWS = [
    ("TWR-TPL-001", "Lebak Bulus", -6.2908, 106.7780),
    ("TWR-TPL-002", "Fatmawati",   -6.2644, 106.8017),
    ("TWR-TPL-003", "Senopati",    -6.2249, 106.8070),
    ("TWR-TPL-004", "Tanah Abang", -6.1854, 106.8128),
    ("TWR-TPL-005", "Sawah Besar", -6.1585, 106.8173),
]


def _build_template_csv() -> str:
    """Build a CSV template string with 5 sample rows."""
    buf = StringIO()
    buf.write(_TEMPLATE_HEADER + "\n")
    for tower_id, name, lat, lon in _TEMPLATE_ROWS:
        buf.write(f"{tower_id},{name},{lat},{lon}\n")
    return buf.getvalue()


@router.get("/{mission_id}/locations/download_template")
def download_template(mission_id: int, db: Session = Depends(get_db)):
    """Return a CSV template with 5 sample Jabodetabek locations.

    The sample rows are spaced 3-5 km apart so users can immediately see
    a realistic layout for a coverage test mission. The mission must exist
    (so callers can't accidentally download a template for a bogus id),
    but no rows are inserted.
    """
    service = LocationService(db)
    # 404 cleanly if the mission doesn't exist
    service._get_mission(mission_id)

    csv_data = _build_template_csv()
    response = Response(content=csv_data, media_type="text/csv")
    response.headers[
        "Content-Disposition"
    ] = f'attachment; filename="mission_{mission_id}_locations_template.csv"'
    return response


@router.get("/{mission_id}/locations", response_model=LocationListResponse)
def list_locations(
    mission_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    db: Session = Depends(get_db),
):
    service = LocationService(db)
    return service.list_locations(mission_id, page, page_size, search)


@router.get("/{mission_id}/locations/{location_id}", response_model=MissionLocationResponse)
def get_location(
    mission_id: int,
    location_id: int,
    db: Session = Depends(get_db),
):
    service = LocationService(db)
    return service.get_location(mission_id, location_id)


@router.delete("/{mission_id}/locations/{location_id}", response_model=DeleteLocationResponse)
def delete_location(
    mission_id: int,
    location_id: int,
    db: Session = Depends(get_db),
):
    service = LocationService(db)
    return service.delete_location(mission_id, location_id)


@router.post("/{mission_id}/locations/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_locations(
    mission_id: int,
    body: BulkDeleteRequest,
    db: Session = Depends(get_db),
):
    service = LocationService(db)
    return service.bulk_delete(mission_id, body.upload_batch_id)
