from typing import Annotated
from fastapi import Depends
from app.core.config import Settings, get_settings

# Convenience alias for injecting settings
SettingsDep = Annotated[Settings, Depends(get_settings)]
