import enum
import logging
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Type

import cv2
import re
import numpy as np

import sqlalchemy
from numpy.typing import ArrayLike
from sqlalchemy.exc import NoResultFound

from subot.hash_image import Overlay, FloorTilesInfo, compute_phash
from subot.models import MasterNPCSprite, SpriteFrame, AltarSprite, Realm, RealmLookup, ProjectItemSprite, \
    NPCSprite, FloorSprite, OverlaySprite, Sprite, HashFrameWithFloor, WallSprite, SpriteType, ChestType, ChestSprite
from subot.settings import Session

import subot.settings as settings

master_name_regex = re.compile(r"master_(?P<race>.*)_[\d].png")
realm_altar_regex = re.compile(r"spr_(?:altar|god)_(?P<realm>.*)_[\d].png")
project_item_regex = re.compile(r"project_(?P<name>.*)_[\d].png")
npc_regex = re.compile(r"npc_(?P<name>.*)_[\d].png")
custom_floortile_regex = re.compile(r"floortiles/(?P<realm>.*)/*.png")
overlay_sprite_regex = re.compile(r"(?P<realm>.*)_overlay_[\d].png")
realm_floortiles_regex = re.compile(r"bg_chaos_0.png")
wall_regex = re.compile(r"wall_(?P<realm>.*)_0.png")
generic_sprite_regex = re.compile(r"(?:spr_)?(?P<long_name>.*)_(?P<frame>[\d]+).png")


# excluded from adding
sprite_crits_battle_regex = re.compile(r"spr_crits_battle_(?P<name>[\d]+).png")
icons_regex = re.compile(r"icons.*_[\d]+.png")
animation_regex = re.compile(r"anim_.*.png")
spell_regex = re.compile(r"spe_.*.png")
wall_alt_regex = re.compile(r"spr_wall_.*.png")

MASTER_ICON_SIZE = 16
MASTER_NPC_SIZE = 32

from dataclasses import dataclass


@dataclass
class ChestResult:
    chest_type: ChestType
    long_name: str
    realm: Optional[Realm]
    opened: bool


from pathlib import Path

generic_chest_regex = re.compile(r"spr_chest_(?P<realm>.*)_(?P<frame>[\d]+).png")

underwater_chest_regex = re.compile(r"spr_bigdebris_(?P<realm>underwater)2_(?P<frame>[\d]+).png")
gem_large_chest_regex = re.compile(r"spr_chest_(?P<realm>gem)_heaping_(?P<frame>[\d]+).png")
blood_large_chest_regex = re.compile(r"spr_(?P<realm>blood)_giantchest_(?P<frame>[\d]+).png")
haunted_chest_regex = re.compile(r"chest_haunted_.*_(?P<frame>[\d]+).png")
spawned_chest_regex = re.compile(r"chest_spawned_(?P<frame>[\d]+).png")


def extract_realm(match: re.Match) -> Realm:
    return Realm.generic_realm_name_to_ingame_realm(match.group('realm'))


def match_chest(sprite_path: Path) -> Optional[ChestResult]:
    name = sprite_path.name
    match = generic_sprite_regex.match(name)
    if not match:
        return

    opened = int(match.group('frame')) == 1
    long_name = match.group('long_name')

    if chest_match := underwater_chest_regex.match(name):
        realm = extract_realm(chest_match)
        chest_type = ChestType.LARGE
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)
    elif chest_match := gem_large_chest_regex.match(name):
        realm = extract_realm(chest_match)
        chest_type = ChestType.LARGE
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)
    elif chest_match := blood_large_chest_regex.match(name):
        realm = extract_realm(chest_match)
        chest_type = ChestType.LARGE
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)
    elif chest_match := haunted_chest_regex.match(name):
        realm = None
        chest_type = ChestType.HAUNTED
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)
    elif chest_match := spawned_chest_regex.match(name):
        realm = None
        chest_type = ChestType.SPAWNED
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)

    elif chest_match := generic_chest_regex.match(name):
        realm = extract_realm(chest_match)
        chest_type = ChestType.NORMAL
        return ChestResult(chest_type=chest_type, realm=realm, opened=opened, long_name=long_name)


def match_master(path: Path) -> Optional[re.Match]:
    img = cv2.imread(path.as_posix())
    height, width, _ = img.shape
    if height == MASTER_ICON_SIZE:
        return
    return master_name_regex.match(path.name)


def master_npcs(sprite_export_dir: Path, dest_dir: Path):
    sprites: dict[str, MasterNPCSprite] = {}

    for ct, master in enumerate(sprite_export_dir.glob("master_*.png")):
        master_race = match_master(master)
        if not master_race:
            continue
        master_race_filepart = (master_race.groups()[0])
        master_race_proper_name = f"{master_race_filepart.replace('_', ' ')} Master"

        destination_file = dest_dir.joinpath(master.name)
        shutil.copy(master, destination_file)

        sprites.setdefault(master_race_proper_name, MasterNPCSprite(short_name=master_race_proper_name, long_name=master_race_proper_name))\
            .frames.append(SpriteFrame(_filepath=destination_file.as_posix()))

        print(f"copied {ct} master frames")

    print(f"{len(sprites)} Masters")
    add_or_update_sprites(sprites)


def match_altar(path: Path) -> Optional[re.Match]:
    return realm_altar_regex.match(path.name)


def altars(sprite_export_dir: Path, dest_dir: Path):

    generic_to_ingame_avatar_mapping = Realm.internal_realm_name_to_god_mapping

    altar_sprites: dict[str, AltarSprite] = {}

    for ct, god_realm_altar_path in enumerate(sprite_export_dir.glob("spr_*.png")):
        altar_realm = match_altar(god_realm_altar_path)
        if not altar_realm:
            continue

        god_name: str = altar_realm.groups()[0]
        god_name_in_game: str = generic_to_ingame_avatar_mapping[god_name]
        altar_name_in_game: str = f"Realm Altar of {god_name_in_game}"

        realm_enum = Realm.god_to_realm_mapping.get(god_name_in_game)
        if realm_enum is None:
            logging.warning(f"realm altar {god_name_in_game} has no realm associated with it. file={god_realm_altar_path.as_posix()}")
            continue

        destination_file = dest_dir.joinpath(god_realm_altar_path.name)
        shutil.copy(god_realm_altar_path, destination_file)

        with Session() as session:
            realm_id = session.query(RealmLookup).filter_by(enum=realm_enum).one().id

            altar_sprites.setdefault(altar_name_in_game, AltarSprite(short_name="Altar", long_name=altar_name_in_game, realm_id=realm_id))\
                .frames.append(SpriteFrame(_filepath=destination_file.as_posix()))

    print(f"{len(altar_sprites)} realm altars")
    add_or_update_sprites(altar_sprites)


def match_project(path: Path) -> Optional[re.Match]:
    return project_item_regex.match(path.name)


def insert_project_items(export_dir: Path, dest_dir: Path):
    sprites: dict[str, ProjectItemSprite] = {}

    for ct, project_item_path in enumerate(export_dir.glob("project_*.png")):
        sprite_frame_match = match_project(project_item_path)
        if not sprite_frame_match:
            continue

        item_name_short: str = sprite_frame_match.groups()[0]
        item_name_short: str = item_name_short.replace("_", " ")
        item_name_long: str = f"Project item {item_name_short}"

        destination_file = dest_dir.joinpath(project_item_path.name)
        shutil.copy(project_item_path, destination_file)

        sprites.setdefault(item_name_long, ProjectItemSprite(short_name=item_name_short, long_name=item_name_long))\
            .frames.append(SpriteFrame(_filepath=destination_file.as_posix()))

    print(f"{len(sprites)} project items")
    add_or_update_sprites(sprites)


def add_chests(export_dir: Path, dest_dir: Path):
    sprites: dict[str, ChestSprite] = {}

    for ct, sprite_path in enumerate(export_dir.glob("*.png")):
        sprite_frame_match = match_chest(sprite_path)
        if not sprite_frame_match:
            continue
        print(f"{sprite_path.name}, {sprite_frame_match}")

        item_name_short: str = "Chest"
        chest_is_opened = sprite_frame_match.opened
        if chest_is_opened:
            item_name_long = f"{sprite_frame_match.long_name} Open"
        else:
            item_name_long = f"{sprite_frame_match.long_name} Closed"

        destination_file = dest_dir.joinpath(sprite_path.name)
        shutil.copy(sprite_path, destination_file)

        realm_id = None
        with Session() as session:
            if realm := sprite_frame_match.realm:
                realm_id = session.query(RealmLookup).filter_by(enum=realm).one().id

        sprites.setdefault(item_name_long, ChestSprite(short_name=item_name_short, long_name=item_name_long, chest_type_id=sprite_frame_match.chest_type.value, realm_id=realm_id, opened=chest_is_opened))\
            .frames.append(SpriteFrame(_filepath=destination_file.as_posix()))

    print(f"{len(sprites)} Chest items")
    add_or_update_sprites(sprites)


def match_npc(path: Path) -> Optional[re.Match]:
    return npc_regex.match(path.name)


def npc(export_dir: Path, dest_dir: Path):
    npc_sprites: dict[str, NPCSprite] = {}

    for ct, sprite_path in enumerate(export_dir.glob("npc_*.png")):

        sprite_name = match_npc(sprite_path)
        if not sprite_name:
            raise Exception(f"Regex did not find a match for NPC file: {sprite_path}")
        sprite_name = (sprite_name.groups()[0])
        sprite_proper_name = f"{sprite_name.replace('_', ' ')}"

        npc_sprite = NPCSprite()
        npc_sprite.short_name = sprite_proper_name
        npc_sprite.long_name = f"NPC {sprite_proper_name}"

        destination_filepath = dest_dir.joinpath(sprite_path.name)
        shutil.copy(sprite_path, destination_filepath)
        npc_sprites.setdefault(sprite_proper_name, npc_sprite).frames.append(SpriteFrame(_filepath=destination_filepath.as_posix()))

        print(f"copied {ct} NPC frames")

    print(f"{len(npc_sprites)} NPCs")
    add_or_update_sprites(npc_sprites)


def match_realm_floortiles(path: Path) -> Optional[re.Match]:
    return realm_floortiles_regex.match(path.name)


def realm_floortiles(export_dir: Path, dest_dir: Path):
    TILE_SIZE = 32
    floortiles_path = export_dir.joinpath("bg_chaos_0.png")
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
    }

    dest_dir_floortiles = dest_dir.joinpath("floortiles")
    dest_dir_floortiles.mkdir(exist_ok=True)

    floor_tiles: dict[str, FloorSprite] = {}

    for row_num, row in enumerate(range(0, floortiles_img.shape[0], TILE_SIZE)):
        tileset: list[tuple[ArrayLike, Path]] = []
        for col_num, column in enumerate(range(0, floortiles_img.shape[0], TILE_SIZE), start=1):
            img = floortiles_img[row:row + TILE_SIZE, column:column + TILE_SIZE]
            is_blank = np.count_nonzero(img) == 0
            if is_blank:
                continue

            if col_num == 1:
                tile_suffix = "_common"
            else:
                tile_suffix = ""
            realm_for_tile = row_to_realm_mapping[row_num]

            series_dir = Path(dest_dir_floortiles).joinpath(f"{realm_for_tile.name}")

            destination_filepath: Path = series_dir.joinpath(f"{row_num}-{col_num}{tile_suffix}.png")
            tileset.append((img, destination_filepath))

            sprite_name_short = "Floor"
            sprite_name_long = f"{realm_for_tile.value} Floor Tile"
            with Session() as session:
                realm_id = session.query(RealmLookup).filter_by(enum=realm_for_tile).one().id

            floor_tiles.setdefault(sprite_name_long, FloorSprite(short_name=sprite_name_short, long_name=sprite_name_long,
                                                                 realm_id=realm_id))\
                .frames.append(SpriteFrame(_filepath=destination_filepath.as_posix()))

        is_blank_tileset = not tileset
        if is_blank_tileset:
            continue

        series_dir.mkdir(exist_ok=True)
        for tile in tileset:
            tile_data = tile[0]
            tile_filepath = tile[1]
            cv2.imwrite(tile_filepath.as_posix(), tile_data)


    # read floor tiles
    print([val.long_name for val in floor_tiles.values()])
    add_or_update_sprites(floor_tiles)


def match_overlay(path: Path) -> Optional[re.Match]:
    return overlay_sprite_regex.match(path.name)


def add_or_update_sprites(sprites: dict[str, Type[Sprite]]):
    with Session() as session:
        for sprite_name, sprite_new in sprites.items():
            try:
                sprite = session.query(sprite_new.__class__).filter_by(long_name=sprite_new.long_name).one()
                print(f"reusing sprite {sprite_new.__class__} id={sprite.id}")
            except NoResultFound:
                print("noresultfuond")
                sprite = sprite_new.__class__()
                session.add(sprite)
            sprite.long_name = sprite_new.long_name
            sprite.short_name = sprite_new.short_name
            try:
                sprite.realm_id = sprite_new.realm_id
            except AttributeError:
                pass
            try:
                sprite.chest_type_id = sprite_new.chest_type_id
            except AttributeError:
                pass
            try:
                sprite.opened = sprite_new.opened
            except AttributeError:
                pass

            session.commit()

            sprite.frames.clear()
            session.flush()
            session.commit()

            sprite_id = sprite.id
            for frame in sprite_new.frames:
                new_path = Path(settings.IMAGE_PATH).joinpath(frame._filepath)
                chopped_path = new_path.relative_to(settings.IMAGE_PATH)
                new_frame = SpriteFrame(sprite_id=sprite_id, _filepath=chopped_path.as_posix())
                session.add(new_frame)
            session.commit()


def add_overlay_tiles(export_dir: Path, dest_dir: Path):

    overlay_sprites: dict[str, OverlaySprite] = {}

    sprite_path: Path
    for sprite_path in export_dir.glob("*.png"):
        match = overlay_sprite_regex.match(sprite_path.name)
        if not match:
            continue
        print("got match for overlay", match.group(0))

        realm_name_internal: str = match.groups()[0]
        realm_in_game: Realm = Realm.generic_realm_name_to_ingame_realm(realm_name_internal)

        overlay_sprite = OverlaySprite()

        overlay_sprite.long_name = f"{realm_in_game.value} Overlay"
        overlay_sprite.short_name = overlay_sprite.long_name
        with Session() as session:
            overlay_sprite.realm_id = session.query(RealmLookup).filter_by(enum=realm_in_game).one().id

        sprite_frame = SpriteFrame()
        sprite_frame._filepath = Path("extracted_assets").joinpath(sprite_path.name).as_posix()
        overlay_sprites.setdefault(overlay_sprite.long_name, overlay_sprite).frames.append(sprite_frame)

        destination_file = dest_dir.joinpath(sprite_path.name)
        shutil.copy(sprite_path, destination_file)

    print(f"{len(overlay_sprites)} overlays found")
    add_or_update_sprites(overlay_sprites)



def match_battle_sprite(path: Path) -> Optional[re.Match]:
    return sprite_crits_battle_regex.match(path.name)


def match_icon(path: Path) -> Optional[re.Match]:
    return re.match(icons_regex, path.name)


def match_attack_animation(path: Path) -> Optional[re.Match]:
    return re.match(animation_regex, path.name)


def match_spell_animation(path: Path) -> Optional[re.Match]:
    return re.match(spell_regex, path.name)


def match_wall(path: Path) -> Optional[re.Match]:
    return re.match(wall_regex, path.name)


def match_alt_walls(path) -> Optional[re.Match]:
    return re.match(wall_alt_regex, path.name)


matchers = {
    'master': match_master,
    'altar': match_altar,
    'chest': match_chest,
    'npc': match_npc,
    'overlay': match_overlay,
    'project': match_project,
    'realm_fllortiles': match_realm_floortiles,
    'crits_battle': match_battle_sprite,
    'wall': match_wall,

    #excluded
    'attack_animation': match_attack_animation,
    'spell_animation': match_spell_animation,
    'icon': match_icon,
    'alt_walls': match_alt_walls,
}


def generic_sprite(sprite_path: Path):
    match = generic_sprite_regex.match(sprite_path.name)
    if not match:
        print(f"generic no match: {sprite_path}")
        return

    img = cv2.imread(sprite_path.as_posix())
    height, width, _ = img.shape
    if height == MASTER_ICON_SIZE or width == MASTER_ICON_SIZE:
        return


    sprite = Sprite()

    sprite.long_name = match.groups()[0]
    sprite.short_name = sprite.long_name
    return sprite




def match_sprites(export_dir: Path, dest_dir: Path):
    generic_dir = dest_dir.joinpath("generic")
    generic_dir.mkdir(exist_ok=True)

    sprites: dict[str, Sprite] = {}

    ct = 0
    sprite_path: Path
    for sprite_path in export_dir.glob("*.png"):
        for matcher_name, matcher in matchers.items():
            if matcher(sprite_path):
                break
        else:
            ct += 1
            partial_sprite: Optional[Sprite] = generic_sprite(sprite_path)
            if not partial_sprite:
                continue
            destination_filepath = generic_dir.joinpath(sprite_path.name)
            shutil.copy(sprite_path, destination_filepath)

            sprites.setdefault(partial_sprite.long_name, partial_sprite).frames.append(
                SpriteFrame(_filepath=destination_filepath.as_posix())
            )
            if ct % 10 == 0:
                print(f"saved {ct} generic frames")
    add_or_update_sprites(sprites)


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
                    if should_skip_hashing(sprite_frame.filepath):
                        print(f"assets_padded skipping = {sprite_frame.filepath}")
                        continue
                    hash_entry = HashFrameWithFloor()
                    hash_entry.floor_sprite_frame_id = floor_frame_id
                    hash_entry.sprite_frame_id = sprite_frame.id

                    sprite_frame_data_color = sprite_frame.data_color
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


def drop_existing_phashes(sprite_type: Optional[SpriteType]=None):
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
            print("Shouldn't delete everything")
            sys.exit(2)
            rows_deleted = session.query(HashFrameWithFloor).delete()
            session.commit()
            print(f"cleared tabled, deleted {rows_deleted} rows")


def add_wall_sprites(export_dir: Path, dest_dir: Path):
    TILE_SIZE = 32

    dest_dir_walls = dest_dir.joinpath("wall_realm_tiles")
    dest_dir_walls.mkdir(exist_ok=True)

    wall_tiles: dict[str, WallSprite] = {}
    for path in export_dir.glob("*"):
        match = match_wall(path)
        if not match:
            continue

        realm: Realm = Realm.generic_realm_name_to_ingame_realm(match.groups()[0])
        dest_realm_wall_dir = dest_dir_walls.joinpath(realm.name)
        dest_realm_wall_dir.mkdir(exist_ok=True)

        img = cv2.imread(path.as_posix(), cv2.IMREAD_UNCHANGED)

        tileset: list[tuple[ArrayLike, Path]] = []
        ct = 1
        for row_num, row in enumerate(range(0, img.shape[0], TILE_SIZE)):
            for col_num, column in enumerate(range(0, img.shape[1], TILE_SIZE)):
                slice = img[row:row + TILE_SIZE, column:column + TILE_SIZE]
                is_blank = np.count_nonzero(slice) == 0
                if is_blank:
                    continue

                destination_filepath: Path = dest_realm_wall_dir.joinpath(f"{ct}.png")
                tileset.append((slice, destination_filepath))

                sprite_name_short = "Wall"
                sprite_name_long = f"{realm.value} Wall"
                with Session() as session:
                    realm_id = session.query(RealmLookup).filter_by(enum=realm).one().id

                wall_tiles.setdefault(sprite_name_long, WallSprite(short_name=sprite_name_short, long_name=sprite_name_long,
                                                                     realm_id=realm_id))\
                    .frames.append(SpriteFrame(_filepath=destination_filepath.as_posix()))
                ct += 1

        for tile in tileset:
            tile_data = tile[0]
            tile_filepath = tile[1]
            cv2.imwrite(tile_filepath.as_posix(), tile_data)


    add_or_update_sprites(wall_tiles)


if __name__ == "__main__":
    export_dir = Path("C:/Program Files (x86)/Steam/steamapps/common/Siralim Ultimate/Export_Textures_0.10.11/")
    dest_dir = settings.IMAGE_PATH.joinpath("extracted_assets")

    drop_existing_phashes()

    realm_floortiles(export_dir, dest_dir)
    npc(export_dir, dest_dir)
    try:
        master_npcs(export_dir, dest_dir=dest_dir)
    except sqlalchemy.exc.IntegrityError:
        logging.info("Reimporting or updating master sprites is not implemented")
    altars(export_dir, dest_dir)
    insert_project_items(export_dir, dest_dir)
    add_overlay_tiles(export_dir, dest_dir)
    add_wall_sprites(export_dir, dest_dir)
    add_chests(export_dir, dest_dir)

    match_sprites(export_dir, dest_dir)
    hash_items()
