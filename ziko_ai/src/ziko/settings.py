from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class Settings:
    data_dir: Path
    operator_user_id: str
    supervisor_token: str = ""

    @classmethod
    def environment(cls):
        return cls(Path(os.environ.get('ZIKO_DATA_DIR', '/data/ziko')),
                   os.environ.get('ZIKO_OPERATOR_USER_ID', ''),
                   os.environ.get('SUPERVISOR_TOKEN', ''))
