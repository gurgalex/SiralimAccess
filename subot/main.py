import os
import sys
import signal
import threading
import enum
import logging
import multiprocessing
from collections import deque, defaultdict
import queue
from logging.handlers import QueueHandler, QueueListener
from multiprocessing import Queue
from threading import Thread
from typing import Optional, Union

import sentry_sdk
import requests
import semantic_version
import webbrowser

from ctypes import windll
from pynput import keyboard
from pynput.keyboard import KeyCode

import win32process

from subot import models, ocr
from subot.ui_areas.CreatureReorderSelectFirst import OCRCreatureRecorderSelectFirst, OCRCreatureRecorderSwapWith
from subot.ui_areas.OCRGodForgeSelect import OCRGodForgeSelectSystem
from subot.ui_areas.creatures_display import OCRCreaturesDisplaySystem
from subot.ui_areas.summoning import OcrSummoningSystem
from subot.trait_info import TraitData, Creature
from subot.hang_monitor import HangMonitorWorker, HangMonitorChan, HangAnnotation, HangMonitorAlert, Shutdown

import cv2
import numpy as np
import mss
from subot.settings import Session, GameControl
import subot.settings as settings
from subot.ocr import detect_green_text, detect_dialog_text, english_installed, detect_title, OCRMode, OCR
from subot.ui_areas.ui_ocr_types import OCR_UI_SYSTEMS
import win32gui
import pygame
import pygame.freetype
import math
import time

from subot.audio import AudioSystem, AudioLocation, SoundType
from subot.datatypes import Rect
from subot.menu import MenuItem, Menu
from subot.messageTypes import NewFrame, MessageImpl, WindowDim, ScanForItems, \
    Resume, Pause
from subot.pathfinder.map import TileType, Map, Color, Movement

from numpy.typing import ArrayLike

from subot.hash_image import ImageInfo, RealmSpriteHasher, compute_hash

from dataclasses import dataclass

from subot.models import Sprite, SpriteFrame, Quest, FloorSprite, Realm, RealmLookup, NPCSprite, HashFrameWithFloor, \
    QuestType, ResourceNodeSprite, \
    SpriteTypeLookup, SpriteType, ChestSprite


from subot.utils import Point, read_version
import traceback


user32 = windll.user32


def set_dpi_aware():
    # makes functions return real pixel numbers instead of scaled values
    user32.SetProcessDPIAware()


set_dpi_aware()


pygame.mixer.init()
pygame.freetype.init()
pygame.display.init()

os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"

# sentry annotation for pyinstaller
def before_send(event, hint):
    event["extra"]["exception"] = ["".join(
        traceback.format_exception(*hint["exc_info"])
    )]
    event["extra"]["app_version"] = read_version()
    return event


TILE_SIZE = 32
NEARBY_TILES_WH: int = 8 * 2 + 1

title_window_access = "Siralim Access"


class GameNotOpenException(Exception):
    pass


class GameFullscreenException(Exception):
    pass


def convert_to_rect(rect, clientRect) -> Rect:
    windowOffset = math.floor(((rect[2] - rect[0]) - clientRect[2]) / 2)
    titleOffset = ((rect[3] - rect[1]) - clientRect[3]) - windowOffset
    newRect = (rect[0] + windowOffset, rect[1] + titleOffset, rect[2] - windowOffset, rect[3] - windowOffset)

    return Rect(x=newRect[0], y=newRect[1], w=newRect[2] - newRect[0], h=newRect[3] - newRect[1])


class GameMinimizedException(Exception):
    pass


class GameNotForegroundException(Exception):
    pass


def clear_queue(q: Queue):
    while not q.empty():
        try:
            q.get_nowait()
        except queue.Empty:
            break


def get_su_client_rect() -> Rect:
    """Returns Rect class of the Siralim Ultimate window. Coordinates are without title bar and borders
    :raises GameNotOpenException if the game is not open
    """
    full_screen_rect = (0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    su_hwnd = win32gui.FindWindow("YYGameMakerYY", "Siralim Ultimate")
    su_is_open = su_hwnd > 0
    if not su_is_open:
        raise GameNotOpenException("Siralim Ultimate is not open")
    root.debug(f"{su_hwnd=}")
    rect = win32gui.GetWindowRect(su_hwnd)
    client_rect = win32gui.GetClientRect(su_hwnd)
    window_rect = convert_to_rect(rect, client_rect)

    is_fullscreen = rect == full_screen_rect
    if is_fullscreen:
        raise GameFullscreenException("game is fullscreen")

    is_minimized = window_rect.w == 0 or window_rect.h == 0
    if is_minimized:
        root.debug("Siralim Ultimate is not in the foreground")
        raise GameMinimizedException('game is minimized')

    su_tid, su_pid = win32process.GetWindowThreadProcessId(su_hwnd)
    if not is_foreground_process(su_pid):
        raise GameNotForegroundException("Siralim Ultimate is not in the foreground")

    return window_rect


@dataclass
class TileCoord:
    """Tells position in tile units"""
    x: int
    y: int

    def point(self) -> Point:
        return Point(x=self.x, y=self.y)


from enum import Enum, auto


class BotMode(Enum):
    UNDETERMINED = auto()
    CASTLE = auto()
    REALM = auto()
    MINIMIZED = auto()



@dataclass(frozen=True)
class AssetGridLoc:
    """Tile coordinate relative to player + game asset name on map"""
    x: int
    y: int

    def point(self) -> Point:
        return Point(x=self.x, y=self.y)




class GridType(enum.Enum):
    WHOLE = enum.auto()
    NEARBY = enum.auto()


root = logging.getLogger()

que = queue.Queue(-1)  # no limit on size
queue_handler = QueueHandler(que)
handler = logging.StreamHandler()
if settings.DEBUG:
    root.setLevel(logging.DEBUG)
    handler.setLevel(logging.DEBUG)
    queue_handler.setLevel(logging.DEBUG)
else:
    root.setLevel(logging.INFO)
    handler.setLevel(logging.INFO)
    queue_handler.setLevel(logging.INFO)
listener = QueueListener(que, handler)

root.addHandler(queue_handler)
formatter = logging.Formatter('%(threadName)s %(levelname)s %(relativeCreated)s: %(message)s')
handler.setFormatter(formatter)
listener.start()

player_direction = {GameControl.UP, GameControl.DOWN, GameControl.LEFT, GameControl.RIGHT}

@dataclass(frozen=True, eq=True)
class FloorInfo:
    realm: Optional[Realm]
    long_name: str

def is_foreground_process(pid: int) -> bool:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return False
    active_tid, active_pid = win32process.GetWindowThreadProcessId(hwnd)
    if active_pid == 0:
        return False
    return pid == active_pid


class Bot:
    def on_release(self, key):
        if self.paused:
            return
        root.debug(f"key released: {key}")
        if key == KeyCode.from_char(self.config.read_dialog_key):
            self.action_queue.put_nowait('read_dialog')
        elif key == KeyCode.from_char(self.config.read_menu_entry_key):
            self.action_queue.put_nowait('read_menu_entry')
        elif key == KeyCode.from_char('v'):
            self.action_queue.put_nowait('read_all_info')
        elif key == KeyCode.from_char('c'):
            self.action_queue.put_nowait('copy_all_info')


    def on_press(self, key):
        pass

    def __init__(self, audio_system: AudioSystem, config: settings.Config):
        self.queue_whole_analyzer_comm_send: queue.Queue = queue.Queue()
        # queue to monitor for incoming hang alert
        self.action_queue = queue.Queue()
        self.config = config
        self.mode: BotMode = BotMode.UNDETERMINED
        self.game_is_foreground: bool = False
        self.paused: bool = False

        self.player_direction: Optional[GameControl] = None
        self.realm: Optional[Realm] = None

        self.hang_alert_queue = multiprocessing.Queue()
        self.hang_control_send = multiprocessing.Queue()
        self.hang_monitor_controller = HangMonitorWorker(daemon=True,
                                                         hang_notify_queue=self.hang_alert_queue, control_port=self.hang_control_send)
        self.hang_monitor_controller.start()


        self.current_quests: set[int] = set()
        self.timer = None
        self.tx_nearby_process_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)

        self.teleportation_shrine_names: set[str] = {'bigroomchanger', 'teleshrine_inactive'}

        self.audio_system = audio_system

        self.color_frame_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)
        self.out_quests: multiprocessing.Queue = multiprocessing.Queue()
        self.rx_color_nearby_queue = multiprocessing.Queue(maxsize=1)

        # queues for communicaitng with WindowGrabber and NearbyGrabber
        self.rx_queue = multiprocessing.Queue(maxsize=10)
        self.tx_window_queue = multiprocessing.Queue(maxsize=10)

        self.nearby_send_deque = queue.Queue(maxsize=10)
        self.quest_sprite_long_names: set[str] = set()


        # Used to analyze the SU window
        try:
            self.su_client_rect = get_su_client_rect()
            self.game_is_foreground = True
        except GameNotOpenException:
            self.audio_system.speak_blocking("Siralim Access will not work unless Siralim Ultimate is open.")

            self.audio_system.speak_blocking("Shutting down")
            sys.exit(1)

        except GameFullscreenException:
            self.audio_system.speak_blocking("Siralim Ultimate cannot be fullscreen")

            self.audio_system.speak_blocking("Shutting down")
            sys.exit(1)

        """player tile position in grid"""
        self.player_position: Rect = Bot.compute_player_position(self.su_client_rect)
        self.player_position_tile = TileCoord(x=self.player_position.x // TILE_SIZE,
                                              y=self.player_position.y // TILE_SIZE)

        self.nearby_rect_mss: Rect = self.compute_nearby_screenshot_area()
        self.nearby_tile_top_left: TileCoord = TileCoord(x=self.nearby_rect_mss.x // TILE_SIZE,
                                                         y=self.nearby_rect_mss.y // TILE_SIZE)
        print(f"{self.su_client_rect=}")
        print(f"{self.nearby_rect_mss=}")

        self.mon_full_window: dict = self.su_client_rect.to_mss_dict()
        self.nearby_mon: dict = {"top": self.su_client_rect.y + self.nearby_rect_mss.y,
                                 "left": self.su_client_rect.x + self.nearby_rect_mss.x,
                                 "width": self.nearby_rect_mss.w, "height": self.nearby_rect_mss.h}

        root.debug(f"{self.player_position_tile=}")
        root.debug(f"{self.player_position=}")

        root.debug(f"{self.nearby_tile_top_left=}")

        self.grid_rect: Rect = Bot.default_grid_rect(self.su_client_rect)

        with Session() as session:
            floor_ids = [floor_id[0] for floor_id in session.query(HashFrameWithFloor.floor_sprite_frame_id).distinct()]
            floor_phashes_query = session.query(HashFrameWithFloor.phash, Sprite.long_name, RealmLookup.enum) \
                .join(SpriteFrame, SpriteFrame.id == HashFrameWithFloor.sprite_frame_id) \
                .join(Sprite, Sprite.id == SpriteFrame.sprite_id) \
                .join(FloorSprite, Sprite.id == FloorSprite.sprite_id) \
                .outerjoin(RealmLookup, FloorSprite.realm_id == RealmLookup.id) \
                .filter(HashFrameWithFloor.sprite_frame_id.in_(floor_ids)) \
                .group_by(HashFrameWithFloor.phash, Sprite.long_name, RealmLookup.enum)
            floor_phashes = floor_phashes_query.all()
            self.floor_hashes: dict[int, FloorInfo] = dict()

            for phash, long_name, realm in floor_phashes:
                self.floor_hashes[phash] = FloorInfo(realm=realm, long_name=long_name)

        # multiple directions playing previous
        self.all_directions: set[Point] = {Point(1, 0), Point(-1, 0), Point(0, 1), Point(0, -1)}

        # Note: images must be read as unchanged when converting to grayscale since IM_READ_GRAYSCALE has platform specific conversion methods and difers from cv2.cv2.BGR2GRAy's implementation in cvtcolor
        # This is needed to ensure the pixels match exactly for comparision, otherwhise the grayscale differs slightly
        # https://docs.opencv.org/4.5.1/d4/da8/group__imgcodecs.html



        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        # keyboard listener
        self.last_key_pressed = None

        # hashes of sprite frames that have matching `self.castle_tile` pixels set to black.
        # This avoids false negative matches if the placed object has matching color pixels in a position
        self.item_hashes: RealmSpriteHasher = RealmSpriteHasher(floor_tiles=None)

        self.all_found_matches: dict[TileType, list[AssetGridLoc]] = defaultdict(list)

        self.stop_event = threading.Event()
        self.nearby_process = NearbyFrameGrabber(name=NearbyFrameGrabber.__name__,
                                                 nearby_area=self.nearby_mon, nearby_queue=self.rx_color_nearby_queue,
                                                 rx_parent=self.tx_nearby_process_queue,
                                                 hang_notifier=self.hang_alert_queue)
        root.debug(f"{self.nearby_process=}")
        self.nearby_process.start()

        self.nearby_processing_thandle = NearPlayerProcessing(name=NearPlayerProcessing.__name__,
                                                              daemon=True,
                                                              nearby_frame_queue=self.rx_color_nearby_queue,
                                                              nearby_comm_deque=self.nearby_send_deque,
                                                              parent=self, stop_event=self.stop_event,
                                                              hang_monitor=self.hang_monitor_controller,
                                                              )
        self.nearby_processing_thandle.start()

        self.window_framegrabber_phandle = WholeWindowGrabber(name=WholeWindowGrabber.__name__,
                                                              outgoing_color_frame_queue=self.color_frame_queue,
                                                              out_quests=self.out_quests,
                                                              screenshot_area=self.mon_full_window,
                                                              rx_queue=self.tx_window_queue,
                                                              hang_notifier=self.hang_alert_queue,
                                                              config=self.config,
                                                              )
        print(f"{self.window_framegrabber_phandle=}")
        self.window_framegrabber_phandle.start()

        self.whole_window_thandle = WholeWindowAnalyzer(name=WholeWindowAnalyzer.__name__,
                                                        incoming_frame_queue=self.color_frame_queue,
                                                        out_quests_queue=self.out_quests,
                                                        queue_child_comm_send=self.queue_whole_analyzer_comm_send,
                                                        su_client_rect=Rect(x=0, y=0, w=self.mon_full_window["width"],
                                                                            h=self.mon_full_window["height"]),
                                                        parent=self,
                                                        stop_event=self.stop_event,
                                                        hang_monitor=self.hang_monitor_controller,
                                                        config=self.config,
                                                        daemon=True
                                                        )
        self.whole_window_thandle.start()

        # UI menu start
        if self.config.show_ui:
            self.game_size = (600, 600)

            self.game_font: pygame.freetype.Font = pygame.freetype.SysFont('Arial', 48, bold=True)
            pygame.display.set_caption("Siralim Access Menu")
            self.screen = pygame.display.set_mode(self.game_size, 0, 32)
            self.screen.fill(Color.black.rgb())

            self.current_menu = self.generate_main_menu()
            self.font_surface, rect = self.game_font.render(self.current_menu.current_entry.title, fgcolor=Color.white.rgb())
        signal.signal(signal.SIGINT, self.stop_signal)

    def clear_all_matches(self):
        for match_group in self.all_found_matches.values():
            match_group.clear()

    def generate_main_menu(self) -> Menu:
        main_menu = Menu(title="Main Menu",
                         entries=[
                             MenuItem("sound list", self.show_submenu),
                             MenuItem("quit", self.stop),
        ])
        return main_menu

    def show_main_menu(self):
        main_menu = self.generate_main_menu()
        self.current_menu = main_menu
        self.font_surface, rect = self.game_font.render(self.current_menu.current_entry.title, fgcolor=Color.white.rgb())

        self.update()
        self.speak_menu_name()
        self.speak_menu_entry_name()

    def speak_menu_name(self):
        self.audio_system.speak_blocking(self.current_menu.title)

    def speak_menu_entry_name(self):
        self.audio_system.speak_nonblocking(self.current_menu.current_entry.title)

    def previous_menu_item(self):
        self.current_menu.previous_entry()
        self.speak_menu_entry_name()

    def next_menu_item(self):
        self.current_menu.next_entry()
        self.speak_menu_entry_name()

    def update(self):
        self.screen.fill(Color.black.rgb())

        menu_name_surface, rect = self.game_font.render(self.current_menu.title, fgcolor=Color.white.rgb())
        self.screen.blit(menu_name_surface, dest=(32,32))

        self.font_surface, rect = self.game_font.render(self.current_menu.current_entry.title, fgcolor=Color.white.rgb())

        text_rect = self.font_surface.get_rect(center=(self.game_size[0] / 2, self.game_size[1] / 2))
        self.screen.blit(self.font_surface, dest=text_rect)


        text_rect = self.font_surface.get_rect(center=(self.game_size[0] / 2, self.game_size[1] / 2))
        self.screen.blit(self.font_surface, dest=text_rect)
        pygame.display.update()

    def play_submenu_sound(self, sound_type: SoundType):
        self.audio_system.play_sound_demo(sound_type, play_for_seconds=0.75)


    def show_submenu(self):
        sounds = self.audio_system.get_available_sounds()
        menu_entries = [MenuItem(title=sound_type.description, fn=self.play_submenu_sound, data={'sound_type': sound_type}) for sound_type in sounds.keys()]
        menu_entries.append(MenuItem("return to main Menu", self.show_main_menu))
        submenu = Menu(title="Sound List", entries=menu_entries)
        self.current_menu = submenu
        self.update()
        self.speak_menu_name()
        self.speak_menu_entry_name()


    def stop(self):
        self.window_framegrabber_phandle.terminate()
        self.nearby_process.terminate()
        self.stop_event.set()
        self.hang_control_send.put(Shutdown())
        root.info("both should be shut down")
        self.audio_system.speak_blocking("Exitting Siralim Access")
        pygame.display.quit()
        pygame.quit()
        sys.exit()

    def stop_signal(self, signum, frame):
        root.info("main: bot should stop")
        self.stop()
        self.audio_system.speak_blocking("bot manual shutdown started")
        sys.exit(1)




    @staticmethod
    def default_grid_rect(mss_rect: Rect) -> Rect:
        tile = Bot.compute_player_position(mss_rect)

        top_left_pt = Bot.top_left_tile(aligned_floor_tile=tile, client_rect=mss_rect)
        bottom_right_pt = Bot.bottom_right_tile(aligned_tile=tile, client_rect=mss_rect)
        return Bot.compute_grid_rect(top_left_tile=top_left_pt, bottom_right_tile=bottom_right_pt)

    @staticmethod
    def compute_player_position(client_dimensions: Rect) -> Rect:
        """The top-left of the player sprite is drawn at the center of the screen (relative to window)"""

        # the player is always in the center of the window of the game
        # offset
        # #######xxxxx###
        # #######xxCxx###
        # #######xxxxx###

        return Rect(x=round(client_dimensions.w / 2), y=round(client_dimensions.h / 2),
                    w=TILE_SIZE, h=TILE_SIZE)

    @staticmethod
    def top_left_tile(aligned_floor_tile: Rect, client_rect: Rect) -> Point:

        top_left_pt = Point(x=aligned_floor_tile.x - (aligned_floor_tile.x // TILE_SIZE) * TILE_SIZE,
                            y=aligned_floor_tile.y - (aligned_floor_tile.y // TILE_SIZE) * TILE_SIZE)
        return top_left_pt

    @staticmethod
    def bottom_right_tile(aligned_tile: Rect, client_rect: Rect) -> Point:
        """Returns top-left coords of bottom-most rectangle"""

        bottom_right_pt = Point(
            x=aligned_tile.x + ((client_rect.w - aligned_tile.x) // TILE_SIZE) * TILE_SIZE - TILE_SIZE,
            y=aligned_tile.y + ((client_rect.h - aligned_tile.y) // TILE_SIZE) * TILE_SIZE - TILE_SIZE
        )
        return bottom_right_pt

    @staticmethod
    def compute_grid_rect(top_left_tile: Point, bottom_right_tile: Point) -> Rect:
        """slice of image that is occuppied by realm tiles
        Rect returns is the (x,y) coords of the top-left tile, the width and height includes the tile size of the bottom-right tile
        All useable tile pixels
        """
        width = bottom_right_tile.x - top_left_tile.x + TILE_SIZE
        height = bottom_right_tile.y - top_left_tile.y + TILE_SIZE
        return Rect(x=top_left_tile.x, y=top_left_tile.y, w=width, h=height)

    def compute_nearby_screenshot_area(self) -> Rect:
        # xxxxxxx
        # xxxxxxx
        # xxxPxxx
        # xxxxxxx
        # xxxxxxx
        #
        pixel_offset_x = round(self.su_client_rect.w / 2) % TILE_SIZE
        pixel_offset_y = round(self.su_client_rect.h / 2) % TILE_SIZE
        return Rect(
            x=pixel_offset_x + ( self.player_position_tile.x - NEARBY_TILES_WH // 2) * TILE_SIZE,
            y=pixel_offset_y + (self.player_position_tile.y - NEARBY_TILES_WH // 2) * TILE_SIZE,
            w=TILE_SIZE * NEARBY_TILES_WH,
            h=TILE_SIZE * NEARBY_TILES_WH,
        )

    def cache_images_using_phashes(self):
        with Session() as session:

            floor_ids = []
            if self.mode is BotMode.REALM:
                if not self.realm:
                    print("no realm attrib")
                    return RealmSpriteHasher()
                realm_id = session.query(RealmLookup).filter_by(enum=self.realm).one().id
                for floor in session.query(FloorSprite).filter_by(realm_id=realm_id).all():
                    for floor_tile in floor.frames:
                        floor_ids.append(floor_tile.id)
            else:
                for floor in session.query(FloorSprite).filter_by(long_name="floor_standard1").all():
                    for floor_tile in floor.frames:
                        floor_ids.append(floor_tile.id)

            realm_phashes_query = session.query(HashFrameWithFloor.phash, Sprite.short_name, Sprite.long_name, SpriteTypeLookup.name) \
                .join(SpriteFrame, SpriteFrame.id == HashFrameWithFloor.sprite_frame_id) \
                .join(Sprite, Sprite.id == SpriteFrame.sprite_id) \
                .join(SpriteTypeLookup, SpriteTypeLookup.id == Sprite.type_id) \
                .filter(HashFrameWithFloor.floor_sprite_frame_id.in_(floor_ids))

            realm_phashes = realm_phashes_query.all()
            for realm_phash, short_name, long_name, sprite_type in realm_phashes:
                img_info = ImageInfo(short_name=short_name, long_name=long_name, sprite_type=sprite_type)
                self.item_hashes[realm_phash] = img_info

    def cache_image_hashes_of_decorations(self):
        start = time.time()
        self.cache_images_using_phashes()
        end = time.time()
        root.info(f"Took {math.ceil((end - start) * 1000)}ms to retrieve {len(self.item_hashes)} phashes")

    def reinit_bot(self, new_full_window_rec: Rect):
        self.su_client_rect = new_full_window_rec
        self.player_position: Rect = Bot.compute_player_position(self.su_client_rect)

        self.player_position_tile = TileCoord(x=self.player_position.x // TILE_SIZE,
                                              y=self.player_position.y // TILE_SIZE)

        self.mon_full_window = new_full_window_rec.to_mss_dict()
        self.nearby_rect_mss: Rect = self.compute_nearby_screenshot_area()
        self.nearby_tile_top_left: TileCoord = TileCoord(x=self.nearby_rect_mss.x // TILE_SIZE,
                                                         y=self.nearby_rect_mss.y // TILE_SIZE)

        self.nearby_mon: dict = {"top": self.su_client_rect.y + self.nearby_rect_mss.y,
                                 "left": self.su_client_rect.x + self.nearby_rect_mss.x,
                                 "width": self.nearby_rect_mss.w, "height": self.nearby_rect_mss.h}

    def pause_bot(self):
        if self.paused:
            return
        self.paused = True
        self.queue_whole_analyzer_comm_send.put(Pause())
        self.nearby_send_deque.put(Pause())

    def resume_bot(self):
        self.paused = False
        self.queue_whole_analyzer_comm_send.put(Resume())
        self.nearby_send_deque.put(Resume())
        root.info("sent bot resume messages to whole and nearby")

    def check_if_window_changed_position(self):
        self.timer = time.time()
        try:
            new_su_client_rect = get_su_client_rect()
            prev_forground = self.game_is_foreground == True
            self.game_is_foreground = True
            if self.paused:
                self.resume_bot()
            if not prev_forground:
                self.resume_bot()
        except GameNotOpenException:
            self.audio_system.speak_blocking("Siralim Ultimate is no longer open")
            self.stop()
            self.audio_system.speak_blocking("Shutting down")
            return

        except GameFullscreenException:
            self.audio_system.speak_blocking("Siralim Ultimate cannot be fullscreen")
            self.stop()
            self.audio_system.speak_blocking("Shutting down")
            return
        except GameMinimizedException:
            self.pause_bot()
            return
        except GameNotForegroundException:
            self.game_is_foreground = False
            if not self.paused:
                self.audio_system.silence()
            self.pause_bot()
            return

        if new_su_client_rect != self.su_client_rect:
            print(f"SU window changed. new={new_su_client_rect}, old={self.su_client_rect}")
            self.reinit_bot(new_su_client_rect)

            self.tx_window_queue.put(WindowDim(mss_dict=self.mon_full_window))
            self.tx_nearby_process_queue.put(WindowDim(mss_dict=self.nearby_mon))

    def run(self):
        self.audio_system.speak_nonblocking("Siralim Access has started")
        self.listener.start()
        if self.config.show_ui:
            self.show_main_menu()

        iters = 0
        every = 10
        clock = pygame.time.Clock()

        self.timer = time.time()
        while True:

            # check for incoming hang messages
            try:
                msg = self.hang_alert_queue.get_nowait()
                root.warning(f"got hang alert msg = {msg=}")
                self.audio_system.speak_blocking("Bot has stopped responding. Shutting down")
                self.stop()
                sys.exit(1)

            except queue.Empty:
                pass
            if (time.time() - self.timer) > 1:
                self.check_if_window_changed_position()

            if not self.paused:
                if self.mode is BotMode.UNDETERMINED:
                    self.nearby_send_deque.put(ScanForItems())
                    if self.realm:
                        self.mode = BotMode.REALM
                elif self.mode is BotMode.REALM:
                    self.nearby_send_deque.put(ScanForItems())
                elif self.mode is BotMode.CASTLE:
                    self.nearby_send_deque.put(ScanForItems())

            if iters % every == 0:
                root.debug(f"FPS: {clock.get_fps()}")
            iters += 1

            try:
                msg = self.action_queue.get_nowait()
                if msg == "read_dialog":
                    self.whole_window_thandle.speak_interaction_info()
                elif msg == "read_menu_entry":
                    self.whole_window_thandle.speak_selected_menu_entry()
                elif msg == "read_all_info":
                    self.whole_window_thandle.speak_all_info()
                elif msg == "copy_all_info":
                    self.whole_window_thandle.copy_all_info()
            except queue.Empty:
                pass

            if self.config.show_ui:
                # pygame menu check events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.stop()
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_DOWN:
                            self.next_menu_item()
                        elif event.key == pygame.K_UP:
                            self.previous_menu_item()
                        elif event.key in [pygame.K_SPACE, pygame.K_RETURN]:
                            self.current_menu.current_entry.on_enter()
                    self.update()

            clock.tick(settings.FPS)

    def speak_nearby_objects(self):

        for tile_type, tiles in self.all_found_matches.items():
            try:
                sound_type = SoundType.from_tile_type(tile_type)
            except KeyError:
                tiles.clear()
                continue

            if not tiles:
                self.audio_system.stop(sound_type)
            else:
                if tile_type is TileType.REACHABLE_DIRECTION:
                    for tile in tiles:
                        audio_location = AudioLocation(distance=tile.point())
                        self.audio_system.play_sound(audio_location, sound_type)
                    # current_direction_points = set([t.point() for t in tiles])
                    # not_active_directions = self.all_directions - current_direction_points
                    # for point in not_active_directions:
                    #     self.audio_system.stop(sound_type, point)
                else:
                    audio_location = AudioLocation(distance=tiles[0].point())
                    self.audio_system.play_sound(audio_location, sound_type)
            tiles.clear()


class Minimized:
    pass


FrameType = Union[ArrayLike, Minimized]

class WholeWindowGrabber(multiprocessing.Process):
    def __init__(self, out_quests: Queue, outgoing_color_frame_queue: multiprocessing.Queue, screenshot_area: dict,
                 rx_queue: multiprocessing.Queue, hang_notifier: queue.Queue[HangMonitorAlert],
                 config: settings.Config,
                 **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.color_frame_queue: queue.Queue[FrameType] = outgoing_color_frame_queue
        self.out_quests: Queue = out_quests
        self.screenshot_area: dict = screenshot_area
        self.rx_parent_queue = rx_queue
        self.hang_monitor: Optional[HangMonitorWorker] = None
        self.hang_notifier = hang_notifier
        self.hang_control: Optional[queue.Queue] = None
        self.activity_notify: Optional[HangMonitorChan] = None
        self.paused: bool = False

    def run(self):
        self.hang_control = queue.Queue()
        self.hang_monitor = HangMonitorWorker(self.hang_notifier, control_port=self.hang_control)
        self.activity_notify = self.hang_monitor.register_component(threading.current_thread(), 3.0)

        try:
            should_stop = False

            with mss.mss() as sct:
                TARGET_WINDOW_CAPTURE_MS = 1 / self.config.whole_window_scanning_frequency
                while not should_stop:
                    start = time.time()
                    # check for incoming messages
                    try:
                        msg = self.rx_parent_queue.get_nowait()
                        if isinstance(msg, WindowDim):
                            msg: WindowDim
                            root.info(f"got windowgrabber newmsg = {msg=}")
                            self.screenshot_area = msg.mss_dict
                        elif isinstance(msg, Pause):
                            root.debug("Pausing capture of whole window frames")
                            self.paused = True
                            self.activity_notify.notify_wait()
                        elif isinstance(msg, Resume):
                            root.debug("Resuming capture of whole window frames")
                            self.paused = False
                    except queue.Empty:
                        pass

                    end = time.time()
                    took = end - start
                    left = TARGET_WINDOW_CAPTURE_MS - took
                    time.sleep(max(0.0, left))

                    if self.paused:
                        root.debug("whole window - skipping capture due to being paused")
                        continue

                    try:
                        self.activity_notify.notify_activity(HangAnnotation({"data": ""}))

                        # Performance: copying overhead is not an issue for needing a frame at 1-2 FPS
                        frame_np: ArrayLike = np.asarray(sct.grab(self.screenshot_area))
                        has_no_data = frame_np.shape[0] == 0 or frame_np.shape[1] == 0
                        if has_no_data:
                            root.debug("whole window frame has no data or is minimized")
                            self.color_frame_queue.put_nowait(Minimized())
                            continue
                        root.debug("Sending whole frame")
                        self.color_frame_queue.put_nowait(frame_np)
                    except queue.Full:
                        continue
        except KeyboardInterrupt:
            self.color_frame_queue.put(None, timeout=10)


class WholeWindowAnalyzer(Thread):
    def __init__(self, incoming_frame_queue: Queue, queue_child_comm_send: queue.Queue, out_quests_queue: Queue, su_client_rect: Rect, parent: Bot, stop_event: threading.Event, hang_monitor: HangMonitorWorker, config: settings.Config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.creature_data = TraitData()
        self.repeat_dialog_text: bool = False
        self.paused: bool = False
        self.config = config
        self.last_selected_text: str = ""
        self.last_dialog_text: str = ""
        # depends on text length
        self.has_menu_entry_text: bool = False
        self.menu_entry_text_repeat: bool = False
        self.has_dialog_text: bool = False
        self.parent: Bot = parent
        self.incoming_frame_queue: Queue = incoming_frame_queue
        self.queue_parent_comm_recv = queue_child_comm_send
        self.out_quests_sprites_queue: Queue = out_quests_queue
        self.stop_event = stop_event
        self._hang_monitor = hang_monitor
        self.hang_activity_sender: Optional[HangMonitorChan] = None

        self.frame: np.typing.ArrayLike = np.zeros(shape=(self.parent.su_client_rect.h, self.parent.su_client_rect.w, 3), dtype="uint8")
        self.gray_frame: np.typing.ArrayLike = np.zeros(shape=(self.parent.su_client_rect.h, self.parent.su_client_rect.w),
                                                        dtype="uint8")
        self.ocr_engine: OCR = OCR()
        self.ocr_mode: OCRMode = OCRMode.UNKNOWN
        self.ocr_ui_system: Optional[OCR_UI_SYSTEMS] = None
        self.quest_frame_scanning_interval: int = self.config.whole_window_scanning_frequency
        self.frames_since_last_scan: int = 0

    def update_quests(self, new_quests: list[Quest]):
        if len(new_quests) == 0:
            return

        new_quest_ids = set()
        for quest in new_quests:
            new_quest_ids.add(quest.id)

        if new_quest_ids == self.parent.current_quests:
            return

        self.parent.quest_sprite_long_names.clear()
        with Session() as session:
            for quest in new_quests:
                if quest.quest_type == QuestType.rescue:
                    self.parent.quest_sprite_long_names = set(sprite.long_name for sprite in session.query(NPCSprite).all())
                elif quest.quest_type == QuestType.resource_node:
                    self.parent.quest_sprite_long_names = set(sprite.long_name for sprite in session.query(ResourceNodeSprite).all())
                elif quest.quest_type == QuestType.cursed_chest:
                    self.parent.quest_sprite_long_names = set(sprite.long_name for sprite in session.query(ChestSprite).filter(ChestSprite.realm_id.is_not(None)).all())
                else:
                    for sprite in quest.sprites:
                        self.parent.quest_sprite_long_names.add(sprite.long_name)

                if not quest.supported:
                    self.parent.audio_system.speak_blocking(f"Unsupported quest: {quest.title}")

        self.parent.current_quests = new_quest_ids

    def speak_dialog_box(self):
        if not self.last_dialog_text:
            return
        root.debug(f"Speaking dialog text: {self.last_dialog_text}")

        self.parent.audio_system.speak_nonblocking(self.last_dialog_text)

    def ocr_title(self):
        mask = detect_title(self.frame)
        resize_factor = 2
        mask = cv2.resize(mask, (mask.shape[1] * resize_factor, mask.shape[0] * resize_factor), interpolation=cv2.INTER_LINEAR)
        ocr_result = self.ocr_engine.recognize_cv2_image(mask)
        detected_system = OCRMode.UNKNOWN
        try:
            title = ocr_result.merged_text
            root.debug(f"title: {title}")
            if title.startswith("Select a creature to summon"):
                detected_system = OCRMode.SUMMON
            elif title.startswith("Creatures"):
                detected_system = OCRMode.CREATURES_DISPLAY
            elif title.startswith("Choose the Avatar"):
                detected_system = OCRMode.SELECT_GODFORGE_AVATAR
            elif title.startswith("Choose the creature whose position"):
                detected_system = OCRMode.CREATURE_REORDER_SELECT
            elif title.startswith("Choose a creature to swap"):
                detected_system = OCRMode.CREATURE_REORDER_WITH
        except IndexError:
            pass

        if detected_system != self.ocr_mode:
            root.debug(f"new ocr system: {detected_system}")
            if detected_system is OCRMode.SUMMON:
                self.ocr_ui_system = OcrSummoningSystem(self.creature_data, self.parent.audio_system, self.config, self.ocr_engine)
            elif detected_system is OCRMode.CREATURES_DISPLAY:
                self.ocr_ui_system = OCRCreaturesDisplaySystem(self.creature_data, self.parent.audio_system, self.config, self.ocr_engine)
            elif detected_system is OCRMode.UNKNOWN:
                self.ocr_mode = OCRMode.UNKNOWN
                self.ocr_ui_system = None
            elif detected_system is OCRMode.SELECT_GODFORGE_AVATAR:
                self.ocr_ui_system = OCRGodForgeSelectSystem(audio_system=self.parent.audio_system, config=self.config, ocr_engine=self.ocr_engine)
            elif detected_system is OCRMode.CREATURE_REORDER_SELECT:
                self.ocr_ui_system = OCRCreatureRecorderSelectFirst(audio_system=self.parent.audio_system, config=self.config, ocr_engine=self.ocr_engine)
            elif detected_system is OCRMode.CREATURE_REORDER_WITH:
                self.ocr_ui_system = OCRCreatureRecorderSwapWith(audio_system=self.parent.audio_system, config=self.config, ocr_engine=self.ocr_engine)
        self.ocr_mode = detected_system

    def speak_interaction_info(self):
        if not self.ocr_ui_system:
            self.speak_dialog_box()
        elif isinstance(self.ocr_ui_system, OcrSummoningSystem):
            self.ocr_ui_system.speak_interaction()

    def ocr_screen(self):
        self.ocr_title()
        if self.ocr_mode is OCRMode.SUMMON or self.ocr_mode is OCRMode.CREATURES_DISPLAY:
            self.ocr_ui_system.ocr(self.frame, self.gray_frame)
            self.ocr_ui_system.speak_auto()
            return
        elif self.ocr_mode == OCRMode.SELECT_GODFORGE_AVATAR:
            self.ocr_ui_system.ocr(self.frame)
            self.ocr_ui_system.speak_auto()
        elif self.ocr_mode == OCRMode.CREATURE_REORDER_SELECT:
            self.ocr_ui_system.ocr(self.frame)
            self.ocr_ui_system.speak_auto()
        elif self.ocr_mode == OCRMode.CREATURE_REORDER_WITH:
            self.ocr_ui_system.ocr(self.frame)
            self.ocr_ui_system.speak_auto()
        elif self.ocr_mode is OCRMode.UNKNOWN:
            if self.config.ocr_selected_menu_item:
                # menu entry selection is latency sensitive, so we do this first
                start = time.time()
                self.read_selected_menu_item()
                end = time.time()
                took_ms = math.ceil((end - start) * 1000)
                root.debug(f"OCR of menu entry took {took_ms}ms")

            if self.config.ocr_read_dialog_boxes:
                self.ocr_dialog_box()

            if self.has_menu_entry_text and not self.menu_entry_text_repeat:
                self.speak_selected_menu_entry()
            if self.last_dialog_text and not self.has_menu_entry_text and not self.repeat_dialog_text:
                self.speak_dialog_box()


            menu_selection_or_dialog_text_present = self.last_selected_text or self.last_dialog_text
            if not menu_selection_or_dialog_text_present:
                root.debug("Pausing due to no menu selection or dialog text present on screen")
                self.parent.audio_system.silence()

    def ocr_dialog_box(self):
        mask = detect_dialog_text(self.frame)
        resize_factor = 2
        mask = cv2.resize(mask, (mask.shape[1] * resize_factor, mask.shape[0] * resize_factor), interpolation=cv2.INTER_LINEAR)
        ocr_result = self.ocr_engine.recognize_cv2_image(mask)
        try:
            first_line = ocr_result.lines[0]
            first_word = first_line.words[0]
            bbox = first_word.bounding_rect
            root.debug(f"dialog box: {ocr_result.text}")

            # health bar text - rect(69, 87, 73, 16), rect(282, 87, 71, 16)
            # dialog box text - rect(14, 23, 75, 16)

            offset_x = mask.shape[0] * 0.40
            root.debug(f"{offset_x=}")
            is_not_dialog_box = bbox.x > offset_x
            root.debug(f"{is_not_dialog_box=}")
            if is_not_dialog_box and not self.has_menu_entry_text:
                self.last_dialog_text = ""
                return
        except IndexError:
            root.debug("no dialog text")
            # no text was found
            self.last_dialog_text = ""
            if not self.has_menu_entry_text and not self.has_dialog_text:
                root.debug("Pause, menu system. both not present")
                self.parent.audio_system.silence()
            self.has_dialog_text = False
            return

        selected_text = ocr_result.merged_text
        self.repeat_dialog_text = False
        # don't count no text at all as dialog text
        if selected_text == "":
            self.has_dialog_text = False
            return
        if selected_text == self.last_dialog_text:
            self.repeat_dialog_text = True
        self.last_dialog_text = selected_text

        if is_not_dialog_box:
            return

        root.debug(f"dialog box text = {selected_text}")
        self.has_dialog_text = True


    def read_selected_menu_item(self):
        mask = detect_green_text(self.frame)
        # remove non-font green pixels
        start_blur_time = time.time()
        blurred = cv2.medianBlur(mask, 3)
        end_blur_time = time.time()
        root.debug(f"blurring took {math.ceil((end_blur_time-start_blur_time)*1000)}ms")
        x,y,w,h = cv2.boundingRect(blurred)

        no_match = w == 0 or h == 0
        if no_match:
            self.last_selected_text = ""
            self.has_menu_entry_text = False
            return

        # padding around font is used to improve OCR output
        padding = 16

        # don't go out of bounds
        y_start = max(y-padding, 0)
        y_end = min(y + h + padding, mask.shape[0])
        x_start = max(x-padding, 0)
        x_end = min(x + w + padding,mask.shape[1])

        roi = mask[y_start:y_end, x_start:x_end]
        # only resize if image capture area likely contains a single section of text (saves CPU)
        if roi.shape[0] < 400 or roi.shape[1] < 400:
            roi = cv2.resize(roi, (roi.shape[1]*2, roi.shape[0]*2), interpolation=cv2.INTER_LINEAR)

        ocr_result = self.ocr_engine.recognize_cv2_image(roi)
        selected_text = ocr_result.merged_text
        self.menu_entry_text_repeat = False


        # don't repeat announcing the same or no text at all
        if selected_text == "":
            self.has_menu_entry_text = False
            return
        elif selected_text == self.last_selected_text:
            self.menu_entry_text_repeat = True

        self.has_menu_entry_text = True
        self.last_selected_text = selected_text

        # # SAPI speech rates
        # # https://stackoverflow.com/a/42819466
        # SPEECH_RATES = {
        #     -10: 1.50,
        #     -9: 1.45,
        #     -8: 1.40,
        #     -7: 1.35,
        #     -6: 1.30,
        #     -5: 1.25,
        #     -4: 1.20,
        #     -3: 1.15,
        #     -2: 1.10,
        #     -1: 1.05,
        #     0: 1.00,
        #     1: 0.9,
        #     2: 0.85,
        #     3: 0.8,
        #     4: 0.7,
        #     5: 0.65,
        #     6: 0.55,
        #     7: 0.50,
        #     8: 0.40,
        #     9: 0.35,
        #     10: 0.25
        # }

        # self.last_selected_text = selected_text

    def extract_quest_name_from_quest_area(self, gray_frame: np.typing.ArrayLike) -> list[Quest]:
        """

        :param gray_frame: greyscale full-windowed frame that the bot captured
        :return: List of quests that appeared in the quest area. an empty list is returned if no quests were found
        """
        quests: list[Quest] = []
        y_text_dim = int(gray_frame.shape[0] * 0.33)
        x_text_dim = int(gray_frame.shape[1] * 0.33)
        quest_area = gray_frame[:y_text_dim, -x_text_dim:]
        thresh, threshold_white = cv2.threshold(quest_area, 215, 255, cv2.THRESH_BINARY_INV)

        text = self.ocr_engine.recognize_cv2_image(threshold_white)

        # see if any lines match a quest title
        with Session() as session:
            for line_info in text.lines:
                line_text = line_info.merged_text
                if quest_obj := session.query(Quest).filter_by(title_first_line=line_text).first():
                    quests.append(quest_obj)
        return quests

    def run(self):
        self.hang_activity_sender = self._hang_monitor.register_component(thread_handle=self, hang_timeout_seconds=10)
        while not self.stop_event.is_set():

            try:
                comm_msg = self.queue_parent_comm_recv.get_nowait()
                if isinstance(comm_msg, Pause):
                    self.paused = True
                    self.hang_activity_sender.notify_wait()
                    root.info("pause. Pause request")
                    self.parent.tx_window_queue.put(Pause())
                    clear_queue(self.incoming_frame_queue)
                    continue

                elif isinstance(comm_msg, Resume):
                    self.paused = False
                    self.parent.tx_window_queue.put(Resume())
            except queue.Empty:
                pass

            if self.paused:
                sleep_duration = 1/self.config.whole_window_scanning_frequency
                time.sleep(sleep_duration)
                root.debug(f"main analyzer sleeping for {sleep_duration} seconds")
                continue

            try:
                msg = self.incoming_frame_queue.get(timeout=5)
                self.hang_activity_sender.notify_activity(HangAnnotation(data={"data": "window analyze"}))
                if msg is None:
                    break
                if isinstance(msg, Minimized):
                    self.paused = True
                    continue

                shot = msg
            except queue.Empty:
                # is it empty because stuff is shut down?
                if self.stop_event.is_set():
                    return
                if self.paused:
                    self.hang_activity_sender.notify_wait()
                    continue

                # something is wrong
                raise Exception("No new full frame for 5 seconds")
            if shot is None:
                break

            self.frame = np.asarray(shot)[:,:, :3]
            cv2.cvtColor(self.frame, cv2.COLOR_BGRA2GRAY, dst=self.gray_frame)
            self.frames_since_last_scan += 1

            self.ocr_screen()

            if self.frames_since_last_scan >= self.quest_frame_scanning_interval:
                self.frames_since_last_scan = 0
                quests = self.extract_quest_name_from_quest_area(self.gray_frame)
                current_quests = [quest.title for quest in quests]
                quest_items = [sprite.long_name for quest in quests for sprite in quest.sprites]
                root.debug(f"quests = {current_quests}")
                root.debug(f"quest items = {quest_items}")

                self.update_quests(quests)
            self.parent.last_key_pressed = None

        root.info("WindowAnalyzer thread shutting down")

    def speak_selected_menu_entry(self):
        notify_dialog_text = ""
        if self.has_dialog_text:
            notify_dialog_text = f"\npress {self.config.read_dialog_key} to here dialog box"
        menu_text = f"{self.last_selected_text}{notify_dialog_text}"
        root.debug(f"speaking menu text: {menu_text}")
        self.parent.audio_system.speak_nonblocking(menu_text)

    def speak_all_info(self):
        if isinstance(self.ocr_ui_system, OcrSummoningSystem):
            self.ocr_ui_system.speak_detailed()

    def copy_all_info(self):
        if isinstance(self.ocr_ui_system, OcrSummoningSystem):
            self.ocr_ui_system.copy_detailed_text()


class NearbyFrameGrabber(multiprocessing.Process):
    def __init__(self, nearby_queue: multiprocessing.Queue, rx_parent: multiprocessing.Queue,
                 hang_notifier: queue.Queue[HangMonitorAlert],
                 nearby_area: dict = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.color_nearby_queue: multiprocessing.Queue = nearby_queue
        self.nearby_area = nearby_area
        self.rx_parent = rx_parent
        self.hang_monitor: Optional[HangMonitorWorker] = None
        self.hang_notifier = hang_notifier
        self.hang_control: Optional[queue.Queue] = None
        self.activity_notify: Optional[HangMonitorChan] = None
        self.paused: bool = False


    def run(self):
        """Screenshots the area defined as nearby the player. no more than 8x8 tiles (256pxx256px)
        :param color_nearby_queue Queue used to send recent nearby screenshot to processing code
        :param nearby_rect dict used in mss.grab. keys `top`, `left`, `width`, `height`
        """
        self.hang_control = queue.Queue()
        self.hang_monitor = HangMonitorWorker(self.hang_notifier, control_port=self.hang_control)
        self.activity_notify = self.hang_monitor.register_component(threading.current_thread(), 3.0)

        TARGET_MS = 1 / settings.FPS

        try:
            should_stop = False
            with mss.mss() as sct:
                while not should_stop:

                    try:
                        msg = self.rx_parent.get_nowait()
                        if isinstance(msg, WindowDim):
                            msg: WindowDim
                            print(f"updated nearbyframeGrabber rect. new={msg.mss_dict} old={self.nearby_area}")
                            self.nearby_area = msg.mss_dict
                        elif isinstance(msg, Pause):
                            root.debug("nearby got pause message. Pause grabbing frames")
                            self.paused = True
                            self.color_nearby_queue.put(Pause())
                        elif isinstance(msg, Resume):
                            root.debug("nearby got resume message. Resume grabbing frames")
                            self.paused = False
                            self.color_nearby_queue.put(Resume())

                    except queue.Empty:
                        pass

                    if self.paused:
                        time.sleep(TARGET_MS)
                        continue

                    start = time.time()
                    # Performance: Unsure if 1MB copying at 60FPS is fine
                    # Note: Possibly use shared memory if performance is an issue
                    try:
                        nearby_shot_np: ArrayLike = np.asarray(sct.grab(self.nearby_area))
                        has_no_data = nearby_shot_np.shape[0] == 0 or nearby_shot_np.shape[1] == 0
                        if has_no_data:
                            print("no nearby frame data")
                            self.color_nearby_queue.put(Minimized())
                            continue

                        root.debug("Sending new nearby frame")
                        self.color_nearby_queue.put(NewFrame(nearby_shot_np), timeout=10)
                    except queue.Full:
                        root.debug("color nearby queue full")
                        pass

                    end = time.time()
                    took = end - start
                    left = TARGET_MS - took
                    time.sleep(max(0, left))
                    continue
        except KeyboardInterrupt:
            self.color_nearby_queue.put(None)


@dataclass()
class RealmAlignment:
    """Tells the realm detected"""
    realm: Realm


@dataclass()
class CastleAlignment:
    pass


class NearPlayerProcessing(Thread):
    def __init__(self, nearby_frame_queue: multiprocessing.Queue, nearby_comm_deque: queue.Queue, parent: Bot, stop_event: threading.Event,hang_monitor: HangMonitorWorker, **kwargs):
        super().__init__(**kwargs)

        self.map = Map(arr=np.zeros((NEARBY_TILES_WH, NEARBY_TILES_WH), dtype='object'))
        self._hang_monitor: HangMonitorWorker = hang_monitor
        self.hang_activity_sender: Optional[HangMonitorChan] = None

        self.parent = parent
        # used for multiprocess communication
        self.nearby_queue = nearby_frame_queue

        # Used for across thread communication
        self.nearby_comm_deque = nearby_comm_deque
        self.stop_event = stop_event

        self.near_frame_color: np.typing.ArrayLike = np.zeros(
            (NEARBY_TILES_WH * TILE_SIZE, NEARBY_TILES_WH * TILE_SIZE, 3), dtype='uint8')
        self.near_frame_gray: np.typing.ArrayLike = np.zeros((NEARBY_TILES_WH * TILE_SIZE, NEARBY_TILES_WH * TILE_SIZE),
                                                             dtype='uint8')

        self.grid_near_rect: Optional[Rect] = parent.nearby_rect_mss

        # The current active quests
        self.active_quests: list[Quest] = []

        self.was_match: bool = False
        self.match_streak: int = 0
        self.last_match_time: float = time.time()
        self.paused: bool = False

    def bfs_near(self) -> Optional[FloorInfo]:
        DIRECTIONS: list[Movement] = [Movement(x=1, y=0), Movement(x=-1, y=0), Movement(x=0, y=1), Movement(x=0, y=-1)]
        queue: deque[Point] = deque()
        marked: set[Point] = set()

        x_tiles = self.grid_near_rect.w // TILE_SIZE
        y_tiles = self.grid_near_rect.h // TILE_SIZE

        center = Point(x=x_tiles // 2, y=y_tiles//2)
        def can_visit(point: Point, marked: set[Point]) -> bool:
            if point in marked:
                return False

            past_tiles_to_search = center.x - point.x >= 4 or center.y - point.y >= 4
            if past_tiles_to_search:
                return False
            out_of_bounds = point.x < 0 or point.x >= x_tiles or point.y < 0 or point.y >= y_tiles
            if out_of_bounds:
                return False

            return True

        queue.append(center)

        while queue:
            node = queue.popleft()
            start_x = node.x * TILE_SIZE
            start_y = node.y * TILE_SIZE
            tile_gray = self.near_frame_gray[start_y:start_y + TILE_SIZE, start_x:start_x + TILE_SIZE]
            try:
                computed_hash = compute_hash(tile_gray[:TILE_SIZE, :TILE_SIZE])
                floor_info = self.parent.floor_hashes[computed_hash]
                return floor_info
            except KeyError:
                pass

            for direction in DIRECTIONS:
                new_point = Point(x=node.x + direction.x, y=node.y + direction.y)
                if can_visit(new_point, marked):
                    queue.append(new_point)
                marked.add(new_point)

    def detect_what_realm_in(self) -> Optional[Union[RealmAlignment, CastleAlignment]]:

        # Scan the nearby tile area for lit tiles to determine what realm we are in currently
        # This area was chosen since the player + 6 creatures are at most this long
        # At least 1 tile will not be dimmed by the fog of war

        floor_type = self.bfs_near()
        if not floor_type:
            return

        if not floor_type.realm:
            return CastleAlignment()

        return RealmAlignment(realm=floor_type.realm)

    def exclude_from_debug(self, img_info: ImageInfo):
        s = img_info.long_name
        if img_info.sprite_type is SpriteType.FLOOR:
            return True
        elif img_info.sprite_type is SpriteType.WALL:
            return True
        elif s == "bck_FOW_Tile":
            return True
        else:
            return False

    def draw_debug(self, start_point, end_point, tile_type: TileType, text: str):
        debug_img = self.near_frame_color
        if tile_type.color:
            cv2.rectangle(debug_img, start_point, end_point, tile_type.color.value, -1)
            cv2.putText(debug_img, text, start_point, cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255))

    def identify_type(self, img_info: ImageInfo, asset_location: AssetGridLoc) -> TileType:
        if img_info.long_name == "bck_FOW_Tile":
            return TileType.BLACK

        elif img_info.long_name in self.parent.quest_sprite_long_names:
            return TileType.QUEST
        elif img_info.long_name in self.parent.teleportation_shrine_names:
            return TileType.TELEPORTATION_SHRINE

        elif img_info.sprite_type is SpriteType.MASTER_NPC:
            return TileType.MASTER_NPC
        elif img_info.sprite_type is SpriteType.ALTAR:
            return TileType.ALTAR
        elif img_info.sprite_type is SpriteType.PROJ_ITEM:
            return TileType.PROJECT_ITEM
        elif img_info.sprite_type is SpriteType.NPC:
            return TileType.NPC
        elif img_info.sprite_type is SpriteType.WALL:
            return TileType.WALL
        elif img_info.sprite_type is SpriteType.FLOOR:
            return TileType.FLOOR
        elif img_info.sprite_type is SpriteType.CHEST:
            return TileType.CHEST
        elif img_info.long_name == "netherportal":
            return TileType.NETHER_PORTAL
        elif img_info.long_name == "summoningbrazier":
            return TileType.SUMMONING
        else:
            return TileType.DECORATION

    def scan_for_items(self):
        """Scans for decorations and quests in the castle"""
        max_stationary_streak = 60 * self.parent.config.required_stationary_seconds
        if not self.parent.config.repeat_sound_when_stationary and self.match_streak >= max_stationary_streak:
            self.parent.clear_all_matches()
            self.parent.speak_nearby_objects()
            return

        self.map.clear()
        self.map.player_direction = self.parent.player_direction
        self.map.set_center(Point(x=self.grid_near_rect.w//TILE_SIZE//2, y=self.grid_near_rect.h//TILE_SIZE//2))

        for row in range(0, self.grid_near_rect.w, TILE_SIZE):
            for col in range(0, self.grid_near_rect.h, TILE_SIZE):
                tile_gray = self.near_frame_gray[col:col + TILE_SIZE, row:row + TILE_SIZE]
                start_point = (row + self.grid_near_rect.x, col + self.grid_near_rect.y)
                end_point = (start_point[0] + TILE_SIZE, start_point[1] + TILE_SIZE)
                asset_location = AssetGridLoc(
                    x=self.parent.nearby_tile_top_left.x + row // TILE_SIZE - self.parent.player_position_tile.x,
                    y=self.parent.nearby_tile_top_left.y + col // TILE_SIZE - self.parent.player_position_tile.y,
                )
                if asset_location.point() == Point(0,0):
                    self.map.set(asset_location.point(), TileType.PLAYER)
                    continue

                try:
                    img_info = self.parent.item_hashes.get_greyscale(tile_gray[:TILE_SIZE, :TILE_SIZE])

                    tile_type = self.identify_type(img_info, asset_location)
                    if not self.exclude_from_debug(img_info):
                        root.debug(f"matched: {img_info.long_name} - asset location = {asset_location.point()}, {tile_type}")
                    if settings.DEBUG:
                        self.draw_debug(start_point, end_point, tile_type, "")
                    self.parent.all_found_matches[tile_type].append(asset_location)

                    self.map.set(asset_location.point(), tile_type)

                except KeyError:
                    self.map.set(asset_location.point(), TileType.UNKNOWN)
        start = time.time()
        self.map.find_reachable_blocks()
        try:
            for point in self.map.adj_list[TileType.BLACK].keys():
                self.parent.all_found_matches[TileType.REACHABLE_BLACK].append(AssetGridLoc(x=point.x, y=point.y))
        except KeyError:
            pass

        try:
            last_key_pressed = self.parent.last_key_pressed
            for point in self.map.adj_list[TileType.REACHABLE_DIRECTION].keys():
                # if last_key_pressed == "j" or last_key_pressed == "l" and point == Point(0, 1) or point == Point(0, -1):
                self.parent.all_found_matches[TileType.REACHABLE_DIRECTION].append(AssetGridLoc(x=point.x, y=point.y))
        except KeyError:
            pass

        end = time.time()
        root.debug(f"reachable took {(end-start)*1000}ms to complete")
        self.parent.speak_nearby_objects()

    def handle_realm_alignment(self, realm_alignment: Optional[Union[RealmAlignment, CastleAlignment]]):
        if not realm_alignment:
            self.match_streak = 0
            if time.time() - self.last_match_time >= 1/15 * 4:
                self.parent.clear_all_matches()
                self.parent.speak_nearby_objects()
            return
        else:
            self.was_match = True
            self.match_streak += 1
            self.last_match_time = time.time()

        if isinstance(realm_alignment, CastleAlignment):
            if self.parent.mode is BotMode.CASTLE:
                return

            self.parent.mode = BotMode.CASTLE
            self.parent.realm = None

            self.parent.item_hashes = RealmSpriteHasher(floor_tiles=None)
            start = time.time()
            self.parent.cache_image_hashes_of_decorations()
            end = time.time()
            root.debug(f"Took {math.ceil((end - start) * 1000)}ms to retrieve {len(self.parent.item_hashes)} phashes")

            root.info(f"castle entered")
            root.info(f"new realm alignment = {realm_alignment=}")
            return

        elif isinstance(realm_alignment, RealmAlignment):
            self.parent.mode = BotMode.REALM
            if realm_alignment.realm != self.parent.realm:
                new_realm = realm_alignment.realm
                if new_realm in models.UNSUPPORTED_REALMS:
                    self.parent.audio_system.speak_blocking(f"Realm unsupported. {new_realm.realm_name}")
                self.parent.realm = realm_alignment.realm

                self.parent.item_hashes = RealmSpriteHasher(floor_tiles=None)
                start = time.time()
                self.hang_activity_sender.notify_activity(HangAnnotation({"data": "get new phashes"}))
                self.parent.cache_image_hashes_of_decorations()
                end = time.time()
                print(
                    f"Took {math.ceil((end - start) * 1000)}ms to retrieve {len(self.parent.item_hashes)} phashes")

                root.info(f"new realm entered: {self.parent.realm.name}")
                root.info(f"new realm alignment = {realm_alignment.realm.name}")
                print(f"new item hashes = {len(self.parent.item_hashes)}")

    def handle_new_frame(self, data: NewFrame):
        self.near_frame_color = data.frame
        if settings.DEBUG:
            self.near_frame_color = self.near_frame_color.copy()

        # make grayscale version
        cv2.cvtColor(self.near_frame_color, cv2.COLOR_BGRA2GRAY, dst=self.near_frame_gray)
        self.grid_near_rect = Bot.default_grid_rect(self.parent.nearby_rect_mss)

        if self.paused:
            return


        realm_alignment = self.detect_what_realm_in()
        self.handle_realm_alignment(realm_alignment)

    def handle_scan_for_item(self):
        start = time.time()
        if self.was_match:
            self.scan_for_items()
        end = time.time()
        latency = end - start
        root.debug(f"realm scanning took {math.ceil(latency * 1000)}ms")

    def run(self):
        self.hang_activity_sender = self._hang_monitor.register_component(self, hang_timeout_seconds=10.0)
        if settings.VIEWER:
            debug_window = cv2.namedWindow("Siralim Access", cv2.WINDOW_KEEPRATIO)

        while not self.stop_event.is_set():

            try:
                # we don't block since we must be ready for new incoming frames ^^
                comm_msg: MessageImpl = self.nearby_comm_deque.get_nowait()

                if isinstance(comm_msg, ScanForItems):
                    self.handle_scan_for_item()
                elif isinstance(comm_msg, Pause):
                    self.paused = True
                    self.parent.tx_nearby_process_queue.put(Pause())
                    self.hang_activity_sender.notify_wait()
                    self.parent.clear_all_matches()
                    self.parent.speak_nearby_objects()
                    clear_queue(self.nearby_queue)
                    root.debug("paused nearby analysis")

                elif isinstance(comm_msg, Resume):
                    self.paused = False
                    self.parent.tx_nearby_process_queue.put(Resume())
                    root.debug("resuming nearby")

                if settings.VIEWER:
                    cv2.imshow("Siralim Access", self.map.img)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        cv2.destroyAllWindows()
                        break
            except queue.Empty:
                pass

            if self.paused:
                root.debug("sleeping nearby analyzer due to being paused")
                time.sleep(1/settings.FPS)
                continue

            try:
                msg: MessageImpl = self.nearby_queue.get(timeout=5)
            except queue.Empty:
                empty_text = "No nearby frame for 5 seconds"
                root.warning(empty_text)
                raise Exception(empty_text)

            self.hang_activity_sender.notify_activity(HangAnnotation({"event": "near_frame_processing"}))
            if msg is None:
                return
            start = time.time()
            if isinstance(msg, NewFrame):
                self.handle_new_frame(msg)
            end = time.time()
            latency = end - start
            root.debug(f"realm scanning took {math.ceil(latency * 1000)}ms")
        root.info(f"{self.name} is shutting down")


def version_check(config, audio_system):
    current_version = semantic_version.Version(read_version())
    try:
        resp = requests.get("https://raw.githubusercontent.com/gurgalex/SiralimAccess/main/VERSION")
    except requests.exceptions.ConnectionError as e:
        root.info("skipping version check due to connection error")
        return

    if resp.status_code != 200:
        return
    latest_version = semantic_version.Version(resp.text)
    if current_version >= latest_version:
        return

    audio_system.speak_nonblocking(f"new version available. {resp.text}.\n Your version: {current_version}")
    if config.update_popup_browser:
        webbrowser.open("https://github.com/gurgalex/SiralimAccess/releases/latest")


def init_bot() -> Bot:
    config = settings.load_config()
    audio_system = AudioSystem(config)
    if not english_installed():
        audio_system.speak_blocking(ocr.ENGLISH_NOT_INSTALLED_EXCEPTION.args[0])
        root.error(ocr.ENGLISH_NOT_INSTALLED_EXCEPTION.args[0])
        audio_system.speak_blocking("Shutting down")
        sys.exit(1)
    version_check(config, audio_system)
    is_minimized = True
    while is_minimized:
        try:
            bot = Bot(audio_system=audio_system, config=config)
            root.debug("Siralim ultimate is not minimized")
            return bot
        except GameMinimizedException:
            root.info("Siralim Ultimate is minimized, waiting")
            time.sleep(1)
        except GameNotForegroundException:
            root.info("Siralim Ultimate is not in foreground, waiting")
            time.sleep(1)


def start_bot():
    bot = init_bot()
    bot.run()


if __name__ == "__main__":
    sentry_sdk.init(
        "https://90ff6a25ab444640becc5ab6a9e35d56@o914707.ingest.sentry.io/5855592",
        traces_sample_rate=1.0,
        before_send=before_send,
    )

    root.info(f"Siralim Access version = {read_version()}")

    try:
        start_bot()
    except KeyboardInterrupt:
        pass
