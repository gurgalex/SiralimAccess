import enum
from typing import Optional

import cv2
import numpy as np
import mss
import win32gui
import win32com.client
import pytesseract
import math
import time
from skimage.util import view_as_blocks

from subot.read_tags import AssetDB, Asset

from numpy.typing import ArrayLike

from subot.hash_image import ImageInfo, HashDecor, CastleDecorationDict

from dataclasses import dataclass

import subot.background_subtract as background_subtract

from subot.models import Sprite, SpriteFrame, Quest, RealmLookup, Realm, SpriteType
from subot.models import Session

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'

# BGR colors
blue = (255, 0, 0)
purple = (255, 0, 255)
green = (0, 255, 0)
red = (0, 0, 255)
yellow = (0, 255, 255)
orange = (0, 215, 255)

TILE_SIZE = 32
NEARBY_TILES_WH: int = 7

title = "SU Vision"


@dataclass(frozen=True)
class TemplateMeta:
    name: str
    data: np.typing.ArrayLike
    color: tuple
    mask: np.typing.ArrayLike


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def as_tuple(self):
        return self.x, self.y


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
    windowOffset = math.floor(((rect[2]-rect[0])-clientRect[2])/2)
    titleOffset = ((rect[3]-rect[1])-clientRect[3]) - windowOffset
    newRect = (rect[0]+windowOffset, rect[1]+titleOffset, rect[2]-windowOffset, rect[3]-windowOffset)

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

class Bot:
    def __init__(self):
        self.quest_sprite_long_names: list[str] = []
        self.mode: BotMode = BotMode.UNDETERMINED
        self.assetDB: AssetDB = AssetDB
        # Used to only analyze the SU window
        self.su_client_rect = get_su_client_rect()
        """player tile position in grid"""
        self.player_position: Rect = Bot.compute_player_position(self.su_client_rect)
        self.player_position_tile: TileCoord = TileCoord(x=self.player_position.x//TILE_SIZE, y=self.player_position.y//TILE_SIZE)
        print(f"{self.player_position_tile=}")
        print(f"{self.player_position=}")

        self.nearby_rect: Rect = self.compute_nearby_screenshot_area()
        self.nearby_tile_top_left: TileCoord = TileCoord(x=self.nearby_rect.x//TILE_SIZE, y=self.nearby_rect.y//TILE_SIZE)
        print(f"{self.su_client_rect=}")
        print(f"{self.nearby_rect=}")

        print(f"{self.player_position_tile=}")
        print(f"{self.nearby_tile_top_left=}")

        # Windows TTS speaker
        self.Speaker = win32com.client.Dispatch("SAPI.SpVoice")
        # don't block the program when speaking. Cancel any pending speaking directions
        self.SVSFlag = 3 # SVSFlagsAsync = 1 + SVSFPurgeBeforeSpeak = 2
        self.Speaker.Voice = self.Speaker.getVoices('Name=Microsoft Zira Desktop').Item(0)

        """player tile position in grid"""
        self.player_position: Rect = Bot.compute_player_position(self.su_client_rect)
        self.player_position_tile: TileCoord = TileCoord(x=self.player_position.x//TILE_SIZE, y=self.player_position.y//TILE_SIZE)
        print(f"{self.player_position_tile=}")
        print(f"{self.player_position=}")
        self.frame: np.typing.ArrayLike = np.zeros(shape=(self.su_client_rect.h, self.su_client_rect.w), dtype="uint8")
        self.gray_frame: np.typing.ArrayLike = np.zeros(shape=(self.su_client_rect.h, self.su_client_rect.w), dtype="uint8")

        # Note: images must be read as unchanged when converting to grayscale since IM_READ_GRAYSCALE has platform specific conversion methods and difers from cv2.cv2.BGR2GRAy's implementation in cvtcolor
        # This is needed to ensure the pixels match exactly for comparision, otherwhise the grayscale differs slightly
        # https://docs.opencv.org/4.5.1/d4/da8/group__imgcodecs.html
        self.castle_tile: np.typing.ArrayLike = cv2.imread("../assets_padded/floortiles/Standard Floor Tile-frame1.png", cv2.IMREAD_COLOR)

        self.castle_tile_gray: np.typing.ArrayLike = cv2.cvtColor(self.castle_tile, cv2.COLOR_BGR2GRAY)
        self.realm_tile: Asset = None

        # used to tell if the player has moved since last scanning for objects
        self.previous_important_tile_locations: list[AssetGridLoc] = []


        self.grid_rect: Optional[Rect] = None
        self.grid_slice_gray: np.typing.ArrayLike = None
        self.grid_slice_color: np.typing.ArrayLike = None
        self.grid_dims: tuple = (self.su_client_rect.w//TILE_SIZE, self.su_client_rect.h//TILE_SIZE)

        self.grid_near_rect: Optional[Rect] = None
        self.grid_near_slice_gray: np.typing.ArrayLike = None
        self.grid_near_slice_color: np.typing.ArrayLike = None

        self.output_debug_gray: np.typing.ArrayLike = None
        self.output_debug_near_gray: np.typing.ArrayLike = None

        # hashes of sprite frames that have matching `self.castle_tile` pixels set to black.
        # This avoids false negative matches if the placed object has matching color pixels in a position
        self.castle_item_hashes: CastleDecorationDict = CastleDecorationDict(castle_tile_gray=self.castle_tile_gray)

        self.realm_hashes: HashDecor = HashDecor()

        self.realm: Optional[str] = None
        self.unique_realm_assets = list[Asset]

        # The current active quests
        self.active_quests: list[Quest] = []
        # self.quest_item_locations: list[QuestAssetGridLoc] = []

        # realm object locations in screenshot
        self.important_tile_locations: list[AssetGridLoc] = []

    def cache_image_hashes_of_decorations(self) -> HashDecor:
        errors = 0
        hash_decor = HashDecor()

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
                    if one_tile_worth_img.shape != (32,32, 4):
                        print(f"not padded tile -skipping - {sprite_frame.filepath}")
                        continue

                    # new castle hasher
                    self.castle_item_hashes.insert_transparent_bgra_image(one_tile_worth_img, metadata)

    def detect_what_realm_in(self) -> Optional[str]:
        # Scan a 7x7 tile area for lit tiles to determine what realm we are in currently
        # This area was chosen since the player + 6 creatures are at most this long
        # At least 1 tile will not be dimmed by the fog of war
        realm_tiles = self.assetDB.all_realm_floortiles()

        block_size = (TILE_SIZE, TILE_SIZE)
        grid_in_tiles = view_as_blocks(self.grid_slice_gray, block_size)


        for y_i, col in enumerate(grid_in_tiles):
            for x_i, row in enumerate(col):
                for realm_tile in realm_tiles:
                    if row.tobytes() == realm_tile.data_gray.tobytes():
                        self.realm_tile = realm_tile
                        return realm_tile.realm



    def detect_if_in_castle(self):
        # Check configured castle tile
        block_size = (TILE_SIZE, TILE_SIZE)
        grid_in_tiles = view_as_blocks(self.grid_slice_gray, block_size)
        castle_tile = self.castle_tile_gray

        for y_i, col in enumerate(grid_in_tiles):
            for x_i, row in enumerate(col):
                if row.tobytes() == castle_tile.tobytes():
                    print("We are in the castle")
                    return True
        return False


    @staticmethod
    def compute_player_position(client_dimensions: Rect) -> Rect:
        """The top-left of the player sprite is drawn at the center of the screen (relative to window)"""

        # the player is always in the center of the window of the game
        #offset
        #######xxxxx###
        #######xxCxx###
        #######xxxxx###

        # return TileCoord(x=client_dimensions.w//32//2, y=client_dimensions.h//32//2)

        ## old way
        return Rect(x=round(client_dimensions.w/2), y=round(client_dimensions.h/2),
                    w=TILE_SIZE, h=TILE_SIZE)

    @staticmethod
    def top_left_tile(aligned_floor_tile: Rect, client_rect: Rect) -> Point:


        top_left_pt =  Point(x=aligned_floor_tile.x - (aligned_floor_tile.x // TILE_SIZE) * TILE_SIZE,
                     y=aligned_floor_tile.y - (aligned_floor_tile.y // TILE_SIZE) * TILE_SIZE)
        return top_left_pt

    @staticmethod
    def bottom_right_tile(aligned_tile: Rect, client_rect: Rect) -> Point:
        """Returns top-left coords of bottom-most rectangle"""

        #todo: Use floor tile alignment and client rect to compute bottom right tile

        bottom_right_pt = Point(x=aligned_tile.x + ((client_rect.w - aligned_tile.x) // TILE_SIZE) * TILE_SIZE - TILE_SIZE,
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
        print(f"{self.player_position=}")
        return Rect(
            x=(self.player_position_tile.x - NEARBY_TILES_WH//2) * TILE_SIZE,
            y=(self.player_position_tile.y - NEARBY_TILES_WH//2) * TILE_SIZE,
            w=TILE_SIZE*NEARBY_TILES_WH,
            h=TILE_SIZE*NEARBY_TILES_WH,
        )


    def enter_castle_scanner(self):
        """Scans for decorations and quests in the castle"""

        quests = extract_quest_name_from_quest_area(gray_frame=self.gray_frame)
        for quest_number, quest in enumerate(quests, start=1):
            sprite_short_names = [sprite.short_name for sprite in quest.sprites]
            sprite_long_names = [sprite.long_name for sprite in quest.sprites]
            print(f"active quest #{quest_number}: {quest.title} - Needs sprites: {sprite_short_names}")
            for sprite_long_name in sprite_long_names:
                self.quest_sprite_long_names.append(sprite_long_name)

        # print(f"{self.nearby_rect=}")
        for row in range(0, self.grid_rect.w-TILE_SIZE, TILE_SIZE):
            for col in range(0, self.grid_rect.h-TILE_SIZE, TILE_SIZE):
                # print(f"{(row, col)=}")
                tile_gray = self.grid_slice_gray[col:col + TILE_SIZE, row:row + TILE_SIZE]
                tile_color = self.grid_slice_color[col:col+TILE_SIZE, row:row+TILE_SIZE, :3]

                fg_only = background_subtract.subtract_background_color_tile(tile=tile_color, floor=self.castle_tile)
                fg_only_gray = cv2.cvtColor(fg_only, cv2.COLOR_BGR2GRAY)
                tile_gray[:] = fg_only_gray
                self.output_debug_gray[col:col + TILE_SIZE, row:row + TILE_SIZE] = fg_only_gray

                try:
                    img_info = self.castle_item_hashes.get_greyscale(tile_gray[:32, :32])
                    if img_info.long_name in self.quest_sprite_long_names:
                        self.important_tile_locations.append(AssetGridLoc(x=row//TILE_SIZE, y=col//TILE_SIZE, short_name=img_info.short_name))
                    # print(f"matched: {img_info.long_name}")
                    cv2.rectangle(self.output_debug_gray, (row, col), (row + TILE_SIZE, col + TILE_SIZE), (255,255,255), 1)
                    # label finding with text
                    cv2.putText(self.output_debug_gray, img_info.long_name, (row, col + TILE_SIZE // 2), cv2.FONT_HERSHEY_PLAIN, 0.9, (255, 255, 255), 2)

                except KeyError as e:
                    pass
        self.speak_nearby_objects()


    def recompute_grid_offset(self, grid_type: GridType):
        # find matching realm tile on map
        # We use matchTemplate since the grid shifts when the player is moving
        # (the tiles smoothly slide to the next `TILE_SIZE increment)
        if self.mode == BotMode.CASTLE or self.mode == BotMode.UNDETERMINED:
            floor_tile = self.castle_tile_gray
        elif self.mode == BotMode.REALM:
            floor_tile = self.realm_tile.data_gray
        assert floor_tile is not None

        if grid_type == GridType.WHOLE:
            gray_frame = self.gray_frame
        elif grid_type == GridType.NEARBY:
            gray_frame = self.near_frame_gray

        res = cv2.matchTemplate(gray_frame, floor_tile, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        threshold = 0.95
        if max_val <= threshold:
            # maybe default to center?
            tile = Bot.compute_player_position(self.su_client_rect)
        else:
            tile = Rect.from_cv2_loc(max_loc, w=TILE_SIZE, h=TILE_SIZE)
            # print(f"aligned floor tile = {tile}")

        if grid_type == GridType.WHOLE:
            top_left_pt = Bot.top_left_tile(aligned_floor_tile=tile, client_rect=self.su_client_rect)
            bottom_right_pt = Bot.bottom_right_tile(aligned_tile=tile, client_rect=self.su_client_rect)
            self.grid_rect = Bot.compute_grid_rect(top_left_tile=top_left_pt, bottom_right_tile=bottom_right_pt)
            # print(f"full grid - {top_left_pt=}, {bottom_right_pt=}")
            # print(f"{self.grid_rect=}")
        elif grid_type == GridType.NEARBY:
            top_left_pt = Bot.top_left_tile(aligned_floor_tile=tile, client_rect=self.nearby_rect)
            bottom_right_pt = Bot.bottom_right_tile(aligned_tile=tile, client_rect=self.nearby_rect)
            self.grid_near_rect = Bot.compute_grid_rect(top_left_tile=top_left_pt, bottom_right_tile=bottom_right_pt)
            # print(f"near grid - {top_left_pt=}, {bottom_right_pt=}")
            # print(f"{self.nearby_rect=}")

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
                    cv2.putText(self.output_debug_gray, realm_item.short_name,
                                (x_i * TILE_SIZE, y_i * TILE_SIZE - TILE_SIZE // 2), cv2.FONT_HERSHEY_PLAIN, 0.9, (255), 1)
                    cv2.rectangle(self.output_debug_gray, top_left, bottom_right, (255), 1)
                    break
                continue

                realm_item: Asset
                for realm_item in self.unique_realm_assets:
                    res = cv2.matchTemplate(row, realm_item.data_gray[-32:, :32], cv2.TM_SQDIFF_NORMED, mask=realm_item.mask[-32:,:32])
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

                    if not min_val <= threshold:
                        continue

                    # loc = np.where(res <= threshold)
                    top_left = (x_i * TILE_SIZE, y_i * TILE_SIZE)
                    bottom_right = ((x_i+1) * TILE_SIZE, (y_i+1)*TILE_SIZE)

                    # 3 Won't work due to transparent mask in template image hashing'
                    # phasher = cv2.img_hash.PHash_create()
                    # tile_hash = phasher.compute(row)
                    # print(f"tile hash = {tile_hash}")
                    # print(f"realm item phash = {realm_item.phash}")
                    # print(f"matched {realm_item.short_name} - tile phash match: {tile_hash == realm_item.phash}")

                    # print(f"matched {realm_item.short_name}, filename = {realm_item.path.stem}")
                    self.important_tile_locations.append(AssetGridLoc(x=x_i, y=y_i, short_name=realm_item.short_name))
                    cv2.putText(self.output_debug_gray, realm_item.short_name, (x_i * TILE_SIZE, y_i * TILE_SIZE - TILE_SIZE // 2), cv2.FONT_HERSHEY_PLAIN, 0.9, (255), 1)
                    cv2.rectangle(self.output_debug_gray, top_left, bottom_right, (255), 1)
                    break
        self.speak_nearby_objects()


    def realm_tile_has_matching_decoration(self) -> bool:
        pass

    def run(self):
        print(f"{self.grid_dims=}")
        # start assetDB
        self.assetDB = self.assetDB()

        print(f"known quests")
        frames_asset: list[Asset]
        with Session() as session:
            quest: Quest
            for quest in session.query(Quest).all():
                print(quest.title, [sprite.long_name for sprite in quest.sprites])


        mon_full_window = {"top": self.su_client_rect.y, "left": self.su_client_rect.x, "width": self.su_client_rect.w, "height": self.su_client_rect.h}
        nearby_mon = {"top": self.su_client_rect.y + self.nearby_rect.y, "left": self.su_client_rect.x + self.nearby_rect.x, "width": self.nearby_rect.w, "height": self.nearby_rect.h}

        iters = 0
        every = 5
        self.player_position_tile = TileCoord(x=self.player_position.x // TILE_SIZE,
                                              y=self.player_position.y // TILE_SIZE)

        with mss.mss() as sct:
            while True:
                self.important_tile_locations.clear()
                if iters % every == 0:
                    start = time.time()
                shot = sct.grab(mon_full_window)

                self.frame = np.asarray(shot)
                cv2.cvtColor(self.frame, cv2.COLOR_BGRA2GRAY, dst=self.gray_frame)
                self.recompute_grid_offset(grid_type=GridType.WHOLE)


                # grab nearby player tiles
                self.near_frame = np.asarray(sct.grab(nearby_mon))
                cv2.cvtColor(self.near_frame, cv2.COLOR_BGRA2GRAY, dst=self.near_frame_gray)

                self.recompute_grid_offset(grid_type=GridType.NEARBY)
                self.grid_slice_gray: np.typing.ArrayLike = self.gray_frame[self.grid_rect.y:self.grid_rect.y + self.grid_rect.h,
                                  self.grid_rect.x:self.grid_rect.x + self.grid_rect.w]
                self.grid_slice_color: np.typing.ArrayLike = self.frame[self.grid_rect.y:self.grid_rect.y + self.grid_rect.h,
                                  self.grid_rect.x:self.grid_rect.x + self.grid_rect.w]

                self.grid_near_slice_gray: np.typing.ArrayLike = self.near_frame_gray[self.grid_near_rect.y:self.grid_near_rect.y + self.grid_near_rect.h,
                                                                   self.grid_near_rect.x:self.grid_near_rect.x + self.grid_near_rect.w]
                self.grid_near_slice_color: np.typing.ArrayLike = self.near_frame_color[self.grid_near_rect.y:self.grid_near_rect.y + self.grid_near_rect.h,
                                                                    self.grid_near_rect.x:self.grid_near_rect.x + self.grid_near_rect.w]

                self.output_debug_gray = self.grid_slice_gray.copy()
                self.output_debug_near_gray = self.grid_near_slice_gray.copy()
                # print(f"{self.near_frame_gray.shape=}")
                # print(f"{self.grid_near_rect=}")
                # print(f"{self.grid_near_slice_gray.shape=}")
                # print(f"{self.output_debug_near_gray.shape=}")

                self.player_position = Bot.compute_player_position(self.grid_rect)
                self.player_position_tile = TileCoord(x=self.player_position.x // TILE_SIZE,
                                                      y=self.player_position.y // TILE_SIZE)

                if self.mode is BotMode.UNDETERMINED:

                    if self.detect_if_in_castle():
                        self.mode = BotMode.CASTLE
                    if realm_in := self.detect_what_realm_in():
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
                    bot.enter_castle_scanner()

                # label player position
                top_left = self.player_position.top_left().as_tuple()
                bottom_right = self.player_position.bottom_right().as_tuple()
                cv2.rectangle(self.grid_slice_gray, top_left, bottom_right, (255), 1)

                cv2.imshow(title, self.output_debug_gray)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cv2.destroyAllWindows()
                    break
                if iters % every == 0:
                    end = time.time()
                    print(f"FPS: {1/((end-start))}")
                iters += 1

    def play_important_objects(self):
        if self.important_tile_locations == self.previous_important_tile_locations:
            pass

    def speak_nearby_objects(self):
        if self.important_tile_locations == self.previous_important_tile_locations:
            return
             # skip speaking since nothing (besides enemies) have changed positions

        for tile in self.important_tile_locations:
            distance_x = tile.x - self.player_position_tile.x
            distance_y = tile.y - self.player_position_tile.y
            y_letter = 'UP' if distance_y < 0 else "D"
            x_letter = 'L' if distance_x < 0 else "R"
            abs_x = abs(distance_x)
            abs_y = abs(distance_y)
            distance_text = f"{tile.short_name} is {abs_x}{x_letter}{abs_y}{y_letter}"
            print(distance_text)
            self.Speaker.Speak(distance_text, self.SVSFlag)

        self.previous_important_tile_locations = self.important_tile_locations[:]


if __name__ == "__main__":
    bot = Bot()
    bot.cache_image_hashes_of_decorations()
    print(f"{bot.su_client_rect=}")
    print(f"{bot.grid_rect=}")
    print(f"hashed {len(bot.castle_item_hashes)} images")
    bot.run()