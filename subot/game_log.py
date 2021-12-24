from __future__ import annotations

from collections import defaultdict
from enum import Enum, auto

# 3.10
# from typing import TypeAlias, Union
from typing import Union

from saver.save import Save, ConfigOptions, load_blank_config
from subot.game_log_events import GameStart, GameSaved, PlayerMoved, ObjPlaced, TeleportToRealm, TeleportToCastle, \
    InnerPortalEntered, SaveUpdated
from subot.pathfinder.map import TileType
from saver.events import ee, QuestReceivedRaw, QuestReceived
from subot.settings import Session

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

from subot.models import Realm, Quest
from subot.utils import Point
from subot.constants import TILE_SIZE

PORTAL_ENTER_PLAYER_LOCATION = Point(864//TILE_SIZE, 1056//TILE_SIZE)

import re

GAME_START_REGEX = re.compile(r"Entering main loop")
PLAYER_LOCATION_REGEX = re.compile(r"Player is at (\d+), (\d+)")
OBJ_PLACEMENT_REGEX = re.compile(r"placing (?P<obj>.*)  (?P<x>\d+), (?P<y>\d+)")
QUEST_RECEIVED_REGEX = re.compile(r"Quest Received: (?P<desc>.*)")
GAME_SAVED_REGEX = re.compile(r'{ "error": 0.0, "id": ')

LowLevelEvent = Union[PlayerMoved, ObjPlaced, TeleportToRealm, QuestReceivedRaw, GameStart, GameSaved]

HighLevelEvent = Union[
    GameStart, ObjPlaced, QuestReceived, TeleportToCastle, TeleportToRealm, InnerPortalEntered, SaveUpdated, GameSaved]


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


CASTLE_REPLACEMENT_NAME = '" + global.castlename + "'

class GameState:
    def __init__(self, save: Save, game_config: ConfigOptions = None, player_position: Optional[Point] = None):
        self.current_config = game_config or load_blank_config()
        self.current_save: Save = save
        self.castle_objects: dict[TileType, list[Point]] = populate_castle_objects_from_save(save)
        self.castle_spawn_point: Point = self.castle_objects[TileType.SPAWN_POINT][0]
        self.prev_player_position: Point = player_position or self.castle_spawn_point
        self.player_position: Point = player_position or self.castle_spawn_point
        self.time_player_last_moved: float = time.time()
        self.realm: Optional[Realm] = None
        self.realm_objs_stationary_locations: list[ObjPlaced] = []
        self.game_mode: BotMode = BotMode.UNDETERMINED
        self.active_quests: list[int] = self.current_save.story_quest()
        self.rewind: bool = True

    def _update_player_position(self, to: Point):
        self.prev_player_position = self.player_position
        self.player_position = to
        self.time_player_last_moved = time.time()

    def _determine_quest(self, event: QuestReceivedRaw) -> Optional[int]:
        orig_desc = event.desc
        desc = orig_desc.replace(self.current_save.castle_name(), CASTLE_REPLACEMENT_NAME)
        with Session() as session:
            if quest := session.query(Quest.id).filter(Quest.description == desc).first():
                return quest[0]
            breakable_text = 'inside breakable objects in this Realm.'
            if desc.endswith(breakable_text):
                if quest := session.query(Quest.id).filter(Quest.description.endswith("inside breakable objects in this Realm.")).first():
                    return quest[0]
            rescue_random_citizen_text = f"Find and rescue {CASTLE_REPLACEMENT_NAME} citizen "
            if desc.startswith(rescue_random_citizen_text):
                if quest := session.query(Quest.id).filter(Quest.description.startswith(rescue_random_citizen_text)).first():
                    return quest[0]

            defeat_enemy_creature_text = "in this Realm by defeating enemy creatures."
            if desc.endswith(defeat_enemy_creature_text):
                if quest := session.query(Quest.id).filter(Quest.description.endswith(defeat_enemy_creature_text)).first():
                    return quest[0]

            recruit_citizen_text = "Recruit citizens from this Realm to populate"
            if desc.startswith(recruit_citizen_text):
                if quest := session.query(Quest.id).filter(Quest.description.startswith(recruit_citizen_text)).first():
                    return quest[0]



    def high_level_event(self, event: HighLevelEvent):
        if isinstance(event, TeleportToCastle):
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

    def emit_event(self, event: Union[HighLevelEvent, LowLevelEvent]):
        if self.rewind:
            return
        ee.emit(event.__name__, event)

    def update(self, event: LowLevelEvent):
        if isinstance(event, PlayerMoved):
            self._update_player_position(event.to)
            self.emit_event(event)
            if tile_sum_diff(self.prev_player_position, self.player_position) > 1 and self.player_position == self.castle_spawn_point:
                teleport_to_castle = TeleportToCastle()
                self.high_level_event(teleport_to_castle)
                self.emit_event(teleport_to_castle)
            if self.game_mode is BotMode.REALM_LOADING:
                self.game_mode = BotMode.REALM

        elif isinstance(event, ObjPlaced):
            self.high_level_event(event)
        elif isinstance(event, TeleportToRealm):
            self._update_player_position(event.spawn_point)
            self.game_mode = BotMode.REALM_LOADING
        elif isinstance(event, QuestReceivedRaw):
            quest_db_id = self._determine_quest(event)
            if quest_db_id:
                self.active_quests.append(quest_db_id)
                quest_received = QuestReceived(db_id=quest_db_id)
                self.emit_event(quest_received)
                # print(f"qid {quest.qid} for quest desc:{quest.description}")
            else:
                print(f"no match: {event.desc}")
        elif isinstance(event, GameStart):
            self.high_level_event(event)
        elif isinstance(event, GameSaved):
            from saver.save import load_most_recent_save
            self.emit_event(event)
            self.current_save = load_most_recent_save(self.current_config)
            save_updated = SaveUpdated(save=self.current_save)
            self.emit_event(save_updated)
        # print(f"game state = {self.player_position}, {self.game_mode}, realm={self.realm}")


def determine_event(line: str) -> Optional[LowLevelEvent]:
    """Extract event info from line in game log"""
    if match := PLAYER_LOCATION_REGEX.match(line):
        tex_px_x, tex_px_y = int(match.group(1)), int(match.group(2))
        return PlayerMoved(to=Point(tex_px_x // TILE_SIZE, tex_px_y // TILE_SIZE))
    elif match := OBJ_PLACEMENT_REGEX.match(line):
        obj_name, tex_px_x, tex_px_y = match.group(1), int(match.group(2)), int(match.group(3))
        placed_at = Point(tex_px_x // TILE_SIZE, tex_px_y // TILE_SIZE)

        if obj_name == "obj_player":
            return TeleportToRealm(spawn_point=placed_at)
        else:
            return ObjPlaced(obj=obj_name, placed_at=placed_at)
    elif match := QUEST_RECEIVED_REGEX.match(line):
        return QuestReceivedRaw(match.group(1))
    elif GAME_START_REGEX.match(line):
        return GameStart()
    elif GAME_SAVED_REGEX.match(line):
        return GameSaved()


def tail_log_file(outgoing_lines: queue.Queue[Optional[str]]):
    proc_tail = subprocess.Popen("coreutils.exe tail -n 10000 -f C:\\Users\\alex\\output.txt", stdout=subprocess.PIPE)
    while True:
        line = proc_tail.stdout.readline()
        if line is None:
            print("None gotten for line", line)
            continue
        line = str(line.decode('ascii')).strip()
        outgoing_lines.put(line)


