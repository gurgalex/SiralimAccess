import enum
import time
from pathlib import Path

import cv2
from numpy.typing import ArrayLike

from subot.utils import Point
import numpy as np

from enum import Enum


class Color(enum.Enum):
    """BGR colors"""
    khaki = (140,230,240)
    black = (0, 0, 0)
    blue = (255, 0, 0)
    goldenrod = (32, 165, 218)
    gray = (153, 136, 119)
    green = (0, 255, 0)
    maroon = (0, 0, 128)
    orange = (0, 215, 255)
    olive = (0, 128, 128)
    purple = (255, 0, 255)
    pink = (147, 0, 255)
    red = (0, 0, 255)
    saddlebrown = (19, 69,139)
    silver = (192, 192, 192)
    white = (255, 255, 255)
    yellow = (0, 255, 255)


class TileType(Enum):
    UNKNOWN = (0, Color.maroon)
    ALTAR = (1, Color.pink)
    BLACK = (99, Color.black)
    CHEST = (2, Color.goldenrod)
    COMMON_CHEST = (3, Color.saddlebrown)
    CREATURE = (4, None)
    DECORATION = (5, Color.khaki)
    DIVINATION_CANDLE = (6, None)
    DUMPLING = (7, None)
    EMBLEM = (8, Color.silver)
    ENEMY = (9, None)
    FLOOR = (10, Color.white)
    MASTER_NPC = (11, Color.orange)
    NPC = (12, Color.green)
    PROJECT_ITEM = (13, Color.yellow)
    PLAYER = (14, Color.olive)
    QUEST = (15, Color.red)
    RESOURCE_NODE = (16, None)
    TELEPORTATION_SHRINE = (17, Color.blue)
    TREASURE_GOLEM = (18, None)
    WALL = (19, Color.gray)
    ARTIFACT_MATERIAL_BAG = (20, None)
    SPELL_MATERIAL_BAG = (21, None)
    # blue bag
    TRICK_MATERIAL_BOX = (22, None)
    TRAIT_MATERIAL_BOX = (23, None)

    def __init__(self, num, color: Color):
        self.num = num
        self.color = color


class Map:
    def __init__(self, map_size: Point):
        self.map: ArrayLike = np.zeros((map_size.y, map_size.x), dtype='uint8')
        self.img: ArrayLike = np.zeros((map_size.y, map_size.x, 3), dtype='uint8')
        self.center: int = map_size.x // 2 + 1

    def set(self, tile: Point, sprite_type: TileType):
        self.map[self.center + tile.y, self.center + tile.x] = sprite_type.num
        if sprite_type.color:
            self.img[self.center + tile.y, self.center + tile.x] = sprite_type.color.value

    def print(self):
        print(f"{self.map=}")
        time_saved = time.time()
        data_dir = Path(__file__).parent.joinpath("datas")
        cv2.imwrite(data_dir.joinpath(f"{time_saved}-map.png").as_posix(), self.img)
        np.save(data_dir.joinpath(f"{time_saved}-data-map.npy").as_posix(), self.map)
        print(f"saved test data {time_saved}")

    def clear(self):
        self.map[:] = TileType.UNKNOWN.num
        self.img[:] = TileType.UNKNOWN.color.value

    def populate_from_list(self, tiles: list):
        pass

    def from_tiles(self, tiles):
        self.map = np.asarray(tiles, dtype='uint8')
        print(f"map shape = {self.map.shape}")


