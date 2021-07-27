import enum

from numpy.typing import ArrayLike

from subot.utils import Point
import numpy as np

from enum import Enum


class Color(enum.Enum):
    """BGR colors"""
    blue = (255, 0, 0)
    goldenrod = (32, 165, 218)
    gray = (153, 136, 119)
    green = (0, 255, 0)
    maroon = (0, 0, 128)
    orange = (0, 215, 255)
    purple = (255, 0, 255)
    pink = (147, 0, 255)
    red = (0, 0, 255)
    saddlebrown = (19, 69,139)
    silver = (192, 192, 192)
    white = (255, 255, 255)
    yellow = (0, 255, 255)


class FoundType(Enum):
    UNKNOWN = (0, None)
    ALTAR = (5, Color.pink)
    BLACK = (99, Color.maroon)
    CHEST = (14, Color.goldenrod)
    COMMON_CHEST = (13, Color.saddlebrown)
    CREATURE = (10, None)
    DECORATION = (50, None)
    EMBLEM = (12, Color.silver)
    ENEMY = (3, None)
    FLOOR = (1, Color.white)
    MASTER_NPC = (6, Color.orange)
    NPC = (4, Color.green)
    PROJ_ITEM = (7, Color.yellow)
    PLAYER = (80, None)
    QUEST = (9, Color.red)
    RESOURCE_NODE = (8, None)
    TELEPORTATION_SHRINE = (11, Color.blue)
    WALL = (2, Color.gray)

    def __init__(self, num, color: Color):
        self.num = num
        self.color = color


class Map:
    def __init__(self, map_size: Point):
        self.map: ArrayLike = np.zeros((map_size.y, map_size.x), dtype='uint8')
        self.center: int = map_size.x // 2 + 1

    def set(self, tile: Point, sprite_type: FoundType):
        self.map[tile.y, tile.x] = sprite_type.value

    def print(self):
        print(f"{self.map=}")

    def clear(self):
        self.map[:] = FoundType.UNKNOWN.value

    def populate_from_list(self, tiles: list):
        pass


