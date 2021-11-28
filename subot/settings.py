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
    open_config_key: str = "C"

    # OCR
    ocr_enabled: bool = True
    read_secondary_key: str = "o"
    read_all_info_key: str = "v"
    copy_all_info_key: str = "c"
    read_menu_entry_key: str = 'm'

    master_volume: int = 100
    main_volume: int = 100
    altar: int = 100
    blacksmith: int = 100
    chest: int = 100
    emblem: int = 100
    exotic_portal: int = 100
    nether_portal: int = 100
    npc_master: int = 100
    npc_generic: int = 100
    pandemonium_statue: int = 100
    project_item: int = 100
    quest: int = 100
    teleportation_shrine: int = 100
    summoning_brazier: int = 100
    riddle_dwarf: int = 100
    treasure_map_item: int = 100
    wardrobe: int = 100

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
            'open_config_key': self.open_config_key
        }

        ini["OCR"] = {
            "enabled": self.ocr_enabled,
            "read_secondary_key": self.read_secondary_key,
            "read_all_info_key": self.read_all_info_key,
            "copy_all_info_key": self.copy_all_info_key,
            "read_menu_entry_key": self.read_menu_entry_key,
        }

        ini["VOLUME"] = {
            "main_volume": self.main_volume,
            "altar": self.altar,
            "blacksmith": self.blacksmith,
            "chest": self.chest,
            "emblem": self.emblem,
            "exotic_portal": self.exotic_portal,
            "nether_portal": self.nether_portal,
            "npc_master": self.npc_master,
            "npc_generic": self.npc_generic,
            "pandemonium_statue": self.pandemonium_statue,
            "project_item": self.project_item,
            "quest": self.quest,
            "summoning_brazier": self.summoning_brazier,
            "teleportation_shrine": self.teleportation_shrine,
            "riddle_dwarf": self.riddle_dwarf,
            "treasure_map_item": self.treasure_map_item,
            "wardrobe": self.wardrobe,
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
        default_config.open_config_key = general.get('open_config_key', fallback=default_config.open_config_key)

        volume = ini["VOLUME"]

        default_config.master_volume = volume.getint("main_volume", fallback=default_config.master_volume)
        default_config.altar = volume.getint("altar", fallback=default_config.altar)
        default_config.blacksmith = volume.getint("blacksmith", fallback=default_config.blacksmith)
        default_config.chest = volume.getint("chest", fallback=default_config.chest)
        default_config.emblem = volume.getint("emblem", fallback=default_config.emblem)
        default_config.exotic_portal = volume.getint("exotic_portal", fallback=default_config.exotic_portal)
        default_config.nether_portal = volume.getint('nether_portal', fallback=default_config.nether_portal)
        default_config.npc_master = volume.getint('npc_master', fallback=default_config.npc_master)
        default_config.npc_generic = volume.getint("npc_generic", fallback=default_config.npc_generic)
        default_config.pandemonium_statue = volume.getint("pandemonium_statue", fallback=default_config.pandemonium_statue)
        default_config.project_item = volume.getint("project_item", fallback=default_config.project_item)
        default_config.quest = volume.getint("quest", fallback=default_config.quest)
        default_config.teleportation_shrine = volume.getint("teleportation_shrine", fallback=default_config.teleportation_shrine)
        default_config.treasure_map_item = volume.getint("treasure_map_item", fallback=default_config.treasure_map_item)
        default_config.summoning_brazier = volume.getint('summoning_brazier', fallback=default_config.summoning_brazier)
        default_config.riddle_dwarf = volume.getint('riddle_dwarf', fallback=default_config.riddle_dwarf)
        default_config.wardrobe = volume.getint('wardrobe', fallback=default_config.wardrobe)


        ocr = ini["OCR"]
        default_config.ocr_enabled = ocr.getboolean("enabled", fallback=default_config.ocr_enabled)
        default_config.read_secondary_key = ocr.get('read_secondary_key', fallback=default_config.read_secondary_key)
        default_config.read_all_info_key = ocr.get("read_all_info_key", fallback=default_config.read_all_info_key)
        default_config.copy_all_info_key = ocr.get("copy_all_info_key", fallback=default_config.copy_all_info_key)
        default_config.read_menu_entry_key = ocr.get('read_menu_entry_key', fallback=default_config.read_menu_entry_key)

        object_detection = ini["REALM_OBJECT_DETECTION"]
        default_config.detect_objects_through_walls = object_detection.getboolean("detect_objects_through_walls", fallback=default_config.detect_objects_through_walls)

        print(f"{default_config=}")
        return default_config


def config_file_path() -> Path:
    return Path(os.path.expandvars("%LOCALAPPDATA%")).joinpath("SiralimAccess").joinpath("config.ini")


def load_config() -> Config:

    config_path = config_file_path()
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
