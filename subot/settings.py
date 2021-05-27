from dataclasses import dataclass
from pathlib import Path

sqlite_path = Path.cwd().parent.joinpath('assets.db')
print(f"{sqlite_path=}")

@dataclass()
class DatabaseConfig:
    uri: str = f"sqlite:///{sqlite_path.as_posix()}"


DATABASE_CONFIG = DatabaseConfig()
IMAGE_PATH: Path = Path("../")

DEBUG = False