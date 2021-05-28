import enum
import multiprocessing
from collections import deque
import queue
from multiprocessing import Queue
from threading import Thread
from typing import Optional

import cv2
import numpy as np
import mss
import pygame
import win32gui
import pytesseract
import math
import time
from skimage.util import view_as_blocks

from subot.audio import AudioSystem, AudioLocation
from subot.messageTypes import NewFrame, MessageImpl, MessageType, ScanForItems, DrawDebug
from subot.read_tags import AssetDB, Asset

from numpy.typing import ArrayLike

from subot.hash_image import ImageInfo, HashDecor, CastleDecorationDict

from dataclasses import dataclass

import subot.background_subtract as background_subtract

from subot.models import Sprite, SpriteFrame, Quest
from subot.models import Session
import subot.settings as settings

from readerwriterlock import rwlock

from subot.utils import Point

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'

# BGR colors
blue = (255, 0, 0)
purple = (255, 0, 255)
green = (0, 255, 0)
red = (0, 0, 255)
yellow = (0, 255, 255)
orange = (0, 215, 255)

TILE_SIZE = 32
NEARBY_TILES_WH: int = 12

title = "SU Vision"


@dataclass(frozen=True)
class TemplateMeta:
    name: str
    data: np.typing.ArrayLike
    color: tuple
    mask: np.typing.ArrayLike


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    def top_left(self) -> Point:
        return Point(x=self.x, y=self.y)

    def bottom_right(self) -> Point:
        return Point(x=self.x + self.w, y=self.y + self.h)

    @classmethod
    def from_cv2_loc(cls, cv2_loc: tuple, w: int, h: int):
        return cls(x=cv2_loc[0], y=cv2_loc[1], w=w, h=h)


def get_su_client_rect() -> Rect:
    """Returns Rect class of the Siralim Ultimate window. Coordinates are without title bar and borders
    :raises Exception if the game is not open
    """
    su_hwnd = win32gui.FindWindow(None, "Siralim Ultimate")
    su_is_open = su_hwnd >= 0
    if not su_is_open:
        raise Exception("Siralim Ultimate is not open")
    print(f"{su_hwnd=}")
    rect = win32gui.GetWindowRect(su_hwnd)

    clientRect = win32gui.GetClientRect(su_hwnd)
    windowOffset = math.floor(((rect[2] - rect[0]) - clientRect[2]) / 2)
    titleOffset = ((rect[3] - rect[1]) - clientRect[3]) - windowOffset
    newRect = (rect[0] + windowOffset, rect[1] + titleOffset, rect[2] - windowOffset, rect[3] - windowOffset)

    return Rect(x=newRect[0], y=newRect[1], w=newRect[2] - newRect[0], h=newRect[3] - newRect[1])


DOWNSCALE_FACTOR = 4

color = blue


@dataclass
class TileCoord:
    """Tells position in tile units"""
    x: int
    y: int


from enum import Enum, auto


class BotMode(Enum):
    UNDETERMINED = auto()
    CASTLE = auto()
    REALM = auto()


@dataclass(frozen=True)
class AssetGridLoc:
    """Tile coordinate + game asset name on map"""
    x: int
    y: int
    short_name: str


def extract_quest_name_from_quest_area(gray_frame: np.typing.ArrayLike) -> list[Quest]:
    """

    :param gray_frame: greyscale full-windowed frame that the bot captured
    :return: List of quests that appeared in the quest area. an empty list is returned if no quests were found
    """
    quests: list[Quest] = []
    y_text_dim = int(gray_frame.shape[0] * 0.15)
    x_text_dim = int(gray_frame.shape[1] * 0.33)
    thresh, threshold_white = cv2.threshold(gray_frame[:y_text_dim, -x_text_dim:], 220, 255, cv2.THRESH_BINARY_INV)
    text = pytesseract.pytesseract.image_to_string(threshold_white, lang="eng")
    quest_text_lines = [line.strip() for line in text.split("\n")]

    # see if any lines match a quest title
    with Session() as session:
        for quest_line in quest_text_lines:
            if quest_obj := session.query(Quest).filter_by(title=quest_line).first():
                quests.append(quest_obj)
    return quests


class GridType(enum.Enum):
    WHOLE = enum.auto()
    NEARBY = enum.auto()


def recompute_grid_offset(floor_tile: ArrayLike, gray_frame: ArrayLike, mss_rect: Rect) -> Rect:
    # find matching realm tile on map
    # We use matchTemplate since the grid shifts when the player is moving
    # (the tiles smoothly slide to the next `TILE_SIZE increment)

    res = cv2.matchTemplate(gray_frame, floor_tile, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    threshold = 0.99
    if max_val <= threshold:
        # maybe default to center?
        tile = Bot.compute_player_position(mss_rect)
    else:
        tile = Rect.from_cv2_loc(max_loc, w=TILE_SIZE, h=TILE_SIZE)

    top_left_pt = Bot.top_left_tile(aligned_floor_tile=tile, client_rect=mss_rect)
    bottom_right_pt = Bot.bottom_right_tile(aligned_tile=tile, client_rect=mss_rect)
    return Bot.compute_grid_rect(top_left_tile=top_left_pt, bottom_right_tile=bottom_right_pt)


class Bot:
    def __init__(self):
        pygame.init()
        self.audio_system: AudioSystem = AudioSystem()

        self.color_frame_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)
        self.out_quests: multiprocessing.Queue = multiprocessing.Queue()
        self.color_nearby_queue = multiprocessing.Queue(maxsize=1)

        self.nearby_send_deque = deque(maxlen=1)
        self.quest_sprite_long_names: set[str] = set()
        self.mode: BotMode = BotMode.UNDETERMINED
        self.assetDB: AssetDB = AssetDB
        # Used to only analyze the SU window
        self.su_client_rect = get_su_client_rect()

        """player tile position in grid"""
        self.player_position: Rect = Bot.compute_player_position(self.su_client_rect)
        self.player_position_tile = TileCoord(x=self.player_position.x // TILE_SIZE,
                                              y=self.player_position.y // TILE_SIZE)

        self.nearby_rect_mss: Rect = self.compute_nearby_screenshot_area()
        self.nearby_tile_top_left: TileCoord = TileCoord(x=self.nearby_rect_mss.x // TILE_SIZE,
                                                         y=self.nearby_rect_mss.y // TILE_SIZE)
        print(f"{self.su_client_rect=}")
        print(f"{self.nearby_rect_mss=}")

        self.mon_full_window: dict = {"top": self.su_client_rect.y, "left": self.su_client_rect.x,
                                      "width": self.su_client_rect.w, "height": self.su_client_rect.h}
        self.nearby_mon: dict = {"top": self.su_client_rect.y + self.nearby_rect_mss.y,
                                 "left": self.su_client_rect.x + self.nearby_rect_mss.x,
                                 "width": self.nearby_rect_mss.w, "height": self.nearby_rect_mss.h}

        print(f"{self.player_position_tile=}")
        print(f"{self.player_position=}")

        print(f"{self.player_position_tile=}")
        print(f"{self.nearby_tile_top_left=}")

        self.grid_rect: Optional[Rect] = None
        self.grid_slice_gray: np.typing.ArrayLike = None
        self.grid_slice_color: np.typing.ArrayLike = None

        self.output_debug_gray: np.typing.ArrayLike = None

        # Note: images must be read as unchanged when converting to grayscale since IM_READ_GRAYSCALE has platform specific conversion methods and difers from cv2.cv2.BGR2GRAy's implementation in cvtcolor
        # This is needed to ensure the pixels match exactly for comparision, otherwhise the grayscale differs slightly
        # https://docs.opencv.org/4.5.1/d4/da8/group__imgcodecs.html
        self.castle_tile: np.typing.ArrayLike = cv2.imread("../assets_padded/floortiles/Standard Floor Tile-frame1.png",
                                                           cv2.IMREAD_COLOR)
        # self.castle_tile: np.typing.ArrayLike = cv2.imread("../assets_padded/floortiles/Yseros' Floor Tile-frame1.png", cv2.IMREAD_COLOR)

        self.castle_tile_gray: np.typing.ArrayLike = cv2.cvtColor(self.castle_tile, cv2.COLOR_BGR2GRAY)
        self.realm_tile: Asset = None

        # hashes of sprite frames that have matching `self.castle_tile` pixels set to black.
        # This avoids false negative matches if the placed object has matching color pixels in a position
        self.castle_item_hashes: CastleDecorationDict = CastleDecorationDict(castle_tile_gray=self.castle_tile_gray)

        self.important_tile_locations_lock = rwlock.RWLockFair()
        # realm object locations in screenshot
        self.important_tile_locations: list[AssetGridLoc] = []

        # used to tell if the player has moved since last scanning for objects
        self.previous_important_tile_locations: list[AssetGridLoc] = []

        self.nearby_process = NearbyFrameGrabber(name=NearbyFrameGrabber.__name__,
                                                 nearby_area=self.nearby_mon, nearby_queue=self.color_nearby_queue)
        print(f"{self.nearby_process=}")
        self.nearby_process.start()

        self.nearby_processing_thandle = NearPlayerProcessing(name=NearPlayerProcessing.__name__,
                                                              nearby_frame_queue=self.color_nearby_queue,
                                                              nearby_comm_deque=self.nearby_send_deque,
                                                              parent=self)
        self.nearby_processing_thandle.start()

        self.window_framegrabber_phandle = WholeWindowGrabber(name=WholeWindowGrabber.__name__,
                                                              outgoing_color_frame_queue=self.color_frame_queue,
                                                              out_quests=self.out_quests,
                                                              screenshot_area=self.mon_full_window)
        print(f"{self.window_framegrabber_phandle=}")
        self.window_framegrabber_phandle.start()

        self.whole_window_thandle = WholeWindowAnalyzer(name=WholeWindowAnalyzer.__name__,
                                                        incoming_frame_queue=self.color_frame_queue,
                                                        out_quests_queue=self.out_quests,
                                                        su_client_rect=Rect(x=0, y=0, w=self.mon_full_window["width"],
                                                                            h=self.mon_full_window["height"]),
                                                        parent=self,
                                                        )
        self.whole_window_thandle.start()



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

    def cache_image_hashes_of_decorations(self):

        with Session() as session:
            sprites = session.query(Sprite).all()
            for sprite in sprites:
                sprite_frame: SpriteFrame
                for sprite_frame in sprite.frames:
                    if "Castle Walls" in sprite_frame.filepath:
                        continue
                    if "ignore" in sprite_frame.filepath:
                        continue
                    img = cv2.imread(sprite_frame.filepath, cv2.IMREAD_UNCHANGED)
                    metadata = ImageInfo(short_name=sprite.short_name, long_name=sprite.long_name)

                    # bottom right "works", just need to specialize on some images which have blank spaces
                    one_tile_worth_img: ArrayLike = img[-32:, :32, :]
                    if one_tile_worth_img.shape != (32, 32, 4):
                        print(f"not padded tile -skipping - {sprite_frame.filepath}")
                        continue

                    # new castle hasher
                    self.castle_item_hashes.insert_transparent_bgra_image(one_tile_worth_img, metadata)

    def run(self):
        # start assetDB
        self.assetDB = self.assetDB()

        print(f"known quests")
        frames_asset: list[Asset]
        with Session() as session:
            quest: Quest
            for quest in session.query(Quest).all():
                print(quest.title, [sprite.long_name for sprite in quest.sprites])

        iters = 0
        every = 5
        start = time.time()

        while True:
            if iters % every == 0:
                start = time.time()

            if self.mode is BotMode.UNDETERMINED:

                if self.nearby_processing_thandle.detect_if_in_castle():
                    self.mode = BotMode.CASTLE
                if realm_in := self.nearby_processing_thandle.detect_what_realm_in():
                    self.realm = realm_in
                    self.unique_realm_assets = self.assetDB.get_realm_assets_for_realm(self.realm)
                    print(f"items to scan: {len(self.unique_realm_assets)}")
                    print([x.long_name for x in self.unique_realm_assets])

                    quests: list[Quest] = extract_quest_name_from_quest_area(gray_frame=self.gray_frame)
                    print(quests)
                    for quest in quests:
                        try:
                            quest_items = self.assetDB.lookup["quest_item"][quest_name]
                            print("got matching quest items")
                            for quest_asset in quest_items:
                                print(quest_asset.long_name)
                                self.quest_items.append(quest_asset)
                        except KeyError:
                            print(f"no quest items for quest: {quest_name}")

                    self.mode = BotMode.REALM

            elif self.mode is BotMode.REALM:
                self.enter_realm_scanner()
            elif self.mode is BotMode.CASTLE:
                self.nearby_send_deque.append(ScanForItems)
                # bot.nearby_processing_thandle.enter_castle_scanner()

            # label player position
            top_left = self.player_position.top_left().as_tuple()
            bottom_right = self.player_position.bottom_right().as_tuple()
            cv2.rectangle(self.grid_slice_gray, top_left, bottom_right, (255), 1)

            if iters % every == 0:
                end = time.time()
                # print(f"FPS: {1 / max((end - start)*every, 0.0001)}")
            iters += 1
            if settings.DEBUG:
                self.nearby_send_deque.append(DrawDebug())
            time.sleep(1/80)

    def speak_nearby_objects(self):
        audio_locations: list[AudioLocation] = []
        with self.important_tile_locations_lock.gen_rlock():

            same_player_position = self.important_tile_locations == self.previous_important_tile_locations
            if same_player_position:
                return

            for tile in self.important_tile_locations[:1]:

                distance = Point(x=tile.x - self.player_position_tile.x,
                                 y=tile.y - self.player_position_tile.y,)
                audio_locations.append(AudioLocation(distance=distance))
            self.audio_system.play_locations(audio_locations)
            self.previous_important_tile_locations = self.important_tile_locations[:]


class WholeWindowGrabber(multiprocessing.Process):
    def __init__(self, out_quests: Queue, outgoing_color_frame_queue: multiprocessing.Queue, screenshot_area: dict,
                 **kwargs):
        super().__init__(**kwargs)
        self.color_frame_queue = outgoing_color_frame_queue
        self.out_quests: Queue = out_quests
        self.screenshot_area: dict = screenshot_area

    def run(self):

        should_stop = False

        with mss.mss() as sct:
            while not should_stop:
                time.sleep(1)
                try:
                    # Performance: copying overhead is not an issue for needing a frame at 1-2 FPS
                    frame_np: ArrayLike = np.asarray(sct.grab(self.screenshot_area))
                    self.color_frame_queue.put_nowait(frame_np)
                except queue.Full:
                    continue


class WholeWindowAnalyzer(Thread):
    def __init__(self, incoming_frame_queue: Queue, out_quests_queue: Queue, su_client_rect: Rect, parent: Bot, **kwargs) -> None:
        super().__init__(**kwargs)
        self.parent_ro: Bot = parent
        self.incoming_frame_queue: Queue = incoming_frame_queue
        self.out_quests_sprites_queue: Queue = out_quests_queue
        self.su_client_rect = su_client_rect

        self.frame: np.typing.ArrayLike = np.zeros(shape=(self.su_client_rect.h, self.su_client_rect.w), dtype="uint8")
        self.gray_frame: np.typing.ArrayLike = np.zeros(shape=(self.su_client_rect.h, self.su_client_rect.w),
                                                        dtype="uint8")

    def discover_quests(self):
        quests = extract_quest_name_from_quest_area(gray_frame=self.gray_frame)
        for quest_number, quest in enumerate(quests, start=1):
            sprite_short_names = [sprite.short_name for sprite in quest.sprites]
            sprite_long_names = [sprite.long_name for sprite in quest.sprites]
            print(f"active quest #{quest_number}: {quest.title} - Needs sprites: {sprite_short_names}")
            for sprite_long_name in sprite_long_names:
                self.out_quests_sprites_queue.put(sprite_long_name, timeout=1)

    def run(self):

        number = 0
        start = time.time()
        while True:
            try:
                msg = self.incoming_frame_queue.get(timeout=10)
                shot = msg
            except queue.Empty:
                raise Exception("No new full frame for 10 seconds")
            if shot is None:
                break
            number += 1
            end = time.time()
            latency = (end - start)
            # print(f"Quest: took {math.ceil(latency * 1000)}ms")
            start = time.time()

            self.frame = np.asarray(shot)
            cv2.cvtColor(self.frame, cv2.COLOR_BGRA2GRAY, dst=self.gray_frame)

            self.grid_rect = recompute_grid_offset(floor_tile=self.parent_ro.castle_tile_gray, gray_frame=self.gray_frame,
                                                   mss_rect=self.parent_ro.su_client_rect)

            self.grid_slice_gray: np.typing.ArrayLike = self.gray_frame[
                                                        self.grid_rect.y:self.grid_rect.y + self.grid_rect.h,
                                                        self.grid_rect.x:self.grid_rect.x + self.grid_rect.w]
            self.grid_slice_color: np.typing.ArrayLike = self.frame[
                                                         self.grid_rect.y:self.grid_rect.y + self.grid_rect.h,
                                                         self.grid_rect.x:self.grid_rect.x + self.grid_rect.w]


            quests = extract_quest_name_from_quest_area(self.gray_frame)
            # print(f"quests = {[quest.title for quest in quests]}")
            for quest in quests:
                for sprite in quest.sprites:
                    self.parent_ro.quest_sprite_long_names.add(sprite.long_name)


class NearbyFrameGrabber(multiprocessing.Process):
    def __init__(self, nearby_queue: multiprocessing.Queue, nearby_area: dict = None, **kwargs):
        super().__init__(**kwargs)
        self.color_nearby_queue: multiprocessing.Queue = nearby_queue
        self.nearby_area = nearby_area

    def run(self):
        """Screenshots the area defined as nearby the player. no more than 8x8 tiles (256pxx256px)
        :param color_nearby_queue Queue used to send recent nearby screenshot to processing code
        :param nearby_rect dict used in mss.grab. keys `top`, `left`, `width`, `height`
        """

        should_stop = False

        with mss.mss() as sct:
            while not should_stop:
                # Performance: Unsure if 1MB copying at 60FPS is fine
                # Note: Possibly use shared memory if performance is an issue
                try:
                    nearby_shot_np: ArrayLike = np.asarray(sct.grab(self.nearby_area))
                    self.color_nearby_queue.put(NewFrame(nearby_shot_np), timeout=10)
                except queue.Full:
                    continue


class NearPlayerProcessing(Thread):
    def __init__(self, nearby_frame_queue: multiprocessing.Queue, nearby_comm_deque: deque, parent: Bot, **kwargs):
        super().__init__(**kwargs)
        self.parent = parent
        # used for multiprocess communication
        self.nearby_queue = nearby_frame_queue

        # Used for across thread communication
        self.nearby_comm_deque: deque = nearby_comm_deque

        self.near_frame_color: np.typing.ArrayLike = np.zeros(
            (NEARBY_TILES_WH * TILE_SIZE, NEARBY_TILES_WH * TILE_SIZE, 3), dtype='uint8')
        self.near_frame_gray: np.typing.ArrayLike = np.zeros((NEARBY_TILES_WH * TILE_SIZE, NEARBY_TILES_WH * TILE_SIZE),
                                                             dtype='uint8')

        self.grid_near_rect: Optional[Rect] = parent.nearby_rect_mss
        self.grid_near_slice_gray: np.typing.ArrayLike = self.near_frame_gray[:]
        self.grid_near_slice_color: np.typing.ArrayLike = self.near_frame_color[:]

        self.output_debug_near_gray: np.typing.ArrayLike = self.near_frame_gray[:]

        self.realm_hashes: HashDecor = HashDecor()

        self.realm: Optional[str] = None
        self.unique_realm_assets = list[Asset]

        # The current active quests
        self.active_quests: list[Quest] = []
        # self.quest_item_locations: list[QuestAssetGridLoc] = []

    def detect_what_realm_in(self) -> Optional[str]:
        # Scan a 7x7 tile area for lit tiles to determine what realm we are in currently
        # This area was chosen since the player + 6 creatures are at most this long
        # At least 1 tile will not be dimmed by the fog of war
        realm_tiles = self.parent.assetDB.all_realm_floortiles()

        block_size = (TILE_SIZE, TILE_SIZE)
        grid_in_tiles = view_as_blocks(self.grid_near_slice_gray, block_size)

        for y_i, col in enumerate(grid_in_tiles):
            for x_i, row in enumerate(col):
                for realm_tile in realm_tiles:
                    if row.tobytes() == realm_tile.data_gray.tobytes():
                        self.realm_tile = realm_tile
                        return realm_tile.realm

    def detect_if_in_castle(self) -> bool:
        # Check configured castle tile
        block_size = (TILE_SIZE, TILE_SIZE)
        grid_in_tiles = view_as_blocks(self.grid_near_slice_gray, block_size)
        castle_tile = self.parent.castle_tile_gray

        for y_i, col in enumerate(grid_in_tiles):
            for x_i, row in enumerate(col):
                if row.tobytes() == castle_tile.tobytes():
                    print("We are in the castle")
                    return True
        return False

    def enter_castle_scanner(self):
        """Scans for decorations and quests in the castle"""

        # block_size = (TILE_SIZE, TILE_SIZE)
        # grid_in_tiles = view_as_blocks(self.grid_slice_gray, block_size)
        with self.parent.important_tile_locations_lock.gen_wlock():
            self.parent.important_tile_locations.clear()

            for row in range(0, self.grid_near_rect.w, TILE_SIZE):
                for col in range(0, self.grid_near_rect.h, TILE_SIZE):
                    tile_gray = self.grid_near_slice_gray[col:col + TILE_SIZE, row:row + TILE_SIZE]
                    tile_color = self.grid_near_slice_color[col:col + TILE_SIZE, row:row + TILE_SIZE, :3]

                    # print(f"bg subtract - {tile_color.shape=}  {self.parent.castle_tile.shape=}")
                    fg_only = background_subtract.subtract_background_color_tile(tile=tile_color,
                                                                                 floor=self.parent.castle_tile)
                    fg_only_gray = cv2.cvtColor(fg_only, cv2.COLOR_BGR2GRAY)
                    tile_gray[:] = fg_only_gray
                    # if settings.DEBUG:
                    #     self.output_debug_near_gray[col:col + TILE_SIZE, row:row + TILE_SIZE] = fg_only_gray

                    try:
                        img_info = self.parent.castle_item_hashes.get_greyscale(tile_gray[:32, :32])
                        if img_info.long_name in self.parent.quest_sprite_long_names:
                            self.parent.important_tile_locations.append(
                                AssetGridLoc(x=self.parent.nearby_tile_top_left.x + row // TILE_SIZE,
                                             y=self.parent.nearby_tile_top_left.y + col // TILE_SIZE,
                                             short_name=img_info.short_name))
                        # print(f"matched: {img_info.long_name}")
                        if settings.DEBUG:
                            cv2.rectangle(self.output_debug_near_gray, (row, col), (row + TILE_SIZE, col + TILE_SIZE),
                                          (255, 255, 255), 1)
                            # label finding with text
                            cv2.putText(self.output_debug_near_gray, img_info.long_name, (row, col + TILE_SIZE // 2),
                                        cv2.FONT_HERSHEY_PLAIN, 0.9, (255, 255, 255), 2)

                    except KeyError as e:
                        pass
        self.parent.speak_nearby_objects()

    def enter_realm_scanner(self):
        # check if still in realm
        if realm_in := self.detect_what_realm_in():
            if realm_in != self.realm:
                self.realm = realm_in
                self.quest_items.clear()
                self.unique_realm_assets = self.assetDB.get_realm_assets_for_realm(self.realm)
                self.mode = BotMode.REALM
                print(f"new realm entered: {self.realm}")

        threshold = 0.10

        block_size = (TILE_SIZE, TILE_SIZE)
        grid_in_tiles = view_as_blocks(self.grid_slice_gray, block_size)

        for y_i, col in enumerate(grid_in_tiles):
            for x_i, row in enumerate(col):
                for realm_item in self.quest_items:
                    res = cv2.matchTemplate(row, realm_item.data_gray[-32:, :32], cv2.TM_SQDIFF_NORMED,
                                            mask=realm_item.mask[-32:, :32])
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

                    if not min_val <= threshold:
                        continue

                    # loc = np.where(res <= threshold)
                    top_left = (x_i * TILE_SIZE, y_i * TILE_SIZE)
                    bottom_right = ((x_i + 1) * TILE_SIZE, (y_i + 1) * TILE_SIZE)

                    self.important_tile_locations.append(AssetGridLoc(x=x_i, y=y_i, short_name=realm_item.short_name))
                    if settings.DEBUG:
                        cv2.putText(self.output_debug_gray, realm_item.short_name,
                                    (x_i * TILE_SIZE, y_i * TILE_SIZE - TILE_SIZE // 2), cv2.FONT_HERSHEY_PLAIN, 0.9, (255),
                                    1)
                        cv2.rectangle(self.output_debug_gray, top_left, bottom_right, (255), 1)
                    break
                continue

                realm_item: Asset
                for realm_item in self.unique_realm_assets:
                    res = cv2.matchTemplate(row, realm_item.data_gray[-32:, :32], cv2.TM_SQDIFF_NORMED,
                                            mask=realm_item.mask[-32:, :32])
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

                    if not min_val <= threshold:
                        continue

                    # loc = np.where(res <= threshold)
                    top_left = (x_i * TILE_SIZE, y_i * TILE_SIZE)
                    bottom_right = ((x_i + 1) * TILE_SIZE, (y_i + 1) * TILE_SIZE)

                    self.important_tile_locations.append(AssetGridLoc(x=x_i, y=y_i, short_name=realm_item.short_name))
                    if settings.DEBUG:
                        cv2.putText(self.output_debug_gray, realm_item.short_name,
                                    (x_i * TILE_SIZE, y_i * TILE_SIZE - TILE_SIZE // 2), cv2.FONT_HERSHEY_PLAIN, 0.9, (255),
                                    1)
                        cv2.rectangle(self.output_debug_gray, top_left, bottom_right, (255), 1)
                    break
        self.parent.speak_nearby_objects()

    def realm_tile_has_matching_decoration(self) -> bool:
        pass

    def handle_new_frame(self, data: NewFrame):
        img = data.frame
        self.near_frame_color = img[:, :, :3]

        # grab nearby player tiles
        cv2.cvtColor(self.near_frame_color, cv2.COLOR_BGRA2GRAY, dst=self.near_frame_gray)

        # calculate the correct alignment for grid
        self.grid_near_rect = recompute_grid_offset(floor_tile=self.parent.castle_tile_gray,
                                                    gray_frame=self.near_frame_gray,
                                                    mss_rect=self.parent.nearby_rect_mss)

        self.grid_near_slice_gray: np.typing.ArrayLike = self.near_frame_gray[
                                                         self.grid_near_rect.y:self.grid_near_rect.y + self.grid_near_rect.h,
                                                         self.grid_near_rect.x:self.grid_near_rect.x + self.grid_near_rect.w]
        self.grid_near_slice_color: np.typing.ArrayLike = self.near_frame_color[
                                                          self.grid_near_rect.y:self.grid_near_rect.y + self.grid_near_rect.h,
                                                          self.grid_near_rect.x:self.grid_near_rect.x + self.grid_near_rect.w]
        if settings.DEBUG:
            self.output_debug_near_gray = self.grid_near_slice_gray.copy()

    def run(self):
        stop = False
        count = 0

        while not stop:
            msg: MessageImpl = self.nearby_queue.get(timeout=15)
            if msg.type is MessageType.NEW_FRAME:
                self.handle_new_frame(msg)
            try:
                # we don't block since we must be ready for new incoming frames ^^
                comm_msg: MessageImpl = self.nearby_comm_deque.pop()

                if comm_msg.type is MessageType.SCAN_FOR_ITEMS:
                    self.enter_castle_scanner()

                elif comm_msg.type is MessageType.DRAW_DEBUG:
                    cv2.imshow("SU Vision - Near bbox", self.output_debug_near_gray)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        cv2.destroyAllWindows()
                        break
            except IndexError:
                continue


if __name__ == "__main__":
    bot = Bot()
    bot.cache_image_hashes_of_decorations()
    print(f"{bot.su_client_rect=}")
    print(f"hashed {len(bot.castle_item_hashes)} images")
    bot.run()