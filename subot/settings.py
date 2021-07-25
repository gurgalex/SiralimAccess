from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sqlite_path = (Path.cwd() / __file__).parent.parent.joinpath('assets.db')

@dataclass()
class DatabaseConfig:
    uri: str = f"sqlite:///{sqlite_path.as_posix()}"


DATABASE_CONFIG = DatabaseConfig()
engine = create_engine(DATABASE_CONFIG.uri, echo=False, connect_args={'timeout': 2})
Session = sessionmaker(engine)
IMAGE_PATH = Path(__file__).parent.parent.joinpath('resources')

DEBUG = False
FPS = 20
