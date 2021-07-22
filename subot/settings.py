from dataclasses import dataclass
from pathlib import Path

sqlite_path = (Path.cwd() / __file__).parent.parent.joinpath('assets.db')

@dataclass()
class DatabaseConfig:
    uri: str = f"sqlite:///{sqlite_path.as_posix()}"


DATABASE_CONFIG = DatabaseConfig()
IMAGE_PATH = Path(__file__).parent.parent.joinpath('resources')
DEBUG = False
FPS = 20