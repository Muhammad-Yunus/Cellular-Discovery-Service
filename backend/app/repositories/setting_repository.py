from sqlalchemy.orm import Session
from typing import Optional
from app.db.models.setting import Setting


class SettingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, key: str) -> Optional[Setting]:
        return self.db.query(Setting).filter(Setting.key == key).first()

    def get_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        setting = self.get_by_key(key)
        return setting.value if setting else default

    def set_value(self, key: str, value: str) -> Setting:
        setting = self.get_by_key(key)
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
            self.db.add(setting)

        self.db.commit()
        self.db.refresh(setting)
        return setting

    def get_all(self) -> list[Setting]:
        return self.db.query(Setting).all()

    def delete(self, key: str) -> bool:
        setting = self.get_by_key(key)
        if not setting:
            return False
        self.db.delete(setting)
        self.db.commit()
        return True
