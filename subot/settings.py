from dataclasses import dataclass
from pathlib import Path

sqlite_path = Path(__file__).parent.parent.joinpath('assets.db')
print(f"{sqlite_path=}")

@dataclass()
class DatabaseConfig:
    uri: str = f"sqlite:///{sqlite_path.as_posix()}"


DATABASE_CONFIG = DatabaseConfig()
IMAGE_PATH = Path(__file__).parent.parent
print(f"{IMAGE_PATH=}")
DEBUG = False