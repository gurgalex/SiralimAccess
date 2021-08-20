from dataclasses import dataclass
from enum import Enum, auto
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
VIEWER = False
FPS = 20



class GameControl(Enum):
    CANCEL = auto()
    CONFIRM = auto()
    DOWN = auto()
    LEFT = auto()
    OPTION = auto()
    RIGHT = auto()
    UP = auto()


keyboard_controls = {
    'w': GameControl.UP,
    'up': GameControl.UP,
    's': GameControl.DOWN,
    'down': GameControl.DOWN,
    'd': GameControl.RIGHT,
    'right': GameControl.RIGHT,
    'a': GameControl.LEFT,
    'left': GameControl.LEFT,
    'e': GameControl.CONFIRM,
    'q': GameControl.CANCEL,
    'f': GameControl.OPTION,
}
