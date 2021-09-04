import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Type, Union, Iterator

import cv2
import re
import numpy as np

from numpy.typing import ArrayLike
from sqlalchemy import update, func
from sqlalchemy.exc import NoResultFound

from subot.hash_image import Overlay, FloorTilesInfo, compute_phash
from subot.models import MasterNPCSprite, SpriteFrame, AltarSprite, Realm, RealmLookup, ProjectItemSprite, \
    NPCSprite, FloorSprite, OverlaySprite, Sprite, HashFrameWithFloor, WallSprite, SpriteType, ChestType, ChestSprite, \
    CastleSprite, CreatureSprite
from subot.settings import Session

import subot.settings as settings

master_name_regex = re.compile(r".*NPCs/Sprites/master_(?P<race>.*)_[\d].png")
realm_altar_regex = re.compile(r".*/Sprites/spr_(?:altar|god)_(?P<name>.*)_[\d].png")
realm_altar_regex2 = re.compile(r".*/Sprites/TS_SU_God_(?P<name>.*)_(?:altar|Altar)_[\d].png")

project_item_regex = re.compile(r".*GUI/Sprites/project_(?P<name>.*)_[\d].png")
npc_regex = re.compile(r".*NPCs/Sprites/(?!master)(?:npc|ospr_)?(?P<name>.*)_[\d].png")
custom_floortile_regex = re.compile(r"floortiles/(?P<realm>.*)/*.png")
overlay_sprite_regex = re.compile(r".*Underwater/Sprites/(?P<realm>.*)_overlay_[\d].png")
pre_extract_realm_floortiles_regex = re.compile(r"Chaos/Sprites/bg_chaos_0.png")
saved_realm_floortiles_regex = re.compile(r".*floortiles/.*/.*.png")
castle_floortile_regex = re.compile(r".*CastleTiles/Sprites/(?P<long_name>.*)_[\d].png")
wall_regex = re.compile(r".*/Sprites/wall_(?P<realm>.*)_0.png")
castle_item_regex = re.compile(r".*Decorations/Sprites/(?:spr_)?(?P<long_name>.*)_(?P<frame>[\d]+).png")
generic_sprite_regex = re.compile(r".*/Sprites/(?:spr_)?(?P<long_name>.*)_(?P<frame>[\d]+).png")
extracted_wall_regex = re.compile(r".*wall_realm_tiles/.*/.*.png")
overworld_regex = re.compile(r".*/Sprites/(?P<long_name>.*_OW)_(?P<frame>[\d]+).png")
overworld_regex2 = re.compile(r".*/Sprites/(?P<long_name>(?:ospr_).*)_(?P<frame>[\d]+).png")

# chests
generic_chest_regex = re.compile(r".*/Sprites/spr_chest_(?P<realm>.*)_(?P<frame>[\d]+).png")

# excluded from adding
sprite_crits_battle_regex = re.compile(r".*BattleCrit/Sprites/.*.png")
animation_regex = re.compile(r".*AttackAnimations/Sprites/anim_.*.png")
spell_regex = re.compile(r".*Spells/Sprites/spe_.*.png")
wall_alt_regex = re.compile(r".*/Sprites/spr_wall_.*.png")
wall_source_regex = re.compile(r".*/Sprites/wall_.*.png")
bg_chaos = re.compile(r".*Chaos/Sprites/bg_chaos_0.png")
gui_regex = re.compile(r".*GUI/Sprites/.*.png")
relic_regex = re.compile(r".*Relics/Sprites/.*.png")
battle_background_regex = re.compile(r".*/Sprites/TS_SU_Battle_.*.png")

MASTER_ICON_SIZE = 16


@dataclass
class ChestResult:
    chest_type: ChestType
    long_name: str
    realm: Optional[Realm]
    opened: bool


def extract_realm(match: re.Match) -> Realm:
    return Realm.generic_realm_name_to_ingame_realm(match.group('realm'))


def match_overworld_sprite(path: Path) -> Optional[re.Match]:
    if path.parent.parent.name == "NPCs":
        return
    str_path = path.as_posix()
    if match := overworld_regex.match(str_path):
        return match
    elif match := overworld_regex2.match(str_path):
        return match


def match_chest(sprite_path: Path) -> Optional[ChestResult]:
    name = sprite_path.as_posix()
    match = generic_sprite_regex.match(name)
    if not match:
        return

    opened = int(match.group('frame')) == 1
    long_name = match.group('long_name')

    realm = None
    try:
        realm = get_realm_from_parent(sprite_path)
    except KeyError:
        pass

    giant_chests_names = {"giant_treasure_chest", "blood_giantchest","chest_gem_heaping", "bigdebris_underwater2"}

    if long_name in giant_chests_names:
        chest_type = ChestType.LARGE
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)
    elif long_name == "chest_haunted_untouched":
        chest_type = ChestType.HAUNTED
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)
    elif long_name == "chest_spawned":
        chest_type = ChestType.SPAWNED
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)

    elif generic_chest_regex.match(name):
        chest_type = ChestType.NORMAL
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)


def match_master(path: Path) -> Optional[re.Match]:

    matched = master_name_regex.match(path.as_posix())
    if not matched:
        return

    img = cv2.imread(path.as_posix())
    height, width, _ = img.shape
    if height == MASTER_ICON_SIZE:
        return
    return matched


def match_altar(path: Path) -> Optional[re.Match]:
    if match := realm_altar_regex.match(path.as_posix()):
        return match
    else:
        return realm_altar_regex2.match(path.as_posix())


def get_realm_from_parent(path: Path) -> Realm:
    return Realm.internal_realm_name_to_god_mapping[path.parent.parent.name]


def match_project(path: Path) -> Optional[re.Match]:
    return project_item_regex.match(path.as_posix())


def match_npc(path: Path) -> Optional[re.Match]:
    return npc_regex.match(path.as_posix())


def match_realm_floortiles(path: Path) -> Optional[re.Match]:
    return pre_extract_realm_floortiles_regex.match(path.name)


def match_overlay(path: Path) -> Optional[re.Match]:
    return overlay_sprite_regex.match(path.name)


def add_or_update_sprites(sprites: dict[str, Type[Sprite]]):
    start = time.time()
    ct = 0
    with Session() as session:
        start_qps = time.time()
        # drop all existing sprite frames
        rows_deleted = session.query(SpriteFrame).delete()
        print(f"deleted {rows_deleted} sprite frames")

        for sprite_name, sprite_new in sprites.items():
            try:
                sprite_base_id, sprite_base_type_id = session.query(Sprite.id, Sprite.type_id).filter_by(long_name=sprite_new.long_name).one()
                sprite_new.id = sprite_base_id
                try:
                    session.query(sprite_new.__class__.id).filter_by(long_name=sprite_new.long_name).one()
                    ct += 1
                    if ct % 1000 == 0:
                        end_qps = time.time()
                        qps = 1 / ((end_qps - start_qps) / 1000)
                        print(f"{qps=}")
                        start_qps = time.time()
                except NoResultFound:
                    if sprite_base_type_id == 2:
                        session.execute(f"INSERT INTO {sprite_new.__tablename__} (sprite_id) VALUES ({sprite_base_id})")
                        session.execute(
                            update(Sprite)
                            .where(Sprite.id == sprite_base_id)
                            .values(type_id=sprite_new.type_id))
                        session.flush()
            except NoResultFound:
                print(f"noresultfuond - {sprite_new.long_name}")

            _ = session.merge(sprite_new)
        session.commit()

    # cleanup sprites without attachment
    with Session() as session:
        session.execute('PRAGMA foreign_keys = ON;')
        session.commit()
        saved_frames_subquery = session.query(SpriteFrame.sprite_id).subquery()
        rows_deleted = session.query(Sprite).filter(Sprite.id.not_in(saved_frames_subquery)).delete(synchronize_session=False)
        session.commit()
        print(f"deleted {rows_deleted} unused sprites")
    end = time.time()
    print(f"adding sprites took {end - start} seconds")


def match_battle_sprite(path: Path) -> Optional[re.Match]:
    return sprite_crits_battle_regex.match(path.as_posix())


def match_attack_animation(path: Path) -> Optional[re.Match]:
    return re.match(animation_regex, path.as_posix())


def match_spell_animation(path: Path) -> Optional[re.Match]:
    return re.match(spell_regex, path.as_posix())


def match_wall(path: Path) -> Optional[re.Match]:
    return re.match(wall_regex, path.as_posix())


def match_alt_walls(path) -> Optional[re.Match]:
    return re.match(wall_alt_regex, path.as_posix())


def should_skip_hashing(filepath: str) -> bool:
    if "/Rhea" in filepath:
        return False

    # skip obelisk life and hash obelisk_life_cleansed and corrupted instead
    elif "spr_obelisk_life_0.png" in filepath:
        return True
    elif "spr_obelisk_life_1.png" in filepath:
        return True

    if "assets_padded" in filepath:
        return True

    return False


def hash_items(sprite_type: Optional[SpriteType]=None):
    @dataclass(frozen=True)
    class PHashReuse:
        phash: int
        floor_frame_id: int
        sprite_canonical_name: Path = field(hash=False, compare=False)

    with Session() as session:
        existing_phashes: dict[PHashReuse, PHashReuse] = {}

        bulk_hash_entries = []

        ct = 1
        similar_ct = 0
        floortiles = session.query(FloorSprite).filter(FloorSprite.realm_id.isnot(None)).all()

        standard_castle_tile = session.query(FloorSprite).filter_by(long_name="floor_standard1").one()
        floortiles.append(standard_castle_tile)

        only_seen_in_castle_sprite_ids = set(session.query(Sprite.id).filter_by(type_id=SpriteType.CASTLE_DECORATION.value).all())
        print(f"only seen in castle len = {len(only_seen_in_castle_sprite_ids)}")

        if not sprite_type:
            query_result = session.query(SpriteFrame).all()
        else:
            query_result = session.query(SpriteFrame).join(Sprite).filter_by(type_id=sprite_type.value).all()

        for floortile in floortiles:
            overlay = None
            if floortile.realm:
                if floortile.realm.enum is Realm.DEAD_SHIPS:
                    overlay_sprite = session.query(OverlaySprite).filter_by(realm_id=floortile.realm.id).one()
                    overlay_tile_part = overlay_sprite.frames[0].data_color[:32, :32, :3]
                    overlay = Overlay(alpha=0.753, tile=overlay_tile_part)

            for floor_frame in floortile.frames:
                floor_frame_id = floor_frame.id
                floor_frame_data_color = floor_frame.data_color

                for sprite_frame in query_result:
                    if sprite_frame.sprite_id in only_seen_in_castle_sprite_ids:
                        print(f"skipping - castle only sprite - {sprite_frame.filepath}")
                        continue

                    if should_skip_hashing(sprite_frame.filepath):
                        print(f"assets_padded skipping = {sprite_frame.filepath}")
                        continue
                    hash_entry = HashFrameWithFloor()
                    hash_entry.floor_sprite_frame_id = floor_frame_id
                    hash_entry.sprite_frame_id = sprite_frame.id

                    sprite_frame_data_color = sprite_frame.data_color
                    if sprite_frame_data_color is None:
                        print(f"{sprite_frame.filepath} no image data")
                        continue
                    one_tile_worth_img: ArrayLike = sprite_frame_data_color[-32:, :32, :]
                    if one_tile_worth_img.shape != (32, 32, 4):
                        print(f"not padded tile -skipping - {sprite_frame.filepath}")
                        continue

                    hash_entry.phash = compute_phash(floor_frame_data_color, one_tile_worth_img, overlay)
                    if not sprite_frame.sprite:
                        continue
                    new_hash = PHashReuse(phash=hash_entry.phash, floor_frame_id=hash_entry.floor_sprite_frame_id, sprite_canonical_name=sprite_frame.sprite.long_name)
                    if existing_hash := existing_phashes.get(new_hash):
                        similar_ct += 1
                        print(f"similar hash detected. old={existing_hash=} new {new_hash=}")
                        continue
                    existing_phashes[new_hash] = new_hash
                    bulk_hash_entries.append(hash_entry)

                    if ct % 5000 == 0:
                        print(f"{ct} hash entries saved")
                        session.add_all(bulk_hash_entries)
                        session.commit()
                        bulk_hash_entries.clear()

                    ct += 1
        session.add_all(bulk_hash_entries)
        session.commit()
        bulk_hash_entries.clear()
        print(f"total hashes = {ct},similar hashes={similar_ct}, similar% = {(similar_ct / ct) * 100}%")


def drop_existing_phashes(sprite_type: Optional[SpriteType] = None):
    # clear all previous hash entries
    with Session() as session:
        if sprite_type:
            frame_ids = session.query(SpriteFrame.id).filter(Sprite.type_id == sprite_type.value)\
                .join(Sprite, Sprite.id == SpriteFrame.sprite_id)\
                .all()
            frame_ids = [frame_id[0] for frame_id in frame_ids]
            rows_deleted = session.query(HashFrameWithFloor)\
                .filter(HashFrameWithFloor.sprite_frame_id.in_(frame_ids))\
                .delete()
            session.commit()
            print(f"cleared {sprite_type.name} type from phash table, deleted {rows_deleted} rows")
        else:
            rows_deleted = session.query(HashFrameWithFloor).delete()
            session.commit()
            print(f"cleared table, deleted {rows_deleted} rows")


class Inserter:
    def __init__(self, export_dir: Path, dest_dir: Path, custom_assets_dir: Path):
        self.export_dir = export_dir
        self.dest_dir = dest_dir
        self.custom_assets_dir = custom_assets_dir
        self.sprites: dict[str, Sprite] = dict()
        self.scanners: list[Callable[[Path], Optional[Sprite]]] = [self.altars,
                                                                   self.floortiles,
                                                                   self.castle_tiles,
                                                                   self.master_npcs,
                                                                   self.npc,
                                                                   self.add_chests,
                                                                   self.add_walls,
                                                                   self.insert_project_items,
                                                                   self.add_overlay_tiles,
                                                                   self.castle_decorations,
                                                                   self.overworld_creatures,
                                                                   self.generic_sprite,
                                                                   ]
        self.paths: list[Path] = list(self.export_dir.glob("**/*/*.png"))

    def overworld_creatures(self, sprite_path: Path) -> Optional[CreatureSprite]:
        match = match_overworld_sprite(sprite_path)
        if not match:
            return

        long_name = match.group('long_name')

        return CreatureSprite(short_name=long_name, long_name=long_name)


    def altars(self, sprite_path: Path) -> Optional[AltarSprite]:

        altar_realm = match_altar(sprite_path)
        if not altar_realm:
            return

        realm = get_realm_from_parent(sprite_path)

        god_name = realm.god_name
        altar_name_in_game: str = f"Realm Altar of {god_name}"

        if realm is None:
            logging.warning(
                f"realm altar {god_name} has no realm associated with it. file={sprite_path.as_posix()}")
            raise Exception(f"realm altar {god_name} has no realm associated with it. file={sprite_path.as_posix()}")

        with Session() as session:
            realm_id = session.query(RealmLookup).filter_by(enum=realm).one().id
        return AltarSprite(short_name="Altar", long_name=altar_name_in_game,realm_id=realm_id)

    def castle_decorations(self, path: Path) -> Optional[CastleSprite]:
        match = castle_item_regex.match(path.as_posix())
        if not match:
            return
        long_name = match.group("long_name")

        return CastleSprite(short_name=long_name, long_name=long_name)

    def extract_realm_floortiles(self):
        TILE_SIZE = 32
        floortiles_path = self.export_dir.joinpath("Chaos").joinpath("Sprites").joinpath("bg_chaos_0.png")
        floortiles_img = cv2.imread(floortiles_path.as_posix(), cv2.IMREAD_UNCHANGED)

        row_to_realm_mapping = {
            0: Realm.GREAT_PANDEMONIUM,
            1: Realm.CAUSTIC_REACTOR,
            2: Realm.TEMPLE_OF_LIES,
            3: Realm.SANCTUM_UMBRA,
            4: Realm.TITAN_WOUND,
            5: Realm.BLOOD_GROVE,
            6: Realm.BASTION_OF_THE_VOID,
            7: Realm.AZURE_DREAM,
            8: Realm.CUTTHROAT_JUNGLE,
            9: Realm.ETERNITY_END,
            10: Realm.FARAWAY_ENCLAVE,
            11: Realm.KINGDOM_OF_HERETICS,
            12: Realm.FROSTBITE_CAVERNS,
            13: Realm.ARACHNID_NEST,
            14: Realm.THE_BARRENS,
            15: Realm.PATH_OF_THE_DAMNED,
            16: Realm.THE_SWAMPLANDS,
            17: Realm.REFUGE_OF_THE_MAGI,
            18: Realm.TORTURE_CHAMBER,
            19: Realm.UNSULLIED_MEADOWS,
            20: Realm.DEAD_SHIPS,
            21: Realm.THE_FAE_LANDS,
            22: Realm.AMALGAM_GARDENS,
            23: Realm.ASTRAL_GALLERY,
            24: Realm.DAMAREL,
            25: Realm.FORBIDDEN_DEPTHS,
            26: Realm.FORGOTTEN_LAB,
            27: Realm.GAMBLERS_HIVE,
            28: Realm.LAND_OF_BALANCE,
            29: Realm.OVERGROWN_TEMPLE,
        }

        dest_dir_floortiles = self.export_dir.joinpath("floortiles")
        dest_dir_floortiles.mkdir(exist_ok=True)

        for row_num, row in enumerate(range(0, floortiles_img.shape[0], TILE_SIZE)):
            for col_num, column in enumerate(range(0, floortiles_img.shape[1], TILE_SIZE), start=1):
                img = floortiles_img[row:row + TILE_SIZE, column:column + TILE_SIZE]
                is_blank = np.count_nonzero(img) == 0
                if is_blank:
                    continue
                realm_for_tile = row_to_realm_mapping[row_num]
                series_dir = Path(dest_dir_floortiles).joinpath(f"{realm_for_tile.internal_realm_name}")
                series_dir.mkdir(exist_ok=True)

                if col_num == 1:
                    tile_suffix = "_common"
                else:
                    tile_suffix = ""

                destination_filepath: Path = series_dir.joinpath(f"{row_num}-{col_num}{tile_suffix}.png")
                cv2.imwrite(destination_filepath.as_posix(), img)

    def extract_wall_sprites(self):
        TILE_SIZE = 32

        dest_dir_walls = self.export_dir.joinpath("wall_realm_tiles")
        dest_dir_walls.mkdir(exist_ok=True)

        for path in self.paths:
            match = match_wall(path)
            if not match:
                continue

            realm: Realm = get_realm_from_parent(path)
            if path.name == "wall_purgatory_0.png":
                realm = Realm.SANCTUM_UMBRA
            dest_realm_wall_dir = dest_dir_walls.joinpath(realm.internal_realm_name)
            dest_realm_wall_dir.mkdir(exist_ok=True)

            img = cv2.imread(path.as_posix(), cv2.IMREAD_UNCHANGED)

            ct = 1
            for row_num, row in enumerate(range(0, img.shape[0], TILE_SIZE)):
                for col_num, column in enumerate(range(0, img.shape[1], TILE_SIZE)):
                    slice = img[row:row + TILE_SIZE, column:column + TILE_SIZE]
                    is_blank = np.count_nonzero(slice) == 0
                    if is_blank:
                        continue

                    destination_filepath: Path = dest_realm_wall_dir.joinpath(f"{ct}.png")

                    cv2.imwrite(destination_filepath.as_posix(), slice)
                    ct += 1

    def add_walls(self, path: Path) -> Optional[WallSprite]:
        if not extracted_wall_regex.match(path.as_posix()):
            return
        with Session() as session:
            realm = Realm.internal_realm_name_to_god_mapping[path.parent.name]
            realm_id = session.query(RealmLookup).filter_by(enum=realm).one().id

        sprite_name_short = "Wall"
        sprite_name_long = f"{realm.realm_name} Wall"
        return WallSprite(short_name=sprite_name_short, long_name=sprite_name_long, realm_id=realm_id)

    def floortiles(self, path: Path) -> Optional[FloorSprite]:

        if not saved_realm_floortiles_regex.match(path.as_posix()):
            return

        realm = Realm.internal_realm_name_to_god_mapping[path.parent.name]

        sprite_name_short = "Floor"
        sprite_name_long = f"{realm.realm_name} Floor Tile"

        with Session() as session:
            realm_id = session.query(RealmLookup).filter_by(enum=realm).one().id

        return FloorSprite(short_name=sprite_name_short, long_name=sprite_name_long, realm_id=realm_id)

    def castle_tiles(self, path: Path) -> Optional[FloorSprite]:
        match = castle_floortile_regex.match(path.as_posix())
        if not match:
            return
        long_name = match.group('long_name')
        if long_name == "floor_standard1":
            return FloorSprite(short_name=long_name, long_name=long_name, realm_id=None)

    def master_npcs(self, sprite_path: Path) -> Optional[MasterNPCSprite]:

        master_race = match_master(sprite_path)
        if not master_race:
            return
        master_race_filepart = (master_race.groups()[0])
        master_race_proper_name = f"{master_race_filepart.replace('_', ' ')} Master"

        return MasterNPCSprite(short_name=master_race_proper_name, long_name=master_race_proper_name)

    def add_chests(self, sprite_path: Path) -> Optional[Union[ChestSprite, Sprite]]:
        sprite_frame_match = match_chest(sprite_path)
        if not sprite_frame_match:
            return

        item_name_short: str = "Chest"
        chest_is_opened = sprite_frame_match.opened
        if chest_is_opened:
            item_name_long = f"{sprite_frame_match.long_name} Open"
        else:
            item_name_long = f"{sprite_frame_match.long_name} Closed"

        realm_id = None
        with Session() as session:
            if realm := sprite_frame_match.realm:
                realm_id = session.query(RealmLookup).filter_by(enum=realm).one().id

        if not chest_is_opened:
            return ChestSprite(short_name=item_name_short, long_name=item_name_long,
                               chest_type_id=sprite_frame_match.chest_type.value, realm_id=realm_id,
                               opened=chest_is_opened)
        else:
            return Sprite(short_name=item_name_long, long_name=item_name_long, type_id=SpriteType.DECORATION.value)

    def insert_project_items(self, path: Path) -> Optional[ProjectItemSprite]:

        sprite_frame_match = match_project(path)
        if not sprite_frame_match:
            return

        item_name_short: str = sprite_frame_match.groups()[0]
        item_name_short: str = item_name_short.replace("_", " ")
        item_name_long: str = f"Project item {item_name_short}"

        return ProjectItemSprite(short_name=item_name_short, long_name=item_name_long)

    def npc(self, sprite_path: Path) -> Optional[NPCSprite]:

        sprite_name = match_npc(sprite_path)
        if not sprite_name:
            return

        sprite_name = (sprite_name.groups()[0])
        if sprite_path.name.startswith("master"):
            raise AssertionError(f"Master not an NPC: {sprite_name}")

        if sprite_path.name.startswith("ospr_"):
            sprite_proper_name = f"ospr_{sprite_name.replace('_', ' ')}"
        elif sprite_path.name.startswith("npc_"):
            sprite_proper_name = f"NPC {sprite_name.replace('_', ' ')}"
            sprite_proper_name = sprite_proper_name.replace("  ", " ")
        else:
            sprite_proper_name = sprite_name
        return NPCSprite(short_name=sprite_proper_name, long_name=sprite_proper_name)

    def add_overlay_tiles(self, sprite_path: Path) -> Optional[OverlaySprite]:

        match = overlay_sprite_regex.match(sprite_path.as_posix())
        if not match:
            return

        realm_in_game: Realm = get_realm_from_parent(sprite_path)
        overlay_sprite = OverlaySprite()
        overlay_sprite.long_name = f"{realm_in_game.realm_name} Overlay"
        overlay_sprite.short_name = overlay_sprite.long_name
        with Session() as session:
            overlay_sprite.realm_id = session.query(RealmLookup).filter_by(enum=realm_in_game).one().id

        return overlay_sprite

    def generic_sprite(self, sprite_path: Path):
        # excluders
        for excluder in [sprite_crits_battle_regex, animation_regex, spell_regex, wall_alt_regex, gui_regex, relic_regex, bg_chaos, battle_background_regex, wall_source_regex]:
            if excluder.match(sprite_path.as_posix()):
                return

        match = generic_sprite_regex.match(sprite_path.as_posix())
        if not match:
            return

        sprite = Sprite()
        sprite.long_name = match.groups()[0]
        sprite.short_name = sprite.long_name
        return sprite

    def manual_sprites(self) -> Iterator[tuple[Path, Sprite]]:

        with Session() as session:
            sprite = FloorSprite(short_name="floor",
                        long_name="Where the Dead Ships Dwell floor tile test with overlay",
                        realm_id=session.query(RealmLookup).filter_by(enum=Realm.DEAD_SHIPS).one().id)
            for path in self.custom_assets_dir.joinpath(("floortiles/Where the Dead Ships Dwell")).glob("*.png"):
                yield path, sprite

            sprite = NPCSprite(short_name="Rhea", long_name="Rhea the Enchantress")
            for path in self.custom_assets_dir.joinpath(("NPCs/Castle/Rhea")).glob("*.png"):
                yield path, sprite

    @staticmethod
    def chop_path(path: Path, source_dir: Path) -> SpriteFrame:
        destination_file = source_dir.joinpath(path.relative_to(source_dir))
        chopped_path = destination_file.relative_to(source_dir)
        chopped_path = Path(source_dir.name).joinpath(chopped_path)
        return SpriteFrame(_filepath=chopped_path.as_posix())

    def scan_sprites(self):
        start = time.time()
        for path in self.paths:
            for scanner in self.scanners:
                if sprite := scanner(path):
                    sprite_frame = self.chop_path(path, self.export_dir)
                    self.sprites.setdefault(sprite.long_name, sprite).frames.append(sprite_frame)
                    break

        for path, sprite in self.manual_sprites():
            sprite_frame = self.chop_path(path, self.custom_assets_dir)
            self.sprites.setdefault(sprite.long_name, sprite).frames.append(sprite_frame)

        end = time.time()
        took = end - start
        print(f"reading sprites took {took} seconds")
        add_or_update_sprites(self.sprites)
        return


if __name__ == "__main__":
    drop_existing_phashes()
    custom_assets_dir = settings.IMAGE_PATH.joinpath("custom_assets")
    export_dir = settings.IMAGE_PATH.joinpath("extracted_assets")
    dest_dir = settings.IMAGE_PATH.joinpath("extracted_assets")
    sprite_scanner = Inserter(export_dir, dest_dir, custom_assets_dir)
    sprite_scanner.extract_wall_sprites()
    sprite_scanner.extract_realm_floortiles()
    sprite_scanner.scan_sprites()
    hash_items()
