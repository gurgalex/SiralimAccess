import logging
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Type

import cv2
import re
import numpy as np

import sqlalchemy
from numpy.typing import ArrayLike
from sqlalchemy.exc import NoResultFound

from subot.models import MasterNPCSprite, SpriteFrame, Session, AltarSprite, Realm, RealmLookup, ProjectItemSprite, \
    NPCSprite, FloorSprite, OverlaySprite, Sprite

master_name_regex = re.compile(r"master_(?P<race>.*)_[\d].png")
realm_altar_regex = re.compile(r"spr_(?:altar|god)_(?P<realm>.*)_[\d].png")
project_item_regex = re.compile(r"project_(?P<name>.*)_[\d].png")
npc_regex = re.compile(r"npc_(?P<name>.*)_[\d].png")
custom_floortile_regex = re.compile(r"floortiles/(?P<realm>.*)/*.png")
overlay_sprite_regex = re.compile(r"(?P<realm>.*)_overlay_[\d].png")
realm_floortiles_regex = re.compile(r"bg_chaos_0.png")


MASTER_ICON_SIZE = 16
MASTER_NPC_SIZE = 32


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

            session.commit()

            sprite.frames.clear()
            session.flush()
            session.commit()

            sprite_id = sprite.id
            for frame in sprite_new.frames:
                new_frame = SpriteFrame(sprite_id=sprite_id, _filepath=frame._filepath)
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


sprite_crits_battle_regex = re.compile(r"spr_crits_battle_(?P<name>[\d]+).png")
def match_battle_sprite(path: Path) -> Optional[re.Match]:
    return sprite_crits_battle_regex.match(path.name)

matchers = {
    'master': match_master,
    'altar': match_altar,
    'npc': match_npc,
    'overlay': match_overlay,
    'project': match_project,
    'realm_fllortiles': match_realm_floortiles,
    'crits_battle': match_battle_sprite,
}


generic_sprite_regex = re.compile(r"spr_(?P<long_name>.*)_[\d]+.png")


def generic_sprite(sprite_path: Path):
    match = generic_sprite_regex.match(sprite_path.name)
    if not match:
        print(f"generic no match: {sprite_path}")
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


if __name__ == "__main__":
    export_dir = Path("C:/Program Files (x86)/Steam/steamapps/common/Siralim Ultimate/Export_Textures_0.9.11/")
    dest_dir = Path("extracted_assets")
    match_sprites(export_dir, dest_dir)
    realm_floortiles(export_dir, dest_dir)
    add_overlay_tiles(export_dir, dest_dir)
    npc(export_dir, dest_dir)
    try:
        master_npcs(export_dir, dest_dir=dest_dir)
    except sqlalchemy.exc.IntegrityError:
        logging.info("Reimporting or updating master sprites is not implemented")
    altars(export_dir, dest_dir)
    insert_project_items(export_dir, dest_dir)
    add_overlay_tiles(export_dir, dest_dir)
