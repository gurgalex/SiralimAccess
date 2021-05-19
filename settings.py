from dataclasses import dataclass
from pathlib import Path


@dataclass()
class DatabaseConfig:
    uri: str = "sqlite:///assets.db"


DATABASE_CONFIG = DatabaseConfig()
IMAGE_PATH: Path = Path("assets_padded/")