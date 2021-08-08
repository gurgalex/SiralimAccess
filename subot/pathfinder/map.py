from __future__ import annotations
import enum
from collections import deque, defaultdict
from typing import Optional, NewType

import cv2
from numpy.typing import ArrayLike

from subot.utils import Point
import numpy as np

from enum import Enum
from recordclass import dataobject, asdict, astuple
from dataclasses import dataclass


class Color(enum.Enum):
    """BGR colors"""
    khaki = (140, 230, 240)
    black = (0, 0, 0)
    blue = (255, 0, 0)
    goldenrod = (32, 165, 218)
    gray = (153, 136, 119)
    green = (0, 255, 0)
    maroon = (0, 0, 128)
    orange = (0, 215, 255)
    olive = (0, 128, 128)
    pastel_red = (160, 160, 250)
    purple = (255, 0, 255)
    pink = (147, 0, 255)
    red = (0, 0, 255)
    saddlebrown = (19, 69, 139)
    silver = (192, 192, 192)
    tan = (140, 180, 210)
    teal = (128, 128, 0)
    white = (255, 255, 255)
    yellow = (0, 255, 255)
    unfilled = (80, 80, 80)


class TileType(Enum):
    UNKNOWN = (0, Color.maroon)
    ALTAR = (1, Color.pink)
    BLACK = (99, Color.black)
    REACHABLE_BLACK = (98, Color.pastel_red)
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
    # gold box
    TRAIT_MATERIAL_BOX = (23, None)
    UNFILLED = (24, Color.unfilled)
    PASSAGEWAY_EXIT = (25, Color.teal)
    DEAD_END = (26, Color.tan)

    def __init__(self, num, color: Color):
        self.num = num
        self.color = color


class Movement(dataobject, fast_new=True, gc=False):
    x: int
    y: int


class DefaultFormatter:
    @classmethod
    def from_tile_type(cls, tile: TileType) -> str:
        return tile.name

    @classmethod
    def to_tile_type(cls, tile: str) -> TileType:
        return TileType[tile]


class AsciiConverter:
    char_to_tile_type = {
        "A": TileType.ALTAR,
        "B": TileType.BLACK,
        "F": TileType.FLOOR,
        "U": TileType.UNKNOWN,
        ".": TileType.UNFILLED,
        "P": TileType.PLAYER,
        "W": TileType.WALL,
        "R": TileType.REACHABLE_BLACK,
    }
    tile_type_to_char = {v: k for k, v in char_to_tile_type.items()}

    @classmethod
    def from_tile_type(cls, tile_type: TileType) -> str:
        return cls.tile_type_to_char[tile_type]

    @classmethod
    def to_tile_type(cls, char: str) -> TileType:
        return cls.char_to_tile_type[char]


@dataclass(frozen=True, eq=True)
class WallSet2:
    north: bool = False
    northeast: bool = False
    east: bool = False
    southeast: bool = False
    south: bool = False
    southwest: bool = False
    west: bool = False
    northwest: bool = False

    def is_corridor(self) -> bool:
        return self in corridors

    def is_dead_end(self) -> bool:
        return self in dead_ends

corridors: set[WallSet2] = set()
corridors.add(WallSet2(northeast=True, northwest=True, southeast=True, southwest=True))
corridors.add(WallSet2(northeast=True, northwest=True, southeast=True, southwest=True, north=True))
corridors.add(WallSet2(northeast=True, northwest=True, southeast=True, southwest=True, east=True))
corridors.add(WallSet2(northeast=True, northwest=True, southeast=True, southwest=True, south=True))
corridors.add(WallSet2(northeast=True, northwest=True, southeast=True, southwest=True, west=True))

dead_ends: set[WallSet2] = set()
dead_ends.add(WallSet2(northeast=True, northwest=True, southeast=True, southwest=True, north=True, south=True, east=True, west=False))
dead_ends.add(WallSet2(northeast=True, northwest=True, southeast=True, southwest=True, north=True, south=True, east=False, west=True))
dead_ends.add(WallSet2(northeast=True, northwest=True, southeast=True, southwest=True, north=True, south=False, east=True, west=True))
dead_ends.add(WallSet2(northeast=True, northwest=True, southeast=True, southwest=True, north=False, south=True, east=True, west=True))

dead_ends.add(WallSet2(north=True, northeast=True, east=True, southeast=True, south=True))
dead_ends.add(WallSet2(north=True, northwest=True, west=True, southwest=True, south=True))

dead_ends.add(WallSet2(north=True, east=True, southeast=True, northwest=True, south=True))
dead_ends.add(WallSet2(east=True, southeast=True, south=True, southwest=True, west=True))

# with player up
dead_ends.add(WallSet2(east=True, southeast=True, south=True, southwest=True, west=True, north=True))

Link = NewType('Link', Point)


class Map:
    movements: list[Movement] = [Movement(x=1, y=0), Movement(x=-1, y=0), Movement(x=0, y=1), Movement(x=0, y=-1)]
    directions = {
        "north": Point(x=0, y=-1),
        "northeast": Point(x=1, y=-1),
        "east": Point(x=1, y=0),
        "southeast": Point(x=1, y=1),
        "south": Point(x=0, y=1),
        "southwest": Point(x=-1, y=1),
        "west": Point(x=-1, y=0),
        "northwest": Point(x=-1, y=-1)
    }

    def __init__(self, arr: ArrayLike, formatter: Optional[object] = None):
        self.map: ArrayLike = arr
        self.img: ArrayLike = np.zeros((self.map.shape[0], self.map.shape[1], 3), dtype='uint8')
        self.center: Point = Point(x=self.map.shape[1] // 2, y=self.map.shape[0] // 2)
        self.adj_list: dict[TileType, dict[Point, list[Point]]] = dict()
        self.formatter = formatter if formatter else DefaultFormatter()

    def set(self, tile: Point, sprite_type: TileType):
        self.map[self.center.y + tile.y, self.center.y + tile.x] = sprite_type
        self.img[self.center.y + tile.y, self.center.y + tile.x] = sprite_type.color.value

    def to_ascii(self) -> list[list[str]]:
        text_map = []
        for y in range(self.map.shape[1]):
            text_map.append([])
            for x in range(self.map.shape[0]):
                item = self.map.item(y, x)
                char = AsciiConverter.from_tile_type(item)
                text_map[y].append(char)
            text_map[y] = ''.join(text_map[y])
        return text_map

    def clear(self):
        self.map[:] = TileType.UNFILLED
        self.img[:] = TileType.UNFILLED.color.value
        self.adj_list.clear()

    @classmethod
    def from_tiles(cls, tiles: list[list[TileType]]):
        arr = np.asarray(tiles, dtype='object')
        return cls(arr)

    @classmethod
    def from_ascii(cls, text: list[str]):
        tiles = []
        for i, row in enumerate(text):
            tiles.append([])
            char: str
            for col in row:
                char = col.upper()
                tile = AsciiConverter.to_tile_type(char)
                tiles[i].append(tile)
        return cls(np.asarray(tiles))

    def save_as_img(self, filename: str):
        img = []
        for i in range(self.map.shape[0]):
            img.append([])
            for j in range(self.map.shape[1]):
                img[i].append(self.map.item(i, j).color.value)

        img = np.asarray(img, dtype='uint8')
        cv2.imwrite(filename, img)

    def analyze_tile_for_walls(self, point: Point, tile_type: TileType) -> TileType:
        if tile_type is TileType.WALL or tile_type is TileType.UNKNOWN:
            return tile_type

        d = {}

        point: Point
        for direction, offset in self.directions.items():
            try:
                nearby_tile = self.map[point.y + offset.y, point.x + offset.x]
                d[direction] = nearby_tile is TileType.WALL
                if nearby_tile is TileType.UNKNOWN:
                    d[direction] = True
                elif nearby_tile is TileType.REACHABLE_BLACK:
                    d[direction] = False
            except IndexError:
                d[direction] = False
        wall_set = WallSet2(**d)

        if wall_set.is_corridor():
            return TileType.PASSAGEWAY_EXIT

        # prevent wrongly marked dead ends (like chests)
        if tile_type is TileType.CHEST:
            return tile_type
        elif tile_type is TileType.DECORATION:
            return tile_type

        if wall_set.is_dead_end():
            return TileType.DEAD_END

        return tile_type


    def find_reachable_blocks(self):
        marked: set[Point] = set()
        # print(f"map center type = {self.map[self.center.y, self.center.x]}")
        queue: deque[tuple[Point, Optional[Link]]] = deque()
        # add player position
        link: Optional[Point] = None
        queue.append((self.center, link))

        while queue:
            v, link = queue.popleft()
            tile: TileType = TileType[self.map[v.y, v.x].name]
            if tile is TileType.WALL or tile is TileType.BLACK or tile is TileType.UNFILLED:
                continue
            elif tile is TileType.UNKNOWN:
                pass
            else:
                link = v
            for movement in Map.movements:
                next_point = Point(x=v.x + movement.x, y=v.y + movement.y)
                if not self.can_visit(next_point, tile, marked):
                    continue
                marked.add(next_point)
                next_tile = TileType[self.map[next_point.y, next_point.x].name]

                if tile is TileType.BLACK or tile is TileType.UNKNOWN or tile is TileType.WALL:
                    link = link
                else:
                    link = v

                self.adj_list.setdefault(next_tile, defaultdict(list))[next_point].append(link)
                queue.append((next_point, link))

        for k, v in self.adj_list.items():
            if k is TileType.BLACK:
                for node, neighbors in v.items():
                    self.map[node.y, node.x] = TileType.REACHABLE_BLACK
                    self.img[node.y, node.x] = TileType.REACHABLE_BLACK.color.value

        # scan 3 tiles way from player for corridors
        PASSAGE_VIEW = min(3, self.center.y)
        ranges = ((-PASSAGE_VIEW, 0+1), (1, PASSAGE_VIEW+1))
        for r in ranges:
            for idx_tile in range(*r):
                tile_to_analyze = Point(x=self.center.x, y=self.center.y + idx_tile)
                numpy_tuple = (tile_to_analyze.y, tile_to_analyze.x)
                current_tile = self.map[numpy_tuple]
                if current_tile is TileType.WALL:
                    break

                new_tile_type = self.analyze_tile_for_walls(tile_to_analyze, current_tile)
                self.map[numpy_tuple] = new_tile_type
                if new_tile_type.color:
                    self.img[numpy_tuple] = new_tile_type.color.value
        for r in ranges:
            for idx_tile in range(*r):
                tile_to_analyze = Point(x=self.center.x + idx_tile, y=self.center.y)
                numpy_tuple = (tile_to_analyze.y, tile_to_analyze.x)
                current_tile = self.map[numpy_tuple]
                if current_tile is TileType.WALL:
                    break

                new_tile_type = self.analyze_tile_for_walls(tile_to_analyze, current_tile)
                self.map[numpy_tuple] = new_tile_type
                if new_tile_type.color:
                    self.img[numpy_tuple] = new_tile_type.color.value

    def can_visit(self, tile: Point, tile_type: TileType, marked: set[Point]) -> bool:
        if tile in marked:
            return False
        if tile_type is TileType.BLACK:
            return False

        out_of_bounds = tile.x < 0 or tile.x >= self.map.shape[1] or tile.y < 0 or tile.y >= self.map.shape[0]
        if out_of_bounds:
            return False

        return True

    def set_center(self, center: Point):
        self.center = center





