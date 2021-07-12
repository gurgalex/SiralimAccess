import sys
import signal
import threading

import sentry_sdk

import enum
import logging
import multiprocessing
from collections import deque
import queue
from logging.handlers import QueueHandler, QueueListener
from multiprocessing import Queue
from pathlib import Path
from threading import Thread
from typing import Optional, Union, Any
from subot.hang_monitor import HangMonitorWorker, HangMonitorChan, HangAnnotation, HangMonitorAlert

import cv2
import numpy as np
import mss
import pygame
import win32gui
import pytesseract
import math
import time
from sqlalchemy.orm import joinedload

from subot.audio import AudioSystem, AudioLocation, SoundType
from subot.datatypes import Rect
from subot.messageTypes import NewFrame, MessageImpl, MessageType, CheckWhatRealmIn, WindowDim, ConfigMsg, Shutdown
from subot.read_tags import Asset

from numpy.typing import ArrayLike

from subot.hash_image import ImageInfo, RealmSpriteHasher, FloorTilesInfo, Overlay

from dataclasses import dataclass

from subot.models import Sprite, SpriteFrame, Quest, FloorSprite, Realm, RealmLookup, AltarSprite, \
    ProjectItemSprite, NPCSprite, OverlaySprite, HashFrameWithFloor, MasterNPCSprite, QuestType
from subot.models import Session
import subot.settings as settings

from readerwriterlock import rwlock

from subot.utils import Point
import traceback

def before_send(event, hint):
    event["extra"]["exception"] = ["".join(
        traceback.format_exception(*hint["exc_info"])
    )]
    return event

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'

# BGR colors
blue = (255, 0, 0)
purple = (255, 0, 255)
green = (0, 255, 0)
red = (0, 0, 255)
yellow = (0, 255, 255)
orange = (0, 215, 255)

TILE_SIZE = 32
NEARBY_TILES_WH: int = 13

title = "SU Vision"


@dataclass(frozen=True)
class TemplateMeta:
    name: str
    data: np.typing.ArrayLike
    color: tuple
    mask: np.typing.ArrayLike


class GameNotOpenException(Exception):
    pass

class GameFullscreenException(Exception):
    pass

def get_su_client_rect() -> Rect:
    """Returns Rect class of the Siralim Ultimate window. Coordinates are without title bar and borders
    :raises GameNotOpenException if the game is not open
    """
    su_hwnd = win32gui.FindWindow(None, "Siralim Ultimate")
    su_is_open = su_hwnd > 0
    if not su_is_open:
        raise GameNotOpenException("Siralim Ultimate is not open")
    root.debug(f"{su_hwnd=}")
    rect = win32gui.GetWindowRect(su_hwnd)

    clientRect = win32gui.GetClientRect(su_hwnd)
    windowOffset = math.floor(((rect[2] - rect[0]) - clientRect[2]) / 2)
    titleOffset = ((rect[3] - rect[1]) - clientRect[3]) - windowOffset
    newRect = (rect[0] + windowOffset, rect[1] + titleOffset, rect[2] - windowOffset, rect[3] - windowOffset)


    window_rect = Rect(x=newRect[0], y=newRect[1], w=newRect[2] - newRect[0], h=newRect[3] - newRect[1])
    if window_rect.w == 0 or window_rect.h == 0:
        raise GameFullscreenException("game is fullscreen")

    return window_rect



DOWNSCALE_FACTOR = 4

color = blue


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


@dataclass(frozen=True)
class AssetGridLoc:
    """Tile coordinate relative to player + game asset name on map"""
    x: int
    y: int
    short_name: str

    def point(self) -> Point:
        return Point(x=self.x, y=self.y)


def extract_quest_name_from_quest_area(gray_frame: np.typing.ArrayLike) -> list[Quest]:
    """

    :param gray_frame: greyscale full-windowed frame that the bot captured
    :return: List of quests that appeared in the quest area. an empty list is returned if no quests were found
    """
    quests: list[Quest] = []
    y_text_dim = int(gray_frame.shape[0] * 0.33)
    x_text_dim = int(gray_frame.shape[1] * 0.33)
    thresh, threshold_white = cv2.threshold(gray_frame[:y_text_dim, -x_text_dim:], 220, 255, cv2.THRESH_BINARY_INV)
    text = pytesseract.pytesseract.image_to_string(threshold_white, lang="eng")
    quest_text_lines = [line.strip() for line in text.split("\n")]

    # see if any lines match a quest title
    with Session() as session:
        for quest_first_line in quest_text_lines:
            if quest_obj := session.query(Quest).filter_by(title_first_line=quest_first_line).first():
                quests.append(quest_obj)
    return quests


class GridType(enum.Enum):
    WHOLE = enum.auto()
    NEARBY = enum.auto()


def recompute_grid_offset(floor_tile: ArrayLike, gray_frame: ArrayLike, mss_rect: Rect) -> Optional[Rect]:
    # find matching realm tile on map
    # We use matchTemplate since the grid shifts when the player is moving
    # (the tiles smoothly slide to the next `TILE_SIZE increment)

    res = cv2.matchTemplate(gray_frame, floor_tile, cv2.TM_SQDIFF)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    threshold = 1 / 16
    if min_val > threshold:
        return
    tile = Rect.from_cv2_loc(min_loc, w=TILE_SIZE, h=TILE_SIZE)

    top_left_pt = Bot.top_left_tile(aligned_floor_tile=tile, client_rect=mss_rect)
    bottom_right_pt = Bot.bottom_right_tile(aligned_tile=tile, client_rect=mss_rect)
    return Bot.compute_grid_rect(top_left_tile=top_left_pt, bottom_right_tile=bottom_right_pt)


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


class Bot:
    def __init__(self):
        # queue to monitor for incoming hang alert
        self.hang_alert_queue = multiprocessing.Queue()
        self.hang_control_send = multiprocessing.Queue()
        self.hang_monitor_controller = HangMonitorWorker(daemon=True,
                                                         hang_notify_queue=self.hang_alert_queue, control_port=self.hang_control_send)
        self.hang_monitor_controller.start()

        self.current_quests: set[int] = set()
        signal.signal(signal.SIGINT, self.stop_signal)
        self.timer = None
        self.tx_nearby_process_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=10)
        self.teleportation_shrine_names: set[str] = {'bigroomchanger', 'teleshrine_inactive'}
        self.teleportation_shrine_location: Optional[AssetGridLoc] = None

        self.npc_normal_locations: list[AssetGridLoc] = []
        self.project_item_locations: list[AssetGridLoc] = []
        with Session() as session:
            altar_names_results: list[tuple] = session.query(AltarSprite).with_entities(AltarSprite.long_name).all()
            self.altars: set[str] = set(result[0] for result in altar_names_results)

            npc_name_results: list[tuple] = session.query(ProjectItemSprite).with_entities(
                ProjectItemSprite.long_name).all()
            self.project_items: set[str] = set(result[0] for result in npc_name_results)

            npc_name_results: list[tuple] = session.query(NPCSprite).with_entities(NPCSprite.long_name).all()
            self.npc_normals: set[str] = set(result[0] for result in npc_name_results)

            master_name_results: list[tuple] = session.query(MasterNPCSprite).with_entities(
                MasterNPCSprite.long_name).all()
            self.masters: set[str] = set(result[0] for result in master_name_results)

        pygame.init()
        self.audio_system: AudioSystem = AudioSystem()

        self.color_frame_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)
        self.out_quests: multiprocessing.Queue = multiprocessing.Queue()
        self.rx_color_nearby_queue = multiprocessing.Queue(maxsize=1)

        # queues for communicaitng with WindowGrabber and NearbyGrabber
        self.rx_queue = multiprocessing.Queue(maxsize=100)
        self.tx_window_queue = multiprocessing.Queue(maxsize=100)


        self.nearby_send_deque = deque(maxlen=10)
        self.quest_sprite_long_names: set[str] = set()

        self.mode: BotMode = BotMode.UNDETERMINED

        # Used to analyze the SU window
        try:
            self.su_client_rect = get_su_client_rect()
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

        root.info(f"{self.player_position_tile=}")
        root.info(f"{self.player_position=}")

        print(f"{self.player_position_tile=}")
        print(f"{self.nearby_tile_top_left=}")

        self.grid_rect: Optional[Rect] = None
        self.grid_slice_gray: np.typing.ArrayLike = None
        self.grid_slice_color: np.typing.ArrayLike = None

        # Note: images must be read as unchanged when converting to grayscale since IM_READ_GRAYSCALE has platform specific conversion methods and difers from cv2.cv2.BGR2GRAy's implementation in cvtcolor
        # This is needed to ensure the pixels match exactly for comparision, otherwhise the grayscale differs slightly
        # https://docs.opencv.org/4.5.1/d4/da8/group__imgcodecs.html

        # Floor tiles detected in current frame
        self.active_floor_tiles: list[np.typing.ArrayLike] = []
        self.active_floor_tiles_gray: list[np.typing.ArrayLike] = []

        self.castle_tile: np.typing.ArrayLike = cv2.imread(
            (Path.cwd() / __file__).parent.parent.joinpath('resources').joinpath("extracted_assets/generic/floor_standard1_0.png").as_posix(),
            cv2.IMREAD_COLOR)

        self.castle_tile_gray: np.typing.ArrayLike = cv2.cvtColor(self.castle_tile, cv2.COLOR_BGR2GRAY)
        self.realm_tile: Asset = None

        # hashes of sprite frames that have matching `self.castle_tile` pixels set to black.
        # This avoids false negative matches if the placed object has matching color pixels in a position
        self.castle_item_hashes: RealmSpriteHasher = RealmSpriteHasher(floor_tiles=self.active_floor_tiles)

        self.important_tile_locations_lock = rwlock.RWLockFair()
        # realm object locations in screenshot
        self.important_tile_locations: list[AssetGridLoc] = []

        # master location
        self.master_tile_location: Optional[AssetGridLoc] = None

        # altar location
        self.altar_tile_location: Optional[AssetGridLoc] = None

        # used to tell if the player has moved since last scanning for objects
        self.previous_important_tile_locations: list[AssetGridLoc] = []
        self.previous_master_location: Optional[AssetGridLoc] = None

        self.stop_event = threading.Event()
        self.nearby_process = NearbyFrameGrabber(name=NearbyFrameGrabber.__name__,
                                                 nearby_area=self.nearby_mon, nearby_queue=self.rx_color_nearby_queue,
                                                 rx_parent=self.tx_nearby_process_queue,
                                                 hang_notifier=self.hang_alert_queue)
        print(f"{self.nearby_process=}")
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
                                                              )
        print(f"{self.window_framegrabber_phandle=}")
        self.window_framegrabber_phandle.start()

        self.whole_window_thandle = WholeWindowAnalyzer(name=WholeWindowAnalyzer.__name__,
                                                        incoming_frame_queue=self.color_frame_queue,
                                                        out_quests_queue=self.out_quests,
                                                        su_client_rect=Rect(x=0, y=0, w=self.mon_full_window["width"],
                                                                            h=self.mon_full_window["height"]),
                                                        parent=self,
                                                        stop_event=self.stop_event,
                                                        hang_monitor=self.hang_monitor_controller,
                                                        daemon=True
                                                        )
        self.whole_window_thandle.start()

    def stop(self):
        self.window_framegrabber_phandle.terminate()
        self.nearby_process.terminate()
        self.stop_event.set()
        root.info("both should be shut down")

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
        #######xxxxx###
        #######xxCxx###
        #######xxxxx###

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
        return Rect(
            x=(self.player_position_tile.x - NEARBY_TILES_WH // 2) * TILE_SIZE,
            y=(self.player_position_tile.y - NEARBY_TILES_WH // 2) * TILE_SIZE,
            w=TILE_SIZE * NEARBY_TILES_WH,
            h=TILE_SIZE * NEARBY_TILES_WH,
        )

    def cache_images_using_phashes(self):
        with Session() as session:

            floor_ids = []
            if self.mode is BotMode.REALM:
                if not hasattr(self, 'realm'):
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

            realm_phashes_query = session.query(HashFrameWithFloor.phash, Sprite.short_name, Sprite.long_name) \
                .join(SpriteFrame, SpriteFrame.id == HashFrameWithFloor.sprite_frame_id) \
                .join(Sprite, Sprite.id == SpriteFrame.sprite_id) \
                .filter(HashFrameWithFloor.floor_sprite_frame_id.in_(floor_ids))

            realm_phashes = realm_phashes_query.all()
            for realm_phash, short_name, long_name in realm_phashes:
                img_info = ImageInfo(short_name=short_name, long_name=long_name)
                self.castle_item_hashes[realm_phash] = img_info

    def cache_image_hashes_of_decorations(self):
        start = time.time()
        self.cache_images_using_phashes()
        end = time.time()
        print(f"cache with phash took {(end - start) * 1000}ms")

    def print_realm_quests(self):
        print(f"known quests")
        frames_asset: list[Asset]
        with Session() as session:
            quest: Quest
            for quest in session.query(Quest).all():
                print(quest.title, [sprite.long_name for sprite in quest.sprites])

    def run(self):

        if settings.DEBUG:
            self.print_realm_quests()

        iters = 0
        every = 10
        FPS = 60
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
                self.timer = time.time()
                try:
                    new_su_client_rect = get_su_client_rect()
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

                if new_su_client_rect != self.su_client_rect:
                    print(f"SU window changed. new={new_su_client_rect}, old={self.su_client_rect}")
                    self.su_client_rect = new_su_client_rect
                    self.mon_full_window = new_su_client_rect.to_mss_dict()
                    self.nearby_mon: dict = {"top": self.su_client_rect.y + self.nearby_rect_mss.y,
                                             "left": self.su_client_rect.x + self.nearby_rect_mss.x,
                                             "width": self.nearby_rect_mss.w, "height": self.nearby_rect_mss.h}

                    self.tx_window_queue.put(WindowDim(mss_dict=self.mon_full_window))
                    self.tx_nearby_process_queue.put(WindowDim(mss_dict=self.nearby_mon))

            if self.mode is BotMode.UNDETERMINED:

                if realm_alignment := self.nearby_processing_thandle.detect_what_realm_in():
                    if isinstance(realm_alignment, RealmAlignment):
                        self.realm = realm_alignment.realm
                    self.mode = BotMode.REALM

            elif self.mode is BotMode.REALM:
                self.nearby_send_deque.append(CheckWhatRealmIn)
            elif self.mode is BotMode.CASTLE:
                self.nearby_send_deque.append(CheckWhatRealmIn)

            # if settings.DEBUG:
            #     cv2.imshow("SU Vision - Near bbox", self.nearby_processing_thandle.grid_near_slice_gray)
            #     if cv2.waitKey(1) & 0xFF == ord("q"):
            #         cv2.destroyAllWindows()
            #         break

                # label player position
                # top_left = self.player_position.top_left().as_tuple()
                # bottom_right = self.player_position.bottom_right().as_tuple()
                # cv2.rectangle(self.grid_slice_gray, top_left, bottom_right, (255), 1)

            if iters % every == 0:
                root.debug(f"FPS: {clock.get_fps()}")
            iters += 1
            clock.tick(FPS)

    def speak_nearby_objects(self):
        audio_locations: list[AudioLocation] = []
        with self.important_tile_locations_lock.gen_rlock():

            for tile in self.important_tile_locations[:1]:
                audio_locations.append(AudioLocation(distance=tile.point()))

            if audio_locations:

                self.audio_system.play_sound(audio_locations[0], sound_type=SoundType.QUEST_ITEM)
                self.previous_important_tile_locations = self.important_tile_locations[:]
            else:
                self.audio_system.stop(sound_type=SoundType.QUEST_ITEM)

        if self.master_tile_location:
            master_distance_audio = AudioLocation(distance=self.master_tile_location.point())
            self.audio_system.play_sound(master_distance_audio, sound_type=SoundType.MASTER_NPC)
            self.previous_master_location = self.master_tile_location
            self.master_tile_location = None
        else:
            self.audio_system.stop(sound_type=SoundType.MASTER_NPC)

        if self.altar_tile_location:
            self.audio_system.play_sound(AudioLocation(distance=self.altar_tile_location.point()),
                                         sound_type=SoundType.ALTAR)
            self.altar_tile_location = None
        else:
            self.audio_system.stop(SoundType.ALTAR)

        if self.project_item_locations:
            for tile in self.project_item_locations[:1]:
                self.audio_system.play_sound(AudioLocation(distance=tile.point()), SoundType.PROJECT_ITEM)
            self.project_item_locations.clear()
        else:
            self.audio_system.stop(SoundType.PROJECT_ITEM)

        if self.npc_normal_locations:
            for tile in self.npc_normal_locations[:1]:
                self.audio_system.play_sound(AudioLocation(distance=tile.point()), SoundType.NPC_NORMAL)
            self.npc_normal_locations.clear()
        else:
            self.audio_system.stop(SoundType.NPC_NORMAL)

        if shrine_location := self.teleportation_shrine_location:
            self.audio_system.play_sound(AudioLocation(distance=shrine_location.point()), SoundType.TELEPORTATION_SHRINE)
            self.teleportation_shrine_location = None
        else:
            self.audio_system.stop(SoundType.TELEPORTATION_SHRINE)


class WholeWindowGrabber(multiprocessing.Process):
    def __init__(self, out_quests: Queue, outgoing_color_frame_queue: multiprocessing.Queue, screenshot_area: dict,
                 rx_queue: multiprocessing.Queue, hang_notifier: queue.Queue[HangMonitorAlert],
                 **kwargs):
        super().__init__(**kwargs)
        self.color_frame_queue = outgoing_color_frame_queue
        self.out_quests: Queue = out_quests
        self.screenshot_area: dict = screenshot_area
        self.rx_parent_queue = rx_queue
        self.hang_monitor: Optional[HangMonitorWorker] = None
        self.hang_notifier = hang_notifier
        self.hang_control: Optional[queue.Queue] = None
        self.activity_notify: Optional[HangMonitorChan] = None

    def run(self):
        self.hang_control = queue.Queue()
        self.hang_monitor = HangMonitorWorker(self.hang_notifier, control_port=self.hang_control)
        self.activity_notify = self.hang_monitor.register_component(threading.current_thread(), 3.0)

        try:
            should_stop = False

            with mss.mss() as sct:
                while not should_stop:
                    # check for incoming messages
                    try:
                        msg = self.rx_parent_queue.get_nowait()
                        if msg.type == ConfigMsg.WINDOW_DIM:
                            msg: WindowDim
                            root.info(f"got windowgrabber newmsg = {msg=}")
                            self.screenshot_area = msg.mss_dict

                    except queue.Empty:
                        pass

                    time.sleep(1)
                    try:
                        self.activity_notify.notify_activity(HangAnnotation({"data": ""}))

                        # Performance: copying overhead is not an issue for needing a frame at 1-2 FPS
                        frame_np: ArrayLike = np.asarray(sct.grab(self.screenshot_area))
                        if frame_np.shape == (0, 0, 4):
                            print("no frame data")
                            continue
                        self.color_frame_queue.put_nowait(frame_np)
                    except queue.Full:
                        continue
        except KeyboardInterrupt:
            self.color_frame_queue.put(None, timeout=10)


class WholeWindowAnalyzer(Thread):
    def __init__(self, incoming_frame_queue: Queue, out_quests_queue: Queue, su_client_rect: Rect, parent: Bot, stop_event: threading.Event, hang_monitor: HangMonitorWorker ,**kwargs) -> None:
        super().__init__(**kwargs)
        self.parent: Bot = parent
        self.incoming_frame_queue: Queue = incoming_frame_queue
        self.out_quests_sprites_queue: Queue = out_quests_queue
        self.stop_event = stop_event
        self._hang_monitor = hang_monitor
        self.hang_activity_sender: Optional[HangMonitorChan] = None
        # self.su_client_rect = su_client_rect

        self.frame: np.typing.ArrayLike = np.zeros(shape=(self.parent.su_client_rect.h, self.parent.su_client_rect.w), dtype="uint8")
        self.gray_frame: np.typing.ArrayLike = np.zeros(shape=(self.parent.su_client_rect.h, self.parent.su_client_rect.w),
                                                        dtype="uint8")

    def discover_quests(self):
        quests = extract_quest_name_from_quest_area(gray_frame=self.gray_frame)
        for quest_number, quest in enumerate(quests, start=1):
            sprite_short_names = [sprite.short_name for sprite in quest.sprites]
            sprite_long_names = [sprite.long_name for sprite in quest.sprites]
            print(f"active quest #{quest_number}: {quest.title} - Needs sprites: {sprite_short_names}")
            for sprite_long_name in sprite_long_names:
                self.out_quests_sprites_queue.put(sprite_long_name, timeout=1)

    def update_quests(self, new_quests: list[Quest]):
        if len(new_quests) == 0:
            return

        new_quest_ids = set()
        for quest in new_quests:
            new_quest_ids.add(quest.id)

        if new_quest_ids == self.parent.current_quests:
            return

        self.parent.quest_sprite_long_names.clear()
        for quest in new_quests:
            if quest.quest_type == QuestType.rescue:
                with Session() as session:
                    self.parent.quest_sprite_long_names = set(sprite.long_name for sprite in session.query(NPCSprite).all())
            else:
                for sprite in quest.sprites:
                    self.parent.quest_sprite_long_names.add(sprite.long_name)

            if not quest.supported:
                self.parent.audio_system.speak_nonblocking(f"Unsupported quest: {quest.title}")

        self.parent.current_quests = new_quest_ids

    def run(self):
        self.hang_activity_sender = self._hang_monitor.register_component(thread_handle=self, hang_timeout_seconds=10)
        while not self.stop_event.is_set():
            try:
                msg = self.incoming_frame_queue.get(timeout=5)
                self.hang_activity_sender.notify_activity(HangAnnotation(data={"data": "window analyze"}))
                if msg is None:
                    break
                shot = msg
            except queue.Empty:
                raise Exception("No new full frame for 10 seconds")
            if shot is None:
                break

            self.frame = np.asarray(shot)
            cv2.cvtColor(self.frame, cv2.COLOR_BGRA2GRAY, dst=self.gray_frame)

            if aligned_rect := recompute_grid_offset(floor_tile=self.parent.castle_tile_gray,
                                                     gray_frame=self.gray_frame,
                                                     mss_rect=self.parent.su_client_rect):
                self.grid_rect = aligned_rect
            else:
                self.grid_rect = Bot.default_grid_rect(self.parent.su_client_rect)

            self.grid_slice_gray: np.typing.ArrayLike = self.gray_frame[
                                                        self.grid_rect.y:self.grid_rect.y + self.grid_rect.h,
                                                        self.grid_rect.x:self.grid_rect.x + self.grid_rect.w]
            self.grid_slice_color: np.typing.ArrayLike = self.frame[
                                                         self.grid_rect.y:self.grid_rect.y + self.grid_rect.h,
                                                         self.grid_rect.x:self.grid_rect.x + self.grid_rect.w]

            quests = extract_quest_name_from_quest_area(self.gray_frame)
            root.info(f"quests = {[quest.title for quest in quests]}")
            root.info(f"quest items = {[sprite.long_name for quest in quests for sprite in quest.sprites]}")

            self.update_quests(quests)
            root.debug(f"quests_len = {len(self.parent.quest_sprite_long_names)}")

            # cv2.imshow("SU Vision - Whole Window", self.frame)
            # if cv2.waitKey(1) & 0xFF == ord("q"):
            #     cv2.destroyAllWindows()
            #     break
        root.info("WindowAnalyzer thread shutting down")


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

    def run(self):
        """Screenshots the area defined as nearby the player. no more than 8x8 tiles (256pxx256px)
        :param color_nearby_queue Queue used to send recent nearby screenshot to processing code
        :param nearby_rect dict used in mss.grab. keys `top`, `left`, `width`, `height`
        """
        self.hang_control = queue.Queue()
        self.hang_monitor = HangMonitorWorker(self.hang_notifier, control_port=self.hang_control)
        self.activity_notify = self.hang_monitor.register_component(threading.current_thread(), 3.0)


        try:
            should_stop = False

            with mss.mss() as sct:
                while not should_stop:
                    # Performance: Unsure if 1MB copying at 60FPS is fine
                    # Note: Possibly use shared memory if performance is an issue
                    try:
                        nearby_shot_np: ArrayLike = np.asarray(sct.grab(self.nearby_area))
                        if nearby_shot_np.shape == (0, 0, 4):
                            print("no nearby frame data")
                        self.color_nearby_queue.put(NewFrame(nearby_shot_np), timeout=10)
                    except queue.Full:
                        root.debug("color nearby queue full")
                        pass

                    try:
                        msg = self.rx_parent.get_nowait()
                        if msg.type == ConfigMsg.WINDOW_DIM:
                            msg: WindowDim
                            print(f"updated nearbyframeGrabber rect. new={msg.mss_dict} old={self.nearby_area}")
                            self.nearby_area = msg.mss_dict
                    except queue.Empty:
                        pass
                    continue
        except KeyboardInterrupt:
            self.color_nearby_queue.put(None)



@dataclass
class RealmAlignment(object):
    """Tells the realm detected and the alignment for the realm"""
    realm: Realm
    alignment: Rect


@dataclass
class CastleAlignment:
    alignment: Rect


class NearPlayerProcessing(Thread):
    def __init__(self, nearby_frame_queue: multiprocessing.Queue, nearby_comm_deque: deque, parent: Bot, stop_event: threading.Event,hang_monitor: HangMonitorWorker, **kwargs):
        super().__init__(**kwargs)
        self._hang_monitor: HangMonitorWorker = hang_monitor
        self.hang_activity_sender: Optional[HangMonitorChan] = None

        self.parent = parent
        # used for multiprocess communication
        self.nearby_queue = nearby_frame_queue

        # Used for across thread communication
        self.nearby_comm_deque: deque = nearby_comm_deque
        self.stop_event = stop_event

        self.near_frame_color: np.typing.ArrayLike = np.zeros(
            (NEARBY_TILES_WH * TILE_SIZE, NEARBY_TILES_WH * TILE_SIZE, 3), dtype='uint8')
        self.near_frame_gray: np.typing.ArrayLike = np.zeros((NEARBY_TILES_WH * TILE_SIZE, NEARBY_TILES_WH * TILE_SIZE),
                                                             dtype='uint8')

        self.grid_near_rect: Optional[Rect] = parent.nearby_rect_mss
        self.grid_near_slice_gray: np.typing.ArrayLike = self.near_frame_gray[:]
        self.grid_near_slice_color: np.typing.ArrayLike = self.near_frame_color[:]

        self.realm: Optional[Realm] = None
        self.unique_realm_assets = list[Asset]

        # The current active quests
        self.active_quests: list[Quest] = []

    def detect_what_realm_in(self) -> Optional[Union[RealmAlignment, CastleAlignment]]:
        # Scan the nearby tile area for lit tiles to determine what realm we are in currently
        # This area was chosen since the player + 6 creatures are at most this long
        # At least 1 tile will not be dimmed by the fog of war

        # fast: if still in same realm
        for last_tile in self.parent.active_floor_tiles_gray:
            if aligned_rect := recompute_grid_offset(floor_tile=last_tile, gray_frame=self.near_frame_gray,
                                                     mss_rect=self.parent.nearby_rect_mss):
                return RealmAlignment(realm=self.realm, alignment=aligned_rect)

        with Session() as session:
            floor_tiles = session.query(FloorSprite).options(joinedload('realm')).all()

        floor_tile: FloorSprite
        for floor_tile in floor_tiles:
            tile_frame: SpriteFrame
            for frame_num, tile_frame in enumerate(floor_tile.frames, start=1):
                if aligned_rect := recompute_grid_offset(floor_tile=tile_frame.data_gray,
                                                         gray_frame=self.near_frame_gray,
                                                         mss_rect=self.parent.nearby_rect_mss):
                    root.debug(f"floor tile = {floor_tile.long_name}")
                    if realm := floor_tile.realm:
                        return RealmAlignment(realm=realm.enum, alignment=aligned_rect)
                    else:
                        root.info("in castle")
                        return CastleAlignment(alignment=aligned_rect)


    def exclude_from_debug(self, s: str):
        if s == "Blood Grove Floor Tile":
            return True
        elif s == "bck_FOW_Tile":
            return True
        else:
            return False

    def enter_castle_scanner(self):
        """Scans for decorations and quests in the castle"""

        with self.parent.important_tile_locations_lock.gen_wlock():
            self.parent.important_tile_locations.clear()

            # Hack: add the grid offset to the player tile to realign the grid when moving left
            aligned_player_tile_x = round(self.parent.nearby_tile_top_left.x + self.grid_near_rect.x / TILE_SIZE)

            for row in range(0, self.grid_near_rect.w, TILE_SIZE):
                for col in range(0, self.grid_near_rect.h, TILE_SIZE):
                    tile_gray = self.grid_near_slice_gray[col:col + TILE_SIZE, row:row + TILE_SIZE]

                    try:
                        img_info = self.parent.castle_item_hashes.get_greyscale(tile_gray[:32, :32])

                        asset_location = AssetGridLoc(
                            x=aligned_player_tile_x + row // TILE_SIZE - self.parent.player_position_tile.x,
                            y=self.parent.nearby_tile_top_left.y + col // TILE_SIZE - self.parent.player_position_tile.y,
                            short_name=img_info.short_name,
                            )

                        is_player_tile = asset_location.point() == Point(0, 0)
                        if is_player_tile:
                            continue
                        if not self.exclude_from_debug(img_info.long_name):
                            root.debug(f"matched: {img_info.long_name} - asset location = {asset_location.point()}")

                        if img_info.long_name in self.parent.quest_sprite_long_names:
                            root.debug(f"Quest item matched {img_info.long_name}")
                            self.parent.important_tile_locations.append(asset_location)
                        elif img_info.long_name in self.parent.teleportation_shrine_names:
                            root.debug(f"Teleportation Shrine matched {img_info.long_name}")
                            self.parent.teleportation_shrine_location = asset_location
                        elif img_info.long_name in self.parent.masters:
                            root.debug(f"Master matched {img_info.long_name}")
                            self.parent.master_tile_location = asset_location
                        elif img_info.long_name in self.parent.altars:
                            root.debug(f"Altar matched {img_info.long_name}")
                            self.parent.altar_tile_location = asset_location
                        elif img_info.long_name in self.parent.project_items:
                            root.debug(f"Project Item matched {img_info.long_name}")
                            self.parent.project_item_locations.append(asset_location)
                        elif img_info.long_name in self.parent.npc_normals:
                            root.debug(f"NPC normal matched {img_info.long_name}")
                            self.parent.npc_normal_locations.append(asset_location)

                    except KeyError as e:
                        pass
        self.parent.speak_nearby_objects()

    def enter_realm_scanner(self):
        realm_alignment = self.detect_what_realm_in()
        if not realm_alignment:
            self.enter_castle_scanner()
            return

        if isinstance(realm_alignment, CastleAlignment):
            self.parent.active_floor_tiles = [self.parent.castle_tile]
            self.parent.active_floor_tiles_gray = [self.parent.castle_tile_gray]
            self.parent.mode = BotMode.CASTLE

            floor_ties_info = FloorTilesInfo(floortiles=self.parent.active_floor_tiles, overlay=None)
            self.parent.castle_item_hashes = RealmSpriteHasher(floor_tiles=floor_ties_info)
            start = time.time()
            self.parent.cache_image_hashes_of_decorations()
            end = time.time()
            print(f"Took {math.ceil((end - start) * 1000)}ms to retrieve {len(self.parent.castle_item_hashes)} phashes")

            root.info(f"castle entered")
            root.info(f"new realm alignment = {realm_alignment=}")
            print(f"new item hashes = {len(self.parent.castle_item_hashes)}")

            self.enter_castle_scanner()
            return
        elif isinstance(realm_alignment, RealmAlignment):
            self.parent.mode = BotMode.REALM
            if realm_alignment.realm != self.realm:
                overlay = None
                self.realm = realm_alignment.realm
                self.parent.realm = realm_alignment.realm
                with Session() as session:
                    realm = session.query(RealmLookup).filter_by(enum=realm_alignment.realm).one()
                    realm_tiles = session.query(FloorSprite).filter_by(realm_id=realm.id).all()
                    temp = []
                    temp_gray = []
                    for realm_tile in realm_tiles:
                        for frame in realm_tile.frames:
                            temp.append(frame.data_color)
                            temp_gray.append(frame.data_gray)
                    self.parent.active_floor_tiles = temp
                    self.parent.active_floor_tiles_gray = temp_gray

                    if self.realm is Realm.DEAD_SHIPS:
                        overlay_sprite = session.query(OverlaySprite).filter_by(realm_id=realm.id).one()
                        overlay_tile_part = overlay_sprite.frames[0].data_color[:TILE_SIZE, :TILE_SIZE, :3]
                        overlay = Overlay(alpha=0.753, tile=overlay_tile_part)

                floor_ties_info = FloorTilesInfo(floortiles=self.parent.active_floor_tiles, overlay=overlay)
                self.parent.castle_item_hashes = RealmSpriteHasher(floor_tiles=floor_ties_info)
                start = time.time()
                self.parent.cache_image_hashes_of_decorations()
                end = time.time()
                print(
                    f"Took {math.ceil((end - start) * 1000)}ms to retrieve {len(self.parent.castle_item_hashes)} phashes")

                root.info(f"new realm entered: {self.realm.name}")
                root.info(f"new realm alignment = {realm_alignment=}")
                print(f"new item hashes = {len(self.parent.castle_item_hashes)}")

        self.enter_castle_scanner()

    def realm_tile_has_matching_decoration(self) -> bool:
        pass

    def handle_new_frame(self, data: NewFrame):
        img = data.frame
        self.near_frame_color = img[:, :, :3]

        # make grayscale version
        cv2.cvtColor(self.near_frame_color, cv2.COLOR_BGR2GRAY, dst=self.near_frame_gray)

        # calculate the correct alignment for grid
        if realm_alignment := self.detect_what_realm_in():
            # print(f"nearby new aligned grid: {realm_alignment.alignment=}")
            self.grid_near_rect = realm_alignment.alignment
        else:
            root.debug(f"using default nearby grid")
            self.grid_near_rect = Bot.default_grid_rect(self.parent.nearby_rect_mss)

        self.grid_near_slice_gray: np.typing.ArrayLike = self.near_frame_gray[
                                                         self.grid_near_rect.y:self.grid_near_rect.y + self.grid_near_rect.h,
                                                         self.grid_near_rect.x:self.grid_near_rect.x + self.grid_near_rect.w]
        self.grid_near_slice_color: np.typing.ArrayLike = self.near_frame_color[
                                                          self.grid_near_rect.y:self.grid_near_rect.y + self.grid_near_rect.h,
                                                          self.grid_near_rect.x:self.grid_near_rect.x + self.grid_near_rect.w]

    def run(self):
        self.hang_activity_sender = self._hang_monitor.register_component(self, hang_timeout_seconds=3.0)

        while not self.stop_event.is_set():
            try:
                msg: MessageImpl = self.nearby_queue.get(timeout=5)
            except queue.Empty:
                return

            self.hang_activity_sender.notify_activity(HangAnnotation({"event": "near_frame_processing"}))
            if msg is None:
                return
            if msg.type is MessageType.NEW_FRAME:
                self.handle_new_frame(msg)
            try:
                # we don't block since we must be ready for new incoming frames ^^
                comm_msg: MessageImpl = self.nearby_comm_deque.pop()

                if comm_msg.type is MessageType.SCAN_FOR_ITEMS:
                    self.enter_castle_scanner()
                elif comm_msg.type is MessageType.CHECK_WHAT_REALM_IN:
                    start = time.time()
                    self.enter_realm_scanner()
                    end = time.time()
                    latency = end - start
                    root.debug(f"realm scanning took {math.ceil(latency * 1000)}ms")

                elif comm_msg.type is MessageType.DRAW_DEBUG:
                    pass
                    # cv2.imshow("SU Vision - Near bbox", self.grid_near_slice_gray)
                    # if cv2.waitKey(1) & 0xFF == ord("q"):
                    #     cv2.destroyAllWindows()
                    #     break
            except IndexError:
                continue
        root.info(f"{self.name} is shutting down")


def start_bot():
    bot = Bot()
    bot.run()


if __name__ == "__main__":
    sentry_sdk.init(
        "https://90ff6a25ab444640becc5ab6a9e35d56@o914707.ingest.sentry.io/5855592",
        traces_sample_rate=1.0,
        before_send=before_send,
    )

    start_bot()
