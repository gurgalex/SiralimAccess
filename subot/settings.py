from __future__ import annotations
import configparser
from dataclasses import dataclass
from enum import Enum, auto
import os
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


@dataclass
class Config:
    debug: bool = False
    map_viewer: bool = False
    show_ui: bool = True
    whole_window_scanning_frequency: int = 7
    update_popup_browser: bool = True

    ocr_selected_menu_item: bool = True
    ocr_read_dialog_boxes: bool = True
    read_dialog_key: str = "o"
    read_menu_entry_key: str = 'm'

    master_volume: int = 100
    main_volume: int = 100
    altar: int = 100
    chest: int = 100
    nether_portal: int = 100
    npc_master: int = 100
    npc_generic: int = 100
    project_item: int = 100
    quest: int = 100
    teleportation_shrine: int = 100
    summoning_brazier: int = 100

    detect_objects_through_walls: bool = True

    # repeat detected object sounds. If false, stops playing the sound if play has not moved
    repeat_sound_when_stationary: bool = False
    required_stationary_seconds: float = 0.5

    def save_config(self, path: Path):
        ini = configparser.ConfigParser()

        ini["GENERAL"] = {
            "show_ui": self.show_ui,
            "whole_window_fps": self.whole_window_scanning_frequency,
            "repeat_sound_when_stationary": self.repeat_sound_when_stationary,
            "repeat_sound_seconds": self.required_stationary_seconds,
            'update_popup_browser': self.update_popup_browser,
        }

        ini["OCR"] = {
            "read_selected_menu": self.ocr_selected_menu_item,
            "read_dialog_boxes": self.ocr_read_dialog_boxes,
            "read_dialog_key": self.read_dialog_key,
            "read_menu_entry_key": self.read_menu_entry_key,
        }

        ini["VOLUME"] = {
            "main_volume": self.main_volume,
            "altar": self.altar,
            "chest": self.chest,
            "nether_portal": self.nether_portal,
            "npc_master": self.npc_master,
            "npc_generic": self.npc_generic,
            "project_item": self.project_item,
            "quest": self.quest,
            "summoning_brazier": self.summoning_brazier,
            "teleportation_shrine": self.teleportation_shrine,
        }

        ini["REALM_OBJECT_DETECTION"] = {
            "detect_objects_through_walls": self.detect_objects_through_walls,
        }

        with open(path, "w+", encoding="utf8") as f:
            ini.write(f)

    @classmethod
    def from_ini(cls, path: Path) -> Config:
        default_config = Config()
        ini = configparser.ConfigParser()
        ini.read(path.as_posix())

        general = ini["GENERAL"]
        default_config.show_ui = general.getboolean("show_ui", fallback=default_config.show_ui)

        default_config.whole_window_scanning_frequency = general.getfloat("whole_window_fps", fallback=default_config.whole_window_scanning_frequency)
        default_config.repeat_sound_when_stationary = general.getboolean('repeat_sound_when_stationary', fallback=default_config.repeat_sound_when_stationary)
        default_config.required_stationary_seconds = general.getfloat('repeat_sound_seconds', fallback=default_config.required_stationary_seconds)
        default_config.update_popup_browser = general.getboolean('update_popup_browser', fallback=default_config.update_popup_browser)

        volume = ini["VOLUME"]

        default_config.master_volume = volume.getint("main_volume", fallback=default_config.master_volume)
        default_config.altar = volume.getint("altar", fallback=default_config.altar)
        default_config.chest = volume.getint("chest", fallback=default_config.chest)
        default_config.nether_portal = volume.getint('nether_portal', fallback=default_config.nether_portal)
        default_config.npc_master = volume.getint('npc_master', fallback=default_config.npc_master)
        default_config.npc_generic = volume.getint("npc_generic", fallback=default_config.npc_generic)
        default_config.project_item = volume.getint("project_item", fallback=default_config.project_item)
        default_config.quest = volume.getint("quest", fallback=default_config.quest)
        default_config.teleportation_shrine = volume.getint("teleportation_shrine", fallback=default_config.teleportation_shrine)
        default_config.summoning_brazier = volume.getint('summoning_brazier', fallback=default_config.summoning_brazier)

        ocr = ini["OCR"]
        default_config.ocr_selected_menu_item = ocr.getboolean("read_selected_menu", fallback=default_config.ocr_selected_menu_item)
        default_config.ocr_read_dialog_boxes = ocr.getboolean('read_dialog_boxes', fallback=default_config.ocr_read_dialog_boxes)
        default_config.read_dialog_key = ocr.get('read_dialog_key', fallback=default_config.read_dialog_key)[0]
        default_config.read_menu_entry_key = ocr.get('read_menu_entry_key', fallback=default_config.read_menu_entry_key)


        object_detection = ini["REALM_OBJECT_DETECTION"]
        default_config.detect_objects_through_walls = object_detection.getboolean("detect_objects_through_walls", fallback=default_config.detect_objects_through_walls)

        print(f"{default_config=}")
        return default_config


def load_config() -> Config:

    config_path = Path(os.path.expandvars("%LOCALAPPDATA%")).joinpath("SiralimAccess").joinpath("config.ini")
    if config_path.exists():
        config = Config.from_ini(config_path)
    else:
        print(f"ini doesn't exist. generating default config for {config_path}")
        config_path.parent.mkdir(exist_ok=True)
        config = Config()
    config.save_config(config_path)
    return config

DEBUG = False
VIEWER = False
FPS = 60


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
