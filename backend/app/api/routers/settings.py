from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services import SettingsService
from app.schemas.scan import SettingResponse, SettingUpdateRequest

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=list[SettingResponse])
def list_settings(
    db: Session = Depends(get_db),
):
    service = SettingsService(db=db)
    return service.get_all()


@router.put("", response_model=list[SettingResponse])
def update_settings(
    updates: list[SettingUpdateRequest],
    db: Session = Depends(get_db),
):
    service = SettingsService(db=db)

    try:
        return service.update_settings(updates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
