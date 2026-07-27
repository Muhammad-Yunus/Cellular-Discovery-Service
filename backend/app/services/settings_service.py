from sqlalchemy.orm import Session
from app.repositories import SettingRepository
from app.schemas.scan import SettingResponse, SettingUpdateRequest


class SettingsService:
    def __init__(self, db: Session):
        self.db = db
        self.setting_repo = SettingRepository(db)

    def get_all(self) -> list[SettingResponse]:
        settings = self.setting_repo.get_all()
        return [
            SettingResponse(
                key=s.key,
                value=s.value,
                updated_at=s.updated_at,
            )
            for s in settings
        ]

    def get_by_key(self, key: str) -> SettingResponse | None:
        setting = self.setting_repo.get_by_key(key)
        if not setting:
            return None

        return SettingResponse(
            key=setting.key,
            value=setting.value,
            updated_at=setting.updated_at,
        )

    def set_value(self, key: str, value: str) -> SettingResponse:
        setting = self.setting_repo.set_value(key=key, value=value)
        return SettingResponse(
            key=setting.key,
            value=setting.value,
            updated_at=setting.updated_at,
        )

    def update_settings(self, updates: list[SettingUpdateRequest]) -> list[SettingResponse]:
        results = []
        for update in updates:
            setting = self.setting_repo.set_value(key=update.key, value=update.value)
            results.append(
                SettingResponse(
                    key=setting.key,
                    value=setting.value,
                    updated_at=setting.updated_at,
                )
            )
        return results
