from __future__ import annotations

import dataclasses
from collections import defaultdict
from enum import Enum, auto

# 3.10
# from typing import TypeAlias, Union
from typing import Union, NewType

from saver.save import Save, load_blank_save
from subot.pathfinder.map import TileType

"""
Seems the location spawned into when entering a portal is the same.
It is unlikely the player is on this exact tile when entering the portal, hopefully the game repeats the location if so.

Player is at 864, 1056 - location teleported to when entering portal

Player is at 864, 1056 - location teleported to when entering portal
Player is at 864, 1056 - location spawned at inside nether boss portal"""
import queue
import subprocess
import time
from typing import Optional

from subot.models import Realm
from subot.utils import Point
from constants import TILE_SIZE
from dataclasses import dataclass




PORTAL_ENTER_PLAYER_LOCATION = Point(864//TILE_SIZE, 1056//TILE_SIZE)

from dataclasses import dataclass

import re

GAME_START_REGEX = re.compile(r"Entering main loop")
PLAYER_LOCATION_REGEX = re.compile(r"Player is at (\d+), (\d+)")
OBJ_PLACEMENT_REGEX = re.compile(r"placing (?P<obj>.*)  (?P<x>\d+), (?P<y>\d+)")
QUEST_RECEIVED_REGEX = re.compile(r"Quest Received: (?P<desc>.*)")


@dataclass(frozen=True)
class GameStart:
    pass


@dataclass(frozen=True)
class PlayerMoved:
    to: Point


@dataclass(frozen=True)
class ObjPlaced:
    obj: str
    placed_at: Point


@dataclass(frozen=True)
class TeleportToRealm:
    spawn_point: Point


@dataclass(frozen=True)
class TeleportToCastle:
    pass


@dataclass(frozen=True)
class InnerPortalEntered:
    """The player entered a portal inside a realm
    future: Portal type + objects spawned in if provided in the future game output
    """
    pass


@dataclass(frozen=True)
class QuestReceived:
    quest_description: str


@dataclass(frozen=True)
class SaveUpdated:
    save: Save


LowLevelEvent = Union[PlayerMoved, ObjPlaced, QuestReceived, GameStart]

HighLevelEvent = Union[GameStart, ObjPlaced, QuestReceived, TeleportToCastle, TeleportToRealm, InnerPortalEntered, SaveUpdated]


def tile_sum_diff(p1: Point, p2: Point) -> int:
    diff = abs(p2.x - p1.x) + abs(p2.y - p1.y)
    return diff


class BotMode(Enum):
    GAME_START_LOADING = auto()
    CASTLE = auto()
    REALM_LOADING = auto()
    REALM = auto()
    BATTLE = auto()
    UNDETERMINED = auto()


OBJ_TO_REALM_MAPPING = {
    "obj_amalg_brazier": Realm.AMALGAM_GARDENS,
    "obj_spidereggs": Realm.ARACHNID_NEST,
    "obj_gallery_portal": Realm.ASTRAL_GALLERY,
    "obj_mirrorball": Realm.AZURE_DREAM,
    "obj_void_portal": Realm.BASTION_OF_THE_VOID,
    "obj_blood_zits": Realm.BLOOD_GROVE,
    "obj_reactor_valve": Realm.CAUSTIC_REACTOR,
    "obj_hut_jungle": Realm.CUTTHROAT_JUNGLE,
    "obj_dam_antiqueclock": Realm.DAMAREL,
    "obj_friden_relic": Realm.DEAD_SHIPS,
    "obj_moonorb": Realm.ETERNITY_END,
    "obj_pineapple": Realm.FARAWAY_ENCLAVE,
    "obj_depths_musicalcrystals": Realm.FORBIDDEN_DEPTHS,
    "obj_lab_modron": Realm.FORGOTTEN_LAB,
    "obj_snowtomb": Realm.FROSTBITE_CAVERNS,
    "obj_hive_largeslot": Realm.GAMBLERS_HIVE,
    "obj_chaos_minivolcano": Realm.GREAT_PANDEMONIUM,
    "obj_gonfurian_supplies": Realm.KINGDOM_OF_HERETICS,
    "obj_land_robes": Realm.LAND_OF_BALANCE,
    "obj_temple_orb": Realm.OVERGROWN_TEMPLE,
    "obj_mushrooms_death": Realm.PATH_OF_THE_DAMNED,
    "obj_telescope": Realm.REFUGE_OF_THE_MAGI,
    "obj_purgatory_brain": Realm.SANCTUM_UMBRA,
    "obj_gem_portal": Realm.TEMPLE_OF_LIES,
    # probably The Barrens = oasis
    "obj_oasis": Realm.THE_BARRENS,
    "obj_fae_fountain": Realm.THE_FAE_LANDS,
    # maybe swamplands
    "obj_berrybush": Realm.THE_SWAMPLANDS,
    "obj_purgatory_mirror": Realm.TITAN_WOUND,
    "obj_ironmaiden": Realm.TORTURE_CHAMBER,
    "obj_goldfeather": Realm.UNSULLIED_MEADOWS,
}

from subot.pathfinder.map import DECORATION_CASTLE_TO_TILE_TYPE
def populate_castle_objects_from_save(save: Save) -> dict[TileType, list[Point]]:
    d = defaultdict(list)
    for decoration_type, decorations in save.castle_decorations.items():
        try:
            tile_type = DECORATION_CASTLE_TO_TILE_TYPE[decoration_type]
        except KeyError:
            continue
        for decoration in decorations:
            point = Point(decoration.x, decoration.y)
            d[tile_type].append(point)
    return d


class GameState:
    def __init__(self, save: Save, player_position: Optional[Point] = None):
        self.current_save: Save = save
        self.castle_objects: dict[TileType, list[Point]] = populate_castle_objects_from_save(save)
        print(f"{self.castle_objects=}")
        self.castle_spawn_point: Point = self.castle_objects[TileType.SPAWN_POINT][0]
        self.prev_player_position: Point = player_position or self.castle_spawn_point
        self.player_position: Point = player_position or self.castle_spawn_point
        self.time_player_last_moved: float = time.time()
        self.realm: Optional[Realm] = None
        self.realm_objs_stationary_locations: list[ObjPlaced] = []
        self.game_mode: BotMode = BotMode.UNDETERMINED

    def _update_player_position(self, to: Point):
        self.prev_player_position = self.player_position
        self.player_position = to
        self.time_player_last_moved = time.time()

    def high_level_event(self, event: HighLevelEvent):
        if isinstance(event, TeleportToRealm):
            self._update_player_position(event.spawn_point)
            self.game_mode = BotMode.REALM_LOADING
        elif isinstance(event, TeleportToCastle):
            self.realm = None
            self.realm_objs_stationary_locations = []
            self.game_mode = BotMode.CASTLE
            self._update_player_position(self.castle_spawn_point)
        elif isinstance(event, ObjPlaced):
            if self.game_mode is BotMode.REALM_LOADING:
                try:
                    self.realm = OBJ_TO_REALM_MAPPING[event.obj]
                except KeyError:
                    pass
            self.realm_objs_stationary_locations.append(event)
        elif isinstance(event, GameStart):
            self.realm = None
            self.game_mode = BotMode.CASTLE
            self.castle_objects = populate_castle_objects_from_save(self.current_save)
        elif isinstance(event, SaveUpdated):
            self.current_save = event.save
            self.castle_objects = populate_castle_objects_from_save(self.current_save)

    def update(self, event: LowLevelEvent):
        if isinstance(event, PlayerMoved):
            self._update_player_position(event.to)
            if tile_sum_diff(self.prev_player_position, self.player_position) > 1 and self.player_position == self.castle_spawn_point:
                self.high_level_event(TeleportToCastle())
            if self.game_mode is BotMode.REALM_LOADING:
                self.game_mode = BotMode.REALM

        elif isinstance(event, ObjPlaced):
            if event.obj == "obj_player":
                self.high_level_event(TeleportToRealm(spawn_point=event.placed_at))
            else:
                self.high_level_event(event)
        elif isinstance(event, GameStart):
            self.high_level_event(event)
        # print(f"game state = {self.player_position}, {self.game_mode}, realm={self.realm}")


def determine_event(line: str) -> Optional[LowLevelEvent]:
    """Extract event info from line in game log"""
    if match := PLAYER_LOCATION_REGEX.match(line):
        tex_px_x, tex_px_y = int(match.group(1)), int(match.group(2))
        return PlayerMoved(to=Point(tex_px_x // TILE_SIZE, tex_px_y // TILE_SIZE))
    elif match := OBJ_PLACEMENT_REGEX.match(line):
        obj_name, tex_px_x, tex_px_y = match.group(1), int(match.group(2)), int(match.group(3))
        return ObjPlaced(obj=obj_name, placed_at=Point(tex_px_x // TILE_SIZE, tex_px_y // TILE_SIZE))
    elif match := QUEST_RECEIVED_REGEX.match(line):
        return QuestReceived(match.group(1))
    elif GAME_START_REGEX.match(line):
        return GameStart()


def tail_log_file(outgoing_lines: queue.Queue[Optional[str]]):
    proc_tail = subprocess.Popen("coreutils.exe tail -n 30000 -f C:\\Users\\alex\\output.txt", stdout=subprocess.PIPE)
    while True:
        line = proc_tail.stdout.readline()
        if line is None:
            print("None gotten for line", line)
            continue
        line = str(line.decode('ascii')).strip()
        outgoing_lines.put(line)


if __name__ == "__main__":
    import threading
    gotten_lines = queue.Queue()
    save = load_blank_save()
    game_state = GameState(save)
    uniq_objs = set()
    su_log_thread = threading.Thread(daemon=True, target=tail_log_file, args=(gotten_lines,))
    su_log_thread.start()
    while True:
        try:
            line = gotten_lines.get_nowait()
            if event := determine_event(line):
                game_state.update(event)
                if isinstance(event, ObjPlaced):
                    if event.obj not in uniq_objs:
                        uniq_objs.add(event.obj)
                        ct = len(uniq_objs)
                        if ct >= 455:
                            uniq_objs = sorted(uniq_objs)
                            print(f"uniq objs = {ct}")
                            for obj in uniq_objs:
                                print(obj)
        except queue.Empty:
            time.sleep(2/1000)
            pass


